# qls-lime-go-agentic

Python SDK for the **Lime Go Agentic public CRM API** (JSON:API, OAuth2 client
credentials). Sync and async clients, fully typed request/response models (pydantic v2,
`mypy --strict` clean), automatic token handling, idempotent retries, ETag concurrency,
pagination and the change feed.

> **Status: early release.** Built against the API's OpenAPI spec v1.0.0, which Lime marks
> as an *unpublished v1 pilot*, and verified against the live API on 2026-10-14 (reads, plus
> task/activity writes). Not an official Lime product. See
> [docs/OPEN_QUESTIONS.md](docs/OPEN_QUESTIONS.md) for what was verified and the spec gaps
> still to confirm with Lime.

## Install

```bash
pip install qls-lime-go-agentic
```

The distribution is `qls-lime-go-agentic`; the import package is `lime_go_agentic`.
Requires Python 3.10+. Depends on `httpx` and `pydantic>=2`.

## Quick start

```python
from decimal import Decimal
from lime_go_agentic import LimeGoClient, CompanyCreate, DealCreate, DealUpdate

with LimeGoClient(client_id="...", client_secret="...", environment="staging") as lime:
    # Upsert by an id WE own (e.g. the contract number) - safe to re-run.
    company = lime.companies.upsert("ORG-5560000000", CompanyCreate(name="Acme AB", status="customer")).resource
    deal = lime.deals.upsert(
        "AVT-2026-0042",
        DealCreate(name="NaaS Kontor", value=Decimal("125000"), currency="SEK", company=company.id),
    ).resource

    # Optimistic concurrency: pass the resource (or its ETag) as if_match.
    deal = lime.deals.update(deal.id, DealUpdate(probability=90), if_match=deal)

    for c in lime.companies.iter({"status": "customer"}, include=["owner"]):
        print(c.id, c.attributes.name, c.relationships.owner.id)
```

Async: `AsyncLimeGoClient` has the same surface with `await` / `async for`.

## Authentication & configuration

`POST {base_url}/oauth/token` with `grant_type=client_credentials`. Tokens are opaque,
live 1800 s and have no refresh token; the SDK caches them, refreshes before expiry and
retries once on a `401`.

| Setting         | Env var (`LIME_GO_[<ENV>_]...`) | Notes |
| --------------- | ------------------------------- | ----- |
| `client_id`     | `CLIENT_ID`                     | required |
| `client_secret` | `CLIENT_SECRET`                 | required |
| `environment`   | `LIME_GO_ENV`                   | `staging` is the only known URL |
| `base_url`      | `BASE_URL`                      | required for any other instance |
| `scopes`        | `SCOPES` (space-separated)      | omit to get the client's default |

There is **no default environment**: a deploy without `LIME_GO_ENV`/`LIME_GO_BASE_URL`
fails fast instead of writing to the wrong instance. Values are looked up
environment-first (`LIME_GO_PROD_CLIENT_ID` before `LIME_GO_CLIENT_ID`), so one `.env`
can hold several instances. `client.granted_scopes` shows what the server granted.

Scopes: `{companies,contacts,deals,activities,tasks}:{read,write,delete}`,
`reference:read` (owners, stages, tags, activity types, custom-field definitions,
relationship reads) and `changes:read`. Request only what an integration needs.

## API map

| Namespace | Operations |
| --- | --- |
| `companies`, `contacts`, `deals`, `activities`, `tasks` | `list`, `iter`, `next_page`, `get`, `create`, `upsert(external_id)`, `update`, `delete` |
| `companies.tags`, `contacts.tags` | relationship `list`, `iter`, `add`, `remove`, `replace` |
| `deals.contacts`, `deals.owners`, `deals.tags` | same as above |
| `tasks.companies`, `tasks.contacts`, `tasks.deals` | same as above |
| `owners`, `stages`, `tags`, `activity_types`, `custom_field_definitions` | `list`, `iter`, `next_page`, `get` |
| `changes` | `read(cursor)`, `iter_pages(cursor)` |
| `request(...)` | escape hatch for any path |

All 74 operations in the spec are covered; `tests/test_spec_conformance.py` enforces it.

### Writing

