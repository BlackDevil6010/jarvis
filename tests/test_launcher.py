"""Automated tests for JARVIS application launcher."""

import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest

from jarvis.core.database import Database
from jarvis.core.launcher import AppLauncher, LaunchResult


@pytest.fixture
def launcher_with_db():
    """Fixture providing an AppLauncher with an isolated test DB."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = Path(tmp_dir) / "launcher_test.db"
        db = Database(db_path=db_path)
        launcher = AppLauncher(db=db)
        yield launcher, db
        del launcher
        del db
        import gc
        gc.collect()


def test_resolve_standard_windows_apps(launcher_with_db):
    """Verify that common Windows system tools resolve to real paths."""
    launcher, _ = launcher_with_db
    notepad_path = launcher.resolve_executable_path("notepad.exe")
    assert notepad_path is not None
    assert Path(notepad_path).exists()
    assert notepad_path.lower().endswith("notepad.exe")


def test_resolve_nonexistent_executable(launcher_with_db):
    """Verify that a missing binary returns None."""
    launcher, _ = launcher_with_db
    resolved = launcher.resolve_executable_path("completely_imaginary_app_987654.exe")
    assert resolved is None


def test_launch_unregistered_app(launcher_with_db):
    """Ensure error message is returned when launching an unregistered app."""
    launcher, _ = launcher_with_db
    result: LaunchResult = launcher.launch("PhantomToolXYZ")
    assert result.success is False
    assert "not registered" in result.message.lower()
    assert result.pid is None


def test_launch_registered_app_with_missing_binary(launcher_with_db):
    """Ensure that if an app is registered but the file is missing, launch fails gracefully."""
    launcher, db = launcher_with_db
    db.add_or_update_application(
        name="MissingTool",
        path="C:\\NonExistentPath_XYZ\\missing.exe",
        aliases=["missing"],
        description="A tool that does not exist"
    )

    result = launcher.launch("MissingTool")
    assert result.success is False
    assert "not found" in result.message.lower() or "does not exist" in result.message.lower()
    assert result.pid is None


def test_launch_handles_permission_error(launcher_with_db):
    """Ensure PermissionError during launch is caught and reported cleanly."""
    launcher, _ = launcher_with_db
    with patch("subprocess.Popen", side_effect=PermissionError("Access Denied")):
        result = launcher.launch("Notepad")
        assert result.success is False
        assert "access denied" in result.message.lower() or "permission" in result.message.lower()


def test_launch_success_returns_pid(launcher_with_db):
    """Verify successful launch reports success=True and valid PID."""
    launcher, _ = launcher_with_db

    mock_proc = MagicMock()
    mock_proc.pid = 4321
    mock_proc.poll.return_value = None

    with patch("subprocess.Popen", return_value=mock_proc):
        result = launcher.launch("Notepad")
        assert result.success is True
        assert result.pid == 4321
        assert "opened notepad successfully" in result.message.lower()


def test_list_registered_applications(launcher_with_db):
    """Verify app listing includes availability check."""
    launcher, _ = launcher_with_db
    apps = launcher.list_registered_applications()
    assert len(apps) >= 5
    for app in apps:
        assert "available" in app
        assert isinstance(app["available"], bool)


def test_app_paths_resolution(launcher_with_db):
    """Verify that resolve_executable_path checks App Paths and handles extensions."""
    launcher, _ = launcher_with_db
    # Standard app
    notepad = launcher.resolve_executable_path("notepad")
    assert notepad is not None
    # Missing app returns None
    assert launcher.resolve_executable_path("definitely_not_installed_12345.exe") is None

