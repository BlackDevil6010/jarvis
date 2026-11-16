"""Windows General Application Discovery and Resolution Engine for JARVIS.

Discovers applications across Windows Start Menu shortcuts, Registry App Paths,
Registry Uninstall entries, standard installation directories, and system URI protocols.
Supports natural language alias resolution, fuzzy matching, and disambiguation.
"""

import os
import winreg
import logging
import difflib
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

logger = logging.getLogger(__name__)


class DiscoveredApp:
    """Represents an application installed or registered on the Windows system."""

    def __init__(
        self,
        name: str,
        target: str,
        source: str,
        category: str = "general",
        aliases: Optional[List[str]] = None,
        description: str = "",
        is_protocol: bool = False
    ):
        self.name = name
        self.clean_name = name.lower().strip()
        self.target = target
        self.source = source  # "start_menu", "app_paths", "registry", "protocol", "builtin"
        self.category = category
        self.aliases = [a.lower().strip() for a in (aliases or [])]
        self.description = description
        self.is_protocol = is_protocol

    def matches_query(self, query: str) -> float:
        """
        Return a match confidence score between 0.0 and 1.0.
        Exact match = 1.0, substring match = 0.85-0.95, fuzzy match = 0.5-0.8.
        """
        q = query.lower().strip()
        if not q:
            return 0.0

        # Exact match on name or alias
        if q == self.clean_name or q in self.aliases:
            return 1.0

        # Substring / word boundary matches
        if q in self.clean_name:
            # Prefer queries that match beginning of name
            if self.clean_name.startswith(q):
                return 0.95
            return 0.85

        for alias in self.aliases:
            if q in alias:
                return 0.90 if alias.startswith(q) else 0.80

        # Fuzzy string similarity
        name_ratio = difflib.SequenceMatcher(None, q, self.clean_name).ratio()
        alias_ratios = [difflib.SequenceMatcher(None, q, a).ratio() for a in self.aliases]
        best_ratio = max([name_ratio] + alias_ratios)

        return best_ratio if best_ratio >= 0.65 else 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "target": self.target,
            "source": self.source,
            "category": self.category,
            "aliases": self.aliases,
            "description": self.description,
            "is_protocol": self.is_protocol,
        }

    def __repr__(self) -> str:
        return f"<DiscoveredApp name='{self.name}' source='{self.source}'>"


# Common Windows URI Protocols and Official Websites for fallback
COMMON_PROTOCOLS: Dict[str, Dict[str, Any]] = {
    "spotify": {
        "uri": "spotify:",
        "website": "https://open.spotify.com",
        "category": "media",
        "aliases": ["music", "songs", "spotify player", "music player", "audio player"]
    },
    "discord": {
        "uri": "discord:",
        "website": "https://discord.com",
        "category": "communication",
        "aliases": ["chat", "gaming chat", "discord chat", "voice chat"]
    },
    "steam": {
        "uri": "steam:",
        "website": "https://store.steampowered.com",
        "category": "gaming",
        "aliases": ["games", "steam client", "game store"]
    },
    "settings": {
        "uri": "ms-settings:",
        "website": "",
        "category": "system",
        "aliases": ["windows settings", "system settings", "pc settings", "preferences"]
    },
    "calculator": {
        "uri": "calc:",
        "website": "",
        "category": "productivity",
        "aliases": ["calc", "math"]
    }
}

# Generic Category Aliases mapped to intended application concepts
CATEGORY_INTENT_MAP: Dict[str, List[str]] = {
    "code editor": ["visual studio code", "vscode", "code", "notepad++", "sublime text", "pycharm", "cursor", "idle"],
    "editor": ["visual studio code", "notepad", "notepad++"],
    "browser": ["google chrome", "microsoft edge", "firefox", "brave", "opera"],
    "music": ["spotify", "apple music", "youtube music", "windows media player", "vlc"],
    "media player": ["vlc media player", "windows media player", "spotify", "potplayer"],
    "terminal": ["command prompt", "powershell", "windows terminal", "cmd"],
    "notes": ["notepad", "onenote", "obsidian", "notion"],
    "documents": ["microsoft word", "word", "libreoffice writer", "adobe acrobat", "acrobat"],
    "sheets": ["microsoft excel", "excel", "libreoffice calc"],
}


