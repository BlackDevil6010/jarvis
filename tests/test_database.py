"""Automated tests for JARVIS SQLite database layer."""

import tempfile
from pathlib import Path
import pytest
from jarvis.core.database import Database


@pytest.fixture
def temp_db():
    """Create an isolated temporary SQLite database for testing."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = Path(tmp_dir) / "test_jarvis.db"
        db = Database(db_path=db_path)
        yield db
        del db
        import gc
        gc.collect()


def test_database_initialization_and_seeding(temp_db):
    """Verify that database seeds default applications on creation."""
    apps = temp_db.get_all_applications()
    assert len(apps) >= 4
    names = [app["name"] for app in apps]
    assert "Notepad" in names
    assert "Calculator" in names
    assert "File Explorer" in names


def test_get_application_by_name_and_alias(temp_db):
    """Verify exact name and alias matching."""
    # Exact name
    app = temp_db.get_application_by_name("Notepad")
    assert app is not None
    assert app["name"] == "Notepad"

    # Case-insensitive
    app_lower = temp_db.get_application_by_name("calculator")
    assert app_lower is not None
    assert app_lower["name"] == "Calculator"

    # By alias
    app_alias = temp_db.get_application_by_name("calc")
    assert app_alias is not None
    assert app_alias["name"] == "Calculator"

    # Non-existent app
    assert temp_db.get_application_by_name("NonExistentToolXYZ") is None


def test_add_and_delete_application(temp_db):
    """Verify adding custom application and deleting it."""
    temp_db.add_or_update_application(
        name="Custom App",
        path="C:\\Tools\\app.exe",
        aliases=["mytool", "custom"],
        description="A custom utility"
    )

    found = temp_db.get_application_by_name("mytool")
    assert found is not None
    assert found["name"] == "Custom App"
    assert found["path"] == "C:\\Tools\\app.exe"

    # Delete
    deleted = temp_db.delete_application("Custom App")
    assert deleted is True
    assert temp_db.get_application_by_name("Custom App") is None


def test_record_command_history(temp_db):
    """Verify command logging to SQLite history."""
    temp_db.record_command("open notepad", "SUCCESS_LAUNCH")
    with temp_db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM command_history WHERE command = ?", ("open notepad",))
        row = cursor.fetchone()
        assert row is not None
        assert row["status"] == "SUCCESS_LAUNCH"
