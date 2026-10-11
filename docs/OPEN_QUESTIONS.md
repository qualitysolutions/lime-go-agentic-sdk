# Open questions for Lime (spec v1.0.0, fetched 2026-10-10)

Gaps found while building the SDK from `spec/openapi.json`. Each item notes what the SDK
does today so it can be adjusted once Lime answers. Nothing here has been verified
against a live response yet: on 2026-10-10 every staging API path returned
`503 unavailable` with `Retry-After: 60`.

1. **Production base URL.** The spec has no `servers` entry. Only staging is known
   (`https://agentic.staging.lime-go.com`). Is there one host for all customers (tenant
   chosen by the OAuth client) or one host per instance ("per-instance limits")?
   *SDK:* `environment="staging"` or an explicit `base_url`; no default.

2. **`GET /api/v1/changes` request parameters.** The response has `meta.cursor`,
   `meta.has_more` and `meta.checkpoint`, but no request parameters are declared. What is
   the cursor parameter called, is there a page size, and how is a checkpoint requested?
   How long does a cursor stay valid (`410 Gone`?).
   *SDK:* sends `cursor=<value>` (`CHANGES_CURSOR_PARAM`), no page size.

3. **ETag format vs `meta.revision`.** Is the ETag derivable from `meta.revision` (e.g.
   `"<revision>"`)? If so, the SDK could allow `if_match=` straight from list items.
   *SDK:* only uses ETags from single-resource responses; list items raise
   `MissingETagError`.

4. **Rate limits.** "Per-instance limits" are mentioned but not specified (requests per
   window, response headers, `Retry-After` on 429?).
   *SDK:* retries 429/5xx with backoff and honours `Retry-After` up to 30 s.

5. **Idempotency-Key semantics.** Retention window, and the response when a key is reused
   with a different body (409? 422?).
   *SDK:* one key per call, reused across its own retries; callers may pass their own.

6. **Error codes.** The spec says codes are stable but lists none. A list of codes per
   status would let integrations branch reliably (known so far: `unavailable`,
   `relationship_too_large`).

7. **`include` values.** "Up to two singular relationships, one level deep". Confirm the
   names (e.g. `company`, `owner`, `stage`) and that `included` follows JSON:API.

8. **`custom_fields` value types.** Read schema is a free object. How do values map from
   `custom-field-definitions.field_type` (dates, numbers, options)?

9. **Filters.** Is `filter[name]` exact, prefix or contains? Is `filter[status]`
   single-valued or comma-separated? Timezone handling of `filter[updated_since]`.

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
