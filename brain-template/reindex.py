#!/usr/bin/env python3
"""Rebuild INDEX.md and <section>/_index.md from the frontmatter of every note.

Usage:
    python3 reindex.py                 # rewrite the indexes (idempotent)
    python3 reindex.py --check         # exit 1 if the indexes are out of date
    python3 reindex.py --root <dir>    # index another library

Only the standard library is used. The library root is the directory this
script lives in unless --root is given.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SECTIONS = ["facts", "people", "projects", "journal"]
FRONTMATTER = re.compile(r"\A---\n(.*?)\n---\n", re.S)


def read_meta(path: Path) -> dict[str, str]:
    """Flat `key: value` frontmatter. Missing name/description get fallbacks."""
    text = path.read_text(encoding="utf-8", errors="replace")
    match = FRONTMATTER.match(text)
    meta: dict[str, str] = {}
    if match:
        for line in match.group(1).splitlines():
            if ":" in line:
                key, value = line.split(":", 1)
                meta[key.strip()] = value.strip().strip("'\"")
    body = text[match.end():] if match else text
    first_line = next((ln.strip("# ").strip() for ln in body.splitlines() if ln.strip()), "")
    meta.setdefault("name", path.stem)
    meta.setdefault("description", first_line[:120])
    return meta


def build() -> dict[Path, str]:
    """Return {path: content} for every index file."""
    out: dict[Path, str] = {}
    top = ["# INDEX", "", "One line per note. Section details: `<section>/_index.md`.", ""]
    for section in SECTIONS:
        folder = ROOT / section
        notes = sorted(p for p in folder.glob("*.md") if p.name != "_index.md") if folder.is_dir() else []
        lines = [f"# {section}", ""]
        for note in notes:
            meta = read_meta(note)
            line = f"- [{meta['name']}]({note.name}) - {meta['description']}"
            if meta.get("tags"):
                line += f" `{meta['tags']}`"
            if meta.get("updated"):
                line += f" ({meta['updated']})"
            lines.append(line)
            top.append(f"- {section}/{note.name} - {meta['description']}")
        if folder.is_dir():
            out[folder / "_index.md"] = "\n".join(lines) + "\n"
        top.append("")
    out[ROOT / "INDEX.md"] = "\n".join(top).rstrip() + "\n"
    return out


def main(argv: list[str]) -> int:
    global ROOT
    if "--root" in argv:
        ROOT = Path(argv[argv.index("--root") + 1]).resolve()
    files = build()
    if "--check" in argv:
        stale = [p for p, body in files.items() if not p.exists() or p.read_text(encoding="utf-8") != body]
        for p in stale:
            print(f"stale: {p.relative_to(ROOT)}")
        return 1 if stale else 0
    for path, body in files.items():
        path.write_text(body, encoding="utf-8")
    notes = sum(body.count("\n- ") for p, body in files.items() if p.name == "_index.md")
    print(f"indexed {notes} notes in {len(files) - 1} sections")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
