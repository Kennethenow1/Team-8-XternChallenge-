"""Historical MISO DPP study discovery, download, and project-level extraction.

Does not merge into Gold. Does not populate events from MTEP documents.
"""

from __future__ import annotations

import io
import json
import re
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote, unquote, urlsplit, urlunsplit
from urllib.request import Request, urlopen

import pandas as pd
import pdfplumber
import pymupdf as fitz

from src.common.paths import SILVER_DIR
from src.enrichment.registry import (
    ENRICHMENT_REPORTS,
    SILVER_ENRICHMENT,
    attach_metadata,
    bronze_dir,
    ensure_enrichment_dirs,
    utc_now_iso,
    write_bronze_bytes,
    write_bronze_text,
)

GI_STUDIES_URL = "https://www.misoenergy.org/planning/resource-utilization/GI_Studies/"
OPTICS_SEARCH_URL = (
    "https://www.misoenergy.org/api/find/Optics_Models_Find_RemoteHostedContentItem/_search"
)

SOURCE_ID = "miso_dpp_studies"
DISCOVERY_METHOD_API = "optics_api_processstage"
DISCOVERY_METHOD_PLAYWRIGHT = "playwright_network"

# Titles must indicate one of these study products (MTEP / SPM / IPWG excluded elsewhere).
INCLUDE_TITLE_RE = re.compile(
    r"""(?ix)
    (
        (?:dpp\s*)?(?:phase|ph)\s*(?:1|i|2|ii|3|iii)\b
        | \bfacilities\s+study\b
        | \bnetwork\s+upgrade\s+facilities\b
        | \brestudy\b
        | \baddendum\b
        | \bsystem\s+impact\s+study\b
        | \bsis\b
        | \bfinal\s+study\b
    )
    """
)

EXCLUDE_TITLE_RE = re.compile(
    r"""(?ix)
    (
        \bmtep\b
        | \bspm\b
        | \bipwg\b
        | queue[\s\-_]*overview
        | \bpolicy\b
        | whitepaper
        | mitigation
        | training
        | kickoff
        | pearl\s+street
        | benchmarking
        | contingent\s+facilities
        | \bmwex\b
        | affected\s+system(?!.*\brestudy\b)
    )
    """
)

PROJECT_ID_RE = re.compile(r"\b(J\d{3,5})\b", re.IGNORECASE)
MONEY_RE = re.compile(r"\$?\s*([\d,]+(?:\.\d+)?)\s*")

DATE_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    # YYYYMMDD
    (re.compile(r"(?<!\d)(20\d{2})(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])(?!\d)"), "%Y%m%d"),
    # MMDDYYYY
    (re.compile(r"(?<!\d)(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])(20\d{2})(?!\d)"), "%m%d%Y"),
    # MMDDYY (ambiguous year; assume 2000+)
    (re.compile(r"(?<!\d)(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])(\d{2})(?!\d)"), "%m%d%y"),
    # YYYY-MM-DD / YYYY/MM/DD
    (re.compile(r"(20\d{2})[-/](0[1-9]|1[0-2])[-/](0[1-9]|[12]\d|3[01])"), "%Y-%m-%d"),
    # MM/DD/YYYY
    (re.compile(r"\b(0?[1-9]|1[0-2])[/-](0?[1-9]|[12]\d|3[01])[/-](20\d{2})\b"), "%m/%d/%Y"),
    # Month DD, YYYY
    (
        re.compile(
            r"\b(January|February|March|April|May|June|July|August|September|October|November|December)"
            r"\s+(\d{1,2}),\s*(20\d{2})\b",
            re.I,
        ),
        "%B %d %Y",
    ),
]


@dataclass
class OpticsDoc:
    object_id: str
    title: str
    filename: str
    url: str
    extension: str
    content_type: str
    study_cycle: str | None
    study_region: str | None
    process_stage: str | None
    publish_date: str | None
    updated_date: str | None
    raw: dict[str, Any]


def _http_json(url: str, payload: dict[str, Any] | None = None) -> Any:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    headers = {
        "User-Agent": "Team8-MISO-DPP/1.0",
        "Accept": "application/json",
        "Origin": "https://www.misoenergy.org",
        "Referer": GI_STUDIES_URL,
    }
    if payload is not None:
        headers["Content-Type"] = "application/json"
    req = Request(url, data=data, headers=headers, method="GET" if data is None else "POST")
    with urlopen(req, timeout=120) as resp:
        raw = resp.read().decode("utf-8", errors="replace")
    parsed = json.loads(raw)
    if isinstance(parsed, str):
        parsed = json.loads(parsed)
    return parsed


def _http_bytes(url: str) -> bytes:
    req = Request(
        url,
        headers={
            "User-Agent": "Team8-MISO-DPP/1.0",
            "Accept": "*/*",
            "Referer": GI_STUDIES_URL,
            "Origin": "https://www.misoenergy.org",
        },
    )
    with urlopen(req, timeout=300) as resp:
        return resp.read()


def discover_with_playwright(bronze: Path) -> dict[str, Any]:
    """Inspect GI Studies page network; record Optics API request shape."""
    from playwright.sync_api import sync_playwright

    posts: list[dict[str, Any]] = []
    responses: list[dict[str, Any]] = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(user_agent="Team8-MISO-DPP/1.0")

        def on_request(req: Any) -> None:
            if "Optics_Models_Find_RemoteHostedContentItem" in req.url:
                posts.append(
                    {
                        "url": req.url,
                        "method": req.method,
                        "post_data": req.post_data,
                    }
                )

        def on_response(resp: Any) -> None:
            if "Optics_Models_Find_RemoteHostedContentItem" in resp.url:
                try:
                    body = resp.text()
                except Exception:  # noqa: BLE001
                    body = None
                responses.append({"url": resp.url, "status": resp.status, "body_len": len(body or "")})

        page.on("request", on_request)
        page.on("response", on_response)
        page.goto(GI_STUDIES_URL, wait_until="networkidle", timeout=120_000)
        page.wait_for_timeout(2000)
        html = page.content()
        (bronze / "gi_studies_rendered.html").write_text(html, encoding="utf-8")
        page.screenshot(path=str(bronze / "gi_studies_screenshot.png"), full_page=True)
        browser.close()

    discovery = {
        "page_url": GI_STUDIES_URL,
        "discovered_at": utc_now_iso(),
        "api_endpoint": OPTICS_SEARCH_URL,
        "playwright_posts": posts,
        "playwright_responses": responses,
        "notes": (
            "Document list is loaded via Optics Elasticsearch-like POST "
            "Optics_Models_Find_RemoteHostedContentItem/_search filtered on "
            "Properties.processstage (Definitive Planning Phase)."
        ),
    }
    (bronze / "discovery_network.json").write_text(json.dumps(discovery, indent=2), encoding="utf-8")
    return discovery