class AppDiscovery:
    """Discovers, caches, and queries applications installed across the host system."""

    def __init__(self):
        self._cache: Dict[str, DiscoveredApp] = {}
        self._is_initialized = False

    def refresh(self) -> None:
        """Scan system directories and registries to build application index."""
        apps: Dict[str, DiscoveredApp] = {}

        # 1. Start Menu Shortcuts (.lnk files)
        start_menu_dirs = [
            Path(os.environ.get("ProgramData", r"C:\ProgramData")) / "Microsoft" / "Windows" / "Start Menu" / "Programs",
            Path(os.environ.get("APPDATA", "")) / "Microsoft" / "Windows" / "Start Menu" / "Programs",
        ]
        for sm_dir in start_menu_dirs:
            if sm_dir.exists():
                try:
                    for lnk in sm_dir.rglob("*.lnk"):
                        name = lnk.stem.strip()
                        name_lower = name.lower()
                        # Filter out uninstaller and helper links
                        if any(x in name_lower for x in ["uninstall", "setup", "install", "help", "readme", "documentation", "configuration"]):
                            continue
                        if name_lower not in apps:
                            apps[name_lower] = DiscoveredApp(
                                name=name,
                                target=str(lnk.resolve()),
                                source="start_menu",
                                aliases=self._generate_aliases(name)
                            )
                except Exception as exc:
                    logger.debug(f"Error scanning Start Menu at {sm_dir}: {exc}")

        # 2. Windows App Paths Registry (HKCU and HKLM)
        for hkey in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
            try:
                with winreg.OpenKey(hkey, r"Software\Microsoft\Windows\CurrentVersion\App Paths") as root_key:
                    subkeys_count, _, _ = winreg.QueryInfoKey(root_key)
                    for i in range(subkeys_count):
                        try:
                            exe_name = winreg.EnumKey(root_key, i)
                            with winreg.OpenKey(root_key, exe_name) as app_key:
                                val, _ = winreg.QueryValueEx(app_key, "")
                                if val:
                                    clean_val = os.path.expandvars(str(val).strip().strip('"'))
                                    path_obj = Path(clean_val)
                                    if path_obj.exists():
                                        base_name = path_obj.stem
                                        key_name = base_name.lower()
                                        if key_name not in apps:
                                            apps[key_name] = DiscoveredApp(
                                                name=base_name,
                                                target=str(path_obj.resolve()),
                                                source="app_paths",
                                                aliases=self._generate_aliases(base_name)
                                            )
                        except OSError:
                            continue
            except OSError:
                continue

        # 3. Add Known Protocol Applications
        for name, proto_info in COMMON_PROTOCOLS.items():
            if name not in apps:
                apps[name] = DiscoveredApp(
                    name=name.capitalize(),
                    target=proto_info["uri"],
                    source="protocol",
                    category=proto_info["category"],
                    aliases=proto_info["aliases"],
                    description=f"Windows protocol URI {proto_info['uri']}",
                    is_protocol=True
                )

        self._cache = apps
        self._is_initialized = True
        logger.info(f"AppDiscovery: Indexed {len(self._cache)} system applications.")

    def _ensure_initialized(self) -> None:
        if not self._is_initialized or not self._cache:
            self.refresh()

    def _generate_aliases(self, app_name: str) -> List[str]:
        """Produce reasonable natural-language aliases based on app name."""
        name_lower = app_name.lower()
        aliases = [name_lower]

        # Common substitutions
        if "visual studio code" in name_lower or name_lower == "code":
            aliases.extend(["vscode", "vs code", "code editor", "programming editor"])
        elif "chrome" in name_lower:
            aliases.extend(["google chrome", "browser", "web browser", "internet"])
        elif "edge" in name_lower:
            aliases.extend(["microsoft edge", "ms edge", "browser", "web browser"])
        elif "notepad" in name_lower and "++" not in name_lower:
            aliases.extend(["notes", "text editor", "simple editor"])
        elif "calculator" in name_lower or "calc" in name_lower:
            aliases.extend(["calc", "math", "math tool"])
        elif "spotify" in name_lower:
            aliases.extend(["music", "songs", "music player"])
        elif "discord" in name_lower:
            aliases.extend(["chat", "gaming chat"])
        elif "steam" in name_lower:
            aliases.extend(["games", "game library"])
        elif "obs studio" in name_lower or "obs" in name_lower:
            aliases.extend(["recorder", "screen recorder", "streaming software"])
        elif "word" in name_lower and "pad" not in name_lower:
            aliases.extend(["word processor", "docs", "document editor"])
        elif "excel" in name_lower:
            aliases.extend(["spreadsheet", "sheets", "workbook"])

        # Strip vendor prefix: e.g. "Google Chrome" -> "Chrome", "Microsoft Edge" -> "Edge"
        for vendor in ["google ", "microsoft ", "adobe ", "apple ", "mozilla "]:
            if name_lower.startswith(vendor):
                aliases.append(name_lower[len(vendor):].strip())

        return list(set(aliases))

    def find_applications(self, query: str, threshold: float = 0.65) -> List[Tuple[DiscoveredApp, float]]:
        """
        Search for applications matching query.
        Returns list of (DiscoveredApp, score) sorted from highest to lowest confidence.
        """
        self._ensure_initialized()
        clean_q = query.strip().lower()
        if not clean_q:
            return []

        # Check category mappings first (e.g. "code editor" -> VS Code)
        category_matches = []
        for cat_name, candidate_names in CATEGORY_INTENT_MAP.items():
            if clean_q == cat_name or cat_name in clean_q:
                for c_name in candidate_names:
                    for app in self._cache.values():
                        if c_name in app.clean_name or any(c_name in a for a in app.aliases):
                            category_matches.append((app, 0.96))
                            break

        matches: List[Tuple[DiscoveredApp, float]] = []
        for app in self._cache.values():
            score = app.matches_query(clean_q)
            if score >= threshold:
                matches.append((app, score))

        # Merge category matches
        seen_targets = set()
        combined = []
        for app, score in category_matches + sorted(matches, key=lambda x: x[1], reverse=True):
            if app.target not in seen_targets:
                seen_targets.add(app.target)
                combined.append((app, score))

        return sorted(combined, key=lambda x: x[1], reverse=True)

    def resolve_application(self, query: str) -> Tuple[Optional[DiscoveredApp], List[DiscoveredApp], Optional[str]]:
        """
        Resolve application query.
        Returns:
            (selected_app, alternative_candidates, suggestion_website)
        """
        matches = self.find_applications(query)
        if not matches:
            # Check if this is a known tool with an official website
            clean_q = query.lower().strip()
            for name, proto_info in COMMON_PROTOCOLS.items():
                if name in clean_q or any(a in clean_q for a in proto_info["aliases"]):
                    return None, [], proto_info["website"]
            return None, [], None

        # Check for ambiguity: if top 2 matches have very close scores (>0.85) and different roots
        if len(matches) > 1:
            top_app, top_score = matches[0]
            second_app, second_score = matches[1]
            if top_score >= 0.85 and second_score >= 0.85 and top_app.name.lower() != second_app.name.lower():
                # If they are very close, return them as candidates for disambiguation
                if abs(top_score - second_score) < 0.05 and top_app.clean_name != query.lower():
                    candidates = [m[0] for m in matches[:3]]
                    return None, candidates, None

        return matches[0][0], [m[0] for m in matches[1:4]], None

    def list_all(self) -> List[DiscoveredApp]:
        """Return all discovered applications."""
        self._ensure_initialized()
        return sorted(self._cache.values(), key=lambda a: a.name)
