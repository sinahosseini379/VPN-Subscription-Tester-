import logging

from vpn_tester.config import Settings
from vpn_tester.main import setup_logging


def test_setup_logging_level_from_config(monkeypatch):
    captured = {}

    def fake_basic_config(**kwargs):
        captured.update(kwargs)

    monkeypatch.setattr(logging, "basicConfig", fake_basic_config)
    setup_logging(Settings(log_level="WARNING", log_file=""), verbose=False)
    assert captured["level"] == logging.WARNING


def test_setup_logging_verbose_overrides(monkeypatch):
    captured = {}

    def fake_basic_config(**kwargs):
        captured.update(kwargs)

    monkeypatch.setattr(logging, "basicConfig", fake_basic_config)
    setup_logging(Settings(log_level="CRITICAL", log_file=""), verbose=True)
    assert captured["level"] == logging.DEBUG
