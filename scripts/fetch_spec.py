"""Download Lime's published OpenAPI spec to spec/openapi.json (gitignored).

    python scripts/fetch_spec.py [URL]

The spec is Lime's document, served publicly at the URL below; it is fetched for the
conformance test instead of being redistributed in this repo.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import httpx

URL = "https://agentic.staging.lime-go.com/docs/api/openapi.json"
OUT = Path(__file__).resolve().parent.parent / "spec" / "openapi.json"


def main() -> None:
    url = sys.argv[1] if len(sys.argv) > 1 else URL
    response = httpx.get(url, timeout=30, follow_redirects=True)
    response.raise_for_status()
    spec = response.json()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(spec, indent=2) + "\n")
    print(f"wrote {OUT} (spec version {spec['info']['version']}, {len(spec['paths'])} paths)")


if __name__ == "__main__":
    main()
