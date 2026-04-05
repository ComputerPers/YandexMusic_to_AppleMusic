#!/usr/bin/env python3
"""
Этап 2.1: Скачивание треков из Яндекс Музыки.

Скачивает все избранные треки (или только ненайденные в Apple Music).

Использование:
    export YANDEX_MUSIC_TOKEN="ваш_токен"

    # Скачать только ненайденные в Apple Music:
    python download_tracks.py

    # Скачать ВСЕ избранные треки:
    python download_tracks.py --all
"""

import json
import os
import re
import sys

from tqdm import tqdm
from yandex_music import Client

import config


def sanitize_filename(name: str) -> str:
    """Убрать недопустимые символы из имени файла."""
    name = re.sub(r'[<>:"/\\|?*]', "_", name)
    name = name.strip(". ")
    return name[:200]


def download_track(client: Client, track_id: str, artist: str, title: str, album: str) -> str | None:
    """Скачать трек и вернуть путь к файлу."""
    artist_dir = sanitize_filename(artist) if artist else "Unknown Artist"
    album_dir = sanitize_filename(album) if album else "Unknown Album"
    filename = sanitize_filename(title) + ".mp3"

    target_dir = os.path.join(config.DOWNLOADS_DIR, artist_dir, album_dir)
    os.makedirs(target_dir, exist_ok=True)
    filepath = os.path.join(target_dir, filename)

    if os.path.exists(filepath):
        return filepath

    try:
        track = client.tracks([track_id])[0]
        track.download(filepath, codec="mp3", bitrate_in_kbps=320)
        return filepath
    except Exception as e:
        print(f"\n  Ошибка скачивания '{artist} - {title}': {e}")
        return None


def main():
    download_all = "--all" in sys.argv

    token = config.YANDEX_TOKEN
    if not token:
        token = input("Введите Yandex Music OAuth токен: ").strip()

    client = Client(token).init()
    print(f"Авторизация: {client.me.account.login}")

    if download_all:
        source_file = config.YANDEX_FAVORITES_JSON
        print("Режим: скачивание ВСЕХ избранных треков")
    else:
        source_file = config.UNMATCHED_TRACKS_JSON
        if not os.path.exists(source_file):
            source_file = config.YANDEX_FAVORITES_JSON
            print("Файл unmatched не найден, скачиваем все треки")
        else:
            print("Режим: скачивание только ненайденных в Apple Music")

    with open(source_file, encoding="utf-8") as f:
        tracks = json.load(f)

    print(f"Треков к скачиванию: {len(tracks)}\n")

    downloaded = 0
    failed = 0
    skipped = 0

    for track in tqdm(tracks, desc="Скачивание"):
        track_id = str(track["yandex_id"])
        artist = track.get("artists", "Unknown")
        title = track.get("title", "Unknown")
        album = track.get("album", "")

        result = download_track(client, track_id, artist, title, album)
        if result:
            if os.path.getsize(result) > 0:
                downloaded += 1
            else:
                skipped += 1
        else:
            failed += 1

    print(f"\nГотово!")
    print(f"  Скачано:  {downloaded}")
    print(f"  Ошибки:   {failed}")
    print(f"  Пропущено (уже есть): {skipped}")
    print(f"  Папка:    {config.DOWNLOADS_DIR}")
    print(f"\nСледующий шаг:")
    print(f"  1. Откройте Music.app на Mac")
    print(f"  2. File → Import... → выберите папку {config.DOWNLOADS_DIR}")
    print(f"  3. iCloud Music Library автоматически синхронизирует на все устройства")


if __name__ == "__main__":
    main()
