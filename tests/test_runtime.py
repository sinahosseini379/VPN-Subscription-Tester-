from __future__ import annotations

from vpn_tester.runtime import Reporter


def test_reporter_lifecycle():
    r = Reporter(max_logs=10)
    assert r.status == "idle"
    r.begin_run("starting")
    assert r.status == "running"
    assert r.stage == "starting"

    r.set_progress("tcp-ping", 5, 10, 0.06, 0.22)
    assert 0.06 <= r.progress <= 0.22
    assert r.stage == "tcp-ping"

    r.set_progress("tcp-ping", 10, 10, 0.06, 0.22)
    assert r.progress == pytest_approx(0.22)

    r.finish(True, {"count": 3})
    assert r.status == "done"
    assert r.progress == 1.0
    assert r.last_meta == {"count": 3}


def test_reporter_logs_after():
    r = Reporter()
    r.log("one")
    seq, lines = r.logs_after(0)
    assert lines == ["one"]

    r.log("two")
    seq2, lines2 = r.logs_after(seq)
    assert lines2 == ["two"]

    seq3, lines3 = r.logs_after(seq2)
    assert lines3 == []


def test_reporter_ring_buffer():
    r = Reporter(max_logs=2)
    r.log("a")
    r.log("b")
    r.log("c")
    _, lines = r.logs_after(0)
    assert lines == ["b", "c"]


def test_snapshot_contains_key_fields():
    r = Reporter()
    snap = r.snapshot()
    assert snap["status"] == "idle"
    assert "progress" in snap
    assert "log_seq" in snap


def pytest_approx(v):
    from pytest import approx

    return approx(v)
