#!/usr/bin/env python3
"""
Добавляет сматченные треки в Apple Music библиотеку и плейлист "Yandex Favorites".

Цепочка для каждого трека:
1. open music://... URL — открывает трек в Music.app
2. AppleScript: play → duplicate to Library → duplicate to playlist

Использование:
    python add_to_apple_music.py          # с начала
    python add_to_apple_music.py --from 50  # с 50-го трека (возобновление)
"""

import json
import os
import subprocess
import sys
import time

import config

PLAYLIST_NAME = "Yandex Favorites"
DELAY_OPEN = 4    # секунд после open URL
DELAY_PLAY = 3    # секунд после play
DELAY_LIBRARY = 2 # секунд после добавления в библиотеку
DELAY_NEXT = 1    # секунд между треками


def run_osascript(script: str) -> str:
    result = subprocess.run(
        ["osascript", "-e", script],
        capture_output=True, text=True, timeout=15,
    )
    return (result.stdout + result.stderr).strip()


def ensure_playlist():
    out = run_osascript(f'''
        tell application "Music"
            try
                set pl to playlist "{PLAYLIST_NAME}"
                return "exists"
            on error
                make new playlist with properties {{name:"{PLAYLIST_NAME}"}}
                return "created"
            end try
        end tell
    ''')
    print(f"Плейлист '{PLAYLIST_NAME}': {out}")


def add_track(url: str, title: str, artist: str) -> bool:
    """Добавить один трек в библиотеку и плейлист."""
    # Конвертируем https:// в music://
    music_url = url.replace("https://", "music://")

    # 1. Открываем трек в Music.app
    subprocess.run(["open", music_url], timeout=5)
    time.sleep(DELAY_OPEN)

    # 2. Play + duplicate to library + add to playlist
    # Экранируем кавычки в названии
    safe_title = title.replace('"', '\\"')
    safe_artist = artist.replace('"', '\\"')

    result = run_osascript(f'''
        tell application "Music"
            play
            delay {DELAY_PLAY}
            try
                set t to current track
                duplicate t to source "Library"
            on error errMsg
                return "ERR_LIB: " & errMsg
            end try
            delay {DELAY_LIBRARY}
            try
                set pl to playlist "{PLAYLIST_NAME}"
                set found to (every track whose name is "{safe_title}" and artist is "{safe_artist}")
                if (count of found) > 0 then
                    duplicate item 1 of found to pl
                    return "OK"
                else
                    -- Попробуем поиск только по названию
                    set found2 to (every track whose name is "{safe_title}")
                    if (count of found2) > 0 then
                        duplicate item 1 of found2 to pl
                        return "OK_TITLE"
                    else
                        return "ERR_NOTFOUND"
                    end if
                end if
            on error errMsg
                return "ERR_PL: " & errMsg
            end try
        end tell
    ''')
    return result.startswith("OK")


def main():
    start_from = 0
    if "--from" in sys.argv:
        idx = sys.argv.index("--from")
        start_from = int(sys.argv[idx + 1])

    with open(config.MATCHED_TRACKS_JSON, encoding="utf-8") as f:
        tracks = json.load(f)

    print(f"Всего треков: {len(tracks)}")
    if start_from > 0:
        print(f"Начинаем с #{start_from}")

    ensure_playlist()

    ok = 0
    fail = 0
    fail_list = []

    for i in range(start_from, len(tracks)):
        t = tracks[i]
        url = t.get("apple_url", "")
        title = t.get("apple_title", t.get("title", ""))
        artist = t.get("apple_artist", t.get("artists", ""))

        if not url:
            fail += 1
            continue

        status = "..."
        try:
            success = add_track(url, title, artist)
            if success:
                ok += 1
                status = "✓"
            else:
                fail += 1
                fail_list.append(f"{artist} — {title}")
                status = "✗"
        except Exception as e:
            fail += 1
            fail_list.append(f"{artist} — {title}")
            status = f"ERR: {e}"

        print(f"[{i+1}/{len(tracks)}] {status} {artist} — {title}")
        time.sleep(DELAY_NEXT)

    print(f"\nГотово!")
    print(f"  Добавлено: {ok}")
    print(f"  Ошибки:    {fail}")

    if fail_list:
        fail_path = os.path.join(config.DATA_DIR, "add_failures.json")
        with open(fail_path, "w", encoding="utf-8") as f:
            json.dump(fail_list, f, ensure_ascii=False, indent=2)
        print(f"  Список ошибок: {fail_path}")


if __name__ == "__main__":
    main()
