"""Data models and validation schemas for Skill Forge."""

from datetime import datetime
from typing import Dict, Any, List, Optional
import uuid
import re

try:
    from pydantic import BaseModel, Field, field_validator
    PYDANTIC_AVAILABLE = True
except ImportError:
    PYDANTIC_AVAILABLE = False


class StepStatus:
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    SKIPPED = "SKIPPED"


class WorkflowStatus:
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    DRY_RUN = "DRY_RUN"
    RUNNING = "RUNNING"


if PYDANTIC_AVAILABLE:
    class SkillStep(BaseModel):
        """Represents a single executable action step within a workflow."""
        id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
        order: int = Field(default=1, ge=1)
        action_type: str = Field(..., min_length=1)
        label: str = Field(default="")
        arguments: Dict[str, Any] = Field(default_factory=dict)
        require_confirmation: bool = Field(default=False)
        status: str = Field(default=StepStatus.PENDING)

        @field_validator("action_type")
        @classmethod
        def validate_action_type(cls, v: str) -> str:
            clean = v.strip().lower()
            if not clean:
                raise ValueError("Action type cannot be empty")
            if not re.match(r"^[a-z0-9_]+$", clean):
                raise ValueError("Action type must contain only lowercase letters, digits, and underscores")
            return clean

        @field_validator("label")
        @classmethod
        def sanitize_label(cls, v: str) -> str:
            return v.strip() if v else ""

    class Skill(BaseModel):
        """Represents a saved, reusable user workflow."""
        id: str = Field(default_factory=lambda: str(uuid.uuid4()))
        name: str = Field(..., min_length=1, max_length=100)
        description: str = Field(default="")
        enabled: bool = Field(default=True)
        steps: List[SkillStep] = Field(default_factory=list)
        created_at: str = Field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        updated_at: str = Field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

        @field_validator("name")
        @classmethod
        def validate_name(cls, v: str) -> str:
            clean = v.strip()
            if not clean:
                raise ValueError("Skill name cannot be empty or blank")
            if len(clean) > 100:
                raise ValueError("Skill name cannot exceed 100 characters")
            return clean

else:
    # Pure Python fallback with full manual validation if Pydantic is not yet loaded
    class SkillStep:
        def __init__(
            self,
            action_type: str,
            order: int = 1,
            label: str = "",
            arguments: Optional[Dict[str, Any]] = None,
            require_confirmation: bool = False,
            status: str = StepStatus.PENDING,
            id: Optional[str] = None
        ):
            clean_type = action_type.strip().lower()
            if not clean_type:
                raise ValueError("Action type cannot be empty")
            if not re.match(r"^[a-z0-9_]+$", clean_type):
                raise ValueError("Action type must contain only lowercase letters, digits, and underscores")

            self.id = id or str(uuid.uuid4())[:8]
            self.order = max(1, int(order))
            self.action_type = clean_type
            self.label = label.strip() if label else ""
            self.arguments = arguments or {}
            self.require_confirmation = bool(require_confirmation)
            self.status = status

        def model_dump(self) -> Dict[str, Any]:
            return {
                "id": self.id,
                "order": self.order,
                "action_type": self.action_type,
                "label": self.label,
                "arguments": self.arguments,
                "require_confirmation": self.require_confirmation,
                "status": self.status,
            }

    class Skill:
        def __init__(
            self,
            name: str,
            description: str = "",
            enabled: bool = True,
            steps: Optional[List[SkillStep]] = None,
            id: Optional[str] = None,
            created_at: Optional[str] = None,
            updated_at: Optional[str] = None
        ):
            clean_name = name.strip()
            if not clean_name:
                raise ValueError("Skill name cannot be empty or blank")
            if len(clean_name) > 100:
                raise ValueError("Skill name cannot exceed 100 characters")

            self.id = id or str(uuid.uuid4())
            self.name = clean_name
            self.description = description.strip() if description else ""
            self.enabled = bool(enabled)
            self.steps = steps or []
            self.created_at = created_at or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.updated_at = updated_at or datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        def model_dump(self) -> Dict[str, Any]:
            return {
                "id": self.id,
                "name": self.name,
                "description": self.description,
                "enabled": self.enabled,
                "steps": [s.model_dump() if hasattr(s, "model_dump") else s.__dict__ for s in self.steps],
                "created_at": self.created_at,
                "updated_at": self.updated_at,
            }


class StepExecutionResult:
    """Outcome of an individual workflow step."""
    def __init__(
        self,
        step_id: str,
        step_order: int,
        action_type: str,
        label: str,
        status: str,
        message: str,
        data: Optional[Dict[str, Any]] = None,
        duration_seconds: float = 0.0
    ):
        self.step_id = step_id
        self.step_order = step_order
        self.action_type = action_type
        self.label = label
        self.status = status
        self.message = message
        self.data = data or {}
        self.duration_seconds = duration_seconds

    def to_dict(self) -> Dict[str, Any]:
        return {
            "step_id": self.step_id,
            "step_order": self.step_order,
            "action_type": self.action_type,
            "label": self.label,
            "status": self.status,
            "message": self.message,
            "data": self.data,
            "duration_seconds": self.duration_seconds,
        }


class SkillExecutionResult:
    """Outcome of an entire workflow run."""
    def __init__(
        self,
        skill_id: str,
        skill_name: str,
        status: str,
        is_dry_run: bool = False,
        execution_id: Optional[str] = None
    ):
        self.execution_id = execution_id or str(uuid.uuid4())[:8]
        self.skill_id = skill_id
        self.skill_name = skill_name
        self.status = status
        self.is_dry_run = is_dry_run
        self.started_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.completed_at = self.started_at
        self.step_results: List[StepExecutionResult] = []
        self.error_message: Optional[str] = None

    @property
    def success(self) -> bool:
        return self.status in [WorkflowStatus.SUCCEEDED, WorkflowStatus.DRY_RUN]

    def add_step_result(self, result: StepExecutionResult) -> None:
        self.step_results.append(result)

    def finalize(self, status: str, error_message: Optional[str] = None) -> None:
        self.status = status
        self.error_message = error_message
        self.completed_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "execution_id": self.execution_id,
            "skill_id": self.skill_id,
            "skill_name": self.skill_name,
            "status": self.status,
            "is_dry_run": self.is_dry_run,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "step_results": [r.to_dict() for r in self.step_results],
            "error_message": self.error_message,
            "success": self.success,
        }
