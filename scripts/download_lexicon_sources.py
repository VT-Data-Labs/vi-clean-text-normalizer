#!/usr/bin/env python3
"""Download all external Vietnamese dictionary sources for lexicon building.

Usage
-----
    python scripts/download_lexicon_sources.py [--data-dir data/raw]
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import requests

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("download_sources")

SOURCES: list[tuple[str, str, str]] = [
    (
        "UVD-1 (HF)",
        "uvd1.txt",
        "https://huggingface.co/datasets/undertheseanlp/UVD-1/resolve/main/data/data.txt",
    ),
    (
        "underthesea/hongocduc",
        "hongocduc.txt",
        "https://raw.githubusercontent.com/undertheseanlp/dictionary/master/dictionaries/hongocduc/words.txt",
    ),
    (
        "underthesea/tudientv",
        "tudientv.txt",
        "https://raw.githubusercontent.com/undertheseanlp/dictionary/master/dictionaries/tudientv/words.txt",
    ),
    (
        "underthesea/wiktionary",
        "wiktionary.txt",
        "https://raw.githubusercontent.com/undertheseanlp/dictionary/master/dictionaries/wiktionary/words.txt",
    ),
    (
        "underthesea/merged",
        "underthesea_merged.txt",
        "https://raw.githubusercontent.com/undertheseanlp/dictionary/master/dictionary/words.txt",
    ),
    (
        "Viet74K",
        "viet74k.txt",
        "https://raw.githubusercontent.com/duyet/vietnamese-wordlist/master/Viet74K.txt",
    ),
    (
        "Aspell (vi)",
        "aspell_vi.dic",
        "https://raw.githubusercontent.com/wooorm/dictionaries/main/dictionaries/vi/index.dic",
    ),
]


def download(url: str, path: Path, name: str) -> bool:
    """Download a single source file. Returns True on success."""
    try:
        resp = requests.get(url, timeout=120)
        resp.raise_for_status()
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "wb") as f:
            f.write(resp.content)
        log.info("Downloaded %s (%s) — %d bytes", name, path.name, len(resp.content))
        return True
    except requests.RequestException as e:
        log.error("Failed to download %s: %s", name, e)
        return False


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Download all external Vietnamese dictionary sources",
    )
    parser.add_argument(
        "--data-dir",
        default="data/raw",
        help="Output directory for raw data (default: data/raw)",
    )
    args = parser.parse_args()
    data_dir = Path(args.data_dir)

    log.info("Downloading %d sources to %s", len(SOURCES), data_dir.resolve())
    success = 0
    for name, filename, url in SOURCES:
        if download(url, data_dir / filename, name):
            success += 1

    log.info("Downloaded %d/%d sources successfully", success, len(SOURCES))
    if success < len(SOURCES):
        log.warning("Some sources failed — the build script will skip missing files")
    sys.exit(0 if success > 0 else 1)


if __name__ == "__main__":
    main()
