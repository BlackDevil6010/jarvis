"""Application launcher for JARVIS with path resolution, validation, and safe execution."""

import os
import shutil
import subprocess
from pathlib import Path
from typing import Tuple, Optional, Dict, Any, List
from jarvis.core.database import Database
from jarvis.core.app_discovery import AppDiscovery, DiscoveredApp


class LaunchResult:
    """Represents the outcome of an application launch attempt."""
    def __init__(self, success: bool, message: str, app_name: str, pid: Optional[int] = None):
        self.success = success
        self.message = message
        self.app_name = app_name
        self.pid = pid

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "message": self.message,
            "app_name": self.app_name,
            "pid": self.pid,
        }

    def __repr__(self) -> str:
        return f"<LaunchResult success={self.success} app='{self.app_name}' msg='{self.message}'>"


class AppLauncher:
    """Handles discovering, validating, and safely launching desktop applications."""

    def __init__(self, db: Optional[Database] = None, discovery: Optional[AppDiscovery] = None):
        self.db = db or Database()
        self.discovery = discovery or AppDiscovery()

    def resolve_executable_path(self, raw_path: str) -> Optional[str]:
        """
        Validate and resolve an executable path on Windows.
        Returns resolved absolute/system path or None if not found.
        """
        if not raw_path:
            return None

        # 1. Expand environment variables (e.g., %SystemRoot%, %ProgramFiles%)
        expanded = os.path.expandvars(raw_path.strip().strip('"'))

        # 2. Direct absolute path check
        path_obj = Path(expanded)
        if path_obj.is_absolute() and path_obj.exists():
            return str(path_obj.resolve())

        # 3. Standard system lookup via PATH
        found_in_path = shutil.which(expanded)
        if found_in_path:
            return found_in_path

        # 4. Check standard Windows System32 / Windows directory if only filename given
        system_root = os.environ.get("SystemRoot", r"C:\Windows")
        candidate_dirs = [
            Path(system_root) / "System32",
            Path(system_root),
            Path(system_root) / "SysWOW64",
            Path(os.environ.get("ProgramFiles", r"C:\Program Files")),
            Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")),
            Path(os.environ.get("LocalAppData", "")) / "Programs",
        ]

        for candidate_dir in candidate_dirs:
            candidate = candidate_dir / expanded
            if candidate.exists():
                return str(candidate.resolve())
            if not expanded.lower().endswith(".exe"):
                candidate_exe = candidate_dir / f"{expanded}.exe"
                if candidate_exe.exists():
                    return str(candidate_exe.resolve())

        # 5. Check Windows App Paths Registry (HKCU and HKLM)
        try:
            import winreg
            exe_key_name = expanded if expanded.lower().endswith(".exe") else f"{expanded}.exe"
            for hkey in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
                try:
                    with winreg.OpenKey(hkey, rf"Software\Microsoft\Windows\CurrentVersion\App Paths\{exe_key_name}") as key:
                        val, _ = winreg.QueryValueEx(key, "")
                        if val:
                            val_expanded = os.path.expandvars(str(val).strip().strip('"'))
                            path_cand = Path(val_expanded)
                            if path_cand.exists():
                                return str(path_cand.resolve())
                except OSError:
                    pass
        except (ImportError, Exception):
            pass

        return None

    def launch(self, app_query: str) -> LaunchResult:
        """
        Look up application in database or discover across system, then launch safely.
        """
        # 1. Check explicitly registered database shortcuts first
        app = self.db.get_application_by_name(app_query)
        if app:
            raw_path = app["path"]
            resolved_path = self.resolve_executable_path(raw_path)

            if not resolved_path:
                return LaunchResult(
                    success=False,
                    message=(
                        f"Executable not found for '{app['name']}'. "
                        f"Configured path '{raw_path}' does not exist on this system."
                    ),
                    app_name=app["name"]
                )

            cmd = [resolved_path]
            if app["args"]:
                cmd.extend(app["args"].split())
            return self._spawn_process(cmd, app["name"])

        # 2. Query General Windows Application Discovery
        discovered, candidates, suggestion_website = self.discovery.resolve_application(app_query)
        if discovered:
            res = self._launch_discovered(discovered)
            if res.success:
                return res

        if candidates and not discovered:
            cand_names = ", ".join([f"'{c.name}'" for c in candidates])
            return LaunchResult(
                success=False,
                message=f"Multiple applications match '{app_query}': {cand_names}. Please specify which one you'd like to open.",
                app_name=app_query
            )

        # 3. Deep System Fallback Waterfall (System32, PATH, ShellExecute, common aliases)
        fallback_res = self._fallback_system_launch(app_query)
        if fallback_res and fallback_res.success:
            return fallback_res

        # 4. Not found anywhere
        if suggestion_website:
            return LaunchResult(
                success=False,
                message=(
                    f"Application '{app_query}' is not registered or installed on this system. "
                    f"You can access its official service online at {suggestion_website}."
                ),
                app_name=app_query
            )

        return LaunchResult(
            success=False,
            message=f"Application '{app_query}' is not registered or installed on this system. Type 'list apps' to see available shortcuts.",
            app_name=app_query
        )

    def _fallback_system_launch(self, app_query: str) -> Optional[LaunchResult]:
        """
        Deep fallback system launcher trying known executables, Windows PATH,
        and Windows ShellExecute before giving up.
        """
        clean_q = app_query.strip().lower()
        if not clean_q:
            return None

        # 1. Known Windows application and system tool alias dictionary
        SYSTEM_APP_MAP = {
            "settings": ("ms-settings:", True),
            "windows settings": ("ms-settings:", True),
            "pc settings": ("ms-settings:", True),
            "system settings": ("ms-settings:", True),
            "whatsapp": ("whatsapp:", True),
            "telegram": ("tg:", True),
            "spotify": ("spotify:", True),
            "discord": ("discord:", True),
            "steam": ("steam:", True),
            "word": ("winword.exe", False),
            "microsoft word": ("winword.exe", False),
            "excel": ("excel.exe", False),
            "microsoft excel": ("excel.exe", False),
            "powerpoint": ("powerpnt.exe", False),
            "microsoft powerpoint": ("powerpnt.exe", False),
            "access": ("msaccess.exe", False),
            "control": ("control.exe", False),
            "control panel": ("control.exe", False),
            "calc": ("calc.exe", False),
            "calculator": ("calc.exe", False),
            "paint": ("mspaint.exe", False),
            "terminal": ("wt.exe", False),
            "windows terminal": ("wt.exe", False),
            "cmd": ("cmd.exe", False),
            "command prompt": ("cmd.exe", False),
            "powershell": ("powershell.exe", False),
            "explorer": ("explorer.exe", False),
            "file explorer": ("explorer.exe", False),
            "my computer": ("explorer.exe", False),
            "this pc": ("explorer.exe", False),
            "task manager": ("taskmgr.exe", False),
            "taskmgr": ("taskmgr.exe", False),
            "regedit": ("regedit.exe", False),
            "registry editor": ("regedit.exe", False),
            "snippingtool": ("snippingtool.exe", False),
            "snipping tool": ("snippingtool.exe", False),
            "snip": ("snippingtool.exe", False),
            "cleanmgr": ("cleanmgr.exe", False),
            "disk cleanup": ("cleanmgr.exe", False),
            "camera": ("microsoft.windows.camera:", True),
            "photos": ("ms-photos:", True),
            "clock": ("ms-clock:", True),
            "alarms": ("ms-clock:", True),
            "store": ("ms-windows-store:", True),
            "microsoft store": ("ms-windows-store:", True),
            "weather": ("msnweather:", True),
            "vlc": ("vlc.exe", False),
            "brave": ("brave.exe", False),
            "chrome": ("chrome.exe", False),
            "edge": ("msedge.exe", False),
            "firefox": ("firefox.exe", False),
        }

        if clean_q in SYSTEM_APP_MAP:
            target, is_proto = SYSTEM_APP_MAP[clean_q]
            try:
                if is_proto:
                    os.startfile(target)
                    return LaunchResult(
                        success=True,
                        message=f"Opened {app_query.title()} successfully via system protocol.",
                        app_name=app_query
                    )
                else:
                    resolved = self.resolve_executable_path(target)
                    if resolved:
                        return self._spawn_process([resolved], app_query.title())
                    os.startfile(target)
                    return LaunchResult(
                        success=True,
                        message=f"Opened {app_query.title()} successfully.",
                        app_name=app_query
                    )
            except Exception:
                pass

        # 2. Check shutil.which directly for clean_q or clean_q.exe
        in_path = shutil.which(clean_q) or shutil.which(f"{clean_q}.exe")
        if in_path:
            return self._spawn_process([in_path], app_query)

        # 3. Check resolved executable path
        resolved = self.resolve_executable_path(clean_q)
        if resolved:
            return self._spawn_process([resolved], app_query)

        # 4. Try native Windows ShellExecute
        try:
            os.startfile(clean_q)
            return LaunchResult(
                success=True,
                message=f"Opened {app_query} successfully via Windows Shell.",
                app_name=app_query
            )
        except Exception:
            pass

        return None

    def _launch_discovered(self, app: DiscoveredApp) -> LaunchResult:
        """Safely launch an application discovered on the Windows system."""
        try:
            # shell:AppsFolder target (Modern Windows Store / UWP / Package Apps)
            if app.target.startswith("shell:AppsFolder\\") or app.target.startswith("shell:"):
                os.startfile(app.target)
                return LaunchResult(
                    success=True,
                    message=f"Opened {app.name} successfully via Windows Shell.",
                    app_name=app.name
                )

            # Protocol URI (e.g., spotify:, discord:, steam:, calc:, whatsapp:, ms-settings:)
            if app.is_protocol or app.target.endswith(":"):
                os.startfile(app.target)
                return LaunchResult(
                    success=True,
                    message=f"Opened {app.name} successfully via system protocol.",
                    app_name=app.name
                )

            # Start Menu Shortcut (.lnk)
            if app.target.lower().endswith(".lnk"):
                os.startfile(app.target)
                return LaunchResult(
                    success=True,
                    message=f"Opened {app.name} successfully from Start Menu.",
                    app_name=app.name
                )

            # Direct Executable (.exe)
            if app.target.lower().endswith(".exe"):
                return self._spawn_process([app.target], app.name)

            # Other file types
            os.startfile(app.target)
            return LaunchResult(
                success=True,
                message=f"Opened {app.name} successfully.",
                app_name=app.name
            )

        except PermissionError:
            return LaunchResult(
                success=False,
                message=f"Access denied: Insufficient permissions to launch '{app.name}'.",
                app_name=app.name
            )
        except FileNotFoundError:
            return LaunchResult(
                success=False,
                message=f"File not found for '{app.name}' at '{app.target}'.",
                app_name=app.name
            )
        except Exception as exc:
            return LaunchResult(
                success=False,
                message=f"Failed to launch '{app.name}': {exc}",
                app_name=app.name
            )

    def _spawn_process(self, cmd: List[str], app_name: str) -> LaunchResult:
        """Spawn executable safely with shell=False."""
        try:
            proc = subprocess.Popen(
                cmd,
                shell=False,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                close_fds=True
            )

            if proc.pid and proc.poll() is None:
                return LaunchResult(
                    success=True,
                    message=f"Opened {app_name} successfully (PID: {proc.pid}).",
                    app_name=app_name,
                    pid=proc.pid
                )
            else:
                if proc.returncode == 0:
                    return LaunchResult(
                        success=True,
                        message=f"Opened {app_name} successfully.",
                        app_name=app_name,
                        pid=proc.pid
                    )
                else:
                    return LaunchResult(
                        success=False,
                        message=f"Process for '{app_name}' exited immediately with code {proc.returncode}.",
                        app_name=app_name
                    )
        except PermissionError:
            return LaunchResult(
                success=False,
                message=f"Access denied: Insufficient permissions to launch '{cmd[0]}'.",
                app_name=app_name
            )
        except FileNotFoundError:
            return LaunchResult(
                success=False,
                message=f"Target file not found: '{cmd[0]}'.",
                app_name=app_name
            )
        except Exception as e:
            return LaunchResult(
                success=False,
                message=f"Failed to launch '{app_name}': {str(e)}",
                app_name=app_name
            )

    def list_registered_applications(self) -> List[Dict[str, Any]]:
        """Return all registered applications with availability status."""
        apps = self.db.get_all_applications()
        for app in apps:
            app["available"] = self.resolve_executable_path(app["path"]) is not None
        return apps
