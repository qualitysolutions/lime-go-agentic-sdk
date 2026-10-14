"""Record live responses as sanitized test fixtures (read-only, GETs only).

    SSL_CERT_FILE=... python scripts/record_fixtures.py   # needs LIME_GO_* in the env

Writes ``tests/fixtures/live/*.json``. Raw responses are never written to disk: every
string that is not on the SAFE allowlist (enums, timestamps, revisions) is replaced with
a placeholder, ids are remapped to fake UUIDs (consistently, so relationships still
line up) and signed cursors/page tokens are replaced. Review the diff before committing.
"""

from __future__ import annotations

import json
import re
import uuid
from pathlib import Path
from typing import Any

from lime_go_agentic import LimeGoClient

OUT = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "live"
READ_SCOPES = ["companies:read", "contacts:read", "deals:read", "tasks:read",
               "activities:read", "reference:read", "changes:read"]
RESOURCES = ["companies", "contacts", "deals", "tasks", "activities", "owners", "stages",
             "tags", "activity-types", "custom-field-definitions"]

#: Attribute keys whose string values are enums or machine values, kept verbatim.
SAFE = {"type", "status", "state", "category", "priority", "taggable_type", "icon", "color",
        "country", "field_type", "created_at", "updated_at", "due_date", "occurred_at",
        "revision"}
UUID_RE = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")


class Sanitizer:
    def __init__(self) -> None:
        self.ids: dict[str, str] = {}

    def fake_id(self, real: str) -> str:
        if real not in self.ids:
            self.ids[real] = str(uuid.UUID(int=len(self.ids) + 1))
        return self.ids[real]

    def value(self, key: str, v: Any) -> Any:
        if isinstance(v, dict):
            return {k: self.value(k, x) for k, x in v.items()}
        if isinstance(v, list):
            return [self.value(key, x) for x in v]
        if not isinstance(v, str):
            return v
        if UUID_RE.fullmatch(v):
            return self.fake_id(v)
        if key in SAFE:
            return v
        if key in ("next", "self", "prev"):
            v = UUID_RE.sub(lambda m: self.fake_id(m.group()), v)
            return re.sub(r"page\[after\]=[^&]+", "page[after]=CURSOR", v)
        if key == "cursor":
            return "CURSOR"
        if key == "request_id":
            return "00000000-0000-0000-0000-00000000beef"
        if key == "email":
            return f"user{len(self.ids)}@example.com"
        if key == "business_id":
            return "556000-0000"
        if key in ("phone", "mobile_phone"):
            return "+46 8 000 00 00"
        if key == "domain":
            return "example.com"
        return f"<{key}>"

    def etag(self, etag: str | None) -> str | None:
        if not etag:
            return etag
        rid, _, rev = etag.strip('"').partition(":")
        return f'"{self.fake_id(rid)}:{rev}"'


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    s = Sanitizer()

    def save(name: str, body: Any, etag: str | None = None) -> None:
        doc = {"body": s.value("", body)}
        if etag is not None:
            doc["etag"] = s.etag(etag)
        (OUT / f"{name}.json").write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n")
        print("wrote", name)

    with LimeGoClient(scopes=READ_SCOPES) as lime:
        for res in RESOURCES:
            page = lime.request("GET", f"/api/v1/{res}", params={"page[size]": 2})
            save(f"{res}_list", page.body)
            data = page.body["data"]
            if data:
                one = lime.request("GET", f"/api/v1/{res}/{data[0]['id']}")
                save(f"{res}_get", one.body, one.etag)
        first = lime.request("GET", "/api/v1/changes")
        save("changes_checkpoint", first.body)
        save("changes_page", lime.request("GET", "/api/v1/changes",
                                          params={"cursor": first.body["meta"]["cursor"]}).body)


if __name__ == "__main__":
    main()
