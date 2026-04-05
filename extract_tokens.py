#!/usr/bin/env python3
"""
Извлечение токенов для Apple Music API.

Developer Token: извлекается автоматически из beta.music.apple.com (не требует аккаунта).
Media User Token: извлекается из cookie браузера (требует подписку Apple Music).

Способы получения Media User Token:

1. РУЧНОЙ (самый надёжный):
   - Откройте https://music.apple.com/ в Chrome
   - DevTools (F12) → Application → Cookies → music.apple.com
   - Скопируйте значение "media-user-token"

2. АВТОМАТИЧЕСКИЙ из Chrome cookies (этот скрипт):
   - Chrome должен быть залогинен на music.apple.com
   - Запустите: python extract_tokens.py --from-chrome

3. АВТОМАТИЧЕСКИЙ из Safari binary cookies:
   - Safari должен быть залогинен на music.apple.com
   - Запустите: python extract_tokens.py --from-safari
   - Требуется: pip install binarycookies

4. ИНТЕРАКТИВНЫЙ через Playwright:
   - Запустите: python extract_tokens.py --interactive
   - Откроется браузер, войдите в Apple Music
   - Токен будет извлечён автоматически
   - Требуется: pip install playwright && playwright install chromium

Использование:
    python extract_tokens.py                 # извлечь только developer token
    python extract_tokens.py --from-chrome   # + user token из Chrome cookies
    python extract_tokens.py --from-safari   # + user token из Safari cookies
    python extract_tokens.py --interactive   # + user token через интерактивный логин
    python extract_tokens.py --save          # сохранить токены в файлы
"""

import argparse
import base64
import json
import os
import re
import sys
import time
import sqlite3
import shutil
import tempfile

import requests


BETA_MUSIC_URL = "https://beta.music.apple.com"
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TOKEN_FILE = os.path.join(SCRIPT_DIR, ".media_user_token")
DEV_TOKEN_FILE = os.path.join(SCRIPT_DIR, ".developer_token")


def extract_developer_token() -> str:
    """Извлекает developer token из JS-бандла beta.music.apple.com."""
    print("=" * 60)
    print("Developer Token")
    print("=" * 60)
    print(f"Загружаем {BETA_MUSIC_URL}...")

    headers = {"User-Agent": USER_AGENT, "Accept": "text/html"}
    resp = requests.get(BETA_MUSIC_URL, headers=headers, timeout=15)
    resp.raise_for_status()

    # Ищем JS файл
    js_match = re.search(r'(?:src|data-src)="(/assets/index-legacy[^"]+\.js)"', resp.text)
    if not js_match:
        js_match = re.search(r'(?:src|data-src)="(/assets/index[^"]+\.js)"', resp.text)
    if not js_match:
        print("ОШИБКА: JS-файл не найден на beta.music.apple.com")
        return ""

    js_url = BETA_MUSIC_URL + js_match.group(1)
    print(f"JS файл: {js_match.group(1)}")

    # Скачиваем JS и ищем JWT
    js_resp = requests.get(js_url, headers=headers, timeout=30)
    js_resp.raise_for_status()

    token_match = re.search(r'(eyJh[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+)', js_resp.text)
    if not token_match:
        print("ОШИБКА: JWT не найден в JS-файле")
        return ""

    token = token_match.group(1)

    # Декодируем payload
    payload_b64 = token.split(".")[1]
    payload_b64 += "=" * (4 - len(payload_b64) % 4)
    payload = json.loads(base64.urlsafe_b64decode(payload_b64))

    from datetime import datetime
    iat = datetime.fromtimestamp(payload["iat"])
    exp = datetime.fromtimestamp(payload["exp"])

    print(f"Issuer: {payload.get('iss')}")
    print(f"Key ID: {json.loads(base64.urlsafe_b64decode(token.split('.')[0] + '==')).get('kid')}")
    print(f"Issued:  {iat.strftime('%Y-%m-%d %H:%M')}")
    print(f"Expires: {exp.strftime('%Y-%m-%d %H:%M')}")

    if payload["exp"] < time.time():
        print("ВНИМАНИЕ: токен истёк!")
    else:
        days_left = (payload["exp"] - time.time()) / 86400
        print(f"Осталось дней: {days_left:.0f}")

    print(f"\nDeveloper Token ({len(token)} символов):")
    print(f"  {token[:50]}...{token[-20:]}")
    return token


