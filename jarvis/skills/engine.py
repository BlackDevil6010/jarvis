"""Workflow execution engine for Skill Forge.

Executes multi-step skills with validation, progress updates, safe cancellation,
dry-run preview, sensitive action confirmation, and strict failure handling.
"""

import time
from typing import Optional, Callable, Dict, Any, Union
from jarvis.skills.models import (
    Skill, SkillStep, SkillExecutionResult, StepExecutionResult,
    StepStatus, WorkflowStatus
)
from jarvis.skills.action_registry import ActionRegistry, ActionResult
from jarvis.skills.storage import SkillStorage


class CancellationToken:
    """Thread-safe cancellation token for running workflows."""

    def __init__(self):
        self._is_cancelled = False

    def cancel(self) -> None:
        self._is_cancelled = True

    @property
    def is_cancelled(self) -> bool:
        return self._is_cancelled

    def reset(self) -> None:
        self._is_cancelled = False


class SkillExecutionEngine:
    """Orchestrates safe, ordered execution of user-defined workflows."""

    def __init__(
        self,
        registry: Optional[ActionRegistry] = None,
        storage: Optional[SkillStorage] = None
    ):
        self.registry = registry or ActionRegistry()
        self.storage = storage or SkillStorage()

    def execute_skill(
        self,
        skill_or_id: Union[Skill, str],
        dry_run: bool = False,
        cancellation_token: Optional[CancellationToken] = None,
        step_progress_callback: Optional[Callable[[SkillStep, str, str], None]] = None,
        confirmation_callback: Optional[Callable[[SkillStep], bool]] = None
    ) -> SkillExecutionResult:
        """
        Execute a skill with step-by-step progress, strict validation, and failure prevention.
        """
        token = cancellation_token or CancellationToken()

        # 1. Resolve skill
        if isinstance(skill_or_id, str):
            skill = self.storage.get_skill(skill_or_id)
            if not skill:
                result = SkillExecutionResult(
                    skill_id=skill_or_id,
                    skill_name="Unknown Skill",
                    status=WorkflowStatus.FAILED,
                    is_dry_run=dry_run
                )
                result.finalize(WorkflowStatus.FAILED, error_message=f"Skill ID '{skill_or_id}' was not found.")
                return result
        else:
            skill = skill_or_id

        result = SkillExecutionResult(
            skill_id=skill.id,
            skill_name=skill.name,
            status=WorkflowStatus.RUNNING,
            is_dry_run=dry_run
        )

        # 2. Refuse execution of disabled skills
        if not skill.enabled:
            err_msg = f"Refusing to execute disabled skill: '{skill.name}'. Enable the skill first."
            result.finalize(WorkflowStatus.FAILED, error_message=err_msg)
            self.storage.record_execution(result)
            return result

        # 3. Check for empty workflow
        if not skill.steps:
            result.finalize(
                WorkflowStatus.FAILED,
                error_message=f"Skill '{skill.name}' has no defined action steps."
            )
            self.storage.record_execution(result)
            return result

        # 4. Pre-execution static validation of all steps (reject unapproved actions upfront)
        sorted_steps = sorted(skill.steps, key=lambda s: s.order)
        for step in sorted_steps:
            is_valid, validation_err = self.registry.validate_action(step.action_type, step.arguments)
            if not is_valid:
                err_msg = (
                    f"Pre-execution validation failed at step {step.order} "
                    f"({step.label or step.action_type}): {validation_err}"
                )
                result.finalize(WorkflowStatus.FAILED, error_message=err_msg)
                self.storage.record_execution(result)
                return result

        # 5. Execute steps in sequential order
        has_failed = False
        was_cancelled = False

        for i, step in enumerate(sorted_steps):
            # Check for cancellation before starting step
            if token.is_cancelled:
                was_cancelled = True
                self._mark_remaining_skipped(sorted_steps[i:], result, step_progress_callback, "Cancelled before execution")
                break

            action_def = self.registry.get_action(step.action_type)
            requires_confirm = step.require_confirmation or (action_def.is_sensitive if action_def else False)

            # Require explicit confirmation for sensitive actions if not dry-run
            if requires_confirm and not dry_run:
                if confirmation_callback:
                    confirmed = confirmation_callback(step)
                    if not confirmed:
                        was_cancelled = True
                        step_result = StepExecutionResult(
                            step_id=step.id,
                            step_order=step.order,
                            action_type=step.action_type,
                            label=step.label,
                            status=StepStatus.CANCELLED,
                            message="User declined confirmation for sensitive action."
                        )
                        result.add_step_result(step_result)
                        if step_progress_callback:
                            step_progress_callback(step, StepStatus.CANCELLED, step_result.message)
                        self._mark_remaining_skipped(sorted_steps[i+1:], result, step_progress_callback, "Previous step confirmation declined")
                        break
                else:
                    # No confirmation callback provided for a sensitive step -> halt safely
                    has_failed = True
                    step_result = StepExecutionResult(
                        step_id=step.id,
                        step_order=step.order,
                        action_type=step.action_type,
                        label=step.label,
                        status=StepStatus.FAILED,
                        message="Sensitive action requires confirmation, but no confirmation handler is attached."
                    )
                    result.add_step_result(step_result)
                    if step_progress_callback:
                        step_progress_callback(step, StepStatus.FAILED, step_result.message)
                    self._mark_remaining_skipped(sorted_steps[i+1:], result, step_progress_callback, "Aborted due to unconfirmed sensitive action")
                    break

            # Update progress to RUNNING
            step.status = StepStatus.RUNNING
            if step_progress_callback:
                step_progress_callback(step, StepStatus.RUNNING, "Executing action...")

            start_time = time.time()
            action_result: ActionResult = self.registry.execute(
                action_type=step.action_type,
                arguments=step.arguments,
                dry_run=dry_run,
                cancellation_token=token
            )
            duration = round(time.time() - start_time, 3)

            # Check if execution was interrupted during the step
            if token.is_cancelled:
                was_cancelled = True
                step_result = StepExecutionResult(
                    step_id=step.id,
                    step_order=step.order,
                    action_type=step.action_type,
                    label=step.label,
                    status=StepStatus.CANCELLED,
                    message="Step interrupted by cancellation request.",
                    duration_seconds=duration
                )
                result.add_step_result(step_result)
                if step_progress_callback:
                    step_progress_callback(step, StepStatus.CANCELLED, step_result.message)
                self._mark_remaining_skipped(sorted_steps[i+1:], result, step_progress_callback, "Cancelled after step interruption")
                break

            if action_result.success:
                step.status = StepStatus.SUCCEEDED
                step_result = StepExecutionResult(
                    step_id=step.id,
                    step_order=step.order,
                    action_type=step.action_type,
                    label=step.label,
                    status=StepStatus.SUCCEEDED,
                    message=action_result.message,
                    data=action_result.data,
                    duration_seconds=duration
                )
                result.add_step_result(step_result)
                if step_progress_callback:
                    step_progress_callback(step, StepStatus.SUCCEEDED, action_result.message)
            else:
                has_failed = True
                step.status = StepStatus.FAILED
                step_result = StepExecutionResult(
                    step_id=step.id,
                    step_order=step.order,
                    action_type=step.action_type,
                    label=step.label,
                    status=StepStatus.FAILED,
                    message=action_result.message,
                    data=action_result.data,
                    duration_seconds=duration
                )
                result.add_step_result(step_result)
                if step_progress_callback:
                    step_progress_callback(step, StepStatus.FAILED, action_result.message)

                # Safe stop on failure: skip all remaining steps
                self._mark_remaining_skipped(
                    sorted_steps[i+1:],
                    result,
                    step_progress_callback,
                    f"Skipped because step {step.order} failed"
                )
                break

        # 6. Finalize overall status
        if was_cancelled:
            result.finalize(WorkflowStatus.CANCELLED, error_message="Workflow execution cancelled by user.")
        elif has_failed:
            failed_step = next((r for r in result.step_results if r.status == StepStatus.FAILED), None)
            err = failed_step.message if failed_step else "One or more steps failed."
            result.finalize(WorkflowStatus.FAILED, error_message=f"Workflow halted: {err}")
        else:
            final_status = WorkflowStatus.DRY_RUN if dry_run else WorkflowStatus.SUCCEEDED
            result.finalize(final_status)

        # 7. Record in history
        self.storage.record_execution(result)
        return result

    def _mark_remaining_skipped(
        self,
        remaining_steps: list,
        result: SkillExecutionResult,
        step_progress_callback: Optional[Callable],
        reason: str
    ) -> None:
        """Mark remaining steps as SKIPPED when a step fails or is cancelled."""
        for step in remaining_steps:
            step.status = StepStatus.SKIPPED
            step_result = StepExecutionResult(
                step_id=step.id,
                step_order=step.order,
                action_type=step.action_type,
                label=step.label,
                status=StepStatus.SKIPPED,
                message=reason
            )
            result.add_step_result(step_result)
            if step_progress_callback:
                step_progress_callback(step, StepStatus.SKIPPED, reason)
