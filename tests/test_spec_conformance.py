"""The SDK must match the vendored OpenAPI spec (spec/openapi.json) exactly.

When Lime changes the API: download the new spec over spec/openapi.json and run this
file. Every failure names the exact drift (new attribute, changed enum, new endpoint...).
"""

from __future__ import annotations

import inspect
import json
import typing
from pathlib import Path
from typing import Any, Literal, get_args, get_origin

import pytest
from pydantic import BaseModel

from lime_go_agentic import LimeGoClient, models
from lime_go_agentic.resources import CHANGES_CURSOR_PARAM  # noqa: F401  (documented gap)
from lime_go_agentic.resources._base import SyncCrudResource, SyncReadResource, SyncRelationship

SPEC = json.loads((Path(__file__).parent.parent / "spec" / "openapi.json").read_text())
PATHS = SPEC["paths"]
SCHEMAS = SPEC["components"]["schemas"]
API = "/api/v1"

READ_MODELS: dict[str, type[models.Resource]] = dict(models.RESOURCE_MODELS)
WRITE_MODELS = {
    "companies": (models.CompanyCreate, models.CompanyUpdate),
    "contacts": (models.ContactCreate, models.ContactUpdate),
    "deals": (models.DealCreate, models.DealUpdate),
    "activities": (models.ActivityCreate, models.ActivityUpdate),
    "tasks": (models.TaskCreate, models.TaskUpdate),
}


def wire_fields(model: type[BaseModel]) -> dict[str, Any]:
    """Wire name -> pydantic FieldInfo."""
    return {(f.alias or name): f for name, f in model.model_fields.items()}


def literal_values(annotation: Any) -> set[str] | None:
    """Collect Literal values from an annotation like ``Literal[...] | None``."""
    if get_origin(annotation) is Literal:
        return set(get_args(annotation))
    for arg in get_args(annotation):
        found = literal_values(arg)
        if found is not None:
            return found
    return None


def read_schema(rtype: str) -> dict[str, Any]:
    if rtype in SCHEMAS:
        return SCHEMAS[rtype]
    # owners are only declared inline on their endpoints.
    return PATHS[f"{API}/{rtype}/{{id}}"]["get"]["responses"]["200"]["content"][
        "application/vnd.api+json"]["schema"]["properties"]["data"]


def body_schema(path: str, method: str) -> dict[str, Any]:
    return PATHS[path][method]["requestBody"]["content"]["application/vnd.api+json"]["schema"][
        "properties"]["data"]


# -- read models ----------------------------------------------------------------------
@pytest.mark.parametrize("rtype", sorted(READ_MODELS))
def test_read_model_attributes_match_spec(rtype: str) -> None:
    schema = read_schema(rtype)
    spec_attrs = schema["properties"]["attributes"]["properties"]
    attributes_model = READ_MODELS[rtype].model_fields["attributes"].annotation
    assert isinstance(attributes_model, type) and issubclass(attributes_model, BaseModel)
    model_attrs = wire_fields(attributes_model)
    assert set(model_attrs) == set(spec_attrs), rtype
    for name, prop in spec_attrs.items():
        if "enum" in prop:
            assert literal_values(model_attrs[name].annotation) == set(prop["enum"]), f"{rtype}.{name}"


@pytest.mark.parametrize("rtype", sorted(READ_MODELS))
def test_read_model_relationships_match_spec(rtype: str) -> None:
    schema = read_schema(rtype)
    spec_rels = schema["properties"].get("relationships", {}).get("properties", {})
    model_field = READ_MODELS[rtype].model_fields.get("relationships")
    model_rels: dict[str, Any] = {}
    if model_field is not None:
        rel_model = model_field.annotation
        assert isinstance(rel_model, type) and issubclass(rel_model, BaseModel)
        model_rels = dict(rel_model.model_fields)
    assert set(model_rels) == set(spec_rels), rtype
    for name, prop in spec_rels.items():
        many = prop["properties"]["data"].get("type") == "array"
        expected = models.ToMany if many else models.ToOne
        assert model_rels[name].annotation is expected, f"{rtype}.{name}"


def test_change_model_matches_spec() -> None:
    item = PATHS[f"{API}/changes"]["get"]["responses"]["200"]["content"][
        "application/vnd.api+json"]["schema"]["properties"]["data"]["items"]
    spec_attrs = item["properties"]["attributes"]["properties"]
    assert set(models.ChangeAttributes.model_fields) == set(spec_attrs)
    meta = PATHS[f"{API}/changes"]["get"]["responses"]["200"]["content"][
        "application/vnd.api+json"]["schema"]["properties"]["meta"]["properties"]
    assert set(meta) == {"cursor", "has_more", "checkpoint"}


# -- write models ---------------------------------------------------------------------
WRITE_CASES = [
    (rtype, label, path, method)
    for rtype in WRITE_MODELS
    for label, path, method in (
        ("create", f"{API}/{rtype}", "post"),
        ("create", f"{API}/{rtype}/external/{{external_id}}", "put"),
        ("update", f"{API}/{rtype}/{{id}}", "patch"),
    )
]


