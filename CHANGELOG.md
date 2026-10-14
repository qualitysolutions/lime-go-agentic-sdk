# Changelog

All notable changes to `qls-lime-go-agentic` are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions are
CalVer `YY.M.D[.N]`.

## [26.10.14] - 2026-10-14 (unreleased, not on PyPI)

### Changed
- Verified read-only against the live API: every list/get resource parses the real
  responses. `tests/test_live_fixtures.py` runs on recorded, sanitized payloads
  (`tests/fixtures/live/`, produced by `scripts/record_fixtures.py`).
- `Resource.etag` falls back to `"<id>:<revision>"` from `meta.revision`, the ETag format the
  API uses, so list items can be passed as `if_match=` without a `get()` first.
  `MissingETagError` now only applies to resources without a revision (`owners`).

### Fixed
- `Config(scopes="a b")` sent one scope per character; a space-separated string is now split.

## [26.10.10] - 2026-10-10 (unreleased, not on PyPI)

### Added
- First version, written against the Lime Go Agentic OpenAPI spec v1.0.0 (pilot).
- Sync (`LimeGoClient`) and async (`AsyncLimeGoClient`) clients covering all 74 operations:
  companies, contacts, deals, activities and tasks (list/iter/get/create/upsert/update/
  delete), to-many relationship endpoints, reference data (owners, stages, tags, activity
  types, custom-field definitions) and the change feed.
- OAuth2 client-credentials token cache with refresh before expiry and a single retry on
  401; optional scope restriction.
- Automatic `Idempotency-Key` on every write, stable across retries; ETag/`If-Match`
  support with `MissingETagError` for list items.
- Typed write models mirroring the spec constraints; pydantic mypy plugin with typed
  constructors.
- `tests/test_spec_conformance.py`: models, filters, scopes and endpoint coverage are
  checked against the vendored `spec/openapi.json`.
