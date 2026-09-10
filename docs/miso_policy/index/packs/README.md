# Bot packet assembly

`retrieve_for_card(card)` in `src/modeling/platinum4/retrieve.py` is catalog-route only.

`retrieve_for_query(query)` in `src/modeling/platinum4/search.py` unions catalog route, lexicon, seed lookup, inverted maps, phrase match, and BM25, then fuses. `search_trace` logs algorithms and directives.

Composer is gpt-4.1 only (`src/modeling/platinum4/compose.py`). Compliance is `not_determined`.

Index **r33 clean only**. r32/redlines stay under `docs/miso_policy/pdfs/` for humans.
