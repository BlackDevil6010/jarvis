"""GUI initialization and integration tests with PySide6."""

import os
import sys
import tempfile
from pathlib import Path
import pytest

from PySide6.QtWidgets import QApplication

from jarvis.core.database import Database
from jarvis.core.launcher import AppLauncher
from jarvis.core.command_processor import CommandProcessor
from jarvis.skills.storage import SkillStorage
from jarvis.skills.action_registry import ActionRegistry
from jarvis.ui.main_window import MainWindow
from jarvis.ui.skills.skill_forge_view import SkillForgeView
from jarvis.ui.skills.skill_dialog import SkillDialog
from jarvis.ui.skills.step_dialog import StepDialog


@pytest.fixture(scope="session")
def qapp():
    """Ensure a single QApplication instance exists for headless/GUI testing."""
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    yield app


@pytest.fixture
def test_environment():
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = Path(tmp_dir) / "gui_test.db"
        db = Database(db_path=db_path)
        storage = SkillStorage(db=db)
        launcher = AppLauncher(db=db)
        processor = CommandProcessor(launcher=launcher, db=db)
        registry = ActionRegistry(launcher=launcher)
        yield {
            "db": db,
            "storage": storage,
            "launcher": launcher,
            "processor": processor,
            "registry": registry,
            "db_path": db_path
        }
        del registry
        del processor
        del launcher
        del storage
        del db
        import gc
        gc.collect()


def test_main_window_instantiation(qapp, test_environment):
    """Verify MainWindow initializes and can switch between HUD and Skill Forge views."""
    processor = test_environment["processor"]
    window = MainWindow(processor=processor)
    assert window is not None
    assert window.windowTitle().startswith("O.M.E.N.") or window.windowTitle().startswith("J.A.R.V.I.S.")

    # Check stacked widget pages
    assert window.stacked_widget.count() == 2

    # Switch to Skill Forge view
    window.switch_view(1)
    assert window.stacked_widget.currentIndex() == 1
    assert window.nav_skills_btn.isChecked() is True
    assert window.nav_hud_btn.isChecked() is False

    # Switch back to HUD view
    window.switch_view(0)
    assert window.stacked_widget.currentIndex() == 0
    assert window.nav_hud_btn.isChecked() is True
    assert window.nav_skills_btn.isChecked() is False

    window.close()


def test_skill_forge_view_components(qapp, test_environment):
    """Verify SkillForgeView loads skills, populates steps, and provides functional controls."""
    storage = test_environment["storage"]
    registry = test_environment["registry"]

    view = SkillForgeView(storage=storage, registry=registry)
    assert view is not None

    # Check that skills list has seeded items
    assert view.skill_list.count() >= 2

    # Select first skill
    view.skill_list.setCurrentRow(0)
    assert view.current_skill is not None
    assert view.steps_table.rowCount() >= 1

    view.close()


def test_skill_dialog_creation(qapp):
    """Verify SkillDialog instantiates and validates properly."""
    dialog = SkillDialog()
    assert dialog is not None
    dialog.name_input.setText("New Coding Routine")
    dialog.desc_input.setPlainText("Routine description")
    dialog.on_save()
    assert dialog.skill is not None
    assert dialog.skill.name == "New Coding Routine"
    dialog.close()


def test_step_dialog_creation(qapp, test_environment):
    """Verify StepDialog instantiates and configures approved action types."""
    registry = test_environment["registry"]
    dialog = StepDialog(registry=registry, step_order=1)
    assert dialog is not None

    # Set action to launch_app
    idx = dialog.action_combo.findData("launch_app")
    assert idx >= 0
    dialog.action_combo.setCurrentIndex(idx)
    dialog.app_name_combo.setEditText("Notepad")
    dialog.on_save()

    assert dialog.step is not None
    assert dialog.step.action_type == "launch_app"
    assert dialog.step.arguments["app_name"] == "Notepad"
    dialog.close()


def test_logo_integration_and_aspect_ratio(qapp, test_environment):
    """Verify that assets/branding/jarvis_logo.png exists, uses relative paths, and preserves aspect ratio."""
    from jarvis.config import LOGO_PATH, BASE_DIR

    # 1. Verify existence
    assert LOGO_PATH.exists(), f"Logo must exist at {LOGO_PATH}"
    assert LOGO_PATH.is_file()

    # 2. Verify relative project structure (not tied to fixed developer machine paths)
    assert LOGO_PATH.is_relative_to(BASE_DIR)

    # 3. Verify MainWindow icon and header logo
    processor = test_environment["processor"]
    window = MainWindow(processor=processor)
    assert not window.windowIcon().isNull()
    assert hasattr(window, "logo_label")
    assert not window.logo_label.pixmap().isNull()
    # Aspect ratio should be 1:1
    pixmap = window.logo_label.pixmap()
    assert pixmap.width() == pixmap.height()

    # 4. Verify ConsoleView banner has logo markup
    console = window.console_view
    assert "jarvis_logo.png" in console.toHtml().lower()

    window.close()


def test_command_input_and_send_button(qapp, test_environment):
    """Verify entering commands, clicking Send, and checking console feedback."""
    import time
    processor = test_environment["processor"]
    window = MainWindow(processor=processor)
    window.show()

    window.command_input.setText("status")
    window.send_button.click()

    # Process events while worker runs
    start = time.time()
    while window.active_worker and window.active_worker.isRunning() and time.time() - start < 3:
        qapp.processEvents()
        time.sleep(0.05)
    qapp.processEvents()

    assert window.command_input.text() == ""
    console_text = window.console_view.toPlainText()
    assert "USER > status" in console_text
    assert "operational" in console_text.lower()
    window.close()


