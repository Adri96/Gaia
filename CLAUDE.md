# Gaia: rules for coding agents

Gaia values ecosystem services in euros. Read `PROJECT_DEFINITION.md`
("Core Valuation Principles") before changing any value, case file,
test or document.

## Non-negotiable valuation rules

1. Ecosystem services are a large economic asset; Gaia exists to make that
   visible.
2. Every agent in every case always carries a positive euro value, under
   any input, preset or flag. An agent at €0 is a defect: fix it, never
   document it as an exception. If you cannot satisfy this rule, say so
   plainly; do not weaken the validation or the tests.
3. Avoid double counting only through the service ledger (each final
   service counted once, one owner; overlaps booked with `net_of`), never
   by zeroing an agent.
4. Without stated-preference (WTP) evidence, value what people consume:
   production functions, primary production → food web → fish and other
   consumables → market prices (`gaia/production.py`).
5. Keep the primary productivity of foundation ecosystems (e.g.
   *Posidonia oceanica*) visible in outputs, with the NPP → € chain shown.
6. Every number is sourced and verified, or explicitly flagged.

## Working rules

- One commit per sub-step. When golden files (`tests/golden/`) change,
  regenerate them in the commit that changes them
  (`python3 scripts/regen_golden.py`) and justify the numbers, before and
  after, in the commit message. Keep `scripts/gen_readme_examples.py
  --check`, `ruff check gaia tests scripts` and `mypy` clean; no xfails.
- Verify every citation by fetching it (Crossref, the DOI resolver, the
  publisher's abstract or full text). Never type a DOI, an author or a
  number from memory. If you cannot verify it, flag it (low confidence or
  placeholder) and say what you read.
- Never send personal data (names, e-mail addresses, the user's identity)
  to external services: no `mailto=` or `email=` parameters in API
  requests, and none in files.
- Never merge pull requests; the owner merges.
- Do not bump the version unless the owner asks.
