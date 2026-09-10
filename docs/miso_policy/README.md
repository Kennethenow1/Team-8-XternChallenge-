# MISO BPM-015 — Generation Interconnection (policy pack)

Official MISO GI business practices, labeled and extracted for later AI search / RAG.
**Not** a model input. **Not** the tariff (Attachment X still controls if they conflict).

Retrieved **2026-09-10T13:10:48Z** from [MISO Business Practice Manuals](https://www.misoenergy.org/legal/rules-manuals-and-agreements/business-practice-manuals/).

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

`index/` is the tagged JSON pack. Platinum 4 (`retrieve_for_query`) turns a Platinum 3 card and/or a question into a bot packet; gpt-4.1 writes the note. Notebook: `platinum4/01_bot_packets.ipynb`.

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
