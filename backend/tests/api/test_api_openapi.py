"""The contract lock: the app's OpenAPI document is the committed docs/api/openapi-v1.json, so a
change behind the API that changes what the frontend sees fails here until the file (and API.md,
and the fixtures) are updated in the same PR. tests/api/test_api_fixtures.py checks the examples."""

from make_openapi import COMMAND, OPENAPI, schema


def test_the_app_s_schema_is_the_committed_contract() -> None:
    live = schema()
    committed = OPENAPI.read_text(encoding="utf-8") if OPENAPI.exists() else ""
    assert live == committed, (
        f"the API's OpenAPI document differs from {OPENAPI.name}. If the change is meant (v1 "
        f"changes are additive only, docs/API.md 'Changing the contract'), regenerate it with: "
        f"{COMMAND}"
    )


def test_the_contract_is_the_same_on_every_build() -> None:
    assert schema() == schema()
