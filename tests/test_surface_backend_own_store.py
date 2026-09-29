"""A Desktop-spawned `serve`/`dashboard` backend must not open the shared gateway store.

Two long-lived read-write owners on one WAL store is the deleted-sidecar
contour that produced page-level corruption upstream (#588/#601/#628). The
surface therefore resolves to its own store unless LCM_DATABASE_PATH pins one.

Detection is core's `is_desktop_owned_backend`, not a hand-rolled argv scan:
`HERMES_DESKTOP=1` is inherited by every shell and agent child the app launches
(#116107 class), so only the per-spawn credential (token env, or the 0600 token
FILE on the SSH spawn's argv) proves ownership.
"""

import sys

from hermes_lcm.config import LCMConfig
from hermes_lcm.engine import (
    SURFACE_BACKEND_STORE_NAME,
    LCMEngine,
    _runs_surface_backend,
)


def _desktop_env(monkeypatch, **env):
    for key in ("HERMES_DESKTOP", "HERMES_DASHBOARD_SESSION_TOKEN"):
        monkeypatch.delenv(key, raising=False)
    for key, value in env.items():
        monkeypatch.setenv(key, value)


def test_inherited_desktop_marker_alone_is_not_ownership(monkeypatch):
    _desktop_env(monkeypatch, HERMES_DESKTOP="1")
    assert not _runs_surface_backend()


def test_desktop_pool_and_ssh_spawns_are_detected(monkeypatch):
    _desktop_env(monkeypatch, HERMES_DESKTOP="1", HERMES_DASHBOARD_SESSION_TOKEN="tok")
    assert _runs_surface_backend()

    # SSH spawn: no token env, the credential arrives as a file on argv.
    _desktop_env(monkeypatch, HERMES_DESKTOP="1")
    monkeypatch.setattr(
        sys,
        "argv",
        ["hermes", "--profile", "default", "serve", "--isolated", "--ssh-session-token-file", "/tmp/t"],
    )
    assert _runs_surface_backend()


def test_desktop_backend_resolves_to_its_own_store(tmp_path, monkeypatch):
    _desktop_env(monkeypatch, HERMES_DESKTOP="1", HERMES_DASHBOARD_SESSION_TOKEN="tok")
    engine = LCMEngine(config=LCMConfig(), hermes_home=str(tmp_path))
    assert engine._storage_db_path == tmp_path / SURFACE_BACKEND_STORE_NAME
    assert engine._storage_db_path.name != "lcm.db"


def test_gateway_keeps_the_shared_store(tmp_path, monkeypatch):
    _desktop_env(monkeypatch)
    monkeypatch.setattr(sys, "argv", ["hermes", "gateway", "run"])
    engine = LCMEngine(config=LCMConfig(), hermes_home=str(tmp_path))
    assert engine._storage_db_path == tmp_path / "lcm.db"


def test_explicit_env_path_wins_over_the_surface_default(tmp_path, monkeypatch):
    _desktop_env(monkeypatch, HERMES_DESKTOP="1", HERMES_DASHBOARD_SESSION_TOKEN="tok")
    pinned = tmp_path / "lcm-serve.db"
    engine = LCMEngine(config=LCMConfig(database_path=str(pinned)), hermes_home=str(tmp_path))
    assert engine._storage_db_path == pinned
