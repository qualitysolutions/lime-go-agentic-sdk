# Open questions for Lime (spec v1.0.0, fetched 2026-10-10)

Gaps found while building the SDK from `spec/openapi.json`. Each item notes what the SDK
does today so it can be adjusted once Lime answers.

**Verified live on 2026-10-14** (read-only, GETs only) once Lime enabled API access: items
marked *Answered* below were settled by observing the API. Note that OAuth clients created
in the admin UI *before* API access was enabled kept returning `401 invalid_client` (even
after rotating the secret); a client created afterwards worked.

1. **Production base URL.** *Partly answered.* Our instance and its OAuth client live on
   `https://agentic.staging.lime-go.com`, which is the production environment while Lime
   Go Agentic is in beta; the token is tenant-scoped (no tenant in the API path). A second
   host, `agentic.lime-go.com`, serves the same spec. Open: will instances and credentials
   move there after the beta, and does the API URL change?
   *SDK:* `environment="staging"` or an explicit `base_url`; no default.

2. **`GET /api/v1/changes` request parameters.** *Answered (mostly).* The cursor parameter
   is `cursor` (`page[cursor]` and `after` give `400 invalid_query`). The first call without
   a cursor returns a checkpoint (`meta.checkpoint: true`, empty `data`); later calls return
   `meta.has_more`. An invalid or expired cursor gives `410` with code `cursor_expired`
   ("restart synchronization"). Open: page size, and how long a cursor stays valid.
   *SDK:* sends `cursor=<value>`; 410 raises `GoneError`.

3. **ETag format vs `meta.revision`.** *Answered.* The ETag is `"<id>:<revision>"` on every
   revisioned resource (companies, contacts, tasks, activities, stages, tags, activity
   types). `owners` have no revision and no ETag.
   *SDK:* `Resource.etag` falls back to that format, so list items work as `if_match=`.

4. **Rate limits.** *Answered.* 120 requests/min per integration and 300/min per
   organization (`x-ratelimit-policy: per-instance; window=60`), reported in
   `x-ratelimit-integration-limit|remaining`, `x-ratelimit-organization-limit|remaining`
   and `x-ratelimit-reset`. Open: whether 429 carries `Retry-After`.
   *SDK:* retries 429/5xx with backoff and honours `Retry-After` up to 30 s.

5. **Idempotency-Key semantics.** Retention window, and the response when a key is reused
   with a different body (409? 422?). (Not tested: needs a write.)
   *SDK:* one key per call, reused across its own retries; callers may pass their own.

6. **Error codes.** *Partly answered.* Seen so far: `unavailable` (503), `not_found` (404),
   `invalid_query` (400, also for unknown filters), `cursor_expired` (410), plus
   `relationship_too_large` from the spec. A full list per status is still wanted.

7. **`include` values.** *Partly answered.* `include=owner` on companies works and returns
   `owners` in `included`. Other names still to confirm.

8. **`custom_fields` value types.** How do values map from
   `custom-field-definitions.field_type` (dates, numbers, options)? (No definitions exist
   on our instance yet.)

9. **Filters.** Is `filter[name]` exact, prefix or contains? Is `filter[status]`
   single-valued or comma-separated? Timezone handling of `filter[updated_since]`. Is a
   `filter[business_id]` (org number) planned? (All companies on our instance have one.)

10. **Owner lifecycle.** What happens to `companies.owner` / `tasks.owner` when a user is
    deactivated (the `owners` list only returns active members)? Is the owner cleared, kept
    but unreadable via `GET /owners/{id}`, or reassigned? QLS will use `companies.owner` as
    the customer's account manager (kundansvarig) and assign CSR tasks to it.

11. **Contacts per company.** `GET /contacts` has no `filter[company]`. Is one planned, or
    should integrations page through `contacts` (or the change feed) and filter locally?

12. **Quotes.** The API has no quote/offer resource, although the product creates and signs
    quotes. Is a quote API planned (create/send a quote, quote number issued by Lime,
    status/signing events)? QLS wants to send quotes from its quote builder via Lime.

13. **Custom fields: creation, types and write semantics.** `custom-field-definitions` is
    read-only in the API, so fields are created in the Lime UI. Which `field_type` values
    exist (boolean, text, multi-value/list, URL)? On PATCH, is `custom_fields` MERGED with
    the existing values or does it REPLACE the whole object (would clobber fields set by
    users or other integrations)? Is the key in `custom_fields` the definition `key`?
    QLS plans two company fields maintained by QARP: "QARP customer" (yes/no) and
    "QARP tenant id(s)".

14. **External id ownership.** `PUT .../external/{external_id}` is "integration-owned". Can
    a record carry external ids from several integrations (QARP and the Fortnox sync), and
    can we look a record up by our external id without upserting?

15. **Pilot status / publication.** OK to publish an open-source SDK for the API, and when
    does v1 leave pilot? (The SDK's public PyPI release waits for this.) Also: may we
    redistribute `spec/openapi.json` in a public repo/sdist? If not, exclude it from the
    sdist and fetch it in CI instead before going public (the wheel never contains it).
