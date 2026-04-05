#!/usr/bin/env python3
"""
Этап 1.2: Матчинг треков из Яндекс Музыки с каталогом Apple Music.

Использует бесплатный iTunes Search API.
Лимит: ~20 запросов/мин, поэтому для 1014 треков займёт ~50 минут.

Использование:
    python match_apple_music.py

Предварительно запустить export_yandex_favorites.py для создания yandex_favorites.json.
"""

import json
import os
import re
import sys
import time
import unicodedata

import requests
from tqdm import tqdm

import config

ITUNES_SEARCH_URL = "https://itunes.apple.com/search"
REQUEST_DELAY = 3.5  # секунд между запросами (≈17 req/min, ниже лимита)


def normalize(text: str) -> str:
    """Нормализация строки для сравнения: lowercase, убрать скобки, feat. и т.д."""
    text = text.lower().strip()
    # Убрать содержимое в скобках (feat., remix info и т.д.)
    text = re.sub(r"\s*[\(\[\{].*?[\)\]\}]", "", text)
    # Убрать feat. / ft. / featuring
    text = re.sub(r"\s*(feat\.?|ft\.?|featuring)\s+.*", "", text)
    # Убрать лишние пробелы
    text = re.sub(r"\s+", " ", text).strip()
    # Нормализация Unicode
    text = unicodedata.normalize("NFKD", text)
    return text


def titles_match(title1: str, title2: str) -> bool:
    """Проверка совпадения названий треков."""
    n1 = normalize(title1)
    n2 = normalize(title2)
    if n1 == n2:
        return True
    # Одно содержит другое
    if n1 in n2 or n2 in n1:
        return True
    return False


def artists_match(yandex_artists: str, apple_artist: str) -> bool:
    """Проверка совпадения исполнителей."""
    ya_norm = normalize(yandex_artists)
    ap_norm = normalize(apple_artist)
    if ya_norm == ap_norm:
        return True
    # Проверяем каждого исполнителя из Яндекса
    ya_parts = [normalize(a.strip()) for a in yandex_artists.split(",")]
    for part in ya_parts:
        if part and (part in ap_norm or ap_norm in part):
            return True
    return False


def _do_search(query: str, country: str, limit: int = 10) -> list[dict]:
    """Выполнить один запрос к iTunes Search API."""
    params = {
        "term": query,
        "media": "music",
        "entity": "song",
        "limit": limit,
        "country": country,
    }
    try:
        resp = requests.get(ITUNES_SEARCH_URL, params=params, timeout=10)
        resp.raise_for_status()
        return resp.json().get("results", [])
    except (requests.RequestException, json.JSONDecodeError) as e:
        print(f"  Ошибка запроса: {e}")
        return []


def _make_entry(result: dict) -> dict:
    return {
        "apple_track_id": result.get("trackId"),
        "apple_title": result.get("trackName", ""),
        "apple_artist": result.get("artistName", ""),
        "apple_album": result.get("collectionName", ""),
        "apple_url": result.get("trackViewUrl", ""),
        "apple_preview_url": result.get("previewUrl", ""),
    }


def _best_match(results: list[dict], title: str, artist: str, title_only: bool = False) -> dict | None:
    """Вернуть первый результат, совпадающий по названию (и исполнителю если title_only=False)."""
    for result in results:
        apple_title = result.get("trackName", "")
        apple_artist = result.get("artistName", "")
        title_ok = titles_match(title, apple_title)
        artist_ok = title_only or artists_match(artist, apple_artist)
        if title_ok and artist_ok:
            return _make_entry(result)
    return None


def search_itunes(title: str, artist: str) -> dict | None:
    """Поиск трека в iTunes Search API.

    Стратегия (для каждой страны ru/us):
    1. Запрос "artist title" — стандартный, проверяем и название и исполнителя
    2. Запрос только по исполнителю — фолбэк для случаев когда кириллический
       title мешает поиску (Fun Mode, E.S.T. и т.д.); проверяем только название
       трека, т.к. исполнитель уже задан в запросе
    3. Запрос только по названию трека — проверяем оба поля
    """
    for country in ("ru", "us"):
        # 1. Комбинированный запрос
        match = _best_match(_do_search(f"{artist} {title}", country), title, artist)
        if match:
            return match

        # 2. Только исполнитель (title_only=True — доверяем поиску по артисту)
        match = _best_match(_do_search(artist, country, limit=25), title, artist, title_only=True)
        if match:
            return match

        # 3. Только название трека
        match = _best_match(_do_search(title, country), title, artist)
        if match:
            return match

    return None


