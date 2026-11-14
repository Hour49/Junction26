"""The extra rule and the allowlist in .gitleaks.toml, checked with Python's re (RE2 reads them the
same way)."""
import re
from pathlib import Path

import tomllib

CONFIG = tomllib.loads((Path(__file__).resolve().parent.parent / ".gitleaks.toml").read_text())
RULE = next(r for r in CONFIG["rules"] if r["id"] == "cloudflare-api-token")
FAKE_KEY = "test-key-0123456789"  # the one fake key unit tests use (docs/ENGINEERING.md section 5)


def found(text):
    # gitleaks runs a rule's regex only when one of its keywords is in the text (case-insensitive)
    has_keyword = any(k in text.lower() for k in RULE["keywords"])
    return has_keyword and re.search(RULE["regex"], text) is not None


def test_default_rules_are_kept():
    assert CONFIG["extend"]["useDefault"] is True


def test_cloudflare_token_is_found():
    token = "cfat" + "_" + "Q7w8E9r0T1y2U3i4O5p6"  # built at runtime so this file passes the scan
    # no "cloudflare" word on the line: the cfat_ keyword must trigger the rule
    assert found(f"export CF_API_TOKEN={token}\n")


def test_cloudflare_look_alikes_are_not():
    for text in ["cfat_short", "tokens start with cfat_ then", "see cfat-notes-for-the-format"]:
        assert not found(text), text


def allowed(value):
    # a global allowlist's regexes are matched against the finding's secret (gitleaks' default target)
    return any(
        re.search(regex, value)
        for allowlist in CONFIG.get("allowlists", [])
        for regex in allowlist.get("regexes", [])
    )


def test_the_fake_test_key_is_allowed():
    assert allowed(FAKE_KEY)


def test_only_that_exact_value_is_allowed():
    near = [FAKE_KEY + "0", "x" + FAKE_KEY, FAKE_KEY[:-1], FAKE_KEY[:-1] + "8", FAKE_KEY.upper()]
    for value in near:
        assert not allowed(value), value


def test_the_allowlist_skips_nothing_else():
    (allowlist,) = CONFIG["allowlists"]
    assert allowlist.get("regexTarget", "secret") == "secret"  # not the whole line or file
    assert set(allowlist) <= {"description", "regexTarget", "regexes"}  # no paths, commits, stopwords