def fetch_optics_gi_documents() -> list[OpticsDoc]:
    """Paginate Optics index for GI / DPP process-stage documents."""
    docs: list[OpticsDoc] = []
    page_size = 50
    from_ = 0
    total = None
    while True:
        payload = {
            "from": from_,
            "size": page_size,
            "sort": [{"SearchPublishDate$$date": {"order": "desc"}}],
            "query": {
                "filtered": {
                    "filter": {"exists": {"field": "Properties.processstage"}},
                    "query": {"query_string": {"query": "*"}},
                }
            },
        }
        result = _http_json(OPTICS_SEARCH_URL, payload)
        hits = result.get("hits", {}).get("hits", [])
        total = result.get("hits", {}).get("total", 0)
        for h in hits:
            src = h.get("_source") or {}
            props = src.get("Properties") or {}
            title = (src.get("Name$$string") or src.get("SearchTitle$$string") or "").strip()
            filename = (src.get("FileName$$string") or src.get("SearchFilename$$string") or title).strip()
            url = (src.get("SearchHitUrl$$string") or "").strip()
            docs.append(
                OpticsDoc(
                    object_id=str(src.get("ObjectId$$number") or src.get("Id$$string") or ""),
                    title=title,
                    filename=filename,
                    url=url,
                    extension=(src.get("SearchFileExtension$$string") or "").lower(),
                    content_type=src.get("ContentType$$string") or "",
                    study_cycle=_clean_meta(props.get("studycycle")),
                    study_region=_clean_meta(props.get("studygroup")),
                    process_stage=_clean_meta(props.get("processstage")),
                    publish_date=_clean_meta(src.get("SearchPublishDate$$date")),
                    updated_date=_clean_meta(src.get("Updated$$date") or src.get("SearchUpdateDate$$date")),
                    raw=src,
                )
            )
        from_ += page_size
        if not hits or from_ >= int(total or 0):
            break
    return docs


def _clean_meta(val: Any) -> str | None:
    if val is None:
        return None
    s = str(val).strip()
    return s or None


def classify_document(title: str, filename: str) -> tuple[bool, str | None, str | None]:
    """Return (accepted, study_phase, document_type)."""
    text = f"{title} {filename}"
    if EXCLUDE_TITLE_RE.search(text):
        return False, None, None
    if not INCLUDE_TITLE_RE.search(text):
        return False, None, None

    phase = None
    doc_type = None
    low = text.lower()

    if re.search(r"\brestudy\b", low):
        phase = "Restudy"
        doc_type = "Restudy"
    if re.search(r"\baddendum\b", low):
        doc_type = "Addendum" if not doc_type else f"{doc_type};Addendum"
    if re.search(r"network\s+upgrade\s+facilities", low):
        phase = phase or "Phase3"
        doc_type = "Network Upgrade Facilities Study"
    elif re.search(r"\bfacilities\s+study\b", low):
        phase = phase or "FacilitiesStudy"
        doc_type = doc_type or "Facilities Study"

    m = re.search(r"(?:phase|ph)\s*(1|i|2|ii|3|iii)\b", low)
    if m:
        token = m.group(1)
        mapping = {"1": "Phase1", "i": "Phase1", "2": "Phase2", "ii": "Phase2", "3": "Phase3", "iii": "Phase3"}
        phase = phase or mapping[token]
        if not doc_type or doc_type == "Addendum":
            base = {
                "Phase1": "DPP Phase 1 System Impact Study",
                "Phase2": "DPP Phase 2 System Impact Study",
                "Phase3": "DPP Phase 3 Final Study",
            }[mapping[token]]
            doc_type = f"{base};{doc_type}" if doc_type else base

    if re.search(r"system\s+impact|\bsis\b", low) and not doc_type:
        doc_type = "System Impact Study"
    if not doc_type:
        doc_type = "DPP Study"
    if not phase:
        if "restudy" in low:
            phase = "Restudy"
        elif "facilities" in low:
            phase = "FacilitiesStudy"
        else:
            phase = "Unknown"
    return True, phase, doc_type


def parse_report_date(*texts: str) -> tuple[str | None, str | None]:
    """Parse first plausible report date; return (ISO date, source_hint)."""
    for text in texts:
        if not text:
            continue
        # Prefer trailing filename date tokens over publish metadata noise.
        for pattern, fmt in DATE_PATTERNS:
            matches = list(pattern.finditer(text))
            if not matches:
                continue
            # Prefer the last date-like token in titles (often the report stamp).
            for m in reversed(matches):
                raw = m.group(0)
                try:
                    if fmt == "%B %d %Y":
                        raw_norm = f"{m.group(1)} {m.group(2)} {m.group(3)}"
                        dt = datetime.strptime(raw_norm, fmt)
                    elif fmt == "%Y-%m-%d":
                        dt = datetime.strptime(f"{m.group(1)}-{m.group(2)}-{m.group(3)}", fmt)
                    elif fmt == "%m/%d/%Y":
                        dt = datetime.strptime(f"{m.group(1)}/{m.group(2)}/{m.group(3)}", "%m/%d/%Y")
                    elif fmt == "%Y%m%d":
                        dt = datetime.strptime(f"{m.group(1)}{m.group(2)}{m.group(3)}", fmt)
                    elif fmt == "%m%d%Y":
                        dt = datetime.strptime(f"{m.group(1)}{m.group(2)}{m.group(3)}", fmt)
                    elif fmt == "%m%d%y":
                        dt = datetime.strptime(f"{m.group(1)}{m.group(2)}{m.group(3)}", fmt)
                    else:
                        dt = datetime.strptime(raw, fmt)
                except ValueError:
                    continue
                if dt.year < 2010 or dt.year > datetime.now(timezone.utc).year + 1:
                    continue
                return dt.strftime("%Y-%m-%d"), f"regex:{fmt}"
    return None, None


