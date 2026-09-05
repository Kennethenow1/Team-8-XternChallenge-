"""Bounded GDELT news ingest → news_events (MISO states + energy themes)."""

from __future__ import annotations

import gzip
import io
import json
import re
import time
import zipfile
from datetime import datetime
from typing import Any
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pandas as pd

from src.enrichment.registry import (
    ENRICHMENT_REPORTS,
    SILVER_ENRICHMENT,
    attach_metadata,
    bronze_dir,
    empty_enrichment_frame,
    ensure_enrichment_dirs,
    utc_now_iso,
    write_bronze_bytes,
    write_bronze_text,
)

SOURCE_ID = "gdelt_news"
GKG_MASTER = "http://data.gdeltproject.org/gdeltv2/masterfilelist.txt"
DOC_API = "https://api.gdeltproject.org/api/v2/doc/doc"

MISO_STATES = {
    "AR",
    "IA",
    "IL",
    "IN",
    "KY",
    "LA",
    "MI",
    "MN",
    "MO",
    "MS",
    "MT",
    "ND",
    "OH",
    "SD",
    "TX",
    "WI",
}
# GDELT ADM1 codes like USWI
MISO_ADM1 = {f"US{st}" for st in MISO_STATES}

ENERGY_THEME_RE = re.compile(
    r"(ENV_SOLAR|ENV_WIND|POWER_|ELEC|ENERGY|INFRASTRUCTURE|WB_2005_ELECTRICITY|"
    r"RENEWABLE|TRANSMISSION|UTILIT|PROTEST|PERMIT)",
    re.I,
)
KEYWORD_RE = re.compile(
    r"(power plant|interconnection|solar|wind|transmission|electric|utility|permit|protest)",
    re.I,
)

# Hard row budget after filtering
DEFAULT_ROW_BUDGET = 75000

_NEWS_EXTRA = [
    "news_event_id",
    "project_id",
    "developer_id",
    "published_at",
    "source_domain",
    "article_title",
    "article_url",
    "event_type",
    "sentiment_score",
    "relevance_score",
    "location_match_score",
    "entity_match_score",
    "duplicate_group_id",
    "extraction_confidence",
    "state_code",
    "county_fips",
]


def _http_get(url: str, timeout: int = 120, retries: int = 3) -> bytes | None:
    for attempt in range(retries):
        try:
            req = Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; Team8-MISO-Enrichment/1.0)"})
            with urlopen(req, timeout=timeout) as resp:
                return resp.read()
        except HTTPError as exc:
            if exc.code == 429 and attempt < retries - 1:
                time.sleep(5 * (attempt + 1))
                continue
            print(f"  gdelt HTTP {exc.code}: {url[:120]}")
            return None
        except Exception as exc:  # noqa: BLE001
            if attempt < retries - 1:
                time.sleep(2)
                continue
            print(f"  gdelt download failed: {exc}")
            return None
    return None


def _sample_gkg_urls(master_text: str, year_start: int = 2020, year_end: int = 2026) -> list[str]:
    """Pick ~monthly GKG files from the master list within panel years."""
    urls: list[str] = []
    seen_months: set[str] = set()
    for line in master_text.splitlines():
        parts = line.strip().split()
        if len(parts) < 3:
            continue
        url = parts[-1]
        if ".gkg.csv" not in url.lower():
            continue
        m = re.search(r"/(\d{14})\.gkg\.csv", url)
        if not m:
            continue
        stamp = m.group(1)
        year = int(stamp[:4])
        if year < year_start or year > year_end:
            continue
        # Prefer ~12:00 UTC files on the 1st and 15th of each month
        day = stamp[6:8]
        hour = stamp[8:10]
        month_key = stamp[:6]
        if day not in {"01", "15"}:
            continue
        if hour not in {"000000"[:2], "12"} and hour not in {"00", "12"}:
            # stamp is YYYYMMDDHHMMSS — hour is chars 8-9
            pass
        hh = stamp[8:10]
        if hh not in {"00", "12"}:
            continue
        slot = f"{month_key}-{day}-{hh}"
        if slot in seen_months:
            continue
        seen_months.add(slot)
        urls.append(url)
    # Cap number of files (~2 per month * 12 * 7 years ≈ 168); keep first N
    return urls[:160]


