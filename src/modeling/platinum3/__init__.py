"""Platinum 3 — risk-card peripherals for a mitigation bot.

Not a new contest model. Assembles Electrum P(quit), Platinum 2 pile
context, gold flags, and scenario re-scores into a ChatGPT-safe JSON card.
"""

from src.modeling.platinum3.cards import build_risk_cards, write_risk_card_bundle
from src.modeling.platinum3.schema import SCHEMA_VERSION

__all__ = ["SCHEMA_VERSION", "build_risk_cards", "write_risk_card_bundle"]
