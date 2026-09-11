"""Platinum 4 — tagged retrieval and gpt-4.1 composition for the mitigation bot.

Not a contest model. Consumes Platinum 3 risk cards and BPM-015 r33
procedure units. Does not unseal 2024 test. Chat model is gpt-4.1 only.
"""

from src.modeling.platinum4.compose import PINNED_MODEL, compose, plan_query
from src.modeling.platinum4.gold_stack import attach_gold_stack, load_full_stack_input
from src.modeling.platinum4.pipeline import run_turn, run_thread
from src.modeling.platinum4.retrieve import retrieve_for_card, write_sample_packets
from src.modeling.platinum4.search import retrieve_for_query

__all__ = [
    "PINNED_MODEL",
    "compose",
    "plan_query",
    "retrieve_for_card",
    "retrieve_for_query",
    "run_turn",
    "run_thread",
    "write_sample_packets",
    "load_full_stack_input",
]
