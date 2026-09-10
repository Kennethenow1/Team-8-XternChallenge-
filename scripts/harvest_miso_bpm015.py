#!/usr/bin/env python3
"""Harvest MISO BPM-015 PDFs, label them, extract text for later AI search.

  python scripts/harvest_miso_bpm015.py
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

REPO = Path(__file__).resolve().parents[1]
ROOT = REPO / "docs" / "miso_policy"
PDF_DIR = ROOT / "pdfs"
EXTRACT_DIR = ROOT / "extracted"
SOURCE_DIR = ROOT / "sources"

BPM_ZIP_URL = "https://cdn.misoenergy.org/BPM-015%20Generator%20Interconnection49574.zip"
BPM_PAGE = "https://www.misoenergy.org/legal/rules-manuals-and-agreements/business-practice-manuals/"
GI_PAGE = "https://www.misoenergy.org/planning/resource-utilization/generator-interconnection/"
FLOW_URL = "https://cdn.misoenergy.org/GI%20Process%20Flow%20Diagram106549.pdf"

HEADER_LINES = {
    "generation interconnection",
    "business practices manual",
    "ops-12",
    "public",
    "unlabeled",
}

TOP_SECTION = re.compile(r"^(\d+)\.\s+([A-Za-z].+?)\s*$")
APPENDIX = re.compile(r"^Appendix\s+([A-Z])\b[.\s]*(.*)$", re.I)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def download(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    req = Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; Team8-policy-harvest/1.0)"})
    with urlopen(req, timeout=120) as resp, dest.open("wb") as fh:
        shutil.copyfileobj(resp, fh)


def slug(text: str, n: int = 70) -> str:
    out = re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")
    return (out or "section")[:n]


def strip_header(page_text: str) -> tuple[str, int | None]:
    lines = [ln.rstrip() for ln in page_text.splitlines()]
    page_no = None
    body: list[str] = []
    skip = True
    for ln in lines:
        low = ln.strip().lower()
        m = re.search(r"page\s+(\d+)\s+of\s+\d+", low)
        if m:
            page_no = int(m.group(1))
            continue
        if skip:
            if not low:
                continue
            if low in HEADER_LINES or low.startswith("bpm-015") or low.startswith("effective date"):
                continue
            skip = False
        body.append(ln)
    text = "\n".join(body).strip()
    return text, page_no


def extract_pages(pdf_path: Path) -> list[dict]:
    import pymupdf

    doc = pymupdf.open(pdf_path)
    pages = []
    for i, page in enumerate(doc, start=1):
        raw = page.get_text() or ""
        body, parsed = strip_header(raw)
        pages.append(
            {
                "page": parsed or i,
                "pdf_page": i,
                "text": body,
                "char_count": len(body),
            }
        )
    return pages


def _title_ok(title: str) -> bool:
    t = title.strip()
    if not t or len(t) > 90:
        return False
    if "shall" in t.lower():
        return False
    return t[0].isalpha() or t[0] in "“\"'"


def split_sections(pages: list[dict]) -> list[dict]:
    """Chapter/appendix marks from body pages (skip TOC), then group following text."""
    marks: list[tuple[int, int, str, str]] = []  # page, line_idx unused, sid, title
    seen_ch: set[int] = set()
    seen_app: set[str] = set()
    for p in pages:
        pg = int(p["page"])
        lines = p["text"].splitlines()
        for j, ln in enumerate(lines):
            s = ln.strip()
            if pg >= 16:
                m = re.match(r"^(\d+)\.\s*$", s)
                if m:
                    n = int(m.group(1))
                    nxt = next((x.strip() for x in lines[j + 1 :] if x.strip()), "")
                    if 1 <= n <= 12 and n not in seen_ch and _title_ok(nxt):
                        seen_ch.add(n)
                        marks.append((pg, j, f"{n:02d}", nxt))
                        continue
                m9 = re.match(r"^9\.\s+(Expedite.+ERAS.*)$", s, re.I)
                if m9 and 9 not in seen_ch and pg >= 130:
                    seen_ch.add(9)
                    marks.append((pg, j, "09", m9.group(1).strip()))
                    continue
            if pg >= 140:
                a = re.match(r"^Appendix\s+([A-Z])\b(.*)$", s, re.I)
                if a:
                    letter = a.group(1).upper()
                    rest = (a.group(2) or "").strip(" .:—-")
                    if letter not in seen_app:
                        seen_app.add(letter)
                        marks.append((pg, j, f"app_{letter}", rest or f"Appendix {letter}"))

    marks.sort(key=lambda x: (x[0], x[1]))
    by_page = {int(p["page"]): p["text"] for p in pages}
    page_nums = sorted(by_page)
    if not marks:
        return [
            {
                "section_id": "full",
                "title": "Full document",
                "text": "\n\n".join(p["text"] for p in pages if p["text"]).strip(),
                "start_page": pages[0]["page"] if pages else 1,
                "end_page": pages[-1]["page"] if pages else 1,
            }
        ]

    sections = []
    first_body = marks[0][0]
    front_pages = [pg for pg in page_nums if pg < first_body]
    if front_pages:
        sections.append(
            {
                "section_id": "00",
                "title": "Front matter (disclaimer, revision history, contents)",
                "text": "\n\n".join(by_page[pg] for pg in front_pages if by_page[pg]).strip(),
                "start_page": front_pages[0],
                "end_page": front_pages[-1],
            }
        )
    for n, (start_pg, _j, sid, title) in enumerate(marks):
        end_pg = marks[n + 1][0] - 1 if n + 1 < len(marks) else page_nums[-1]
        texts = []
        for pg in page_nums:
            if start_pg <= pg <= end_pg:
                texts.append(by_page[pg])
        sections.append(
            {
                "section_id": sid,
                "title": title,
                "text": "\n\n".join(t for t in texts if t).strip(),
                "start_page": start_pg,
                "end_page": end_pg,
            }
        )
    return sections


def write_markdown(path: Path, meta: dict, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fm = ["---"]
    for k, v in meta.items():
        if v is None:
            continue
        if isinstance(v, str) and (":" in v or "#" in v):
            fm.append(f'{k}: {json.dumps(v)}')
        else:
            fm.append(f"{k}: {v}")
    fm.append("---")
    path.write_text("\n".join(fm) + "\n\n" + body.strip() + "\n", encoding="utf-8")


def label_copy(src: Path, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)


def main() -> int:
    ROOT.mkdir(parents=True, exist_ok=True)
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    EXTRACT_DIR.mkdir(parents=True, exist_ok=True)
    SOURCE_DIR.mkdir(parents=True, exist_ok=True)

    zip_path = SOURCE_DIR / "BPM-015_Generator_Interconnection.zip"
    if not zip_path.exists():
        print(f"download {BPM_ZIP_URL}", flush=True)
        download(BPM_ZIP_URL, zip_path)

    unzip = SOURCE_DIR / "_unzipped"
    if unzip.exists():
        shutil.rmtree(unzip)
    unzip.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall(unzip)

    flow_path = SOURCE_DIR / "GI_Process_Flow_Diagram.pdf"
    if not flow_path.exists():
        print(f"download {FLOW_URL}", flush=True)
        download(FLOW_URL, flow_path)

    # Map zip members to labeled files
    docs = []
    zip_pdfs = {p.name: p for p in unzip.glob("*.pdf")}

    def add(src: Path, dest_name: str, rec: dict) -> None:
        dest = PDF_DIR / dest_name
        label_copy(src, dest)
        rec = dict(rec)
        rec["file"] = dest.name
        rec["bytes"] = dest.stat().st_size
        rec["sha256"] = sha256(dest)
        rec["retrieved_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        docs.append((dest, rec))

    # Current official clean copy
    r33_clean = next(p for n, p in zip_pdfs.items() if "r33" in n and "CLEAN" in n.upper() and "REDLINE" not in n.upper())
    r33_red = next(p for n, p in zip_pdfs.items() if "r33" in n and "REDLINE" in n.upper())
    r32_clean = next(p for n, p in zip_pdfs.items() if "r32" in n and "CLEAN" in n.upper())

    add(
        r33_clean,
        "01_bpm-015-r33_generator_interconnection_clean.pdf",
        {
            "doc_id": "bpm-015-r33-clean",
            "title": "BPM-015 r33 Generator Interconnection (CLEAN)",
            "revision": "r33",
            "effective_date": "2026-07-01",
            "status": "current",
            "kind": "bpm",
            "role": "Use this for AI search. Current MISO GI business practices implementing Attachment X.",
            "source_url": BPM_ZIP_URL,
            "source_page": BPM_PAGE,
        },
    )
    add(
        r33_red,
        "02_bpm-015-r33_generator_interconnection_redlines.pdf",
        {
            "doc_id": "bpm-015-r33-redlines",
            "title": "BPM-015 r33 Generator Interconnection (REDLINES vs r32)",
            "revision": "r33",
            "effective_date": "2026-07-01",
            "status": "redlines",
            "kind": "bpm_redlines",
            "role": "Shows what changed from r32. Do not treat as the clean rule text.",
            "source_url": BPM_ZIP_URL,
            "source_page": BPM_PAGE,
        },
    )
    add(
        r32_clean,
        "03_bpm-015-r32_generator_interconnection_clean.pdf",
        {
            "doc_id": "bpm-015-r32-clean",
            "title": "BPM-015 r32 Generator Interconnection (CLEAN, prior)",
            "revision": "r32",
            "effective_date": "2025-12-15",
            "status": "superseded",
            "kind": "bpm",
            "role": "Prior revision. Keep for diff / historical as-of dates only.",
            "source_url": BPM_ZIP_URL,
            "source_page": BPM_PAGE,
        },
    )
    add(
        flow_path,
        "04_gi_process_flow_diagram.pdf",
        {
            "doc_id": "gi-process-flow-diagram",
            "title": "Generator Interconnection Process Flow Diagram",
            "revision": None,
            "effective_date": None,
            "status": "companion",
            "kind": "diagram",
            "role": "Milestone / DPP timeline graphic referenced by BPM-015. Text extract is thin; keep the PDF.",
            "source_url": FLOW_URL,
            "source_page": GI_PAGE,
        },
    )

    chunks: list[dict] = []
    catalog_docs = []
    for dest, rec in docs:
        print(f"extract {dest.name}", flush=True)
        pages = extract_pages(dest)
        sections = split_sections(pages)
        out_dir = EXTRACT_DIR / rec["doc_id"]
        if out_dir.exists():
            shutil.rmtree(out_dir)
        (out_dir / "pages").mkdir(parents=True)
        (out_dir / "sections").mkdir(parents=True)
        full_text = "\n\n".join(f"## Page {p['page']}\n\n{p['text']}" for p in pages if p["text"])
        write_markdown(
            out_dir / "FULL.md",
            {k: rec[k] for k in ("doc_id", "title", "revision", "effective_date", "status", "kind", "source_url") if k in rec},
            full_text,
        )
        for p in pages:
            if not p["text"]:
                continue
            write_markdown(
                out_dir / "pages" / f"p{p['page']:03d}.md",
                {"doc_id": rec["doc_id"], "page": p["page"], "title": rec["title"]},
                p["text"],
            )
        for sec in sections:
            fname = f"{sec['section_id']}_{slug(sec['title'])}.md"
            write_markdown(
                out_dir / "sections" / fname,
                {
                    "doc_id": rec["doc_id"],
                    "section_id": sec["section_id"],
                    "section_title": sec["title"],
                    "start_page": sec.get("start_page"),
                    "end_page": sec.get("end_page"),
                    "status": rec["status"],
                    "source_pdf": rec["file"],
                },
                f"# {sec['section_id']} {sec['title']}\n\n{sec['text']}",
            )
            chunks.append(
                {
                    "id": f"{rec['doc_id']}::sec-{sec['section_id']}",
                    "text": sec["text"],
                    "metadata": {
                        "doc_id": rec["doc_id"],
                        "title": rec["title"],
                        "section_id": sec["section_id"],
                        "section_title": sec["title"],
                        "start_page": sec.get("start_page"),
                        "end_page": sec.get("end_page"),
                        "status": rec["status"],
                        "source_pdf": rec["file"],
                        "source_url": rec.get("source_url"),
                    },
                }
            )
        rec_out = dict(rec)
        rec_out["n_pages"] = len(pages)
        rec_out["n_sections"] = len(sections)
        rec_out["extracted_dir"] = str(out_dir.relative_to(ROOT)).replace("\\", "/")
        catalog_docs.append(rec_out)

    catalog = {
        "pack": "miso_bpm015_generator_interconnection",
        "retrieved_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "note": (
            "BPM-015 implements Attachment X of the MISO Tariff. If BPM and tariff conflict, the tariff controls. "
            "Attachment X PDF was not bundled in the official BPM zip; download from the Tariff page if needed."
        ),
        "sources": {
            "bpm_manuals_page": BPM_PAGE,
            "bpm015_zip": BPM_ZIP_URL,
            "gi_page": GI_PAGE,
            "flow_diagram": FLOW_URL,
            "tariff_page": "https://www.misoenergy.org/legal/rules-manuals-and-agreements/tariff/",
        },
        "documents": catalog_docs,
        "n_chunks": len(chunks),
    }
    (ROOT / "catalog.json").write_text(json.dumps(catalog, indent=2), encoding="utf-8")
    with (EXTRACT_DIR / "chunks.jsonl").open("w", encoding="utf-8") as fh:
        for c in chunks:
            fh.write(json.dumps(c, ensure_ascii=False) + "\n")

    readme = f"""# MISO BPM-015 — Generation Interconnection (policy pack)

