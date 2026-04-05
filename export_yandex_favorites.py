#!/usr/bin/env python3
"""
Этап 1.1: Экспорт избранных треков из Яндекс Музыки.

Использование:
    export YANDEX_MUSIC_TOKEN="ваш_токен"
    python export_yandex_favorites.py

Получить токен:
    https://oauth.yandex.ru/authorize?response_type=token&client_id=23cabbbdc6cd418abb4b39c32c41195d
"""

import csv
import json
import os
import sys

from tqdm import tqdm
from yandex_music import Client

import config


def get_client(token: str) -> Client:
    if not token:
        print("Ошибка: токен не задан.")
        print("Установите переменную окружения YANDEX_MUSIC_TOKEN")
        print("или отредактируйте config.py")
        sys.exit(1)
    client = Client(token).init()
    print(f"Авторизация успешна: {client.me.account.login}")
    return client


def fetch_favorites(client: Client) -> list[dict]:
    print("Загрузка списка избранных треков...")
    likes = client.users_likes_tracks()
    print(f"Найдено {len(likes)} избранных треков")

    tracks_data = []
    # Получаем треки батчами для скорости
    track_ids = [like.track_id for like in likes]

    # yandex-music позволяет получить треки пачкой
    batch_size = 100
    all_tracks = []
    for i in range(0, len(track_ids), batch_size):
        batch = track_ids[i : i + batch_size]
        all_tracks.extend(client.tracks(batch))

    for track in tqdm(all_tracks, desc="Обработка треков"):
        artists = ", ".join(a.name for a in track.artists if a.name)
        albums = ", ".join(a.title for a in track.albums if a.title) if track.albums else ""

        tracks_data.append(
            {
                "yandex_id": track.id,
                "title": track.title,
                "artists": artists,
                "album": albums,
                "duration_ms": track.duration_ms,
                "duration_str": format_duration(track.duration_ms) if track.duration_ms else "",
                "artist_list": [a.name for a in track.artists if a.name],
            }
        )

    return tracks_data


def format_duration(ms: int) -> str:
    seconds = ms // 1000
    minutes = seconds // 60
    secs = seconds % 60
    return f"{minutes}:{secs:02d}"


def save_json(tracks: list[dict], path: str):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(tracks, f, ensure_ascii=False, indent=2)
    print(f"JSON сохранён: {path} ({len(tracks)} треков)")


def save_csv(tracks: list[dict], path: str):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fieldnames = ["yandex_id", "title", "artists", "album", "duration_str"]
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(tracks)
    print(f"CSV сохранён: {path} ({len(tracks)} треков)")


def main():
    token = config.YANDEX_TOKEN
    if not token:
        token = input("Введите Yandex Music OAuth токен: ").strip()

    client = get_client(token)
    tracks = fetch_favorites(client)

    save_json(tracks, config.YANDEX_FAVORITES_JSON)
    save_csv(tracks, config.YANDEX_FAVORITES_CSV)

    print(f"\nГотово! Экспортировано {len(tracks)} треков")
    print(f"  JSON: {config.YANDEX_FAVORITES_JSON}")
    print(f"  CSV:  {config.YANDEX_FAVORITES_CSV}")


if __name__ == "__main__":
    main()
