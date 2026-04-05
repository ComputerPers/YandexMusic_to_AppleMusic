#!/usr/bin/env python3
"""
Добавляет сматченные треки в Apple Music через API.

Использование:
    python add_to_apple_music_api.py                    # все треки
    python add_to_apple_music_api.py --from 100         # с 100-го
    python add_to_apple_music_api.py --dry-run           # только проверка
    python add_to_apple_music_api.py --playlist "Name"   # + создать плейлист
"""

import json
import os
import sys
import time

import requests

import config

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEV_TOKEN_FILE = os.path.join(SCRIPT_DIR, ".developer_token")
USER_TOKEN_FILE = os.path.join(SCRIPT_DIR, ".apple_music_token")

API_BASE = "https://amp-api.music.apple.com/v1"
BATCH_SIZE = 25  # Apple рекомендует до 25 ID за запрос


def load_tokens():
    if not os.path.exists(DEV_TOKEN_FILE):
        print("Developer token не найден. Запустите: python extract_tokens.py --save")
        sys.exit(1)
    if not os.path.exists(USER_TOKEN_FILE):
        print(f"User token не найден: {USER_TOKEN_FILE}")
        print("Скопируйте media-user-token из browser DevTools → Cookies → music.apple.com")
        sys.exit(1)

    with open(DEV_TOKEN_FILE) as f:
        dev = f.read().strip()
    with open(USER_TOKEN_FILE) as f:
        user = f.read().strip()
    return dev, user


def make_headers(dev_token, user_token):
    return {
        "Authorization": f"Bearer {dev_token}",
        "Music-User-Token": user_token,
        "Origin": "https://music.apple.com",
        "Content-Type": "application/json",
    }


def verify_tokens(headers):
    r = requests.get(f"{API_BASE}/me/library/songs", headers=headers, params={"limit": 1})
    if r.status_code == 200:
        print("Токены валидны ✓")
        return True
    print(f"Ошибка авторизации: {r.status_code} — {r.text[:200]}")
    return False


def add_songs_to_library(headers, track_ids):
    """Добавить batch треков в библиотеку. Возвращает True при успехе."""
    ids_str = ",".join(str(tid) for tid in track_ids)
    r = requests.post(f"{API_BASE}/me/library", headers=headers, params={"ids[songs]": ids_str})
    return r.status_code == 202


def create_playlist(headers, name, track_ids):
    """Создать плейлист и добавить в него треки."""
    body = {
        "attributes": {"name": name},
        "relationships": {
            "tracks": {
                "data": [{"id": str(tid), "type": "songs"} for tid in track_ids]
            }
        }
    }
    r = requests.post(f"{API_BASE}/me/library/playlists", headers=headers, json=body)
    if r.status_code in (200, 201):
        pl_id = r.json().get("data", [{}])[0].get("id", "?")
        print(f"Плейлист '{name}' создан (id: {pl_id})")
        return pl_id
    else:
        print(f"Ошибка создания плейлиста: {r.status_code} — {r.text[:200]}")
        return None


def add_tracks_to_playlist(headers, playlist_id, track_ids):
    """Добавить треки в существующий плейлист."""
    body = {"data": [{"id": str(tid), "type": "songs"} for tid in track_ids]}
    r = requests.post(f"{API_BASE}/me/library/playlists/{playlist_id}/tracks", headers=headers, json=body)
    return r.status_code in (200, 201, 204)


def main():
    start_from = 0
    dry_run = "--dry-run" in sys.argv
    playlist_name = None

    if "--from" in sys.argv:
        idx = sys.argv.index("--from")
        start_from = int(sys.argv[idx + 1])
    if "--playlist" in sys.argv:
        idx = sys.argv.index("--playlist")
        playlist_name = sys.argv[idx + 1]

    dev_token, user_token = load_tokens()
    headers = make_headers(dev_token, user_token)

    if not verify_tokens(headers):
        sys.exit(1)

    with open(config.MATCHED_TRACKS_JSON, encoding="utf-8") as f:
        tracks = json.load(f)

    # Собираем track IDs
    all_ids = []
    id_to_info = {}
    for t in tracks:
        tid = t.get("apple_track_id")
        if tid:
            all_ids.append(tid)
            id_to_info[tid] = f"{t.get('apple_artist', '?')} — {t.get('apple_title', '?')}"

    print(f"Всего треков с Apple ID: {len(all_ids)}")
    if start_from > 0:
        print(f"Начинаем с #{start_from}")
    if dry_run:
        print("Dry run — ничего не добавляем")
        return

    # Добавляем батчами
    ids_to_add = all_ids[start_from:]
    total_batches = (len(ids_to_add) + BATCH_SIZE - 1) // BATCH_SIZE
    added = 0
    failed = 0

    for i in range(0, len(ids_to_add), BATCH_SIZE):
        batch = ids_to_add[i:i + BATCH_SIZE]
        batch_num = i // BATCH_SIZE + 1

        success = add_songs_to_library(headers, batch)
        if success:
            added += len(batch)
            first = id_to_info.get(batch[0], "?")
            last = id_to_info.get(batch[-1], "?")
            print(f"[{batch_num}/{total_batches}] ✓ {len(batch)} треков ({first} ... {last})")
        else:
            failed += len(batch)
            print(f"[{batch_num}/{total_batches}] ✗ ОШИБКА batch")

        time.sleep(1)  # пауза между запросами

    print(f"\nДобавлено в библиотеку: {added}")
    if failed:
        print(f"Ошибки: {failed}")

    # Создаём плейлист если указан
    if playlist_name and added > 0:
        print(f"\nСоздаём плейлист '{playlist_name}'...")
        # API позволяет создать плейлист с треками за один запрос
        # Но есть лимит, поэтому создаём пустой и добавляем батчами
        pl_id = create_playlist(headers, playlist_name, [])
        if pl_id:
            for i in range(0, len(all_ids), BATCH_SIZE):
                batch = all_ids[i:i + BATCH_SIZE]
                ok = add_tracks_to_playlist(headers, pl_id, batch)
                status = "✓" if ok else "✗"
                print(f"  Playlist batch {i//BATCH_SIZE + 1}: {status} ({len(batch)} треков)")
                time.sleep(0.5)
            print(f"Плейлист '{playlist_name}' готов!")

    print("\nГотово! Откройте Music.app — треки появятся в библиотеке.")


if __name__ == "__main__":
    main()