Official MISO GI business practices, labeled and extracted for later AI search / RAG.
**Not** a model input. **Not** the tariff (Attachment X still controls if they conflict).

Retrieved **{catalog['retrieved_at']}** from [MISO Business Practice Manuals]({BPM_PAGE}).

## Use this file first

| File | What it is |
|------|------------|
| `pdfs/01_bpm-015-r33_generator_interconnection_clean.pdf` | **Current** BPM-015 r33 (effective 2026-07-01) |
| `pdfs/02_bpm-015-r33_generator_interconnection_redlines.pdf` | Tracked changes vs r32 |
| `pdfs/03_bpm-015-r32_generator_interconnection_clean.pdf` | Prior clean copy (superseded 2025-12-15) |
| `pdfs/04_gi_process_flow_diagram.pdf` | DPP / milestone flow graphic |
| `extracted/chunks.jsonl` | Chapter-grain chunks (too coarse for the bot) |
| `index/` | **Tagged procedure units** for retrieval (r33 clean only) |
| `catalog.json` | IDs, hashes, roles |

Current extract lives under `extracted/bpm-015-r33-clean/` (`FULL.md`, `sections/`, `pages/`).

## Retrieval index (use this for the bot)

`index/` is the tagged JSON pack. Platinum 4 (`retrieve_for_card`) turns a Platinum 3 card into a bot packet. Notebook: `platinum4/01_bot_packets.ipynb`.

```text
python scripts/build_miso_policy_index.py
```

Index **r33 clean only**. r32/redlines stay on disk for humans; do not retrieve them unless the as-of date is before 2026-07-01.

Rebuild PDFs/extracts:

```text
python scripts/harvest_miso_bpm015.py
```

## Missing on purpose

- **Attachment X (GIP)** — legally controlling; not inside the BPM zip. Get it from the [Tariff page](https://www.misoenergy.org/legal/rules-manuals-and-agreements/tariff/).
- Company-internal playbooks — `developer_serial_quit`, `hazard_exposure`, and `policy_incentive` stay stubs. Other Platinum 3 risks use `bpm015_index`.
"""
    (ROOT / "README.md").write_text(readme, encoding="utf-8")
    shutil.rmtree(unzip, ignore_errors=True)
    print(json.dumps({"n_docs": len(catalog_docs), "n_chunks": len(chunks), "root": str(ROOT)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
