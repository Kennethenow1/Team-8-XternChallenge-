"""BPM dialect pack: terms, heading order, sample returns. Pass 1 of gpt-4.1 receives this pack."""

from __future__ import annotations

from src.modeling.platinum4.policy_index import INDEX_DIR

DIALECT_DIR = INDEX_DIR / "dialect"
DIALECTS = ("auto", "short", "standard", "long", "citation_brief", "bpm_register")
SHAPES = ("short", "standard", "long", "citation_brief", "diagram")
SHAPE_TO_SAMPLE = {
    "short": "short_reply.md",
    "standard": "standard.md",
    "long": "bpm_register.md",
    "citation_brief": "citation_brief.md",
    "diagram": "bpm_register.md",
}

HEADING_ORDER_BPM = (
    "# Interconnection procedure note",
    "## Situation",
    "## Workflow",
    "## Procedure map",
    "## Stakeholders",
    "## Citations",
    "## Gaps",
    "## Must not claim",
)

BANNED_PHRASES = (
    "basically",
    "the bottom line",
    "in a nutshell",
    "key takeaway",
    "in our experience",
    "developers often",
    "ferc-compliant",
    "step-up failure",
    "2024 test",
    "will slip",
)

OPENER_BANS = ("so ", "look ", "importantly ", "note that ")


def load_file(name: str) -> str:
    path = DIALECT_DIR / name
    return path.read_text(encoding="utf-8") if path.exists() else ""


def dialect_pack() -> str:
    parts = [
        load_file("TERMS.md"),
        "\n\n# Sample: bpm_register\n\n",
        load_file("bpm_register.md"),
        "\n\n# Sample: standard\n\n",
        load_file("standard.md"),
        "\n\n# Sample: short_reply\n\n",
        load_file("short_reply.md"),
        "\n\n# Sample: citation_brief\n\n",
        load_file("citation_brief.md"),
        "\n\n# Sample: zero hits\n\n",
        load_file("zero_hits.md"),
    ]
    return "".join(parts)


def writer_pack(shape: str) -> str:
    """TERMS plus one sample. Writer does not need the full four-sample pack."""
    sample = SHAPE_TO_SAMPLE.get(shape, "standard.md")
    return load_file("TERMS.md") + "\n\n# Sample for this turn\n\n" + load_file(sample)


def normalize_shape(shape: str | None, dialect: str | None = None) -> str:
    s = (shape or "").strip().lower()
    if s in SHAPES:
        return s
    d = (dialect or "").strip().lower()
    if d in {"bpm_register", "long"}:
        return "long"
    if d in SHAPES:
        return d
    if d == "citation_brief":
        return "citation_brief"
    return "standard"


def sample_zero_hits() -> str:
    return load_file("zero_hits.md").strip() + "\n"


def sample_bpm_register() -> str:
    return load_file("bpm_register.md").strip() + "\n"


def sample_citation_brief() -> str:
    return load_file("citation_brief.md").strip() + "\n"
