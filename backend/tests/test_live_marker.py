"""`live` tests are skipped, with the reason shown, unless RUN_LIVE_TESTS=1 (tests/conftest.py)."""

from pathlib import Path

import pytest

CONFTEST = Path(__file__).with_name("conftest.py")
INI = f"[pytest]\nmarkers =\n    live: real service\npythonpath = {CONFTEST.parent.parent}\n"
LIVE_TEST = """
import pytest

@pytest.mark.live
def test_calls_the_real_service():
    pass
"""


def run_live_test(pytester: pytest.Pytester) -> pytest.RunResult:
    pytester.makeconftest(CONFTEST.read_text())
    pytester.makeini(INI)
    pytester.makepyfile(LIVE_TEST)
    return pytester.runpytest_subprocess("-rs")


def test_live_test_is_skipped_without_the_flag(
    pytester: pytest.Pytester, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("RUN_LIVE_TESTS", raising=False)
    result = run_live_test(pytester)
    result.assert_outcomes(skipped=1)
    result.stdout.fnmatch_lines(["*live test: set RUN_LIVE_TESTS=1 to call the real service*"])


def test_live_test_runs_with_the_flag(
    pytester: pytest.Pytester, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("RUN_LIVE_TESTS", "1")
    run_live_test(pytester).assert_outcomes(passed=1)
