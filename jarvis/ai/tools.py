"""Structured Tool Registry and execution validator for JARVIS AI Task Engine.

All tools exposed to AI models are strictly registered, schema-validated,
and executed only through approved native interfaces without shell evaluation.
"""

import os
import re
import urllib.parse
import webbrowser
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple, Callable

from jarvis.core.launcher import AppLauncher, LaunchResult
from jarvis.core.system_info import SystemInfoCollector
from jarvis.core.database import Database
from jarvis.skills.storage import SkillStorage
from jarvis.skills.engine import SkillExecutionEngine
from jarvis.skills.models import Skill, SkillStep


class ToolDefinition:
    """Represents a verified, approved tool callable by an AI provider."""

    def __init__(
        self,
        name: str,
        description: str,
        parameters: Dict[str, Any],
        handler: Callable[..., Any],
        requires_confirmation: bool = False
    ):
        self.name = name
        self.description = description
        self.parameters = parameters
        self.handler = handler
        self.requires_confirmation = requires_confirmation

    def to_schema(self) -> Dict[str, Any]:
        """Generate OpenAI/Gemini compatible JSON schema."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            }
        }


class ToolResult:
    """Standard outcome from a tool execution."""

    def __init__(
        self,
        success: bool,
        message: str,
        tool_name: str,
        data: Optional[Dict[str, Any]] = None,
        needs_user_confirmation: bool = False
    ):
        self.success = success
        self.message = message
        self.tool_name = tool_name
        self.data = data or {}
        self.needs_user_confirmation = needs_user_confirmation

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "message": self.message,
            "tool_name": self.tool_name,
            "data": self.data,
            "needs_user_confirmation": self.needs_user_confirmation,
        }

    def __repr__(self) -> str:
        return f"<ToolResult {self.tool_name} success={self.success} msg='{self.message}'>"


class ToolRegistry:
    """Manages and executes approved system actions for the AI assistant."""

    def __init__(self, launcher: Optional[AppLauncher] = None, db: Optional[Database] = None):
        self.db = db or Database()
        self.launcher = launcher or AppLauncher(self.db)
        self.skill_storage = SkillStorage(self.db)
        self.skill_engine = SkillExecutionEngine(self.skill_storage, self.launcher)
        self._tools: Dict[str, ToolDefinition] = {}
        self._register_default_tools()

    def _register_default_tools(self) -> None:
        """Register the 10 approved system tools."""

        # 1. Launch Application
        self.register_tool(ToolDefinition(
            name="launch_application",
            description="Discover and open any installed Windows desktop application (e.g. Chrome, VS Code, Discord, Spotify, Notepad, Calculator, Excel, etc.).",
            parameters={
                "type": "object",
                "properties": {
                    "app_name": {
                        "type": "string",
                        "description": "Name or common alias of the application to launch (e.g. 'Spotify', 'Visual Studio Code', 'code editor', 'Chrome')."
                    },
                    "args": {
                        "type": "string",
                        "description": "Optional command-line arguments to pass to the application."
                    }
                },
                "required": ["app_name"]
            },
            handler=self._tool_launch_application
        ))

        # 2. Open Folder
        self.register_tool(ToolDefinition(
            name="open_folder",
            description="Safely open a user directory or verified system folder (e.g. Downloads, Documents, Desktop, or a validated path) in Windows File Explorer.",
            parameters={
                "type": "object",
                "properties": {
                    "folder_path": {
                        "type": "string",
                        "description": "Directory name or path (e.g., 'downloads', 'documents', 'desktop', or an absolute directory path)."
                    }
                },
                "required": ["folder_path"]
            },
            handler=self._tool_open_folder
        ))

        # 3. Open Website
        self.register_tool(ToolDefinition(
            name="open_website",
            description="Safely open an official website or web address in the user's default web browser.",
            parameters={
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "The full HTTP or HTTPS website URL to navigate to (e.g. 'https://spotify.com')."
                    }
                },
                "required": ["url"]
            },
            handler=self._tool_open_website
        ))

        # 4. Search Web
        self.register_tool(ToolDefinition(
            name="search_web",
            description="Perform a web search for programming documentation, tutorials, or general queries in the default web browser.",
            parameters={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query or keywords to look up."
                    }
                },
                "required": ["query"]
            },
            handler=self._tool_search_web
        ))

        # 5. System Diagnostics
        self.register_tool(ToolDefinition(
            name="system_diagnostics",
            description="Gather live host hardware telemetry: CPU utilization, RAM consumption, disk storage, machine uptime, and Windows OS details.",
            parameters={"type": "object", "properties": {}},
            handler=self._tool_system_diagnostics
        ))

        # 6. List Applications
        self.register_tool(ToolDefinition(
            name="list_applications",
            description="List discovered desktop applications and registered shortcuts available on this Windows computer.",
            parameters={
                "type": "object",
                "properties": {
                    "category": {
                        "type": "string",
                        "description": "Optional category filter: 'all', 'code', 'browser', 'media', 'system'."
                    }
                }
            },
            handler=self._tool_list_applications
        ))

        # 7. List Skills
        self.register_tool(ToolDefinition(
            name="list_skills",
            description="List all multi-step automation workflows created in Skill Forge.",
            parameters={"type": "object", "properties": {}},
            handler=self._tool_list_skills
        ))

        # 8. Run Skill
        self.register_tool(ToolDefinition(
            name="run_skill",
            description="Execute a multi-step Skill Forge workflow by name.",
            parameters={
                "type": "object",
                "properties": {
                    "skill_name": {
                        "type": "string",
                        "description": "The exact or partial name of the Skill Forge workflow to execute."
                    }
                },
                "required": ["skill_name"]
            },
            handler=self._tool_run_skill
        ))

        # 9. Test Skill (Dry-Run)
        self.register_tool(ToolDefinition(
            name="test_skill",
            description="Simulate a Skill Forge workflow in safe dry-run mode to inspect its sequence without side effects.",
            parameters={
                "type": "object",
                "properties": {
                    "skill_name": {
                        "type": "string",
                        "description": "Name of the workflow to test."
                    }
                },
                "required": ["skill_name"]
            },
            handler=self._tool_test_skill
        ))

        # 10. Create Skill Workflow
        self.register_tool(ToolDefinition(
            name="create_skill",
            description="Create a new automated multi-step workflow in Skill Forge with approved actions.",
            parameters={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Unique descriptive name for the workflow."},
                    "description": {"type": "string", "description": "Summary of what the workflow accomplishes."},
                    "steps": {
                        "type": "array",
                        "description": "List of action steps. Each step must have action_type and args dict.",
                        "items": {
                            "type": "object",
                            "properties": {
                                "action_type": {"type": "string"},
                                "label": {"type": "string"},
                                "args": {"type": "object"}
                            },
                            "required": ["action_type", "args"]
                        }
                    }
                },
                "required": ["name", "steps"]
            },
            handler=self._tool_create_skill
        ))

        # 11. Play Music / Audio
        self.register_tool(ToolDefinition(
            name="play_music",
            description="Search and play a song, artist, album, or playlist on Spotify or media player (e.g. 'play element', 'play John Michael Howell', 'play Bohemian Rhapsody on Spotify'). Automatically launches Spotify directly to the requested track/artist, or opens web music search.",
            parameters={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Song name, artist, track, album, or playlist to search and play (e.g. 'element', 'John Michael Howell', 'lo-fi beats')."
                    },
                    "platform": {
                        "type": "string",
                        "description": "Platform to play music on: 'spotify' (default) or 'youtube'."
                    }
                },
                "required": ["query"]
            },
            handler=self._tool_play_music
        ))

        # 12. Control Media Playback
        self.register_tool(ToolDefinition(
            name="control_media",
            description="Control media playback on Windows (Spotify, YouTube, VLC, media players): play, pause, resume, toggle play/pause, next track, previous track, stop, volume up, volume down, mute.",
            parameters={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "description": "The media playback control action: 'play', 'pause', 'play_pause', 'resume', 'next', 'previous', 'stop', 'volume_up', 'volume_down', 'mute'."
                    }
                },
                "required": ["action"]
            },
            handler=self._tool_control_media
        ))

        # 13. Set Timer / Reminder
        self.register_tool(ToolDefinition(
            name="set_timer",
            description="Set a countdown timer or reminder (e.g. 'set timer for 10 minutes', 'remind me in 5 minutes to stretch').",
            parameters={
                "type": "object",
                "properties": {
                    "minutes": {
                        "type": "number",
                        "description": "Duration in minutes (e.g. 5, 0.5, 15)."
                    },
                    "label": {
                        "type": "string",
                        "description": "Description or reason for the timer (e.g. 'check oven', 'stand up', 'meeting')."
                    }
                },
                "required": ["minutes"]
            },
            handler=self._tool_set_timer
        ))

        # 14. List Timers / Reminders
        self.register_tool(ToolDefinition(
            name="list_timers",
            description="List active countdown timers and pending reminders.",
            parameters={"type": "object", "properties": {}},
            handler=self._tool_list_timers
        ))

        # 15. Windows Workstation & Window Automation
        self.register_tool(ToolDefinition(
            name="windows_automation",
            description="Perform Windows desktop management tasks: lock workstation ('lock'), minimize all windows / show desktop ('minimize_all').",
            parameters={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "description": "Action to perform: 'lock' or 'minimize_all'."
                    }
                },
                "required": ["action"]
            },
            handler=self._tool_windows_automation
        ))

        # 16. Search User Files
        self.register_tool(ToolDefinition(
            name="find_files",
            description="Search for files in user folders (Downloads, Documents, Desktop) by name or pattern.",
            parameters={
                "type": "object",
                "properties": {
                    "pattern": {
                        "type": "string",
                        "description": "Filename or wildcard pattern (e.g. 'budget.xlsx', 'report', '*.pdf')."
                    },
                    "folder": {
                        "type": "string",
                        "description": "Optional directory filter: 'downloads', 'documents', 'desktop'."
                    }
                },
                "required": ["pattern"]
            },
            handler=self._tool_find_files
        ))

        # 17. Inspect Screen (Vision)
        self.register_tool(ToolDefinition(
            name="analyze_screen",
            description="Capture the user's desktop screen and visually analyze open windows, errors, code, or images using Gemini Vision.",
            parameters={
                "type": "object",
                "properties": {
                    "prompt": {
                        "type": "string",
                        "description": "Specific instruction or question for what to inspect on screen (e.g. 'explain the error on screen', 'summarize this document')."
                    }
                }
            },
            handler=self._tool_analyze_screen
        ))

    def register_tool(self, tool: ToolDefinition) -> None:
        self._tools[tool.name] = tool

    def get_tool(self, name: str) -> Optional[ToolDefinition]:
        return self._tools.get(name)

    def get_all_tools(self) -> List[ToolDefinition]:
        return list(self._tools.values())

    def get_schemas(self) -> List[Dict[str, Any]]:
        return [t.to_schema() for t in self._tools.values()]

    def execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> ToolResult:
        """Validate and execute an approved tool. Arbitrary tool names are strictly rejected."""
        tool = self.get_tool(tool_name)
        if not tool:
            return ToolResult(
                success=False,
                message=f"SECURITY ALERT: Tool '{tool_name}' is not in the approved action registry and was blocked.",
                tool_name=tool_name
            )

        # Validate arguments safety (reject dangerous patterns in arguments)
        for k, v in arguments.items():
            if isinstance(v, str):
                if any(p in v for p in [";", "&&", "||", "`", "$(", "<", ">"]):
                    return ToolResult(
                        success=False,
                        message=f"SECURITY ALERT: Argument '{k}' contains prohibited shell control characters.",
                        tool_name=tool_name
                    )

        try:
            return tool.handler(**arguments)
        except TypeError as type_err:
            return ToolResult(
                success=False,
                message=f"Invalid arguments for tool '{tool_name}': {type_err}",
                tool_name=tool_name
            )
        except Exception as exc:
            return ToolResult(
                success=False,
                message=f"Error executing tool '{tool_name}': {exc}",
                tool_name=tool_name
            )

    # -------------------------------------------------------------------------
    # Tool Handlers
    # -------------------------------------------------------------------------

    def _tool_launch_application(self, app_name: str, args: str = "") -> ToolResult:
        res: LaunchResult = self.launcher.launch(app_name)
        return ToolResult(
            success=res.success,
            message=res.message,
            tool_name="launch_application",
            data=res.to_dict()
        )

    def _tool_open_folder(self, folder_path: str) -> ToolResult:
        target = folder_path.strip().lower()
        user_home = Path.home()

        folder_map = {
            "downloads": user_home / "Downloads",
            "documents": user_home / "Documents",
            "desktop": user_home / "Desktop",
            "pictures": user_home / "Pictures",
            "music": user_home / "Music",
            "videos": user_home / "Videos",
            "project": Path.cwd(),
        }

        resolved_path: Optional[Path] = folder_map.get(target)
        if not resolved_path:
            # Check absolute path
            cand = Path(os.path.expandvars(folder_path.strip('"')))
            if cand.is_absolute() and cand.is_dir():
                resolved_path = cand

        if not resolved_path or not resolved_path.exists():
            return ToolResult(
                success=False,
                message=f"Folder '{folder_path}' could not be located on this system.",
                tool_name="open_folder"
            )

        try:
            os.startfile(str(resolved_path.resolve()))
            return ToolResult(
                success=True,
                message=f"Opened folder: {resolved_path.resolve()}",
                tool_name="open_folder",
                data={"path": str(resolved_path.resolve())}
            )
        except Exception as exc:
            return ToolResult(
                success=False,
                message=f"Failed to open folder: {exc}",
                tool_name="open_folder"
            )

    def _tool_open_website(self, url: str) -> ToolResult:
        clean_url = url.strip()
        if not (clean_url.startswith("http://") or clean_url.startswith("https://")):
            clean_url = f"https://{clean_url}"

        # Validate URL format
        parsed = urllib.parse.urlparse(clean_url)
        if not parsed.netloc:
            return ToolResult(
                success=False,
                message=f"Invalid URL structure: '{url}'.",
                tool_name="open_website"
            )

        try:
            webbrowser.open(clean_url)
            return ToolResult(
                success=True,
                message=f"Navigating to website: {clean_url}",
                tool_name="open_website",
                data={"url": clean_url}
            )
        except Exception as exc:
            return ToolResult(
                success=False,
                message=f"Failed to open browser: {exc}",
                tool_name="open_website"
            )

    def _tool_search_web(self, query: str) -> ToolResult:
        clean_q = query.strip()
        if not clean_q:
            return ToolResult(success=False, message="Search query cannot be empty.", tool_name="search_web")

        encoded = urllib.parse.quote_plus(clean_q)
        search_url = f"https://www.google.com/search?q={encoded}"
        try:
            webbrowser.open(search_url)
            return ToolResult(
                success=True,
                message=f"Opened web search for: '{clean_q}'",
                tool_name="search_web",
                data={"query": clean_q, "url": search_url}
            )
        except Exception as exc:
            return ToolResult(
                success=False,
                message=f"Failed to initiate web search: {exc}",
                tool_name="search_web"
            )

    def _tool_system_diagnostics(self) -> ToolResult:
        report = SystemInfoCollector.get_formatted_report()
        summary = SystemInfoCollector.get_system_summary()
        return ToolResult(
            success=True,
            message=report,
            tool_name="system_diagnostics",
            data=summary
        )

    def _tool_list_applications(self, category: str = "") -> ToolResult:
        db_apps = self.launcher.list_registered_applications()
        discovered_apps = self.launcher.discovery.list_all()

        lines = ["REGISTERED & DISCOVERED APPLICATIONS:"]
        seen = set()
        for a in db_apps:
            status = "✓ Ready" if a["available"] else "✗ Missing"
            lines.append(f" • [Primary] {a['name']:<22} [{status}]")
            seen.add(a["name"].lower())

        disc_count = 0
        for d in discovered_apps:
            if d.clean_name not in seen and disc_count < 25:
                lines.append(f" • [Discovered] {d.name:<20} (Source: {d.source})")
                seen.add(d.clean_name)
                disc_count += 1

        total_discovered = len(discovered_apps)
        lines.append(f"\nTotal discovered on host: {total_discovered} applications. You can ask me to open any of them.")
        return ToolResult(
            success=True,
            message="\n".join(lines),
            tool_name="list_applications",
            data={"count": total_discovered}
        )

    def _tool_list_skills(self) -> ToolResult:
        skills = self.skill_storage.get_all_skills()
        if not skills:
            return ToolResult(
                success=True,
                message="No workflows currently saved in Skill Forge. You can create one via the Skill Forge view or by asking me.",
                tool_name="list_skills"
            )

        lines = ["SKILL FORGE AUTOMATION WORKFLOWS:"]
        for s in skills:
            status = "ACTIVE" if s.enabled else "DISABLED"
            lines.append(f" • {s.name:<24} [{status}] — {len(s.steps)} step(s)")
            if s.description:
                lines.append(f"   Summary: {s.description}")

        return ToolResult(
            success=True,
            message="\n".join(lines),
            tool_name="list_skills",
            data={"skills_count": len(skills)}
        )

    def _tool_run_skill(self, skill_name: str) -> ToolResult:
        skill = self.skill_storage.get_skill_by_name(skill_name)
        if not skill:
            return ToolResult(
                success=False,
                message=f"Skill '{skill_name}' was not found in Skill Forge registry.",
                tool_name="run_skill"
            )

        res = self.skill_engine.execute_skill(skill, dry_run=False)
        lines = [f"WORKFLOW EXECUTION: {skill.name} [{res.status}]"]
        for sr in res.step_results:
            icon = "✓" if sr.status == "SUCCEEDED" else "✗"
            lines.append(f" [{icon}] Step {sr.step_order} ({sr.label or sr.action_type}): {sr.message}")

        return ToolResult(
            success=res.success,
            message="\n".join(lines),
            tool_name="run_skill",
            data=res.to_dict()
        )

    def _tool_test_skill(self, skill_name: str) -> ToolResult:
        skill = self.skill_storage.get_skill_by_name(skill_name)
        if not skill:
            return ToolResult(
                success=False,
                message=f"Skill '{skill_name}' not found.",
                tool_name="test_skill"
            )

        res = self.skill_engine.execute_skill(skill, dry_run=True)
        lines = [f"DRY-RUN SIMULATION: {skill.name} [{res.status}]"]
        for sr in res.step_results:
            lines.append(f" [SIMULATED] Step {sr.step_order} ({sr.label or sr.action_type}): {sr.message}")

        return ToolResult(
            success=res.success,
            message="\n".join(lines),
            tool_name="test_skill",
            data=res.to_dict()
        )

    def _tool_create_skill(self, name: str, description: str, steps: List[Dict[str, Any]]) -> ToolResult:
        wf_steps = []
        for idx, s in enumerate(steps, start=1):
            action_type = s.get("action_type", "")
            step_args = s.get("args", {})
            label = s.get("label", f"Step {idx}")
            wf_steps.append(SkillStep(
                order=idx,
                action_type=action_type,
                arguments=step_args,
                label=label
            ))

        workflow = Skill(
            name=name,
            description=description,
            steps=wf_steps,
            enabled=True
        )

        saved = self.skill_storage.save_skill(workflow)
        if saved:
            return ToolResult(
                success=True,
                message=f"Created Skill Forge workflow '{name}' with {len(wf_steps)} step(s).",
                tool_name="create_skill",
                data={"skill_id": workflow.id, "name": name}
            )
        else:
            return ToolResult(
                success=False,
                message=f"Failed to save workflow '{name}' in Skill Forge.",
                tool_name="create_skill"
            )

    def _tool_play_music(self, query: str, platform: str = "spotify") -> ToolResult:
        """Search and play a song, artist, album, or playlist on Spotify or YouTube."""
        clean_q = query.strip()
        encoded = urllib.parse.quote(clean_q)
        target_platform = platform.lower().strip() if platform else "spotify"

        # Explicit YouTube request
        if "youtube" in target_platform or "youtube" in clean_q.lower():
            url = f"https://www.youtube.com/results?search_query={encoded}"
            webbrowser.open(url)
            return ToolResult(
                success=True,
                message=f"Playing '{clean_q}' via YouTube in your default browser.",
                tool_name="play_music",
                data={"platform": "youtube", "query": clean_q, "url": url}
            )

        # Spotify URI protocol
        spotify_uri = f"spotify:search:{encoded}"
        launched_native = False

        # First verify if Spotify is already running or launch cleanly from Start Menu / exe
        try:
            import psutil
            spotify_procs = [p for p in psutil.process_iter(['name']) if p.info['name'] and 'spotify' in p.info['name'].lower()]
            if not spotify_procs:
                # Launch Spotify first if not running
                self.launcher.launch("Spotify")
                import time
                time.sleep(1.2)
        except Exception:
            pass

        try:
            if hasattr(os, "startfile"):
                os.startfile(spotify_uri)
                launched_native = True
        except Exception as e:
            logger.warning(f"Failed to startfile with spotify URI: {e}")

        if not launched_native:
            # Fallback to web Spotify
            try:
                web_url = f"https://open.spotify.com/search/{encoded}"
                webbrowser.open(web_url)
                return ToolResult(
                    success=True,
                    message=f"Opened Spotify Web Player searching for '{clean_q}'.",
                    tool_name="play_music",
                    data={"platform": "spotify_web", "query": clean_q, "url": web_url}
                )
            except Exception as exc:
                return ToolResult(
                    success=False,
                    message=f"Could not open music player for '{clean_q}': {exc}",
                    tool_name="play_music"
                )

        return ToolResult(
            success=True,
            message=f"Playing '{clean_q}' on Spotify.",
            tool_name="play_music",
            data={"platform": "spotify", "query": clean_q, "uri": spotify_uri}
        )

    def _tool_control_media(self, action: str) -> ToolResult:
        """Send media playback control events on Windows (play, pause, next, previous, stop, volume, mute)."""
        import ctypes
        import time

        action_clean = action.lower().strip().replace(" ", "_")

        key_map = {
            "play": 0xB3,        # VK_MEDIA_PLAY_PAUSE
            "pause": 0xB3,
            "play_pause": 0xB3,
            "resume": 0xB3,
            "toggle": 0xB3,
            "next": 0xB0,        # VK_MEDIA_NEXT_TRACK
            "skip": 0xB0,
            "previous": 0xB1,    # VK_MEDIA_PREV_TRACK
            "prev": 0xB1,
            "back": 0xB1,
            "stop": 0xB2,        # VK_MEDIA_STOP
            "volume_up": 0xAF,   # VK_VOLUME_UP
            "louder": 0xAF,
            "volume_down": 0xAE, # VK_VOLUME_DOWN
            "quieter": 0xAE,
            "mute": 0xAD,        # VK_VOLUME_MUTE
            "unmute": 0xAD,
        }

        vk_code = key_map.get(action_clean)
        if not vk_code:
            return ToolResult(
                success=False,
                message=f"Unsupported media action '{action}'. Supported actions: play, pause, next, previous, stop, volume_up, volume_down, mute.",
                tool_name="control_media"
            )

        try:
            ctypes.windll.user32.keybd_event(vk_code, 0, 0, 0)
            time.sleep(0.05)
            ctypes.windll.user32.keybd_event(vk_code, 0, 2, 0)

            action_desc_map = {
                0xB3: "Toggled Play/Pause",
                0xB0: "Skipped to Next Track",
                0xB1: "Returned to Previous Track",
                0xB2: "Stopped Media Playback",
                0xAF: "Increased Volume",
                0xAE: "Decreased Volume",
                0xAD: "Toggled Audio Mute",
            }
            desc = action_desc_map.get(vk_code, f"Media action {action_clean}")
            return ToolResult(
                success=True,
                message=f"{desc} successfully.",
                tool_name="control_media",
                data={"action": action_clean, "vk_code": vk_code}
            )
        except Exception as exc:
            return ToolResult(
                success=False,
                message=f"Failed to send media control event: {exc}",
                tool_name="control_media"
            )

    def _tool_set_timer(self, minutes: float, label: str = "Timer") -> ToolResult:
        """Schedule a timer or reminder."""
        try:
            from jarvis.core.reminders import ReminderManager
            mgr = ReminderManager(self.db)
            res = mgr.add_timer(float(minutes), label=label)
            return ToolResult(
                success=True,
                message=f"Timer set for {minutes} minute(s) ({label}). I will notify you when it expires.",
                tool_name="set_timer",
                data=res
            )
        except Exception as exc:
            return ToolResult(
                success=False,
                message=f"Could not set timer: {exc}",
                tool_name="set_timer"
            )

    def _tool_list_timers(self) -> ToolResult:
        """List active pending timers."""
        try:
            from jarvis.core.reminders import ReminderManager
            mgr = ReminderManager(self.db)
            pending = mgr.list_pending()
            if not pending:
                return ToolResult(
                    success=True,
                    message="No active timers or pending reminders.",
                    tool_name="list_timers"
                )
            lines = ["ACTIVE TIMERS & REMINDERS:"]
            for r in pending:
                lines.append(f" • [#{r['id']}] {r['message']} — {r['remaining_minutes']} min remaining")
            return ToolResult(
                success=True,
                message="\n".join(lines),
                tool_name="list_timers",
                data={"pending": pending}
            )
        except Exception as exc:
            return ToolResult(
                success=False,
                message=f"Could not retrieve timers: {exc}",
                tool_name="list_timers"
            )

    def _tool_windows_automation(self, action: str) -> ToolResult:
        """Lock workstation or toggle desktop."""
        try:
            from jarvis.core.window_manager import WindowsAutomation
            act = action.lower().strip()
            if act in ["lock", "lock_workstation", "lock_pc"]:
                res = WindowsAutomation.lock_workstation()
                return ToolResult(success=res["success"], message=res["message"], tool_name="windows_automation")
            elif act in ["minimize_all", "desktop", "show_desktop"]:
                res = WindowsAutomation.minimize_all_windows()
                return ToolResult(success=res["success"], message=res["message"], tool_name="windows_automation")
            else:
                return ToolResult(
                    success=False,
                    message=f"Unknown automation action '{action}'. Supported: 'lock', 'minimize_all'.",
                    tool_name="windows_automation"
                )
        except Exception as exc:
            return ToolResult(success=False, message=f"Windows automation failed: {exc}", tool_name="windows_automation")

    def _tool_find_files(self, pattern: str, folder: Optional[str] = None) -> ToolResult:
        """Search user folders for files."""
        try:
            from jarvis.core.window_manager import WindowsAutomation
            files = WindowsAutomation.find_user_files(pattern, search_dir=folder)
            if not files:
                return ToolResult(
                    success=True,
                    message=f"No files matching '{pattern}' found in user directories.",
                    tool_name="find_files"
                )
            lines = [f"FOUND {len(files)} FILE(S) MATCHING '{pattern}':"]
            for f in files:
                lines.append(f" • {f['name']} ({round(f['size_bytes'] / 1024, 1)} KB)\n   Path: {f['path']}")
            return ToolResult(
                success=True,
                message="\n".join(lines),
                tool_name="find_files",
                data={"files": files}
            )
        except Exception as exc:
            return ToolResult(success=False, message=f"File search failed: {exc}", tool_name="find_files")

    def _tool_analyze_screen(self, prompt: str = "Analyze the active screen and explain what is visible, highlighting any errors, open apps, or key details.") -> ToolResult:
        """Capture primary screen and analyze with Gemini Vision."""
        try:
            from jarvis.core.screen_analyzer import ScreenAnalyzer
            res = ScreenAnalyzer.analyze_screen(prompt=prompt)
            return ToolResult(
                success=res["success"],
                message=res["message"],
                tool_name="analyze_screen",
                data=res
            )
        except Exception as exc:
            return ToolResult(success=False, message=f"Screen inspection failed: {exc}", tool_name="analyze_screen")
