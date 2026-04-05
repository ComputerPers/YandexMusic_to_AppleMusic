# Yandex Music → Apple Music

Набор скриптов на Python для переноса избранных треков из **Яндекс Музыки** в **Apple Music** на macOS: экспорт списка, сопоставление с каталогом Apple через iTunes Search API, добавление в библиотеку и плейлист (через Music.app или MusicKit API), опционально — скачивание MP3 с Яндекса и генерация Apple Shortcuts.

## Требования

- macOS (для `add_to_apple_music.py`, Music.app, AppleScript)
- Python 3.10+
- Аккаунт Яндекс с доступом к Музыке
- Для импорта в Apple Music — подписка Apple Music и авторизация в приложении «Музыка»

## Установка

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Каталог `data/` создаётся скриптами автоматически; в репозитории хранится только маркер `data/.gitkeep`. **Не коммитьте** свои `yandex_favorites.json`, токены и отчёты миграции.

## Переменные окружения и секреты

| Что | Где задать |
|-----|------------|
| OAuth Яндекс Музыки | `export YANDEX_MUSIC_TOKEN="..."` |
| Developer + Media User Token для API Apple | `python extract_tokens.py --save` → файлы `.developer_token` и `.apple_music_token` (уже в `.gitignore`) |

Получение OAuth-токена Яндекса (в документации в скриптах и в `config.py` указан client_id приложения):

https://oauth.yandex.ru/authorize?response_type=token&client_id=23cabbbdc6cd418abb4b39c32c41195d

Подробности по токенам Apple Music — в шапке `extract_tokens.py` (Chrome/Safari cookies, Playwright и т.д.).

## Пайплайн

### 1. Экспорт избранного из Яндекс Музыки

```bash
export YANDEX_MUSIC_TOKEN="ваш_токен"
python export_yandex_favorites.py
```

Результат: `data/yandex_favorites.json` и `data/yandex_favorites.csv`.

### 2. Сопоставление с Apple Music (iTunes Search API)

```bash
python match_apple_music.py
```

Учитывается лимит запросов (~20/мин); между запросами есть задержка. Результаты: `data/matched_tracks.json`, `data/unmatched_tracks.json`, `data/migration_report.txt`.

### 3. Добавление в библиотеку Apple Music

**Вариант A — через Music.app и AppleScript** (медленнее, но без отдельных API-токенов Apple кроме работы приложения):

```bash
python add_to_apple_music.py
python add_to_apple_music.py --from 50   # продолжить с 50-го трека
```

**Вариант B — через MusicKit / amp-api** (нужны токены из `extract_tokens.py`):

```bash
python extract_tokens.py --save   # при необходимости сначала --from-chrome и т.п.
python add_to_apple_music_api.py
python add_to_apple_music_api.py --dry-run
python add_to_apple_music_api.py --playlist "Мой плейлист"
```

### 4. Опционально: скачивание треков с Яндекса

```bash
python download_tracks.py          # в приоритете несматченные в Apple Music
python download_tracks.py --all    # все избранные
```

Файлы попадают в каталог `downloads/` (в `.gitignore`).

### 5. Опционально: Apple Shortcuts

```bash
python generate_shortcut.py
```

Дальше импортируйте сгенерированные `.shortcut` из `data/shortcuts/` (каталог появится локально и не должен попадать в git).

## Состав репозитория

| Файл | Назначение |
|------|------------|
| `config.py` | Пути к `data/` и переменная `YANDEX_MUSIC_TOKEN` |
| `export_yandex_favorites.py` | Экспорт лайков |
| `match_apple_music.py` | Матчинг по iTunes Search |
| `add_to_apple_music.py` | Импорт через Music.app |
| `add_to_apple_music_api.py` | Импорт через API |
| `extract_tokens.py` | Токены для API Apple |
| `download_tracks.py` | Загрузка MP3 |
| `generate_shortcut.py` | Генерация шорткатов |

## Ограничения и замечания

- Качество матчинга зависит от метаданных и регионального каталога iTunes/Apple Music.
- Автоматизация через Music.app опирается на тайминги (`sleep`); при медленной машине или сети может понадобиться подстроить задержки в коде.
- Скачивание треков регулируется условиями использования Яндекс Музыки; используйте ответственно.
