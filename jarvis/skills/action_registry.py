"""Extensible Action Registry for Skill Forge with typed schema validation."""

import os
import time
from pathlib import Path
from typing import Dict, Any, Callable, Optional, List
from jarvis.core.launcher import AppLauncher, LaunchResult
from jarvis.core.system_info import SystemInfoCollector


class ActionResult:
    """Standardized output from an action handler execution."""
    def __init__(self, success: bool, message: str, data: Optional[Dict[str, Any]] = None):
        self.success = success
        self.message = message
        self.data = data or {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "message": self.message,
            "data": self.data,
        }

    def __repr__(self) -> str:
        return f"<ActionResult success={self.success} msg='{self.message}'>"


class ActionDefinition:
    """Metadata, validation schema, and handler for an approved action."""
    def __init__(
        self,
        action_type: str,
        display_name: str,
        description: str,
        parameters_schema: Dict[str, Any],
        handler: Callable[[Dict[str, Any], bool, Any], ActionResult],
        is_sensitive: bool = False
    ):
        self.action_type = action_type
        self.display_name = display_name
        self.description = description
        self.parameters_schema = parameters_schema
        self.handler = handler
        self.is_sensitive = is_sensitive

    def to_dict(self) -> Dict[str, Any]:
        return {
            "action_type": self.action_type,
            "display_name": self.display_name,
            "description": self.description,
            "parameters_schema": self.parameters_schema,
            "is_sensitive": self.is_sensitive,
        }