Write bodies are typed models: `XxxCreate` (create + upsert) and `XxxUpdate` (PATCH).
Only fields you set are sent: omit a field to leave it unchanged, set a nullable field to
`None` to clear it. Non-nullable fields, unknown fields, bad enum values, >100 custom
fields, >100 relationship ids and out-of-range values fail locally (pydantic) and, with
the pydantic mypy plugin, at type-check time. Relationships are plain ids:
`DealCreate(name=..., company="<uuid>", owners=["<uuid>"])`.

Notes from the spec:
- `ActivityUpdate` only accepts `content` and `type`; relationships and `occurred_at`
  can only be set on create. In Python the activity `type` attribute is `activity_type`.
- `TaskCreate` requires `owner` (an owner id, or explicitly `None`).
- Deal `value` is a `Decimal`, sent as the API's decimal string (max 15+4 digits).

### Idempotency

Every write carries an `Idempotency-Key` (the API requires it). The SDK generates one per
call and **reuses it across its own retries**, so a retried POST cannot create duplicates.
For retries across processes (a re-run sync job), pass your own stable key:
`create(data, idempotency_key="sync-AVT-2026-0042")`. Better still, use `upsert` with an
external id.

### Concurrency (ETag / If-Match)

`update`, `delete` and relationship writes require `if_match`. Resources returned by
`get`/`create`/`update`/`upsert` carry the response `.etag`; items from a list page derive
it from `meta.revision` as `"<id>:<revision>"` (the API's format, verified live), so you can
pass any resource itself. Only resources without a revision raise `MissingETagError`. A
stale ETag raises `PreconditionFailedError` (412): re-read
and retry. Relationship calls return the parent's new ETag in `page.etag`.

### Pagination

Cursor-based, max 100 per page. `list()` returns a `Page` (`data`, `included`,
`next_url`, `has_more`); `iter()` follows `links.next` for you. `include=` (CRUD
resources) returns related to-one records typed in `page.included`. `fields=` limits the
attributes returned (timestamps are always included). `sort` is `"id"` or `"-id"`.

### Change feed

```python
checkpoint = lime.changes.read()           # first run: get a checkpoint cursor, persist it
for page in lime.changes.iter_pages(cursor):
    for ch in page.data:
        a = ch.attributes                  # resource_type, resource_id, revision, deleted
        if a.origin_integration_id == MY_INTEGRATION_ID:
            continue                       # skip echoes of our own writes
        ...
    save_cursor(page.cursor)               # durable; resume from here next time
```

> The request parameter carrying the cursor is not documented in the spec; the SDK sends
> `cursor` (`lime_go_agentic.resources.CHANGES_CURSOR_PARAM`). To be confirmed with Lime.

## Errors

All errors derive from `LimeGoError`. HTTP errors raise an `APIStatusError` subclass per
status (`BadRequestError` 400, `UnauthorizedError` 401, `ForbiddenError` 403,
`NotFoundError` 404, `NotAcceptableError` 406, `ConflictError` 409, `GoneError` 410,
`PreconditionFailedError` 412, `PayloadTooLargeError` 413,
`UnsupportedMediaTypeError` 415, `UnprocessableEntityError` 422,
`PreconditionRequiredError` 428, `RateLimitError` 429, `ServiceUnavailableError` 503,
`ServerError` 5xx) with `.errors` (parsed JSON:API error objects), `.code` (Lime
documents codes as stable, e.g. `relationship_too_large`, `unavailable`) and
`.request_id` (`x-request-id`, quote it to Lime support).

Retries: network errors, 429 and 5xx are retried `max_retries` times (default 2) with
backoff, honouring `Retry-After` up to `max_retry_after` (default 30 s); a longer
server-requested wait raises immediately instead of blocking.

## Logging

The SDK logs to the `lime_go_agentic` logger: DEBUG (method, path, status, timing,
request id) and WARNING (retries). It never logs credentials, tokens, headers or bodies.

## Development

```bash
uv venv .venv && uv pip install -e ".[dev]"
.venv/bin/mypy src/lime_go_agentic
.venv/bin/pytest -q                      # unit tests (integration tests deselected)
.venv/bin/pytest -m integration          # live, needs LIME_GO_* in the environment
```

**Spec conformance:** Lime's OpenAPI spec is not redistributed here. Fetch it with
`python scripts/fetch_spec.py` (writes the gitignored `spec/openapi.json`), then run
`pytest tests/test_spec_conformance.py`; every failure names the exact difference. CI
fetches the live spec on every run, so it also flags when Lime changes the API.

## License

MIT
