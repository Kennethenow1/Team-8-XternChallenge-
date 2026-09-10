"""Typed error codes for Platinum 4 retrieval and composition."""

from __future__ import annotations


class BotError(Exception):
    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(message)


EMPTY_QUERY = "empty_query"
INDEX_MISSING = "index_missing"
ZERO_HITS = "zero_hits"
STUB_ONLY = "stub_only"
OPENAI_MISSING_KEY = "openai_missing_key"
OPENAI_AUTH = "openai_auth"
OPENAI_RATE_LIMIT = "openai_rate_limit"
OPENAI_TIMEOUT = "openai_timeout"
OPENAI_BAD_MODEL = "openai_bad_model"
CRITIC_FAILED = "critic_failed"
INVENTED_CITE = "invented_cite"
PACKET_TOO_LARGE = "packet_too_large"
TEST_SEALED = "test_sealed"
MERMAID_INVALID = "mermaid_invalid"