def parse_cover_date(pdf_path: Path, max_pages: int = 3) -> tuple[str | None, str | None]:
    texts: list[str] = []
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages[:max_pages]:
                texts.append(page.extract_text() or "")
    except Exception:  # noqa: BLE001
        try:
            doc = fitz.open(pdf_path)
            for i in range(min(max_pages, doc.page_count)):
                texts.append(doc.load_page(i).get_text("text"))
            doc.close()
        except Exception:  # noqa: BLE001
            return None, None
    joined = "\n".join(texts)
    # Prefer revision-history Final Report dates when present.
    m = re.search(
        r"(?im)(\d{1,2}[/-]\d{1,2}[/-]20\d{2}|\w+\s+\d{1,2},\s*20\d{2}).{0,40}final\s+report"
        r"|final\s+report.{0,40}(\d{1,2}[/-]\d{1,2}[/-]20\d{2}|\w+\s+\d{1,2},\s*20\d{2})",
        joined,
    )
    if m:
        blob = m.group(1) or m.group(2) or m.group(0)
        d, hint = parse_report_date(blob)
        if d:
            return d, f"cover_final:{hint}"
    return parse_report_date(joined)


def build_project_whitelist() -> dict[str, str]:
    """Map uppercase project_id -> project_key using master/crosswalk IDs only."""
    mapping: dict[str, str] = {}
    master = pd.read_parquet(SILVER_DIR / "projects" / "project_master.parquet")
    xw_path = SILVER_DIR / "crosswalks" / "project_crosswalk.parquet"
    if xw_path.exists():
        xw = pd.read_parquet(xw_path)
        for _, row in xw.iterrows():
            pk = str(row.get("project_key") or "")
            for col in ("miso_project_id", "berkeley_project_id"):
                pid = row.get(col)
                if pd.notna(pid) and str(pid).strip():
                    mapping[str(pid).strip().upper()] = pk or mapping.get(str(pid).strip().upper(), "")
    # Fill from silver project files / snapshots source IDs
    for path in [
        SILVER_DIR / "projects" / "miso_all.parquet",
        SILVER_DIR / "projects" / "berkeley_all.parquet",
        SILVER_DIR / "snapshots" / "project_snapshots.parquet",
    ]:
        if not path.exists():
            continue
        df = pd.read_parquet(path)
        cols = [c for c in ("source_project_id", "project_key") if c in df.columns]
        if len(cols) < 2:
            continue
        for _, row in df[cols].drop_duplicates().iterrows():
            pid = str(row["source_project_id"]).strip().upper()
            pk = str(row["project_key"])
            if pid and pid != "NAN":
                mapping.setdefault(pid, pk)
    # Ensure master keys that embed IDs are present
    for pk in master["project_key"].astype(str):
        m = PROJECT_ID_RE.search(pk)
        if m:
            mapping.setdefault(m.group(1).upper(), pk)
    return {k: v for k, v in mapping.items() if k}


def is_miso_hosted(url: str) -> bool:
    u = (url or "").lower()
    return u.startswith("https://cdn.misoenergy.org/") or u.startswith("https://www.misoenergy.org/")


def normalize_cdn_url(url: str) -> str:
    """Percent-encode path spaces/special chars so urllib can fetch CDN links.

    Optics / prior manifests may be single- or double-encoded; fully unquote first.
    """
    if not url:
        return url
    parts = urlsplit(url.strip())
    path = parts.path
    prev = None
    while prev != path:
        prev = path
        path = unquote(path)
    path = quote(path, safe="/")
    return urlunsplit((parts.scheme, parts.netloc, path, parts.query, parts.fragment))


ZIP_MEMBER_NOISE_RE = re.compile(
    r"""(?ix)
    (
        appendix_[a-z0-9]
        | \bcriteria\b
        | methodology
        | assessment\s+practices
        | bpm-?015
        | interconnection-guide
        | power[_\s-]?factor
        | contingenc
        | screening
        | planning_criteria
        | plg[-_]
        | generator-facility-interconnection
    )
    """
)


def zip_member_is_study_pdf(member: str) -> bool:
    """Keep primary SIS/phase/restudy PDFs; drop methodology appendices inside ZIPs."""
    name = Path(member).name
    if not name.lower().endswith(".pdf"):
        return False
    if EXCLUDE_TITLE_RE.search(name) or ZIP_MEMBER_NOISE_RE.search(name):
        return False
    ok, _, _ = classify_document(name, name)
    if ok:
        return True
    return bool(
        re.search(
            r"(?i)(system[\s_\-]?impact|\bsis\b|phase[\s_\-]*[123iii]+|ph[\s_\-]*[123]|restudy|addendum|facilities\s+study)",
            name,
        )
    )



def build_document_manifest(docs: list[OpticsDoc], discovered_at: str) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for doc in docs:
        ok, phase, doc_type = classify_document(doc.title, doc.filename)
        if not ok:
            continue
        url = normalize_cdn_url(doc.url)
        if not is_miso_hosted(url):
            continue
        report_date, date_hint = parse_report_date(doc.filename, doc.title)
        rows.append(
            {
                "document_title": doc.title,
                "document_url": url,
                "study_cycle": doc.study_cycle,
                "study_region": doc.study_region,
                "study_phase": phase,
                "document_type": doc_type,
                "report_date": report_date,
                "report_date_source": date_hint,
                "discovery_method": DISCOVERY_METHOD_API,
                "discovered_at": discovered_at,
                "object_id": doc.object_id,
                "filename": doc.filename,
                "extension": doc.extension,
                "process_stage": doc.process_stage,
                "publish_date_meta": doc.publish_date,
                "download_eligible": bool(report_date and doc.url),
            }
        )
    return pd.DataFrame(rows)