def _parse_tone(v2tone: str | None) -> float | None:
    if not v2tone or pd.isna(v2tone):
        return None
    try:
        return float(str(v2tone).split(",")[0])
    except Exception:  # noqa: BLE001
        return None


def _states_from_v2locations(loc: str | None) -> list[str]:
    if not loc:
        return []
    found: list[str] = []
    for part in str(loc).split(";"):
        bits = part.split("#")
        if len(bits) < 4:
            continue
        adm1 = bits[3].strip().upper()
        if adm1 in MISO_ADM1:
            found.append(adm1[-2:])
        elif bits[2].strip().upper() == "US":
            # sometimes ADM1 empty; try name
            name = bits[1].upper()
            for st in MISO_STATES:
                if f", {st}" in name or name.endswith(f" {st}"):
                    found.append(st)
    return list(dict.fromkeys(found))


def _event_type_from_themes(themes: str | None) -> str:
    t = themes or ""
    if re.search(r"PROTEST|STRIKE|DEMONST", t, re.I):
        return "opposition"
    if re.search(r"PERMIT|REGULATION|LEGISL", t, re.I):
        return "permit"
    if re.search(r"ENV_SOLAR|SOLAR", t, re.I):
        return "solar"
    if re.search(r"ENV_WIND|WIND", t, re.I):
        return "wind"
    if re.search(r"TRANSMISSION|POWER_|ELEC", t, re.I):
        return "grid"
    return "energy_other"


def _ingest_gkg_file(raw: bytes, fname: str) -> list[dict[str, Any]]:
    # GKG may be zip or plain csv
    text: str
    if fname.endswith(".zip") or raw[:2] == b"PK":
        with zipfile.ZipFile(io.BytesIO(raw)) as zf:
            member = zf.namelist()[0]
            text = zf.read(member).decode("utf-8", errors="replace")
    elif raw[:2] == b"\x1f\x8b":
        text = gzip.decompress(raw).decode("utf-8", errors="replace")
    else:
        text = raw.decode("utf-8", errors="replace")

    rows: list[dict[str, Any]] = []
    for line in text.splitlines():
        if not line.strip():
            continue
        cols = line.split("\t")
        if len(cols) < 16:
            continue
        # GKG 2.0: 0=id, 1=date, 3=domain, 4=url, 7=themes, 9=locations? — verify indices
        # Standard: DATE=1, SourceCommonName=3, DocumentIdentifier=4, Themes=7, V2Themes=8,
        # Locations=9, V2Locations=10, V2Tone=15
        gkg_id = cols[0]
        date_raw = cols[1]
        domain = cols[3] if len(cols) > 3 else None
        url = cols[4] if len(cols) > 4 else None
        themes = cols[7] if len(cols) > 7 else ""
        v2themes = cols[8] if len(cols) > 8 else ""
        v2loc = cols[10] if len(cols) > 10 else ""
        v2tone = cols[15] if len(cols) > 15 else ""
        theme_blob = f"{themes} {v2themes}"
        if not ENERGY_THEME_RE.search(theme_blob) and not KEYWORD_RE.search(theme_blob):
            # also check URL path lightly
            if not KEYWORD_RE.search(url or ""):
                continue
        states = _states_from_v2locations(v2loc)
        if not states:
            continue
        try:
            # DATE is YYYYMMDDHHMMSS
            published = datetime.strptime(date_raw[:14], "%Y%m%d%H%M%S")
        # store tz-naive UTC wall time for PIT joins
        published = pd.Timestamp(published)
        except Exception:  # noqa: BLE001
            continue
        tone = _parse_tone(v2tone)
        for st in states:
            rows.append(
                {
                    "news_event_id": f"{gkg_id}:{st}",
                    "project_id": None,
                    "developer_id": None,
                    "published_at": pd.Timestamp(published),
                    "source_domain": domain,
                    "article_title": None,
                    "article_url": url,
                    "event_type": _event_type_from_themes(theme_blob),
                    "sentiment_score": tone,
                    "relevance_score": 0.6,
                    "location_match_score": 0.8,
                    "entity_match_score": 0.0,
                    "duplicate_group_id": gkg_id,
                    "extraction_confidence": 0.7,
                    "state_code": st,
                    "county_fips": None,
                }
            )
    return rows