class ActionRegistry:
    """Maintains approved actions, enforces argument validation, and executes handlers."""

    def __init__(self, launcher: Optional[AppLauncher] = None):
        self.launcher = launcher or AppLauncher()
        self._actions: Dict[str, ActionDefinition] = {}
        self._register_default_actions()

    def register_action(self, action_def: ActionDefinition) -> None:
        """Register an action definition in the allowlist."""
        self._actions[action_def.action_type.lower()] = action_def

    def get_action(self, action_type: str) -> Optional[ActionDefinition]:
        """Look up registered action definition."""
        return self._actions.get(action_type.strip().lower())

    def get_all_actions(self) -> List[ActionDefinition]:
        """Return list of all registered actions."""
        return list(self._actions.values())

    def validate_action(self, action_type: str, arguments: Dict[str, Any]) -> tuple[bool, Optional[str]]:
        """Strictly validate action type and required parameters."""
        action = self.get_action(action_type)
        if not action:
            return False, f"Unregistered action type '{action_type}'. Only approved actions are permitted."

        schema = action.parameters_schema
        # Check required fields
        for param_name, param_info in schema.items():
            if param_info.get("required", False):
                if param_name not in arguments or arguments[param_name] is None:
                    return False, f"Missing required parameter '{param_name}' for action '{action_type}'."
                val = arguments[param_name]
                if isinstance(val, str) and not val.strip():
                    return False, f"Parameter '{param_name}' cannot be empty."

            # Value-specific validation
            if param_name in arguments and arguments[param_name] is not None:
                expected_type = param_info.get("type")
                val = arguments[param_name]
                if expected_type == "int" and not isinstance(val, int):
                    try:
                        arguments[param_name] = int(val)
                    except (ValueError, TypeError):
                        return False, f"Parameter '{param_name}' must be an integer."
                elif expected_type == "float" and not isinstance(val, (int, float)):
                    try:
                        arguments[param_name] = float(val)
                    except (ValueError, TypeError):
                        return False, f"Parameter '{param_name}' must be a numeric value."

        return True, None

    def execute(
        self,
        action_type: str,
        arguments: Dict[str, Any],
        dry_run: bool = False,
        cancellation_token: Any = None
    ) -> ActionResult:
        """Execute action handler with validation and dry-run support."""
        is_valid, error_msg = self.validate_action(action_type, arguments)
        if not is_valid:
            return ActionResult(success=False, message=error_msg or "Validation failed")

        action = self.get_action(action_type)
        if not action:
            return ActionResult(success=False, message=f"Action '{action_type}' not found")

        try:
            return action.handler(arguments, dry_run, cancellation_token)
        except Exception as e:
            return ActionResult(success=False, message=f"Unhandled error executing '{action_type}': {str(e)}")

    def _register_default_actions(self) -> None:
        """Initialize approved built-in actions."""

        # 1. Launch Application
        def handle_launch_app(args: Dict[str, Any], dry_run: bool, token: Any) -> ActionResult:
            app_name = str(args.get("app_name", "")).strip()
            if dry_run:
                app = self.launcher.db.get_application_by_name(app_name)
                if not app:
                    return ActionResult(
                        success=False,
                        message=f"[DRY-RUN PREVIEW] App '{app_name}' is not registered in O.M.E.N."
                    )
                resolved = self.launcher.resolve_executable_path(app["path"])
                if not resolved:
                    return ActionResult(
                        success=False,
                        message=f"[DRY-RUN PREVIEW] Target executable for '{app_name}' ('{app['path']}') does not exist on disk."
                    )
                return ActionResult(
                    success=True,
                    message=f"[DRY-RUN PREVIEW] Would launch '{app['name']}' ({resolved}).",
                    data={"app_name": app["name"], "resolved_path": resolved}
                )

            # Live execution
            res: LaunchResult = self.launcher.launch(app_name)
            return ActionResult(success=res.success, message=res.message, data=res.to_dict())

        self.register_action(ActionDefinition(
            action_type="launch_app",
            display_name="Launch Desktop Application",
            description="Launch a registered application (Notepad, Calculator, File Explorer, etc.)",
            parameters_schema={
                "app_name": {
                    "type": "str",
                    "required": True,
                    "description": "Name or alias of registered application"
                }
            },
            handler=handle_launch_app,
            is_sensitive=False
        ))

        # 2. Open Folder
        def handle_open_folder(args: Dict[str, Any], dry_run: bool, token: Any) -> ActionResult:
            raw_path = str(args.get("folder_path", "")).strip()
            expanded_path = os.path.expandvars(os.path.expanduser(raw_path))
            target = Path(expanded_path).resolve()

            if not target.exists():
                return ActionResult(
                    success=False,
                    message=f"Target directory '{target}' does not exist on this machine."
                )
            if not target.is_dir():
                return ActionResult(
                    success=False,
                    message=f"Specified path '{target}' is a file, not a directory."
                )

            if dry_run:
                return ActionResult(
                    success=True,
                    message=f"[DRY-RUN PREVIEW] Would open folder: {target}",
                    data={"path": str(target)}
                )

            # Live execution: open folder in Windows Explorer without shell execution
            try:
                import subprocess
                explorer_exe = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "explorer.exe")
                proc = subprocess.Popen(
                    [explorer_exe, str(target)],
                    shell=False,
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
                return ActionResult(
                    success=True,
                    message=f"Opened folder '{target}' in File Explorer.",
                    data={"path": str(target), "pid": proc.pid}
                )
            except Exception as e:
                return ActionResult(success=False, message=f"Failed to open folder: {str(e)}")

        self.register_action(ActionDefinition(
            action_type="open_folder",
            display_name="Open Directory / Folder",
            description="Open a validated directory on disk in Windows File Explorer",
            parameters_schema={
                "folder_path": {
                    "type": "str",
                    "required": True,
                    "description": "Path to folder on disk (e.g., C:\\Projects or %USERPROFILE%\\Documents)"
                }
            },
            handler=handle_open_folder,
            is_sensitive=False
        ))

        # 3. System Diagnostics
        def handle_system_diagnostics(args: Dict[str, Any], dry_run: bool, token: Any) -> ActionResult:
            if dry_run:
                return ActionResult(
                    success=True,
                    message="[DRY-RUN PREVIEW] Would collect live CPU, memory, disk, and OS diagnostics."
                )
            report = SystemInfoCollector.get_formatted_report()
            summary = SystemInfoCollector.get_system_summary()
            return ActionResult(
                success=True,
                message=report,
                data=summary
            )

        self.register_action(ActionDefinition(
            action_type="system_diagnostics",
            display_name="System Diagnostics",
            description="Collect and report real-time host hardware, memory, and CPU metrics",
            parameters_schema={},
            handler=handle_system_diagnostics,
            is_sensitive=False
        ))

        # 4. Log Message
        def handle_log_message(args: Dict[str, Any], dry_run: bool, token: Any) -> ActionResult:
            msg = str(args.get("message", "")).strip()
            prefix = "[DRY-RUN PREVIEW] Would log: " if dry_run else ""
            return ActionResult(
                success=True,
                message=f"{prefix}{msg}",
                data={"message": msg}
            )

        self.register_action(ActionDefinition(
            action_type="log_message",
            display_name="Log Message",
            description="Echo a notification or progress status message into the workflow activity log",
            parameters_schema={
                "message": {
                    "type": "str",
                    "required": True,
                    "description": "Message text to display"
                }
            },
            handler=handle_log_message,
            is_sensitive=False
        ))

        # 5. Delay Step
        def handle_delay_step(args: Dict[str, Any], dry_run: bool, token: Any) -> ActionResult:
            raw_sec = args.get("seconds", 1.0)
            try:
                seconds = max(0.1, min(60.0, float(raw_sec)))
            except (ValueError, TypeError):
                seconds = 1.0

            if dry_run:
                return ActionResult(
                    success=True,
                    message=f"[DRY-RUN PREVIEW] Would pause execution for {seconds:.1f} second(s).",
                    data={"seconds": seconds}
                )

            # Sleep in small increments to allow cancellation responsiveness
            interval = 0.1
            elapsed = 0.0
            while elapsed < seconds:
                if token and getattr(token, "is_cancelled", False):
                    return ActionResult(
                        success=False,
                        message="Delay cancelled by user request.",
                        data={"interrupted": True}
                    )
                time.sleep(min(interval, seconds - elapsed))
                elapsed += interval

            return ActionResult(
                success=True,
                message=f"Completed wait of {seconds:.1f} second(s).",
                data={"seconds": seconds}
            )

        self.register_action(ActionDefinition(
            action_type="delay_step",
            display_name="Wait / Delay",
            description="Pause workflow execution safely for specified seconds (0.1s to 60s)",
            parameters_schema={
                "seconds": {
                    "type": "float",
                    "required": True,
                    "description": "Number of seconds to pause (max 60)"
                }
            },
            handler=handle_delay_step,
            is_sensitive=False
        ))