def _safe_name(text: str, limit: int = 120) -> str:
    s = re.sub(r"[^\w.\-]+", "_", text).strip("_")
    return s[:limit] or "document"


def download_eligible_documents(manifest: pd.DataFrame, bronze: Path) -> pd.DataFrame:
    """Download PDFs/ZIPs with explicit URL + report_date; expand ZIPs to PDFs."""
    files_dir = bronze / "files"
    files_dir.mkdir(parents=True, exist_ok=True)
    expanded_rows: list[dict[str, Any]] = []

    eligible = manifest[manifest["download_eligible"] == True].copy()  # noqa: E712
    for _, row in eligible.iterrows():
        url = normalize_cdn_url(str(row["document_url"]))
        ext = str(row.get("extension") or Path(urlsplit(url).path).suffix.lstrip(".") or "bin").lower()
        base = _safe_name(f"{row.get('object_id')}_{row.get('filename') or row['document_title']}")
        dest = files_dir / f"{base}.{ext if ext in ('pdf', 'zip') else 'bin'}"
        try:
            if not dest.exists():
                dest.write_bytes(_http_bytes(url))
        except Exception as exc:  # noqa: BLE001
            expanded_rows.append(
                {**row.to_dict(), "document_url": url, "local_path": None, "download_status": f"failed:{exc}"}
            )
            continue

        if ext == "pdf" or dest.suffix.lower() == ".pdf":
            # Optionally refine date from cover if missing (should already have date).
            report_date = row.get("report_date")
            date_source = row.get("report_date_source")
            if not report_date:
                report_date, date_source = parse_cover_date(dest)
            if not report_date:
                expanded_rows.append(
                    {
                        **row.to_dict(),
                        "local_path": str(dest),
                        "download_status": "downloaded_no_date",
                    }
                )
                continue
            expanded_rows.append(
                {
                    **row.to_dict(),
                    "report_date": report_date,
                    "report_date_source": date_source,
                    "local_path": str(dest),
                    "download_status": "ok",
                    "source_file": dest.name,
                }
            )
            continue

        if ext == "zip" or dest.suffix.lower() == ".zip":
            try:
                with zipfile.ZipFile(dest) as zf:
                    pdf_members = [n for n in zf.namelist() if zip_member_is_study_pdf(n)]
                    if not pdf_members:
                        expanded_rows.append(
                            {**row.to_dict(), "local_path": str(dest), "download_status": "zip_no_study_pdf"}
                        )
                        continue
                    for member in pdf_members:
                        ok, phase, doc_type = classify_document(Path(member).name, Path(member).name)
                        member_date, member_hint = parse_report_date(
                            member, str(row.get("filename")), str(row.get("document_title"))
                        )
                        out_pdf = files_dir / f"{base}__{_safe_name(Path(member).name)}.pdf"
                        if not out_pdf.exists():
                            out_pdf.write_bytes(zf.read(member))
                        report_date = member_date or row.get("report_date")
                        date_source = member_hint or row.get("report_date_source")
                        if not report_date:
                            report_date, date_source = parse_cover_date(out_pdf)
                        if not report_date:
                            expanded_rows.append(
                                {
                                    **row.to_dict(),
                                    "document_title": f"{row['document_title']} :: {Path(member).name}",
                                    "study_phase": phase or row.get("study_phase"),
                                    "document_type": doc_type or row.get("document_type"),
                                    "local_path": str(out_pdf),
                                    "download_status": "extracted_no_date",
                                    "source_file": out_pdf.name,
                                }
                            )
                            continue
                        expanded_rows.append(
                            {
                                **row.to_dict(),
                                "document_title": f"{row['document_title']} :: {Path(member).name}",
                                "study_phase": phase or row.get("study_phase"),
                                "document_type": doc_type or row.get("document_type"),
                                "report_date": report_date,
                                "report_date_source": date_source,
                                "local_path": str(out_pdf),
                                "download_status": "ok_from_zip",
                                "source_file": out_pdf.name,
                                "zip_member": member,
                            }
                        )
            except Exception as exc:  # noqa: BLE001
                expanded_rows.append({**row.to_dict(), "local_path": str(dest), "download_status": f"zip_error:{exc}"})
        else:
            expanded_rows.append({**row.to_dict(), "local_path": str(dest), "download_status": f"skipped_ext:{ext}"})

    # Second pass: title lacked date — try cover for remaining accepted host URLs.
    need_cover = manifest[
        (manifest["download_eligible"] == False)  # noqa: E712
        & manifest["document_url"].notna()
        & manifest["document_url"].astype(str).str.startswith("https://")
    ]
    for _, row in need_cover.iterrows():
        url = normalize_cdn_url(str(row["document_url"]))
        if not is_miso_hosted(url):
            continue
        ext = str(row.get("extension") or "").lower()
        if ext not in ("pdf", "zip"):
            continue
        base = _safe_name(f"{row.get('object_id')}_{row.get('filename') or row['document_title']}")
        dest = files_dir / f"{base}.{ext}"
        try:
            if not dest.exists():
                dest.write_bytes(_http_bytes(url))
        except Exception as exc:  # noqa: BLE001
            expanded_rows.append({**row.to_dict(), "document_url": url, "download_status": f"cover_fetch_failed:{exc}"})
            continue
        if ext == "pdf":
            report_date, date_source = parse_cover_date(dest)
            if report_date:
                expanded_rows.append(
                    {
                        **row.to_dict(),
                        "document_url": url,
                        "report_date": report_date,
                        "report_date_source": date_source,
                        "local_path": str(dest),
                        "download_status": "ok_cover_date",
                        "source_file": dest.name,
                        "download_eligible": True,
                    }
                )
            else:
                # Do not keep undated downloads in extract set.
                expanded_rows.append(
                    {
                        **row.to_dict(),
                        "document_url": url,
                        "local_path": str(dest),
                        "download_status": "fetched_cover_no_date",
                    }
                )
        elif ext == "zip":
            try:
                with zipfile.ZipFile(dest) as zf:
                    for member in [n for n in zf.namelist() if zip_member_is_study_pdf(n)]:
                        out_pdf = files_dir / f"{base}__{_safe_name(Path(member).name)}.pdf"
                        if not out_pdf.exists():
                            out_pdf.write_bytes(zf.read(member))
                        report_date, date_source = parse_cover_date(out_pdf)
                        if not report_date:
                            report_date, date_source = parse_report_date(
                                member, str(row.get("filename")), str(row.get("document_title"))
                            )
                        if not report_date:
                            continue
                        ok, phase, doc_type = classify_document(Path(member).name, Path(member).name)
                        expanded_rows.append(
                            {
                                **row.to_dict(),
                                "document_url": url,
                                "document_title": f"{row['document_title']} :: {Path(member).name}",
                                "study_phase": phase or row.get("study_phase"),
                                "document_type": doc_type or row.get("document_type"),
                                "report_date": report_date,
                                "report_date_source": date_source,
                                "local_path": str(out_pdf),
                                "download_status": "ok_cover_date_zip",
                                "source_file": out_pdf.name,
                                "download_eligible": True,
                                "zip_member": member,
                            }
                        )
            except Exception as exc:  # noqa: BLE001
                expanded_rows.append({**row.to_dict(), "document_url": url, "download_status": f"cover_zip_error:{exc}"})

    return pd.DataFrame(expanded_rows)