def _ingest_doc_api(row_budget: int) -> list[dict[str, Any]]:
    """Fallback: DOC ArtList queries by state + energy keywords, quarterly windows."""
    rows: list[dict[str, Any]] = []
    queries = [
        "(solar OR wind OR interconnection OR transmission OR \"power plant\")",
    ]
    # Quarterly windows 2020–2026
    windows: list[tuple[str, str]] = []
    for year in range(2020, 2027):
        for m0, m1 in ((1, 3), (4, 6), (7, 9), (10, 12)):
            start = f"{year}{m0:02d}01000000"
            end_m = m1
            end_d = 28 if end_m == 2 else 30 if end_m in {4, 6, 9, 11} else 31
            end = f"{year}{end_m:02d}{end_d:02d}235959"
            windows.append((start, end))

    for st in sorted(MISO_STATES):
        for qbase in queries:
            for start, end in windows:
                if len(rows) >= row_budget:
                    return rows
                q = f'{qbase} sourcecountry:US {st}'
                params = (
                    f"query={urllib_quote(q)}&mode=ArtList&format=json&maxrecords=250"
                    f"&startdatetime={start}&enddatetime={end}&sort=DateDesc"
                )
                url = f"{DOC_API}?{params}"
                raw = _http_get(url, timeout=90)
                time.sleep(1.2)
                if raw is None:
                    continue
                try:
                    payload = json.loads(raw.decode("utf-8", errors="replace"))
                except Exception:  # noqa: BLE001
                    continue
                arts = payload.get("articles") or []
                for a in arts:
                    if len(rows) >= row_budget:
                        return rows
                    title = a.get("title") or ""
                    if not KEYWORD_RE.search(title) and not KEYWORD_RE.search(a.get("url") or ""):
                        # keep geo-filtered energy query hits anyway
                        pass
                    seendate = a.get("seendate") or a.get("seenDate")
                    try:
                        published = pd.to_datetime(seendate, errors="coerce")
                    except Exception:  # noqa: BLE001
                        published = pd.NaT
                    if pd.isna(published):
                        continue
                    tone = a.get("tone")
                    try:
                        tone_f = float(str(tone).split(",")[0]) if tone is not None else None
                    except Exception:  # noqa: BLE001
                        tone_f = None
                    rows.append(
                        {
                            "news_event_id": f"doc:{st}:{a.get('url')}",
                            "project_id": None,
                            "developer_id": None,
                            "published_at": published,
                            "source_domain": a.get("domain"),
                            "article_title": title[:500] if title else None,
                            "article_url": a.get("url"),
                            "event_type": _event_type_from_themes(title),
                            "sentiment_score": tone_f,
                            "relevance_score": 0.5,
                            "location_match_score": 0.7,
                            "entity_match_score": 0.0,
                            "duplicate_group_id": a.get("url"),
                            "extraction_confidence": 0.55,
                            "state_code": st,
                            "county_fips": None,
                        }
                    )
                print(f"  gdelt DOC {st} {start[:6]} arts={len(arts)} total={len(rows)}")
    return rows


def urllib_quote(s: str) -> str:
    from urllib.parse import quote

    return quote(s)