@pytest.mark.parametrize(("rtype", "label", "path", "method"), WRITE_CASES)
def test_write_model_matches_request_body(rtype: str, label: str, path: str, method: str) -> None:
    create, update = WRITE_MODELS[rtype]
    model = create if label == "create" else update
    data = body_schema(path, method)
    spec_attrs = data["properties"]["attributes"]["properties"]
    spec_rels = data["properties"].get("relationships", {}).get("properties", {})
    fields = wire_fields(model)

    expected = set(spec_attrs) | set(spec_rels)
    if label == "create" and "id" in data["properties"]:
        expected.add("id")  # client-generated id on create
    assert set(fields) == expected, f"{rtype} {method.upper()}"

    # Relationship kinds and targets.
    assert set(model.relationship_fields) == set(spec_rels)
    for name, prop in spec_rels.items():
        d = prop["properties"]["data"]
        many = d.get("type") == "array"
        target = (d["items"] if many else d)["properties"]["type"]["enum"][0]
        assert model.relationship_fields[name] == ("many" if many else "one", target), f"{rtype}.{name}"

    # Required fields: attributes.required + relationships.required.
    spec_required = set(data["properties"]["attributes"].get("required", []))
    spec_required |= set(data["properties"].get("relationships", {}).get("required", []))
    model_required = {wire for wire, f in fields.items() if f.is_required()}
    assert model_required == spec_required, f"{rtype} {method.upper()} required"

    # Non-nullable attributes are rejected as null locally.
    non_nullable_wire = {
        (model.model_fields[n].alias or n) for n in model.non_nullable_fields
    }
    spec_non_nullable = {k for k, p in spec_attrs.items() if p.get("nullable") is False}
    assert non_nullable_wire == spec_non_nullable, f"{rtype} {method.upper()} nullable"

    # Enums.
    for name, prop in spec_attrs.items():
        if "enum" in prop:
            assert literal_values(fields[name].annotation) == set(prop["enum"]), f"{rtype}.{name}"


# -- list filters ---------------------------------------------------------------------
def _filter_type(resource: SyncReadResource[Any, Any]) -> type:
    for base in getattr(type(resource), "__orig_bases__", ()):
        args = get_args(base)
        if args:
            return typing.cast(type, args[1])
    raise AssertionError(type(resource))


def _resources(client: LimeGoClient) -> dict[str, SyncReadResource[Any, Any]]:
    return {n: v for n, v in vars(client).items() if isinstance(v, SyncReadResource)}


@pytest.fixture
def sdk() -> LimeGoClient:
    return LimeGoClient(client_id="x", client_secret="y", base_url="https://lime.test")


def test_filters_and_include_match_spec(sdk: LimeGoClient) -> None:
    for name, resource in _resources(sdk).items():
        params = {p["name"] for p in PATHS[resource._path]["get"].get("parameters", [])}
        spec_filters = {p[len("filter["):-1] for p in params if p.startswith("filter[")}
        assert set(typing.get_type_hints(_filter_type(resource))) == spec_filters, name
        assert ("include" in params) == isinstance(resource, SyncCrudResource), name


# -- endpoint coverage ----------------------------------------------------------------
def _sdk_operations(sdk: LimeGoClient) -> set[tuple[str, str]]:
    ops = {("post", "/oauth/token"), ("get", f"{API}/changes")}
    for resource in _resources(sdk).values():
        p = resource._path
        ops |= {("get", p), ("get", f"{p}/{{id}}")}
        if isinstance(resource, SyncCrudResource):
            ops |= {("post", p), ("put", f"{p}/external/{{external_id}}"),
                    ("patch", f"{p}/{{id}}"), ("delete", f"{p}/{{id}}")}
        for rel in vars(resource).values():
            if isinstance(rel, SyncRelationship):
                rp = f"{p}/{{id}}/relationships/{rel._name}"
                ops |= {(m, rp) for m in ("get", "post", "patch", "delete")}
    return ops


def test_every_spec_operation_is_covered(sdk: LimeGoClient) -> None:
    spec_ops = {(m, p) for p, item in PATHS.items() for m in item if m != "parameters"}
    sdk_ops = _sdk_operations(sdk)
    assert spec_ops - sdk_ops == set(), "operations in the spec without SDK support"
    assert sdk_ops - spec_ops == set(), "SDK calls operations the spec does not declare"


def test_spec_has_74_operations() -> None:
    """Pins the spec version this SDK release was written against."""
    assert SPEC["info"]["version"] == "1.0.0"
    assert sum(1 for item in PATHS.values() for m in item if m != "parameters") == 74


def test_scopes_match_spec() -> None:
    from lime_go_agentic import ALL_SCOPES

    declared = SPEC["components"]["securitySchemes"]["oauth"]["flows"]["clientCredentials"]["scopes"]
    assert set(ALL_SCOPES) == set(declared)


def test_async_client_mirrors_sync_client() -> None:
    from lime_go_agentic import AsyncLimeGoClient

    s = LimeGoClient(client_id="x", client_secret="y", base_url="https://lime.test")
    a = AsyncLimeGoClient(client_id="x", client_secret="y", base_url="https://lime.test")
    assert set(vars(s)) == set(vars(a))
    for name, res in vars(s).items():
        if name.startswith("_"):
            continue
        ares = getattr(a, name)
        public = {m for m, _ in inspect.getmembers(res, callable) if not m.startswith("_")}
        apublic = {m for m, _ in inspect.getmembers(ares, callable) if not m.startswith("_")}
        assert public == apublic, name
        assert {k for k, v in vars(res).items() if not k.startswith("_")} == \
               {k for k, v in vars(ares).items() if not k.startswith("_")}, name
