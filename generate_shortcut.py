#!/usr/bin/env python3
"""
Генерирует Apple Shortcuts (.shortcut файлы) для добавления
сматченных треков в плейлист Apple Music "Yandex Favorites".

Разбивает 870 треков на батчи по 100 — один шорткат на батч.

Использование:
    python generate_shortcut.py
    # Затем импортировать каждый файл:
    open data/shortcuts/YandexToApple_01.shortcut
"""

import json
import os
import plistlib
import uuid

import config

BATCH_SIZE = 50  # по 50 треков — 100 actions на батч
PLAYLIST_NAME = "Yandex Favorites"
OUTPUT_DIR = os.path.join(config.DATA_DIR, "shortcuts")


def make_uuid():
    return str(uuid.uuid4()).upper()


def text_token(text):
    return {
        "Value": {"attachmentsByRange": {}, "string": text},
        "WFSerializationType": "WFTextTokenString",
    }


def var_ref(output_uuid, output_name):
    return {
        "Value": {
            "attachmentsByRange": {
                "{0, 1}": {
                    "OutputName": output_name,
                    "OutputUUID": output_uuid,
                    "Type": "ActionOutput",
                }
            },
            "string": "\uFFFC",
        },
        "WFSerializationType": "WFTextTokenString",
    }


def build_shortcut(queries, batch_num):
    """Плоский шорткат: для каждого трека отдельный Search + Add to Playlist."""
    actions = [
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.comment",
            "WFWorkflowActionParameters": {
                "WFCommentActionText": f"Yandex → Apple Music batch {batch_num}: {len(queries)} tracks",
            },
        },
    ]

    for query in queries:
        search_uuid = make_uuid()
        # Search iTunes Store (Find iTunes Store Items)
        actions.append({
            "WFWorkflowActionIdentifier": "is.workflow.actions.searchitunes",
            "WFWorkflowActionParameters": {
                "UUID": search_uuid,
                "WFEntity": "Song",
                "WFMediaCountry": "RU",
                "WFSearchTerm": text_token(query),
            },
        })
        # Add to Playlist
        actions.append({
            "WFWorkflowActionIdentifier": "is.workflow.actions.addtoplaylist",
            "WFWorkflowActionParameters": {
                "WFPlaylistName": PLAYLIST_NAME,
            },
        })

    return {
        "WFWorkflowActions": actions,
        "WFWorkflowClientVersion": "2302.0.4",
        "WFWorkflowClientRelease": "2302.0.4",
        "WFWorkflowHasShortcutInputVariables": True,
        "WFWorkflowIcon": {
            "WFWorkflowIconGlyphNumber": 59657,
            "WFWorkflowIconStartColor": 4282601983,
        },
        "WFWorkflowInputContentItemClasses": ["WFStringContentItem"],
        "WFWorkflowMinimumClientVersion": 900,
        "WFWorkflowMinimumClientVersionString": "900",
        "WFWorkflowTypes": ["NCWidget", "WatchKit"],
    }


def main():
    with open(config.MATCHED_TRACKS_JSON, encoding="utf-8") as f:
        tracks = json.load(f)

    queries = []
    for t in tracks:
        artist = t.get("apple_artist", t.get("artists", ""))
        title = t.get("apple_title", t.get("title", ""))
        if artist and title:
            queries.append(f"{artist} {title}")

    print(f"Треков: {len(queries)}")
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    batches = [queries[i:i + BATCH_SIZE] for i in range(0, len(queries), BATCH_SIZE)]
    print(f"Батчей по {BATCH_SIZE}: {len(batches)}\n")

    for i, batch in enumerate(batches):
        n = i + 1
        shortcut = build_shortcut(batch, n)
        path = os.path.join(OUTPUT_DIR, f"YandexToApple_{n:02d}.shortcut")
        with open(path, "wb") as f:
            plistlib.dump(shortcut, f, fmt=plistlib.FMT_BINARY)
        print(f"  {os.path.basename(path)} — {len(batch)} треков")

    print(f"\nФайлы: {OUTPUT_DIR}")
    print(f"\nИмпорт (по одному):")
    for i in range(len(batches)):
        print(f"  open \"{OUTPUT_DIR}/YandexToApple_{i+1:02d}.shortcut\"")
    print(f"\nПосле импорта запускайте каждый шорткат в Shortcuts.app")


if __name__ == "__main__":
    main()
