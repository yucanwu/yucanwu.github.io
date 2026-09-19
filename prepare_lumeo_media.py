#!/usr/bin/env python3
"""
prepare_lumeo_media.py

What it does:
1) Recursively scans assets/lumeo/photo
2) Renames ONLY generic image filenames (conservative by default)
3) Preserves filenames that already look manually annotated
4) Creates contact sheets for every folder that directly contains images
5) Writes a rename log and duplicate report

Usage:
    python3 prepare_lumeo_media.py
        -> dry run: preview rename plan, do not rename files

    python3 prepare_lumeo_media.py --apply
        -> actually rename files, then generate contact sheets

Install dependency first:
    python3 -m pip install pillow
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import math
import re
from pathlib import Path
from typing import Iterable

from PIL import Image, ImageDraw, ImageFont, ImageOps

# ---------------------------------------------------------------------
# CONFIG
# ---------------------------------------------------------------------

PHOTO_ROOT = Path("assets/lumeo/photo")
CONTACT_ROOT_NAME = "_contact_sheets"

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp"}

# Conservative rule:
# only filenames matching one of these patterns will be auto-renamed.
# Everything else is treated as "already annotated" and is preserved.
GENERIC_NAME_PATTERNS = [
    re.compile(r"^微信图片[_-].*", re.IGNORECASE),
    re.compile(r"^IMG[_-]?\d+.*", re.IGNORECASE),
    re.compile(r"^DSC[_-]?\d+.*", re.IGNORECASE),
    re.compile(r"^PXL[_-]?\d+.*", re.IGNORECASE),
    re.compile(r"^Screenshot[ _-].*", re.IGNORECASE),
]

# Short names for your current folder tree.
# Edit freely later if you add new folders.
FOLDER_ALIASES = {
    "01-overview": "overview",
    "01-clean": "clean",
    "02-atmosphere": "atmosphere",

    "02-testing": "testing",
    "01-arm": "arm",
    "02-autonomous-driving": "autodrive",
    "01-2025": "2025",
    "02-2026-07": "2026-07",

    "03-technical": "technical",
    "01-code": "code",
    "02-mechanical-design": "mech",
    "01-simulation": "simulation",
    "02-cad": "cad",

    "04-team": "team",
    "05-events": "events",
}

# Contact sheet appearance
THUMB_W = 360
THUMB_H = 240
COLS = 4
ROWS = 5
CELL_W = 390
CELL_H = 300
MARGIN = 24
LABEL_H = 50
BG = (245, 245, 245)
FG = (20, 20, 20)
BORDER = (205, 205, 205)

# ---------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------

def is_image(path: Path) -> bool:
    return path.is_file() and path.suffix.lower() in IMAGE_EXTS


def is_generic_name(path: Path) -> bool:
    stem = path.stem
    return any(p.fullmatch(stem) or p.match(stem) for p in GENERIC_NAME_PATTERNS)


def slug_component(name: str) -> str:
    if name in FOLDER_ALIASES:
        return FOLDER_ALIASES[name]

    # Remove leading ordering prefix such as "01-"
    name = re.sub(r"^\d{1,3}[-_ ]*", "", name)
    name = name.strip().lower()
    name = re.sub(r"[^a-z0-9]+", "-", name)
    return name.strip("-") or "media"


def folder_prefix(folder: Path, root: Path) -> str:
    rel = folder.relative_to(root)
    parts = [slug_component(p) for p in rel.parts]
    return "-".join(p for p in parts if p)


def unique_target(folder: Path, prefix: str, ext: str, used: set[str], start: int = 1) -> Path:
    n = start
    while True:
        filename = f"{prefix}-{n:03d}{ext.lower()}"
        if filename not in used and not (folder / filename).exists():
            used.add(filename)
            return folder / filename
        n += 1


def load_font(size: int):
    candidates = [
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
        "/System/Library/Fonts/SFNS.ttf",
        "/Library/Fonts/Arial Unicode.ttf",
    ]
    for p in candidates:
        if Path(p).exists():
            try:
                return ImageFont.truetype(p, size=size)
            except Exception:
                pass
    return ImageFont.load_default()


def shorten(text: str, max_len: int = 46) -> str:
    if len(text) <= max_len:
        return text
    return text[: max_len - 1] + "…"


def file_hash(path: Path, chunk_size: int = 1024 * 1024) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


# ---------------------------------------------------------------------
# RENAME
# ---------------------------------------------------------------------

def build_rename_plan(root: Path):
    plan = []

    for folder in sorted(p for p in root.rglob("*") if p.is_dir()):
        if CONTACT_ROOT_NAME in folder.parts:
            continue

        images = sorted(
            [p for p in folder.iterdir() if is_image(p)],
            key=lambda p: p.name.lower(),
        )
        generic = [p for p in images if is_generic_name(p)]

        if not generic:
            continue

        prefix = folder_prefix(folder, root)
        used = {p.name for p in images if not is_generic_name(p)}

        counter = 1
        for src in generic:
            dst = unique_target(folder, prefix, src.suffix, used, start=counter)
            # advance next preferred number
            m = re.search(r"-(\d{3})$", dst.stem)
            if m:
                counter = int(m.group(1)) + 1
            plan.append((src, dst))

    return plan


def apply_rename_plan(plan, apply: bool, root: Path):
    log_path = root / "rename-map.csv"
    rows = []

    print("\nRename plan:")
    if not plan:
        print("  No generic filenames found.")
    else:
        for src, dst in plan:
            print(f"  {src.relative_to(root)}")
            print(f"    -> {dst.relative_to(root)}")

    if apply:
        # Rename one by one. Targets are designed not to collide.
        for src, dst in plan:
            src.rename(dst)
            rows.append([
                str(src.relative_to(root)),
                str(dst.relative_to(root)),
                "renamed",
            ])
        print(f"\nApplied {len(plan)} renames.")
    else:
        for src, dst in plan:
            rows.append([
                str(src.relative_to(root)),
                str(dst.relative_to(root)),
                "dry-run only",
            ])
        print("\nDRY RUN ONLY — no files were renamed.")
        print("Run again with --apply when the plan looks correct.")

    with log_path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(["old_path", "new_path", "status"])
        writer.writerows(rows)

    print(f"Rename log: {log_path}")


# ---------------------------------------------------------------------
# CONTACT SHEETS
# ---------------------------------------------------------------------

def make_contact_sheets(root: Path):
    contact_root = root / CONTACT_ROOT_NAME
    contact_root.mkdir(parents=True, exist_ok=True)

    title_font = load_font(25)
    label_font = load_font(17)
    small_font = load_font(14)

    folders = []
    for folder in sorted(p for p in root.rglob("*") if p.is_dir()):
        if CONTACT_ROOT_NAME in folder.parts:
            continue
        images = sorted([p for p in folder.iterdir() if is_image(p)], key=lambda p: p.name.lower())
        if images:
            folders.append((folder, images))

    per_page = COLS * ROWS

    for folder, images in folders:
        rel = folder.relative_to(root)
        folder_id = "__".join(rel.parts)
        pages = math.ceil(len(images) / per_page)

        for page_i in range(pages):
            batch = images[page_i * per_page : (page_i + 1) * per_page]

            canvas_w = MARGIN * 2 + COLS * CELL_W
            header_h = 72
            canvas_h = MARGIN * 2 + header_h + ROWS * CELL_H

            canvas = Image.new("RGB", (canvas_w, canvas_h), BG)
            draw = ImageDraw.Draw(canvas)

            title = str(rel)
            draw.text((MARGIN, MARGIN), title, fill=FG, font=title_font)
            subtitle = f"{len(images)} images · page {page_i + 1}/{pages}"
            draw.text((MARGIN, MARGIN + 34), subtitle, fill=(90, 90, 90), font=small_font)

            for i, img_path in enumerate(batch):
                row = i // COLS
                col = i % COLS

                x0 = MARGIN + col * CELL_W
                y0 = MARGIN + header_h + row * CELL_H

                # cell border
                draw.rectangle(
                    [x0, y0, x0 + CELL_W - 12, y0 + CELL_H - 12],
                    outline=BORDER,
                    width=1,
                )

                try:
                    with Image.open(img_path) as im:
                        im = ImageOps.exif_transpose(im).convert("RGB")
                        thumb = ImageOps.contain(im, (THUMB_W, THUMB_H))

                    ix = x0 + (CELL_W - 12 - thumb.width) // 2
                    iy = y0 + 8 + (THUMB_H - thumb.height) // 2
                    canvas.paste(thumb, (ix, iy))
                except Exception as e:
                    err = f"[Could not open]\n{e}"
                    draw.multiline_text((x0 + 10, y0 + 20), err, fill=(160, 40, 40), font=small_font)

                label = shorten(img_path.name)
                tx = x0 + 8
                ty = y0 + THUMB_H + 18
                draw.text((tx, ty), label, fill=FG, font=label_font)

            suffix = f"_p{page_i + 1:02d}" if pages > 1 else ""
            out = contact_root / f"{folder_id}{suffix}.jpg"
            canvas.save(out, "JPEG", quality=88, optimize=True)
            print(f"Contact sheet: {out}")


# ---------------------------------------------------------------------
# DUPLICATE REPORT
# ---------------------------------------------------------------------

def write_duplicate_report(root: Path):
    images = [
        p for p in root.rglob("*")
        if is_image(p) and CONTACT_ROOT_NAME not in p.parts
    ]

    groups = {}
    for p in images:
        try:
            h = file_hash(p)
        except Exception:
            continue
        groups.setdefault(h, []).append(p)

    dup_groups = [paths for paths in groups.values() if len(paths) > 1]
    report = root / "duplicate-report.csv"

    with report.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(["group", "path"])
        for i, paths in enumerate(dup_groups, start=1):
            for p in paths:
                writer.writerow([i, str(p.relative_to(root))])

    print(f"Duplicate report: {report} ({len(dup_groups)} duplicate groups)")


# ---------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually rename generic files. Without this flag, only preview.",
    )
    args = parser.parse_args()

    if not PHOTO_ROOT.exists():
        raise SystemExit(
            f"Cannot find {PHOTO_ROOT}\n"
            "Run this script from the root of your yucanwu.github.io repository."
        )

    print(f"Photo root: {PHOTO_ROOT.resolve()}")

    plan = build_rename_plan(PHOTO_ROOT)
    apply_rename_plan(plan, args.apply, PHOTO_ROOT)

    # If --apply was used, sheets reflect the new filenames.
    # Without --apply, sheets reflect current filenames.
    make_contact_sheets(PHOTO_ROOT)
    write_duplicate_report(PHOTO_ROOT)

    print("\nDone.")
    print("Generated:")
    print(f"  {PHOTO_ROOT / CONTACT_ROOT_NAME}/")
    print(f"  {PHOTO_ROOT / 'rename-map.csv'}")
    print(f"  {PHOTO_ROOT / 'duplicate-report.csv'}")


if __name__ == "__main__":
    main()
