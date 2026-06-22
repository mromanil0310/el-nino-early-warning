"""
test_retry_util.py
Unit tests for retry_call (pipeline/scripts/retry_util.py). `sleep` is stubbed so the
tests never wait.

Run: python -m pytest pipeline/tests/test_retry_util.py -v
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from retry_util import retry_call  # noqa: E402


def make_flaky(fail_times, exc=ValueError):
    """Return a callable that raises `exc` the first `fail_times` calls, then returns 'ok'."""
    state = {"calls": 0}

    def fn():
        state["calls"] += 1
        if state["calls"] <= fail_times:
            raise exc(f"boom {state['calls']}")
        return "ok"

    fn.state = state
    return fn


def test_returns_on_first_success_without_sleeping():
    slept = []
    fn = make_flaky(0)
    assert retry_call(fn, sleep=slept.append) == "ok"
    assert fn.state["calls"] == 1
    assert slept == []


def test_recovers_after_transient_failures():
    slept = []
    fn = make_flaky(2)
    assert retry_call(fn, attempts=3, base_delay=1.0, sleep=slept.append) == "ok"
    assert fn.state["calls"] == 3
    assert slept == [1.0, 2.0]  # exponential backoff between the 3 attempts


def test_reraises_after_exhausting_attempts():
    slept = []
    fn = make_flaky(5)
    with pytest.raises(ValueError, match="boom 3"):
        retry_call(fn, attempts=3, sleep=slept.append)
    assert fn.state["calls"] == 3
    assert len(slept) == 2


def test_unlisted_exception_propagates_immediately():
    slept = []
    fn = make_flaky(5, exc=KeyError)
    with pytest.raises(KeyError):
        retry_call(fn, attempts=3, exceptions=(ValueError,), sleep=slept.append)
    assert fn.state["calls"] == 1  # no retries for an unlisted exception
    assert slept == []


def test_max_delay_caps_backoff():
    slept = []
    fn = make_flaky(4)
    retry_call(fn, attempts=5, base_delay=10.0, max_delay=15.0, sleep=slept.append)
    assert slept == [10.0, 15.0, 15.0, 15.0]  # 10, 20→15, 40→15, 80→15


def test_invalid_attempts():
    with pytest.raises(ValueError):
        retry_call(lambda: 1, attempts=0)
