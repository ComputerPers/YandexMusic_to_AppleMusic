import os

# Яндекс Музыка OAuth токен
# Получить: https://oauth.yandex.ru/authorize?response_type=token&client_id=23cabbbdc6cd418abb4b39c32c41195d
YANDEX_TOKEN = os.environ.get("YANDEX_MUSIC_TOKEN", "")

# Пути к файлам данных
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
DOWNLOADS_DIR = os.path.join(os.path.dirname(__file__), "downloads")

YANDEX_FAVORITES_JSON = os.path.join(DATA_DIR, "yandex_favorites.json")
YANDEX_FAVORITES_CSV = os.path.join(DATA_DIR, "yandex_favorites.csv")
MATCHED_TRACKS_JSON = os.path.join(DATA_DIR, "matched_tracks.json")
UNMATCHED_TRACKS_JSON = os.path.join(DATA_DIR, "unmatched_tracks.json")
MIGRATION_REPORT = os.path.join(DATA_DIR, "migration_report.txt")