def run_gdelt_ingest(*, row_budget: int = DEFAULT_ROW_BUDGET) -> pd.DataFrame:
    ensure_enrichment_dirs()
    retrieved_at = utc_now_iso()
    bronze = bronze_dir(SOURCE_ID)
    all_rows: list[dict[str, Any]] = []
    mode = "none"

    master = _http_get(GKG_MASTER, timeout=180)
    if master:
        write_bronze_bytes(SOURCE_ID, "masterfilelist.txt", master, overwrite=True)
        urls = _sample_gkg_urls(master.decode("utf-8", errors="replace"))
        write_bronze_text(
            SOURCE_ID,
            "gkg_sample_urls.txt",
            "\n".join(urls) + "\n",
            overwrite=True,
        )
        print(f"  gdelt GKG sample files={len(urls)}")
        for i, url in enumerate(urls):
            if len(all_rows) >= row_budget:
                break
            raw = _http_get(url, timeout=180)
            if raw is None:
                continue
            fname = url.rstrip("/").split("/")[-1]
            write_bronze_bytes(SOURCE_ID, f"gkg_{fname}", raw, overwrite=True)
            try:
                part = _ingest_gkg_file(raw, fname)
            except Exception as exc:  # noqa: BLE001
                write_bronze_text(SOURCE_ID, f"parse_error_{fname}.txt", str(exc), overwrite=True)
                continue
            all_rows.extend(part)
            mode = "gkg_sample"
            if i % 10 == 0:
                print(f"  gdelt GKG file={i}/{len(urls)} rows={len(all_rows)}")
            if len(all_rows) >= row_budget:
                all_rows = all_rows[:row_budget]
                break

    if len(all_rows) < 500:
        print("  gdelt GKG thin — trying DOC API fallback…")
        doc_rows = _ingest_doc_api(row_budget - len(all_rows))
        all_rows.extend(doc_rows)
        mode = "gkg+doc" if all_rows and mode == "gkg_sample" else ("doc_api" if doc_rows else mode)

    if not all_rows:
        write_bronze_text(
            SOURCE_ID,
            "NOTE.txt",
            "GDELT ingest returned no rows (API/GKG blocked or empty filter).\n",
            overwrite=True,
        )
        df = empty_enrichment_frame(_NEWS_EXTRA)
        df.to_parquet(SILVER_ENRICHMENT / "news_events.parquet", index=False)
        summary = {"news_events": 0, "mode": mode, "retrieved_at": retrieved_at}
        (ENRICHMENT_REPORTS / "gdelt_ingest_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
        print("news_events empty typed written")
        return df

    events = pd.DataFrame(all_rows)
    events = events.drop_duplicates(subset=["news_event_id"], keep="first")
    events["available_date"] = pd.to_datetime(events["published_at"], errors="coerce")
    events["effective_date"] = events["available_date"]
    events["entity_key"] = events["news_event_id"]
    events["geographic_key"] = events["state_code"]
    events = attach_metadata(
        events,
        source_name="GDELT GKG/DOC",
        source_url="https://www.gdeltproject.org/",
        retrieved_at=retrieved_at,
        match_method="state_geo_theme_filter",
        match_confidence=0.65,
        entity_key_col="entity_key",
        geographic_key_col="geographic_key",
    )
    events.to_parquet(SILVER_ENRICHMENT / "news_events.parquet", index=False)
    inv = pd.DataFrame(
        {
            "mode": [mode],
            "rows": [len(events)],
            "states": [int(events["state_code"].nunique())],
            "with_tone": [int(events["sentiment_score"].notna().sum())],
        }
    )
    inv.to_csv(bronze / "gdelt_ingest_inventory.csv", index=False)
    summary = {
        "news_events": int(len(events)),
        "mode": mode,
        "unique_states": int(events["state_code"].nunique()),
        "with_sentiment": int(events["sentiment_score"].notna().sum()),
        "retrieved_at": retrieved_at,
    }
    (ENRICHMENT_REPORTS / "gdelt_ingest_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return events


if __name__ == "__main__":
    run_gdelt_ingest()