def extract_from_chrome() -> str:
    """
    Извлекает media-user-token из Chrome cookies на macOS.

    Chrome шифрует cookie values с помощью Keychain. Для дешифрации
    нужен доступ к Keychain (macOS запросит разрешение).
    """
    print()
    print("=" * 60)
    print("Media User Token из Chrome")
    print("=" * 60)

    # Chrome хранит cookies в SQLite, но значения зашифрованы
    # Путь к cookies может быть в Default или Network
    home = os.path.expanduser("~")
    cookie_paths = [
        os.path.join(home, "Library/Application Support/Google/Chrome/Default/Network/Cookies"),
        os.path.join(home, "Library/Application Support/Google/Chrome/Default/Cookies"),
    ]

    cookie_path = None
    for p in cookie_paths:
        if os.path.exists(p):
            cookie_path = p
            break

    if not cookie_path:
        print("Chrome cookies файл не найден")
        return ""

    print(f"Файл: {cookie_path}")

    # Копируем БД (Chrome может её заблокировать)
    with tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False) as tmp:
        tmp_path = tmp.name
    shutil.copy2(cookie_path, tmp_path)

    try:
        conn = sqlite3.connect(tmp_path)
        cursor = conn.cursor()

        # Ищем cookie media-user-token для apple.com
        cursor.execute(
            "SELECT name, host_key, encrypted_value, expires_utc "
            "FROM cookies "
            "WHERE name = 'media-user-token' AND host_key LIKE '%apple.com%'"
        )
        rows = cursor.fetchall()
        conn.close()

        if not rows:
            print("Cookie 'media-user-token' не найден в Chrome")
            print("  Убедитесь что вы залогинены на https://music.apple.com/")
            return ""

        # Chrome на macOS шифрует cookies с ключом из Keychain
        # Пробуем расшифровать
        row = rows[0]
        encrypted_value = row[2]

        if encrypted_value[:3] == b"v10":
            print("Cookie зашифрован (Chrome v10 encryption)")
            print("Для расшифровки нужен ключ из Keychain.")
            print()
            print("Альтернативный способ — скопируйте токен вручную:")
            print("  Chrome → DevTools (F12) → Application → Cookies")
            print("  → music.apple.com → media-user-token → скопировать Value")
            return ""
        else:
            # Незашифрованное значение (маловероятно на macOS)
            value = encrypted_value.decode("utf-8", errors="replace")
            if value:
                print(f"Токен найден ({len(value)} символов)")
                return value

    finally:
        os.unlink(tmp_path)

    return ""


def extract_from_safari() -> str:
    """
    Извлекает media-user-token из Safari binary cookies на macOS.

    Safari хранит cookies в .binarycookies файлах.
    Для чтения нужна библиотека: pip install binarycookies
    """
    print()
    print("=" * 60)
    print("Media User Token из Safari")
    print("=" * 60)

    home = os.path.expanduser("~")
    cookie_paths = [
        os.path.join(home, "Library/Cookies/Cookies.binarycookies"),
        os.path.join(home, "Library/Containers/com.apple.Safari/Data/Library/Cookies/Cookies.binarycookies"),
        os.path.join(home, "Library/HTTPStorages/com.apple.Safari/httpstorages.sqlite"),
    ]

    found_path = None
    for p in cookie_paths:
        if os.path.exists(p):
            found_path = p
            break

    if not found_path:
        print("Safari cookies файл не найден")
        print("Проверенные пути:")
        for p in cookie_paths:
            print(f"  {p}")
        return ""

    print(f"Файл: {found_path}")

    if found_path.endswith(".binarycookies"):
        try:
            import binarycookies
        except ImportError:
            print("Нужна библиотека: pip install binarycookies")
            return ""

        with open(found_path, "rb") as f:
            cookies = binarycookies.load(f)

        for cookie in cookies:
            name = cookie.get("name", "") if isinstance(cookie, dict) else getattr(cookie, "name", "")
            if name == "media-user-token":
                value = cookie.get("value", "") if isinstance(cookie, dict) else getattr(cookie, "value", "")
                if value:
                    print(f"Токен найден ({len(value)} символов)")
                    return value

        print("Cookie 'media-user-token' не найден в Safari")
    elif found_path.endswith(".sqlite"):
        # HTTPStorages SQLite format
        conn = sqlite3.connect(found_path)
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT * FROM sqlite_master WHERE type='table'")
            tables = cursor.fetchall()
            print(f"Таблицы: {[t[1] for t in tables]}")
            # TODO: parse the specific format
        except Exception as e:
            print(f"Ошибка чтения SQLite: {e}")
        finally:
            conn.close()

    return ""