def load_yandex_tracks(path: str) -> list[dict]:
    if not os.path.exists(path):
        print(f"Файл не найден: {path}")
        print("Сначала запустите export_yandex_favorites.py")
        sys.exit(1)

    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_json(data: list[dict], path: str):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def generate_report(
    total: int, matched: list[dict], unmatched: list[dict], path: str
):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write("=" * 60 + "\n")
        f.write("ОТЧЁТ МИГРАЦИИ ЯНДЕКС МУЗЫКА → APPLE MUSIC\n")
        f.write("=" * 60 + "\n\n")
        f.write(f"Всего треков в Яндекс Музыке: {total}\n")
        f.write(f"Найдено в Apple Music:        {len(matched)} ({len(matched)*100//total}%)\n")
        f.write(f"НЕ найдено:                   {len(unmatched)} ({len(unmatched)*100//total}%)\n")
        f.write("\n")

        if unmatched:
            f.write("-" * 60 + "\n")
            f.write("ТРЕКИ, НЕ НАЙДЕННЫЕ В APPLE MUSIC:\n")
            f.write("-" * 60 + "\n")
            for t in unmatched:
                f.write(f"  {t['artists']} — {t['title']}\n")

    print(f"\nОтчёт сохранён: {path}")


def main():
    rerun = "--rerun" in sys.argv

    if rerun:
        # Повторный матчинг только по ненайденным трекам
        source_file = config.UNMATCHED_TRACKS_JSON
        tracks = load_yandex_tracks(source_file)
        # Загружаем уже найденные, чтобы потом объединить
        prev_matched = []
        if os.path.exists(config.MATCHED_TRACKS_JSON):
            with open(config.MATCHED_TRACKS_JSON, encoding="utf-8") as f:
                prev_matched = json.load(f)
        print(f"Повторный матчинг: {len(tracks)} ненайденных треков (уже найдено: {len(prev_matched)})")
    else:
        source_file = config.YANDEX_FAVORITES_JSON
        tracks = load_yandex_tracks(source_file)
        prev_matched = []
        print(f"Загружено {len(tracks)} треков из Яндекс Музыки")

    total_tracks = len(prev_matched) + len(tracks)
    print(f"Задержка между запросами: {REQUEST_DELAY}с (~{60/REQUEST_DELAY:.0f} req/min)")
    estimated_minutes = len(tracks) * REQUEST_DELAY / 60
    print(f"Примерное время: {estimated_minutes:.0f} минут\n")

    matched = []
    unmatched = []

    # Загружаем прогресс если есть (для возобновления)
    progress_file = os.path.join(config.DATA_DIR, ".match_progress.json")
    start_idx = 0
    if os.path.exists(progress_file):
        with open(progress_file, encoding="utf-8") as f:
            progress = json.load(f)
        matched = progress.get("matched", [])
        unmatched = progress.get("unmatched", [])
        start_idx = progress.get("last_index", 0) + 1
        if start_idx > 0:
            print(f"Возобновление с трека #{start_idx} (найдено: {len(matched)}, не найдено: {len(unmatched)})")

    try:
        for i in tqdm(range(start_idx, len(tracks)), desc="Матчинг", initial=start_idx, total=len(tracks)):
            track = tracks[i]
            result = search_itunes(track["title"], track["artists"])

            if result:
                entry = {**track, **result}
                matched.append(entry)
            else:
                unmatched.append(track)

            # Сохраняем прогресс каждые 50 треков
            if (i + 1) % 50 == 0:
                save_json(
                    {"matched": matched, "unmatched": unmatched, "last_index": i},
                    progress_file,
                )

            if i < len(tracks) - 1:
                time.sleep(REQUEST_DELAY)

    except KeyboardInterrupt:
        print("\n\nПрервано пользователем. Прогресс сохранён.")
        save_json(
            {"matched": matched, "unmatched": unmatched, "last_index": i},
            progress_file,
        )
        print(f"Обработано: {i + 1}/{len(tracks)}, найдено: {len(matched)}, не найдено: {len(unmatched)}")
        sys.exit(0)

    # При --rerun объединяем с ранее найденными
    all_matched = prev_matched + matched

    save_json(all_matched, config.MATCHED_TRACKS_JSON)
    save_json(unmatched, config.UNMATCHED_TRACKS_JSON)
    generate_report(total_tracks, all_matched, unmatched, config.MIGRATION_REPORT)

    # Удаляем файл прогресса
    if os.path.exists(progress_file):
        os.remove(progress_file)

    print(f"\nГотово!")
    print(f"  Найдено в Apple Music: {len(all_matched)}/{total_tracks}")
    print(f"  Не найдено:           {len(unmatched)}/{total_tracks}")
    print(f"  Отчёт:                {config.MIGRATION_REPORT}")


if __name__ == "__main__":
    main()
