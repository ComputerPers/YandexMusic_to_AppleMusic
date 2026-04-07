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


| Что                                        | Где задать                                                                          |
| ------------------------------------------ | ----------------------------------------------------------------------------------- |
| OAuth Яндекс Музыки                        | `export YANDEX_MUSIC_TOKEN="..."`                                                   |
| Developer + Media User Token для API Apple | см. раздел ниже про «точечные» файлы и раздел «Как получить токены для Apple Music» |


### Токены в скрытых файлах корня репозитория (`.*`)

Все перечисленные файлы лежат **в корне проекта** (рядом со скриптами), **в git не попадают** (см. `.gitignore`). Это секреты — не публикуйте их и не шарьте копию каталога с ними.


| Файл                 | Назначение                                                                                                                                                                                                                                       |
| -------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `.developer_token`   | Developer Token (JWT) для Apple Music API. Создаётся командой `python extract_tokens.py --save` (или вручную одной строкой в файл). Читает `add_to_apple_music_api.py`.                                                                          |
| `.media_user_token`  | Media User Token из cookie `music.apple.com`. Сохраняет `**extract_tokens.py --save`** после успешного извлечения (`--from-chrome`, `--from-safari`, `--interactive` и т.д.).                                                                    |
| `.apple_music_token` | Тот же смысл, что и media-user-token для библиотеки: `**add_to_apple_music_api.py` читает именно этот файл**. Если у вас есть только `.media_user_token`, скопируйте его содержимое в `.apple_music_token` или заведите один файл под оба имени. |
| `.token`             | Зарезервировано под локальные секреты (например, если вы решите хранить OAuth Яндекса в файле вместо переменной окружения). Скрипты по умолчанию ожидают `YANDEX_MUSIC_TOKEN`; файл не обязателен.                                               |


Получение OAuth-токена Яндекса (в документации в скриптах и в `config.py` указан client_id приложения):

[https://oauth.yandex.ru/]
[https://oauth.yandex.ru/authorize?response_type=token&client_id=23c43123341321431234123](https://oauth.yandex.ru/authorize?response_type=token&client_id=23c1234123412341234)

## Как получить токены для Apple Music

Нужны **два** значения: **Developer Token** (JWT) и **Media User Token** (cookie `media-user-token` для вашего аккаунта). Оба используются `add_to_apple_music_api.py`. Скрипт `extract_tokens.py` умеет доставать первый автоматически, второй — из браузера или вручную.

**Условия:** активная подписка **Apple Music**, вход на [music.apple.com](https://music.apple.com/) в том браузере, откуда будете брать cookie (для автоматических способов).

### 1. Developer Token

Это сервисный JWT, который Apple отдаёт внутри страницы [beta.music.apple.com](https://beta.music.apple.com). Отдельный Apple Developer аккаунт для этого **не нужен**.

```bash
python extract_tokens.py
```

Скрипт скачает страницу, найдёт JWT в JS-бандле и выведет срок действия. Токен **временный** (порядка нескольких месяцев); когда истечёт — запустите команду снова.

Сохранить в файл:

```bash
python extract_tokens.py --save
```

Появится `**.developer_token**` в корне проекта (уже в `.gitignore`).

### 2. Media User Token (привязка к вашей библиотеке)

Это длинная строка из cookie сайта Apple Music. Без неё API не увидит вашу медиатеку.

**Вручную (надёжно):**

1. Откройте [music.apple.com](https://music.apple.com/) в Chrome (или другом браузере с DevTools).
2. Войдите в аккаунт с подпиской.
3. DevTools (F12) → вкладка **Application** (или «Хранилище») → **Cookies** → `https://music.apple.com`.
4. Найдите cookie `**media-user-token`**, скопируйте **значение** целиком.
5. Вставьте в файл `**.apple_music_token`** в корне репозитория одной строкой (файл создайте вручную, в git не коммитьте).

**Через скрипт из Chrome** (Chrome должен быть залогинен на music.apple.com):

```bash
python extract_tokens.py --from-chrome --save
```

User-token сохранится в `**.media_user_token**`. Для `add_to_apple_music_api.py` скопируйте содержимое в `**.apple_music_token**` или продублируйте файл.

**Через Safari** (нужен пакет `binarycookies`):

```bash
pip install binarycookies
python extract_tokens.py --from-safari --save
```

**Интерактивно** (откроется Chromium, можно войти в Apple ID):

```bash
pip install playwright
playwright install chromium
python extract_tokens.py --interactive --save
```

### 3. Проверка и сохранение обоих сразу

```bash
python extract_tokens.py --from-chrome --save --verify
```

Вместо `--from-chrome` можно `--from-safari` или `--interactive`. Флаг `**--verify**` выполняет тестовый запрос к Apple Music API и смыслен только если в **этом же** запуске удалось получить user token (ручной ввод из буфера скрипт не подхватывает — тогда сохраните cookie в `.apple_music_token` и проверяйте запуском `add_to_apple_music_api.py --dry-run`).

Итог для импорта: в корне должны быть `**.developer_token`** и `**.apple_music_token**` (если сохраняли только в `.media_user_token` — скопируйте в `.apple_music_token`).

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


| Файл                         | Назначение                                       |
| ---------------------------- | ------------------------------------------------ |
| `config.py`                  | Пути к `data/` и переменная `YANDEX_MUSIC_TOKEN` |
| `export_yandex_favorites.py` | Экспорт лайков                                   |
| `match_apple_music.py`       | Матчинг по iTunes Search                         |
| `add_to_apple_music.py`      | Импорт через Music.app                           |
| `add_to_apple_music_api.py`  | Импорт через API                                 |
| `extract_tokens.py`          | Токены для API Apple                             |
| `download_tracks.py`         | Загрузка MP3                                     |
| `generate_shortcut.py`       | Генерация шорткатов                              |


## Ограничения и замечания

- Качество матчинга зависит от метаданных и регионального каталога iTunes/Apple Music.
- Автоматизация через Music.app опирается на тайминги (`sleep`); при медленной машине или сети может понадобиться подстроить задержки в коде.
- Скачивание треков регулируется условиями использования Яндекс Музыки; используйте ответственно.