def extract_interactive() -> str:
    """
    Открывает браузер через Playwright для интерактивного логина.
    После входа извлекает media-user-token из cookies.
    """
    print()
    print("=" * 60)
    print("Интерактивный логин в Apple Music")
    print("=" * 60)

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("Нужна библиотека Playwright:")
        print("  pip install playwright")
        print("  playwright install chromium")
        return ""

    print("Открываем браузер...")
    print("  1. Войдите в Apple Music (Apple ID)")
    print("  2. Дождитесь загрузки music.apple.com")
    print("  3. Браузер закроется автоматически когда токен будет получен")
    print()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()

        page.goto("https://music.apple.com/")

        # Ждём появления cookie media-user-token
        print("Ожидаем media-user-token cookie...")
        print("(Войдите в Apple Music если нужно)")

        max_wait = 300  # 5 минут
        start = time.time()
        token = ""

        while time.time() - start < max_wait:
            cookies = context.cookies("https://music.apple.com")
            for c in cookies:
                if c["name"] == "media-user-token" and c["value"]:
                    token = c["value"]
                    break
            if token:
                break
            time.sleep(2)

        browser.close()

        if token:
            print(f"\nТокен получен! ({len(token)} символов)")
            return token
        else:
            print("\nТаймаут: токен не получен за 5 минут")
            return ""


def verify_tokens(dev_token: str, user_token: str) -> bool:
    """Проверяет работоспособность токенов."""
    print()
    print("=" * 60)
    print("Проверка токенов")
    print("=" * 60)

    headers = {
        "Authorization": f"Bearer {dev_token}",
        "Music-User-Token": user_token,
        "User-Agent": USER_AGENT,
        "Origin": "https://music.apple.com",
    }

    # Тест 1: Каталог (только dev token)
    print("Тест каталога (developer token)...", end=" ")
    resp = requests.get(
        "https://amp-api.music.apple.com/v1/catalog/us/songs/1440650711",
        headers={"Authorization": f"Bearer {dev_token}", "User-Agent": USER_AGENT, "Origin": "https://music.apple.com"},
        timeout=15,
    )
    if resp.status_code == 200:
        data = resp.json()
        song = data["data"][0]["attributes"]
        print(f"OK ({song['name']} - {song['artistName']})")
    else:
        print(f"ОШИБКА {resp.status_code}")
        return False

    # Тест 2: Библиотека (dev + user token)
    print("Тест библиотеки (user token)...", end=" ")
    resp = requests.get(
        "https://amp-api.music.apple.com/v1/me/library/songs",
        params={"limit": 1},
        headers=headers,
        timeout=15,
    )
    if resp.status_code == 200:
        data = resp.json()
        count = len(data.get("data", []))
        print(f"OK (библиотека доступна)")
        return True
    elif resp.status_code == 403:
        print("ОШИБКА 403: media-user-token невалиден или нет подписки")
        return False
    else:
        print(f"ОШИБКА {resp.status_code}: {resp.text[:200]}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Извлечение токенов Apple Music")
    parser.add_argument("--from-chrome", action="store_true",
                        help="Извлечь user token из Chrome cookies")
    parser.add_argument("--from-safari", action="store_true",
                        help="Извлечь user token из Safari cookies")
    parser.add_argument("--interactive", action="store_true",
                        help="Интерактивный логин через Playwright")
    parser.add_argument("--save", action="store_true",
                        help="Сохранить токены в файлы")
    parser.add_argument("--verify", action="store_true",
                        help="Проверить токены после извлечения")
    args = parser.parse_args()

    # Developer token
    dev_token = extract_developer_token()

    # User token
    user_token = ""

    if args.from_chrome:
        user_token = extract_from_chrome()
    elif args.from_safari:
        user_token = extract_from_safari()
    elif args.interactive:
        user_token = extract_interactive()

    if not user_token and (args.from_chrome or args.from_safari or args.interactive):
        print()
        print("User token не удалось извлечь автоматически.")
        print("Используйте ручной способ:")
        print("  1. Откройте https://music.apple.com/ в Chrome")
        print("  2. DevTools (F12) → Application → Cookies → music.apple.com")
        print("  3. Скопируйте значение 'media-user-token'")

    # Сохранение
    if args.save and dev_token:
        with open(DEV_TOKEN_FILE, "w") as f:
            f.write(dev_token)
        print(f"\nDeveloper token сохранён: {DEV_TOKEN_FILE}")

    if args.save and user_token:
        with open(TOKEN_FILE, "w") as f:
            f.write(user_token)
        print(f"User token сохранён: {TOKEN_FILE}")

    # Проверка
    if args.verify and dev_token and user_token:
        verify_tokens(dev_token, user_token)

    # Итог
    print()
    print("=" * 60)
    print("Итог")
    print("=" * 60)
    print(f"Developer Token: {'OK' if dev_token else 'НЕТ'}")
    print(f"User Token:      {'OK' if user_token else 'НЕТ (нужен ручной ввод)'}")

    if dev_token and not user_token:
        print()
        print("Для получения media-user-token:")
        print("  Вариант A: python extract_tokens.py --interactive")
        print("  Вариант B: Скопируйте вручную из DevTools браузера")
        print(f"  Сохраните в: {TOKEN_FILE}")


if __name__ == "__main__":
    main()
