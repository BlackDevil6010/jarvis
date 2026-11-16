"""Automated tests for command parser and security whitelist enforcement."""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock
import pytest

from jarvis.core.database import Database
from jarvis.core.launcher import AppLauncher, LaunchResult
from jarvis.core.command_processor import CommandProcessor


@pytest.fixture
def processor_fixture():
    with tempfile.TemporaryDirectory() as tmp_dir:
        db = Database(db_path=Path(tmp_dir) / "proc_test.db")
        launcher = AppLauncher(db=db)
        processor = CommandProcessor(launcher=launcher, db=db)
        yield processor, launcher, db
        del processor
        del launcher
        del db
        import gc
        gc.collect()


def test_empty_command(processor_fixture):
    processor, _, _ = processor_fixture
    res = processor.process("")
    assert res.success is False
    assert "awaiting command" in res.text.lower()


def test_help_command(processor_fixture):
    processor, _, _ = processor_fixture
    res = processor.process("help")
    assert res.success is True
    assert res.action_type == "help"
    assert "direct" in res.text.lower()


def test_status_command(processor_fixture):
    processor, _, _ = processor_fixture
    res = processor.process("status")
    assert res.success is True
    assert "operational" in res.text.lower()


def test_clear_command(processor_fixture):
    processor, _, _ = processor_fixture
    res = processor.process("clear")
    assert res.success is True
    assert res.action_type == "clear"


def test_system_info_command(processor_fixture):
    processor, _, _ = processor_fixture
    res = processor.process("Show system information")
    assert res.success is True
    assert "system diagnostics" in res.text.lower()
    assert "cpu" in res.text.lower()
    assert "memory" in res.text.lower()


def test_list_apps_command(processor_fixture):
    processor, _, _ = processor_fixture
    res = processor.process("list apps")
    assert res.success is True
    assert "registered application shortcuts" in res.text.lower()
    assert "notepad" in res.text.lower()


def test_open_notepad_command(processor_fixture):
    processor, launcher, _ = processor_fixture
    launcher.launch = MagicMock(return_value=LaunchResult(
        success=True,
        message="Opened Notepad successfully (PID: 1234).",
        app_name="Notepad",
        pid=1234
    ))

    res = processor.process("Open Notepad")
    assert res.success is True
    assert res.action_type == "launch"
    assert "opened notepad" in res.text.lower()
    launcher.launch.assert_called_once_with("Notepad")


def test_security_blocks_shell_operators(processor_fixture):
    processor, _, db = processor_fixture
    dangerous_inputs = [
        "notepad && dir",
        "calc || notepad",
        "echo test | more",
        "notepad; rmdir C:\\",
        "powershell -ExecutionPolicy Bypass",
        "cmd /c whoami",
        "curl http://malicious.site",
        "del /f file.txt"
    ]

    for danger in dangerous_inputs:
        res = processor.process(danger)
        assert res.success is False
        assert res.action_type == "error"
        assert "security protocol" in res.text.lower() or "prohibited" in res.text.lower()


def test_security_rejects_arbitrary_terminal_commands(processor_fixture):
    processor, _, _ = processor_fixture
    arbitrary_terminal_cmds = [
        "dir",
        "ipconfig",
        "netstat",
        "tasklist",
        "whoami"
    ]

    for cmd in arbitrary_terminal_cmds:
        res = processor.process(cmd)
        assert res.success is False
        assert "arbitrary terminal commands are disallowed" in res.text.lower()


def test_list_skills_command(processor_fixture):
    processor, _, db = processor_fixture
    from jarvis.skills.storage import SkillStorage
    from jarvis.skills.models import Skill, SkillStep
    storage = SkillStorage(db=db)
    storage.save_skill(Skill(
        name="Test Workflow Alpha",
        steps=[SkillStep(action_type="log_message", order=1, arguments={"message": "ok"})]
    ))

    res = processor.process("list skills")
    assert res.success is True
    assert "skill forge - registered workflows" in res.text.lower()
    assert "test workflow alpha" in res.text.lower()


def test_run_skill_command(processor_fixture):
    processor, _, db = processor_fixture
    from jarvis.skills.storage import SkillStorage
    from jarvis.skills.models import Skill, SkillStep
    storage = SkillStorage(db=db)
    storage.save_skill(Skill(
        name="Auto Setup",
        steps=[SkillStep(action_type="log_message", order=1, arguments={"message": "Setup Done"})]
    ))

    res = processor.process("run skill Auto Setup")
    assert res.success is True
    assert "skill execution report: auto setup" in res.text.lower()
    assert "setup done" in res.text.lower()


def test_test_skill_command(processor_fixture):
    processor, _, db = processor_fixture
    from jarvis.skills.storage import SkillStorage
    from jarvis.skills.models import Skill, SkillStep
    storage = SkillStorage(db=db)
    storage.save_skill(Skill(
        name="Preview Workflow",
        steps=[SkillStep(action_type="log_message", order=1, arguments={"message": "Preview Message"})]
    ))

    res = processor.process("test skill Preview Workflow")
    assert res.success is True
    assert "dry-run preview" in res.text.lower()

