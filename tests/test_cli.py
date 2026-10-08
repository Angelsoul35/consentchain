from __future__ import annotations

import pytest

from consentchain import cli

pytestmark = pytest.mark.chain


def test_demo_runs_end_to_end(capsys):
    cli.demo()
    out = capsys.readouterr().out
    assert "Deploying ConsentRegistry" in out
    assert "granted" in out
    assert "ALLOW" in out
    assert "DENY" in out
    assert "revoked" in out


def test_main_dispatches_demo(monkeypatch):
    called = {"demo": False}
    monkeypatch.setattr(cli, "demo", lambda: called.__setitem__("demo", True))
    monkeypatch.setattr("sys.argv", ["consentchain", "demo"])
    cli.main()
    assert called["demo"] is True
