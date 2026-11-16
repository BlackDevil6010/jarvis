"""Safe Windows automation utilities: window management, workstation lock, and file finding."""

import os
import ctypes
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)


class WindowsAutomation:
    """Provides safe, approved Windows OS automations without arbitrary shell commands."""

    @staticmethod
    def lock_workstation() -> Dict[str, Any]:
        """Safely lock Windows workstation (equivalent to Win + L)."""
        try:
            res = ctypes.windll.user32.LockWorkStation()
            if res != 0:
                return {"success": True, "message": "Workstation locked securely."}
            return {"success": False, "message": "Failed to lock workstation."}
        except Exception as e:
            return {"success": False, "message": f"Error locking workstation: {e}"}

    @staticmethod
    def minimize_all_windows() -> Dict[str, Any]:
        """Minimize all windows to display desktop (Win + M / Win + D)."""
        try:
            # PostMessage to Shell window for minimize all
            # Or use keybd_event Win + D
            VK_LWIN = 0x5B
            VK_D = 0x44
            ctypes.windll.user32.keybd_event(VK_LWIN, 0, 0, 0)
            ctypes.windll.user32.keybd_event(VK_D, 0, 0, 0)
            ctypes.windll.user32.keybd_event(VK_D, 0, 2, 0)
            ctypes.windll.user32.keybd_event(VK_LWIN, 0, 2, 0)
            return {"success": True, "message": "Toggled desktop display / minimized open windows."}
        except Exception as e:
            return {"success": False, "message": f"Error minimizing windows: {e}"}

    @staticmethod
    def find_user_files(filename_pattern: str, search_dir: Optional[str] = None, max_results: int = 10) -> List[Dict[str, Any]]:
        """
        Safely search for files matching pattern in user directories (Downloads, Documents, Desktop)
        without invoking cmd/powershell.
        """
        import fnmatch
        user_home = Path.home()
        dirs_to_search = []

        if search_dir:
            cleaned = search_dir.lower().strip()
            if cleaned in ["downloads", "download"]:
                dirs_to_search.append(user_home / "Downloads")
            elif cleaned in ["documents", "doc", "docs"]:
                dirs_to_search.append(user_home / "Documents")
            elif cleaned in ["desktop"]:
                dirs_to_search.append(user_home / "Desktop")
            else:
                p = Path(search_dir)
                if p.exists() and p.is_dir():
                    dirs_to_search.append(p)
        else:
            dirs_to_search = [
                user_home / "Downloads",
                user_home / "Documents",
                user_home / "Desktop",
            ]

        results = []
        pat = f"*{filename_pattern.lower()}*" if not any(c in filename_pattern for c in ["*", "?"]) else filename_pattern.lower()

        for d in dirs_to_search:
            if not d.exists():
                continue
            try:
                # Walk with shallow depth limit (max 2 subfolders) to be fast & safe
                for root, _, files in os.walk(str(d)):
                    # Compute relative depth
                    rel = os.path.relpath(root, str(d))
                    if rel != "." and rel.count(os.sep) >= 2:
                        continue
                    for f in files:
                        if fnmatch.fnmatch(f.lower(), pat):
                            full_path = os.path.join(root, f)
                            try:
                                sz = os.path.getsize(full_path)
                            except OSError:
                                sz = 0
                            results.append({
                                "name": f,
                                "path": full_path,
                                "size_bytes": sz,
                                "directory": root
                            })
                            if len(results) >= max_results:
                                return results
            except Exception as ex:
                logger.warning(f"Error scanning directory {d}: {ex}")

        return results