def _page_text(pdf_path: Path, page_index: int) -> tuple[str, str]:
    """Return (text, method). OCR only if image-like empty text."""
    text = ""
    method = "pdfplumber"
    try:
        with pdfplumber.open(pdf_path) as pdf:
            if page_index < len(pdf.pages):
                text = pdf.pages[page_index].extract_text() or ""
    except Exception:  # noqa: BLE001
        text = ""
    if text.strip():
        return text, method
    try:
        doc = fitz.open(pdf_path)
        if page_index < doc.page_count:
            text = doc.load_page(page_index).get_text("text") or ""
            method = "pymupdf"
        doc.close()
    except Exception:  # noqa: BLE001
        text = ""
    if text.strip():
        return text, method
    # Optional OCR
    try:
        import pytesseract  # type: ignore
        from PIL import Image

        doc = fitz.open(pdf_path)
        page = doc.load_page(page_index)
        pix = page.get_pixmap(dpi=200)
        img = Image.open(io.BytesIO(pix.tobytes("png")))
        text = pytesseract.image_to_string(img) or ""
        doc.close()
        if text.strip():
            return text, "ocr"
    except Exception:  # noqa: BLE001
        pass
    return "", "empty"


def _parse_money(val: Any) -> float | None:
    if val is None:
        return None
    s = str(val).replace(",", "").replace("$", "").strip()
    if not s or s in {"-", "—", "N/A", "n/a"}:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _normalize_header(cell: Any) -> str:
    return re.sub(r"\s+", " ", str(cell or "").replace("\n", " ")).strip().lower()


def _find_col(headers: list[str], *needles: str) -> int | None:
    for i, h in enumerate(headers):
        if all(n in h for n in needles):
            return i
    for i, h in enumerate(headers):
        if any(n == h or n in h for n in needles):
            return i
    return None


