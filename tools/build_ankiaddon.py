"""Build the .ankiaddon file to upload to AnkiWeb (or install by hand).

Usage: python tools/build_ankiaddon.py  ->  dist/review_smoother-<version>.ankiaddon

The archive holds the contents of `review_smoother/` at its root (no
enclosing folder), without what Anki or Python write there (`meta.json`,
`__pycache__`), plus a `manifest.json` for installs from the file (AnkiWeb
ignores it). Only the files tracked by git are packed, so nothing local
slips in.
"""

from __future__ import annotations

import json
import os
import subprocess
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PACKAGE = "review_smoother"
VERSION = "1.0.0"
MANIFEST = {
    "package": PACKAGE,
    "name": "Review Smoother",
    "human_version": VERSION,
    "homepage": "https://github.com/AntoineToPHPin/anki-review-smoother",
    # Anki 2.1.66: oldest version with every API used (the Statistics
    # window's deck chooser came last). Tested on 26.09 only.
    "min_point_version": 66,
    "conflicts": [],
}


def tracked_files() -> list:
    output = subprocess.run(
        ["git", "ls-files", "-z", PACKAGE], cwd=ROOT, check=True, capture_output=True
    ).stdout.decode("utf-8")
    return [path for path in output.split("\0") if path]


def build() -> str:
    files = [
        path for path in tracked_files()
        if "__pycache__" not in path.split("/") and os.path.basename(path) != "meta.json"
    ]
    os.makedirs(os.path.join(ROOT, "dist"), exist_ok=True)
    target = os.path.join(ROOT, "dist", f"{PACKAGE}-{VERSION}.ankiaddon")
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(files):
            archive.write(os.path.join(ROOT, path), path[len(PACKAGE) + 1:])
        archive.writestr("manifest.json", json.dumps(MANIFEST, indent=2) + "\n")
    return target


if __name__ == "__main__":
    path = build()
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
    print(f"{path}: {len(names)} files")
    for name in names:
        print(f"  {name}")
