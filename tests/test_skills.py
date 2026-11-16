"""Automated tests for Skill Forge models, storage, action registry, and execution engine."""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from jarvis.core.database import Database
from jarvis.core.launcher import AppLauncher, LaunchResult
from jarvis.skills.models import (
    Skill, SkillStep, StepStatus, WorkflowStatus
)
from jarvis.skills.storage import SkillStorage
from jarvis.skills.action_registry import ActionRegistry, ActionDefinition, ActionResult
from jarvis.skills.engine import SkillExecutionEngine, CancellationToken


@pytest.fixture
def skill_system_fixture():
    """Provides isolated DB, storage, registry, and execution engine."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = Path(tmp_dir) / "test_skills.db"
        db = Database(db_path=db_path)
        storage = SkillStorage(db=db)
        launcher = AppLauncher(db=db)
        registry = ActionRegistry(launcher=launcher)
        engine = SkillExecutionEngine(registry=registry, storage=storage)
        yield {
            "db": db,
            "storage": storage,
            "launcher": launcher,
            "registry": registry,
            "engine": engine,
            "db_path": db_path
        }
        del engine
        del registry
        del launcher
        del storage
        del db
        import gc
        gc.collect()


# 1. Creating and saving a valid skill
def test_create_and_save_valid_skill(skill_system_fixture):
    storage: SkillStorage = skill_system_fixture["storage"]

    skill = Skill(
        name="Focus Session",
        description="Launch editor and diagnostics",
        enabled=True,
        steps=[
            SkillStep(
                action_type="log_message",
                order=1,
                label="Notify",
                arguments={"message": "Starting focus"}
            ),
            SkillStep(
                action_type="launch_app",
                order=2,
                label="Launch Notepad",
                arguments={"app_name": "Notepad"}
            )
        ]
    )
    storage.save_skill(skill)

    retrieved = storage.get_skill(skill.id)
    assert retrieved is not None
    assert retrieved.name == "Focus Session"
    assert len(retrieved.steps) == 2
    assert retrieved.steps[0].action_type == "log_message"
    assert retrieved.steps[1].action_type == "launch_app"


# 2. Editing and deleting a skill
def test_edit_and_delete_skill(skill_system_fixture):
    storage: SkillStorage = skill_system_fixture["storage"]

    skill = Skill(name="Temp Workflow", description="To be edited")
    storage.save_skill(skill)

    # Edit
    skill.name = "Renamed Workflow"
    skill.description = "Updated description"
    storage.save_skill(skill)

    updated = storage.get_skill(skill.id)
    assert updated.name == "Renamed Workflow"
    assert updated.description == "Updated description"

    # Delete
    deleted = storage.delete_skill(skill.id)
    assert deleted is True
    assert storage.get_skill(skill.id) is None


# 3. Persistence across application restarts / DB reconnection
def test_persistence_across_reconnection(skill_system_fixture):
    db_path = skill_system_fixture["db_path"]
    storage: SkillStorage = skill_system_fixture["storage"]

    custom_skill = Skill(
        name="Persistent Skill",
        description="Must survive process restarts",
        steps=[
            SkillStep(
                action_type="log_message",
                order=1,
                label="Step One",
                arguments={"message": "Alive"}
            )
        ]
    )
    storage.save_skill(custom_skill)

    # Simulate fresh restart with new storage instance pointing to same file
    new_db = Database(db_path=db_path)
    new_storage = SkillStorage(db=new_db)
    reloaded = new_storage.get_skill_by_name("Persistent Skill")

    assert reloaded is not None
    assert reloaded.name == "Persistent Skill"
    assert len(reloaded.steps) == 1
    assert reloaded.steps[0].arguments["message"] == "Alive"


# 4. Enabling and disabling skills
def test_enable_disable_skill(skill_system_fixture):
    storage: SkillStorage = skill_system_fixture["storage"]

    skill = Skill(name="Toggleable Skill", enabled=True)
    storage.save_skill(skill)

    # Disable
    storage.set_skill_enabled(skill.id, False)
    assert storage.get_skill(skill.id).enabled is False

    # Re-enable
    storage.set_skill_enabled(skill.id, True)
    assert storage.get_skill(skill.id).enabled is True


# 5. Validation of missing or invalid arguments
def test_argument_validation(skill_system_fixture):
    registry: ActionRegistry = skill_system_fixture["registry"]

    # Missing required argument for launch_app
    is_valid, err = registry.validate_action("launch_app", {})
    assert is_valid is False
    assert "missing required parameter 'app_name'" in err.lower()

    # Empty string for required argument
    is_valid, err = registry.validate_action("launch_app", {"app_name": "   "})
    assert is_valid is False
    assert "cannot be empty" in err.lower()

    # Valid arguments
    is_valid, err = registry.validate_action("launch_app", {"app_name": "Notepad"})
    assert is_valid is True
    assert err is None


# 6. Rejection of unregistered action types
def test_rejection_of_unregistered_action(skill_system_fixture):
    registry: ActionRegistry = skill_system_fixture["registry"]
    engine: SkillExecutionEngine = skill_system_fixture["engine"]

    is_valid, err = registry.validate_action("malicious_arbitrary_shell_command", {})
    assert is_valid is False
    assert "unregistered action type" in err.lower()

    # Skill with invalid action type halts before execution
    invalid_skill = Skill(
        name="Bad Action Skill",
        steps=[
            SkillStep(
                action_type="unknown_action_xyz",
                order=1,
                arguments={}
            )
        ]
    )
    result = engine.execute_skill(invalid_skill)
    assert result.success is False
    assert result.status == WorkflowStatus.FAILED
    assert "validation failed" in result.error_message.lower()


# 7. Ordered execution of multi-step workflow
def test_ordered_execution(skill_system_fixture):
    engine: SkillExecutionEngine = skill_system_fixture["engine"]

    execution_order = []

    def mock_log(args, dry_run, token):
        execution_order.append(args["message"])
        return ActionResult(success=True, message=args["message"])

    skill_system_fixture["registry"].register_action(ActionDefinition(
        action_type="custom_ordered_action",
        display_name="Custom Log",
        description="",
        parameters_schema={"message": {"type": "str", "required": True}},
        handler=mock_log
    ))

    skill = Skill(
        name="Ordered Workflow",
        steps=[
            SkillStep(action_type="custom_ordered_action", order=2, arguments={"message": "Second"}),
            SkillStep(action_type="custom_ordered_action", order=1, arguments={"message": "First"}),
            SkillStep(action_type="custom_ordered_action", order=3, arguments={"message": "Third"}),
        ]
    )

    result = engine.execute_skill(skill)
    assert result.success is True
    assert execution_order == ["First", "Second", "Third"]


# 8. Accurate reporting of successful and failed steps
def test_accurate_reporting_of_step_failure(skill_system_fixture):
    engine: SkillExecutionEngine = skill_system_fixture["engine"]
    launcher: AppLauncher = skill_system_fixture["launcher"]

    # Configure launcher to return failure for an app
    launcher.launch = MagicMock(return_value=LaunchResult(
        success=False,
        message="Executable missing on disk.",
        app_name="NonExistentApp"
    ))

    skill = Skill(
        name="Failure Handling Skill",
        steps=[
            SkillStep(action_type="log_message", order=1, label="Step 1", arguments={"message": "Pre-flight"}),
            SkillStep(action_type="launch_app", order=2, label="Step 2", arguments={"app_name": "NonExistentApp"}),
            SkillStep(action_type="log_message", order=3, label="Step 3", arguments={"message": "Should not run"}),
        ]
    )

    result = engine.execute_skill(skill)
    assert result.success is False
    assert result.status == WorkflowStatus.FAILED
    assert len(result.step_results) == 3

    assert result.step_results[0].status == StepStatus.SUCCEEDED
    assert result.step_results[1].status == StepStatus.FAILED
    assert "executable missing" in result.step_results[1].message.lower()
    # Step 3 must be skipped safely
    assert result.step_results[2].status == StepStatus.SKIPPED
    assert "failed" in result.step_results[2].message.lower()


# 9. Safe cancellation where supported
def test_safe_cancellation(skill_system_fixture):
    engine: SkillExecutionEngine = skill_system_fixture["engine"]
    token = CancellationToken()

    # Cancel token before step 2 runs
    call_count = 0

    def progressive_callback(step, status, msg):
        nonlocal call_count
        if status == StepStatus.RUNNING and step.order == 2:
            token.cancel()

    skill = Skill(
        name="Cancellable Skill",
        steps=[
            SkillStep(action_type="log_message", order=1, arguments={"message": "Step 1"}),
            SkillStep(action_type="delay_step", order=2, arguments={"seconds": 2.0}),
            SkillStep(action_type="log_message", order=3, arguments={"message": "Step 3"}),
        ]
    )

    result = engine.execute_skill(
        skill,
        cancellation_token=token,
        step_progress_callback=progressive_callback
    )

    assert result.status == WorkflowStatus.CANCELLED
    assert result.success is False


# 10. Refusal to execute disabled skill
def test_refuse_disabled_skill(skill_system_fixture):
    engine: SkillExecutionEngine = skill_system_fixture["engine"]

    disabled_skill = Skill(
        name="Disabled Workflow",
        enabled=False,
        steps=[SkillStep(action_type="log_message", order=1, arguments={"message": "No"})]
    )

    result = engine.execute_skill(disabled_skill)
    assert result.success is False
    assert result.status == WorkflowStatus.FAILED
    assert "disabled" in result.error_message.lower()


# 11. Confirmation requirements for sensitive actions
def test_confirmation_requirement_declined(skill_system_fixture):
    engine: SkillExecutionEngine = skill_system_fixture["engine"]

    sensitive_skill = Skill(
        name="Sensitive Workflow",
        steps=[
            SkillStep(
                action_type="log_message",
                order=1,
                label="High Risk Action",
                arguments={"message": "Critical Operation"},
                require_confirmation=True
            )
        ]
    )

    # User declines confirmation
    confirm_callback = MagicMock(return_value=False)

    result = engine.execute_skill(sensitive_skill, confirmation_callback=confirm_callback)
    assert confirm_callback.called
    assert result.status == WorkflowStatus.CANCELLED
    assert result.step_results[0].status == StepStatus.CANCELLED


def test_confirmation_requirement_accepted(skill_system_fixture):
    engine: SkillExecutionEngine = skill_system_fixture["engine"]

    sensitive_skill = Skill(
        name="Sensitive Workflow Approved",
        steps=[
            SkillStep(
                action_type="log_message",
                order=1,
                label="High Risk Action",
                arguments={"message": "Approved Operation"},
                require_confirmation=True
            )
        ]
    )

    # User confirms
    confirm_callback = MagicMock(return_value=True)

    result = engine.execute_skill(sensitive_skill, confirmation_callback=confirm_callback)
    assert confirm_callback.called
    assert result.status == WorkflowStatus.SUCCEEDED
    assert result.step_results[0].status == StepStatus.SUCCEEDED


# 12. Prevention of arbitrary code and shell-command execution
def test_prevention_of_arbitrary_commands(skill_system_fixture):
    registry: ActionRegistry = skill_system_fixture["registry"]

    # Attempts to register shell command / eval
    disallowed_actions = [
        "eval_python_code",
        "exec_shell_command",
        "run_bash_script",
        "powershell_eval"
    ]
    for action_type in disallowed_actions:
        assert registry.get_action(action_type) is None


# 13. Dry-run behavior without side effects
def test_dry_run_behavior(skill_system_fixture):
    engine: SkillExecutionEngine = skill_system_fixture["engine"]
    launcher: AppLauncher = skill_system_fixture["launcher"]

    # Mock real launch to verify it is NOT called during dry-run
    launcher.launch = MagicMock()

    skill = Skill(
        name="Dry Run Test",
        steps=[
            SkillStep(action_type="launch_app", order=1, arguments={"app_name": "Notepad"}),
            SkillStep(action_type="system_diagnostics", order=2, arguments={})
        ]
    )

    result = engine.execute_skill(skill, dry_run=True)
    assert result.is_dry_run is True
    assert result.status == WorkflowStatus.DRY_RUN
    assert result.success is True
    assert launcher.launch.call_count == 0  # Crucial: NO real launch performed!

    for sr in result.step_results:
        assert "[DRY-RUN PREVIEW]" in sr.message


# 14. Duplicate skill
def test_duplicate_skill(skill_system_fixture):
    storage: SkillStorage = skill_system_fixture["storage"]

    original = Skill(
        name="Original Skill",
        description="Master template",
        steps=[SkillStep(action_type="log_message", order=1, arguments={"message": "Hi"})]
    )
    storage.save_skill(original)

    clone = storage.duplicate_skill(original.id)
    assert clone is not None
    assert clone.id != original.id
    assert clone.name == "Original Skill (Copy)"
    assert len(clone.steps) == 1