def extract_from_pdf(
    pdf_path: Path,
    meta: dict[str, Any],
    whitelist: dict[str, str],
    max_table_pages: int = 40,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """Extract project events, review rows, and unmatched mentions."""
    events: list[dict[str, Any]] = []
    review: list[dict[str, Any]] = []
    unmatched: list[dict[str, Any]] = []

    try:
        doc = fitz.open(pdf_path)
        n_pages = doc.page_count
        doc.close()
    except Exception as exc:  # noqa: BLE001
        review.append({**meta, "issue": f"open_failed:{exc}", "local_path": str(pdf_path)})
        return events, review, unmatched

    # Per-project accumulators keyed by project_id
    by_project: dict[str, dict[str, Any]] = {}
    group_total_cost: float | None = None
    shared_group_cost: float | None = None

    def ensure(pid: str, page_num: int, method: str) -> dict[str, Any]:
        pid_u = pid.upper()
        if pid_u not in by_project:
            by_project[pid_u] = {
                "project_id": pid_u,
                "project_key": whitelist.get(pid_u),
                "report_date": meta.get("report_date"),
                "study_cycle": meta.get("study_cycle"),
                "study_region": meta.get("study_region"),
                "study_group": meta.get("study_region"),
                "study_phase": meta.get("study_phase"),
                "decision_point": None,
                "capacity_mw": None,
                "eris_mw": None,
                "nris_mw": None,
                "poi": None,
                "transmission_owner": None,
                "network_upgrade_cost": None,
                "interconnection_facility_cost": None,
                "affected_system_cost": None,
                "capacity_reduction_mw": None,
                "withdrawal_mentioned": 0,
                "restudy_flag": 1 if "restudy" in str(meta.get("document_type", "")).lower() or meta.get("study_phase") == "Restudy" else 0,
                "source_url": meta.get("document_url"),
                "source_file": meta.get("source_file") or pdf_path.name,
                "source_page": page_num,
                "extraction_method": method,
                "extraction_confidence": 0.5,
                "project_cost": None,
                "shared_group_cost": None,
                "total_group_cost": None,
                "cost_allocation_known": 0,
                "document_type": meta.get("document_type"),
            }
        return by_project[pid_u]

    # Table pass (executive summary pages)
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page_index, page in enumerate(pdf.pages[:max_table_pages]):
                page_num = page_index + 1
                tables = page.extract_tables() or []
                page_text = page.extract_text() or ""
                if re.search(r"total network upgrades for all projects|total cost of network upgrades for .* group", page_text, re.I):
                    # Capture group total if explicitly stated once; do not assign to projects.
                    money = re.findall(r"\$[\d,]+(?:\.\d+)?", page_text)
                    if money:
                        try:
                            group_total_cost = max(float(m.replace("$", "").replace(",", "")) for m in money)
                        except ValueError:
                            pass

                for table in tables:
                    if not table or len(table) < 2:
                        continue
                    # Merge multi-row headers when first data row lacks project id
                    header_rows = table[0]
                    headers = [_normalize_header(c) for c in header_rows]
                    if table[1] and not PROJECT_ID_RE.search(str(table[1][0] or "")):
                        headers = [_normalize_header(f"{a} {b}") for a, b in zip(header_rows, table[1])]
                        data_rows = table[2:]
                    else:
                        data_rows = table[1:]

                    proj_col = _find_col(headers, "project")
                    if proj_col is None:
                        # sometimes first column is project #
                        if headers and ("project" in headers[0] or headers[0] in {"#", "num", "project #", "project num"}):
                            proj_col = 0
                        elif data_rows and PROJECT_ID_RE.search(str(data_rows[0][0] or "")):
                            proj_col = 0
                    if proj_col is None:
                        continue

                    cap_col = _find_col(headers, "max", "output") or _find_col(headers, "mw") or _find_col(headers, "capacity")
                    to_col = _find_col(headers, "to") or _find_col(headers, "transmission")
                    poi_col = _find_col(headers, "point of interconnection") or _find_col(headers, "poi") or _find_col(headers, "interconnection")
                    svc_col = _find_col(headers, "service")
                    total_cost_col = (
                        _find_col(headers, "total network", "upgrade")
                        or _find_col(headers, "total network")
                        or _find_col(headers, "total cost")
                    )
                    toif_col = _find_col(headers, "toif") or _find_col(headers, "interconnection", "facilities")
                    afs_cols = [i for i, h in enumerate(headers) if "afs" in h or "affected" in h]

                    for raw_row in data_rows:
                        if not raw_row or proj_col >= len(raw_row):
                            continue
                        cell = str(raw_row[proj_col] or "")
                        m = PROJECT_ID_RE.search(cell)
                        if not m:
                            continue
                        pid = m.group(1).upper()
                        if pid not in whitelist:
                            unmatched.append(
                                {
                                    "project_id": pid,
                                    "source_url": meta.get("document_url"),
                                    "source_file": pdf_path.name,
                                    "source_page": page_num,
                                    "context": cell[:200],
                                    "reason": "not_in_project_master_whitelist",
                                }
                            )
                            continue
                        rec = ensure(pid, page_num, "pdfplumber_table")
                        rec["extraction_confidence"] = max(float(rec["extraction_confidence"]), 0.85)
                        if cap_col is not None and cap_col < len(raw_row) and rec["capacity_mw"] is None:
                            rec["capacity_mw"] = _parse_money(raw_row[cap_col])
                        if to_col is not None and to_col < len(raw_row) and not rec["transmission_owner"]:
                            rec["transmission_owner"] = str(raw_row[to_col] or "").replace("\n", " ").strip() or None
                        if poi_col is not None and poi_col < len(raw_row) and not rec["poi"]:
                            rec["poi"] = str(raw_row[poi_col] or "").replace("\n", " ").strip() or None
                        if svc_col is not None and svc_col < len(raw_row):
                            svc = str(raw_row[svc_col] or "").upper()
                            if "ERIS" in svc and rec["eris_mw"] is None and rec["capacity_mw"] is not None:
                                rec["eris_mw"] = rec["capacity_mw"]
                            if "NRIS" in svc and rec["nris_mw"] is None and rec["capacity_mw"] is not None:
                                rec["nris_mw"] = rec["capacity_mw"]
                        # Project-specific costs only from per-project columns — never broadcast group totals.
                        if total_cost_col is not None and total_cost_col < len(raw_row):
                            cost = _parse_money(raw_row[total_cost_col])
                            if cost is not None:
                                rec["network_upgrade_cost"] = cost
                                rec["project_cost"] = cost
                                rec["cost_allocation_known"] = 1
                                rec["extraction_confidence"] = max(float(rec["extraction_confidence"]), 0.9)
                        if toif_col is not None and toif_col < len(raw_row):
                            toif = _parse_money(raw_row[toif_col])
                            if toif is not None:
                                rec["interconnection_facility_cost"] = toif
                        afs_sum = 0.0
                        afs_any = False
                        for ai in afs_cols:
                            if ai < len(raw_row):
                                v = _parse_money(raw_row[ai])
                                if v is not None:
                                    afs_sum += v
                                    afs_any = True
                        if afs_any:
                            rec["affected_system_cost"] = afs_sum
    except Exception as exc:  # noqa: BLE001
        review.append({**meta, "issue": f"table_extract_failed:{exc}", "local_path": str(pdf_path)})

    # Text scan for whitelist IDs + withdrawal / capacity reduction cues (all pages, capped).
    max_scan = min(n_pages, 80)
    for page_index in range(max_scan):
        text, method = _page_text(pdf_path, page_index)
        if not text:
            if page_index < 5:
                review.append(
                    {
                        **meta,
                        "issue": "empty_page_text_possible_scan",
                        "source_page": page_index + 1,
                        "extraction_method": method,
                    }
                )
            continue
        page_num = page_index + 1
        for m in PROJECT_ID_RE.finditer(text):
            pid = m.group(1).upper()
            if pid not in whitelist:
                unmatched.append(
                    {
                        "project_id": pid,
                        "source_url": meta.get("document_url"),
                        "source_file": pdf_path.name,
                        "source_page": page_num,
                        "context": text[max(0, m.start() - 40) : m.end() + 40].replace("\n", " "),
                        "reason": "not_in_project_master_whitelist",
                    }
                )
                continue
            rec = ensure(pid, page_num, method)
            # Per-project summary cost lines
            window = text[m.start() : m.start() + 400]
            if re.search(r"withdrawn|withdrawal", window, re.I):
                rec["withdrawal_mentioned"] = 1
            red = re.search(r"(?:capacity\s+reduction|reduced(?:\s+to)?)\s*[:=]?\s*([\d,.]+)\s*mw", window, re.I)
            if red:
                rec["capacity_reduction_mw"] = _parse_money(red.group(1))
            # "Total Cost Per Project ... $X"
            near = re.search(
                rf"{pid}.{{0,120}}Total Cost Per Project[^\n$]*\$([\d,]+(?:\.\d+)?)",
                text,
                flags=re.I | re.S,
            )
            if near and rec.get("project_cost") is None:
                rec["project_cost"] = _parse_money(near.group(1))
                rec["network_upgrade_cost"] = rec["network_upgrade_cost"] or rec["project_cost"]
                rec["cost_allocation_known"] = 1
                rec["extraction_confidence"] = max(float(rec["extraction_confidence"]), 0.8)
                rec["source_page"] = page_num
                rec["extraction_method"] = method

        if re.search(r"decision point\s*(1|i)\b", text, re.I):
            for rec in by_project.values():
                if rec.get("decision_point") is None:
                    rec["decision_point"] = "DP1"
        if re.search(r"decision point\s*(2|ii)\b", text, re.I):
            for rec in by_project.values():
                rec["decision_point"] = "DP2"

    # Attach group-level cost fields without allocating to each project as project_cost.
    for rec in by_project.values():
        rec["total_group_cost"] = group_total_cost
        rec["shared_group_cost"] = shared_group_cost
        if rec.get("project_cost") is None and rec.get("network_upgrade_cost") is not None:
            rec["project_cost"] = rec["network_upgrade_cost"]
        events.append(rec)

    if not events:
        review.append(
            {
                **meta,
                "issue": "no_whitelist_projects_extracted",
                "local_path": str(pdf_path),
                "pages": n_pages,
            }
        )

    return events, review, unmatched


def validate_events(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    required_ok = (
        df["project_id"].notna()
        & df["report_date"].notna()
        & df["source_url"].notna()
        & df["source_page"].notna()
        & (df["study_phase"].notna() | df["document_type"].notna())
    )
    out = df.loc[required_ok].copy()
    out = out.drop_duplicates(
        subset=["project_id", "report_date", "study_phase", "document_type", "source_page"],
        keep="first",
    )
    return out


def write_coverage_report(
    manifest: pd.DataFrame,
    downloaded: pd.DataFrame,
    events: pd.DataFrame,
    review: pd.DataFrame,
    unmatched: pd.DataFrame,
    path: Path,
) -> None:
    n_manifest = len(manifest)
    n_dated = int(manifest["report_date"].notna().sum()) if n_manifest else 0
    n_dl = int((downloaded.get("download_status", pd.Series(dtype=str)).astype(str).str.startswith("ok")).sum()) if len(downloaded) else 0
    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>DPP Coverage Report</title>
<style>
body{{font-family:Georgia,serif;margin:2rem;background:#f7f4ef;color:#1a1a1a}}
h1{{font-size:1.6rem}} td,th{{padding:.35rem .6rem;border-bottom:1px solid #ddd;text-align:left}}
.stat{{display:inline-block;margin:0 1rem 1rem 0;padding:.6rem 1rem;background:#fff;border:1px solid #ddd}}
</style></head><body>
<h1>MISO DPP Historical Extraction Coverage</h1>
<p>Source: <a href="{GI_STUDIES_URL}">{GI_STUDIES_URL}</a>. Gold merge not performed.</p>
<div class="stat"><b>{n_manifest}</b><br>manifest docs</div>
<div class="stat"><b>{n_dated}</b><br>with title/meta date</div>
<div class="stat"><b>{n_dl}</b><br>downloaded extractable PDFs</div>
<div class="stat"><b>{len(events)}</b><br>valid events</div>
<div class="stat"><b>{events['project_id'].nunique() if len(events) else 0}</b><br>unique projects</div>
<div class="stat"><b>{events['report_date'].nunique() if len(events) else 0}</b><br>unique report dates</div>
<div class="stat"><b>{len(review)}</b><br>review rows</div>
<div class="stat"><b>{len(unmatched)}</b><br>unmatched mentions</div>
<h2>Events by phase</h2>
{events.groupby('study_phase').size().rename('n').reset_index().to_html(index=False) if len(events) else '<p>None</p>'}
<h2>Download status</h2>
{downloaded.groupby('download_status').size().rename('n').reset_index().to_html(index=False) if len(downloaded) and 'download_status' in downloaded.columns else '<p>None</p>'}
</body></html>"""
    path.write_text(html, encoding="utf-8")


def run_miso_dpp_ingest(*, skip_playwright: bool = False) -> dict[str, Any]:
    ensure_enrichment_dirs()
    bronze = bronze_dir(SOURCE_ID)
    reports = ENRICHMENT_REPORTS
    reports.mkdir(parents=True, exist_ok=True)
    discovered_at = utc_now_iso()

    discovery = {}
    if not skip_playwright:
        print("Playwright discovery…", flush=True)
        discovery = discover_with_playwright(bronze)
    else:
        discovery = {"skipped": True, "api_endpoint": OPTICS_SEARCH_URL}

    print("Fetching Optics GI document index…", flush=True)
    optics_docs = fetch_optics_gi_documents()
    write_bronze_text(
        SOURCE_ID,
        "optics_gi_index.json",
        json.dumps(
            [
                {
                    "object_id": d.object_id,
                    "title": d.title,
                    "filename": d.filename,
                    "url": d.url,
                    "extension": d.extension,
                    "study_cycle": d.study_cycle,
                    "study_region": d.study_region,
                    "process_stage": d.process_stage,
                }
                for d in optics_docs
            ],
            indent=2,
        ),
        overwrite=True,
    )
    print(f"Optics docs with processstage: {len(optics_docs)}", flush=True)

    manifest = build_document_manifest(optics_docs, discovered_at)
    # Pre-download manifest (plan item 6)
    manifest_path = bronze / "dpp_document_manifest.csv"
    manifest.to_csv(manifest_path, index=False)
    manifest.to_csv(reports / "miso_dpp_document_manifest.csv", index=False)
    manifest.to_csv(bronze / "miso_dpp_document_manifest.csv", index=False)
    print(
        f"Manifest accepted docs: {len(manifest)}; dated/eligible: "
        f"{int(manifest['download_eligible'].sum()) if len(manifest) else 0}",
        flush=True,
    )

    print("Downloading dated documents…", flush=True)
    downloaded = download_eligible_documents(manifest, bronze)
    downloaded.to_csv(bronze / "dpp_download_inventory.csv", index=False)
    print(f"Download inventory rows: {len(downloaded)}", flush=True)

    whitelist = build_project_whitelist()
    print(f"Project ID whitelist size: {len(whitelist)}", flush=True)

    all_events: list[dict[str, Any]] = []
    all_review: list[dict[str, Any]] = []
    all_unmatched: list[dict[str, Any]] = []

    extractable = downloaded[downloaded["download_status"].astype(str).str.startswith("ok")].copy() if len(downloaded) else downloaded
    for _, row in extractable.iterrows():
        local = row.get("local_path")
        if not local or not Path(local).exists():
            continue
        if not str(local).lower().endswith(".pdf"):
            continue
        print(f"Extracting {Path(local).name}…", flush=True)
        ev, rev, un = extract_from_pdf(Path(local), row.to_dict(), whitelist)
        all_events.extend(ev)
        all_review.extend(rev)
        all_unmatched.extend(un)

    events_df = pd.DataFrame(all_events)
    review_df = pd.DataFrame(all_review)
    unmatched_df = pd.DataFrame(all_unmatched)
    if len(unmatched_df):
        unmatched_df = unmatched_df.drop_duplicates(
            subset=[c for c in ["project_id", "source_file", "source_page", "reason"] if c in unmatched_df.columns]
        )

    events_df = validate_events(events_df) if len(events_df) else events_df

    # Flag low-confidence extractions for human review (do not drop from events).
    if len(events_df) and "extraction_confidence" in events_df.columns:
        low = events_df[events_df["extraction_confidence"].fillna(0) < 0.75].copy()
        if len(low):
            low["issue"] = "low_extraction_confidence"
            all_review.extend(low.to_dict(orient="records"))
            review_df = pd.DataFrame(all_review)

    # Map to silver miso_dpp_events with mandatory metadata (historical schema + requested fields).
    if len(events_df):
        silver = events_df.copy()
        silver["source_project_id"] = silver["project_id"]
        silver["event_date"] = pd.to_datetime(silver["report_date"], errors="coerce")
        silver["effective_date"] = silver["event_date"]
        silver["available_date"] = silver["event_date"]
        silver["upgrade_cost_usd"] = silver.get("network_upgrade_cost")
        silver["upgrade_cost_per_mw"] = None
        if "capacity_mw" in silver.columns and "network_upgrade_cost" in silver.columns:
            with pd.option_context("mode.chained_assignment", None):
                silver["upgrade_cost_per_mw"] = silver.apply(
                    lambda r: (r["network_upgrade_cost"] / r["capacity_mw"])
                    if pd.notna(r.get("network_upgrade_cost")) and pd.notna(r.get("capacity_mw")) and r.get("capacity_mw")
                    else None,
                    axis=1,
                )
        silver["phase"] = silver["study_phase"]
        silver["source_pdf_url"] = silver["source_url"]
        silver["source_page_ref"] = silver["source_page"].astype(str)
        silver["geographic_key"] = silver.get("poi")
        silver = attach_metadata(
            silver,
            source_name="MISO DPP GI Studies",
            source_url=GI_STUDIES_URL,
            retrieved_at=discovered_at,
            match_method="project_id_whitelist",
            match_confidence=0.9,
            entity_key_col="project_key",
            geographic_key_col="geographic_key",
        )
        # Prefer row-level confidence when present
        if "extraction_confidence" in silver.columns:
            silver["match_confidence"] = silver["extraction_confidence"]
    else:
        silver = pd.DataFrame(
            columns=[
                "effective_date",
                "available_date",
                "source_name",
                "source_url",
                "retrieved_at",
                "entity_key",
                "geographic_key",
                "match_method",
                "match_confidence",
                "project_key",
                "source_project_id",
                "project_id",
                "report_date",
                "study_cycle",
                "study_region",
                "study_group",
                "study_phase",
                "phase",
                "event_date",
                "decision_point",
                "capacity_mw",
                "eris_mw",
                "nris_mw",
                "poi",
                "transmission_owner",
                "network_upgrade_cost",
                "interconnection_facility_cost",
                "affected_system_cost",
                "capacity_reduction_mw",
                "withdrawal_mentioned",
                "restudy_flag",
                "source_file",
                "source_page",
                "extraction_method",
                "extraction_confidence",
                "project_cost",
                "shared_group_cost",
                "total_group_cost",
                "cost_allocation_known",
                "document_type",
                "source_pdf_url",
                "source_page_ref",
                "upgrade_cost_usd",
                "upgrade_cost_per_mw",
            ]
        )

    out_parquet = SILVER_ENRICHMENT / "miso_dpp_events.parquet"
    silver.to_parquet(out_parquet, index=False)
    # Keep study_events as historical alias of validated DPP events (not queue copy).
    silver.to_parquet(SILVER_ENRICHMENT / "study_events.parquet", index=False)

    events_df.to_csv(reports / "miso_dpp_events.csv", index=False)
    review_df.to_csv(reports / "dpp_extraction_review.csv", index=False)
    unmatched_df.to_csv(reports / "dpp_unmatched_project_mentions.csv", index=False)
    write_coverage_report(
        manifest,
        downloaded,
        events_df,
        review_df,
        unmatched_df,
        reports / "dpp_coverage_report.html",
    )

    summary = {
        "discovered_at": discovered_at,
        "optics_docs": len(optics_docs),
        "manifest_docs": len(manifest),
        "download_ok": int(extractable.shape[0]) if len(downloaded) else 0,
        "events": len(events_df),
        "unique_projects": int(events_df["project_id"].nunique()) if len(events_df) else 0,
        "unique_report_dates": int(events_df["report_date"].nunique()) if len(events_df) else 0,
        "review_rows": len(review_df),
        "unmatched_rows": len(unmatched_df),
        "gold_merged": False,
        "discovery_api": discovery.get("api_endpoint", OPTICS_SEARCH_URL),
    }
    (reports / "dpp_ingest_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return summary


if __name__ == "__main__":
    run_miso_dpp_ingest()
