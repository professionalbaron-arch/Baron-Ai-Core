"""
BARON CORE - Dynamic Windows Software & Application Discovery Engine
Scans, indexes, and enables voice control for EVERY installed application on the Windows Desktop.
"""

import os
import sys
import glob
import logging
import difflib
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

logger = logging.getLogger("BaronAppDiscovery")

COMMON_SYSTEM_APPS = {
    "notepad": {"name": "Notepad", "target": "notepad.exe", "category": "utility"},
    "calculator": {"name": "Calculator", "target": "calc.exe", "category": "utility"},
    "calc": {"name": "Calculator", "target": "calc.exe", "category": "utility"},
    "task manager": {"name": "Task Manager", "target": "taskmgr.exe", "category": "system"},
    "taskmgr": {"name": "Task Manager", "target": "taskmgr.exe", "category": "system"},
    "command prompt": {"name": "Command Prompt", "target": "cmd.exe", "category": "system"},
    "cmd": {"name": "Command Prompt", "target": "cmd.exe", "category": "system"},
    "powershell": {"name": "Windows PowerShell", "target": "powershell.exe", "category": "system"},
    "file explorer": {"name": "File Explorer", "target": "explorer.exe", "category": "system"},
    "explorer": {"name": "File Explorer", "target": "explorer.exe", "category": "system"},
    "control panel": {"name": "Control Panel", "target": "control.exe", "category": "system"},
    "settings": {"name": "Windows Settings", "target": "start ms-settings:", "category": "system", "is_uri": True},
    "paint": {"name": "Paint", "target": "mspaint.exe", "category": "utility"},
    "snip": {"name": "Snipping Tool", "target": "snippingtool.exe", "category": "utility"},
    "registry editor": {"name": "Registry Editor", "target": "regedit.exe", "category": "system"},
    "regedit": {"name": "Registry Editor", "target": "regedit.exe", "category": "system"},
    "device manager": {"name": "Device Manager", "target": "devmgmt.msc", "category": "system"},
    "services": {"name": "Services", "target": "services.msc", "category": "system"},
}

# Ignore unhelpful utility/uninstall shortcuts
IGNORED_PATTERNS = [
    "uninstall", "remove", "help", "documentation", "release notes", 
    "readme", "license", "deactivate", "manual", "website", "config editor"
]


class AppDiscoveryEngine:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(AppDiscoveryEngine, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self.app_catalog: Dict[str, Dict[str, Any]] = {}
        self.app_aliases: Dict[str, str] = {}
        self.refresh_catalog()
        self._initialized = True

    def refresh_catalog(self):
        """Scans the Windows filesystem and start menus for installed applications."""
        catalog: Dict[str, Dict[str, Any]] = {}

        # 1. Add Common Built-in Windows Apps
        for key, info in COMMON_SYSTEM_APPS.items():
            catalog[key] = info

        # 2. Start Menu Paths
        start_menu_dirs = [
            os.path.expandvars(r"%ProgramData%\Microsoft\Windows\Start Menu\Programs"),
            os.path.expandvars(r"%AppData%\Microsoft\Windows\Start Menu\Programs"),
            os.path.expandvars(r"%USERPROFILE%\Desktop"),
            os.path.expandvars(r"%PUBLIC%\Desktop")
        ]

        for base_dir in start_menu_dirs:
            if not os.path.isdir(base_dir):
                continue
            for root, _, files in os.walk(base_dir):
                for f in files:
                    if f.lower().endswith(".lnk"):
                        app_name = os.path.splitext(f)[0].strip()
                        lower_name = app_name.lower()

                        # Skip unwanted shortcuts
                        if any(ign in lower_name for ign in IGNORED_PATTERNS):
                            continue

                        full_path = os.path.join(root, f)
                        catalog[lower_name] = {
                            "name": app_name,
                            "target": full_path,
                            "is_shortcut": True,
                            "category": "application"
                        }

        self.app_catalog = catalog
        self._build_aliases()
        logger.info(f"Indexed {len(self.app_catalog)} desktop applications and utilities.")

    def _build_aliases(self):
        """Builds convenient voice aliases for common software."""
        aliases = {}
        alias_rules = [
            ("photoshop", ["ps", "adobe photoshop", "photoshop cs6", "photoshop cc"]),
            ("after effects", ["ae", "adobe after effects", "after effect", "aftereffects"]),
            ("visual studio code", ["vs code", "vscode", "code"]),
            ("google chrome", ["chrome", "google"]),
            ("microsoft edge", ["edge", "browser"]),
            ("vlc media player", ["vlc", "vlc player"]),
            ("wondershare filmora 15", ["filmora", "wondershare filmora", "video editor"]),
            ("topaz video ai", ["topaz", "topaz video", "video enhancer"]),
            ("coreldraw 2021 (64-bit)", ["coreldraw", "corel draw", "corel"]),
            ("autocad 2023 - english", ["autocad", "cad"]),
            ("3ds max 2022 - english", ["3ds max", "3d max", "3dsmax"]),
            ("word 2013", ["word", "ms word", "microsoft word"]),
            ("excel 2013", ["excel", "ms excel", "microsoft excel"]),
            ("powerpoint 2013", ["powerpoint", "ppt", "ms powerpoint"]),
            ("discord", ["discord app"]),
            ("github desktop", ["github"]),
            ("winrar", ["rar"]),
            ("windows powershell", ["powershell"]),
            ("command prompt", ["cmd"]),
            ("task manager", ["task manager", "taskmgr"]),
        ]

        for real_key, synonyms in alias_rules:
            # Find the best matching key in catalog
            target_key = None
            if real_key in self.app_catalog:
                target_key = real_key
            else:
                for cat_k in self.app_catalog:
                    if real_key in cat_k:
                        target_key = cat_k
                        break

            if target_key:
                for syn in synonyms:
                    aliases[syn] = target_key

        self.app_aliases = aliases

    def find_app(self, query: str) -> Optional[Dict[str, Any]]:
        """Finds an application in the catalog using exact, alias, substring, or fuzzy matching."""
        q = query.lower().strip()
        if not q:
            return None

        # Check aliases first
        if q in self.app_aliases:
            canonical = self.app_aliases[q]
            return self.app_catalog.get(canonical)

        # Direct exact match
        if q in self.app_catalog:
            return self.app_catalog[q]

        # Substring search (e.g. "photoshop" in "adobe photoshop cs6 (64 bit)")
        for key, info in self.app_catalog.items():
            if q in key:
                return info

        # Reversed substring search (e.g. key in query)
        for key, info in self.app_catalog.items():
            if len(key) >= 4 and key in q:
                return info

        # Fuzzy match
        matches = difflib.get_close_matches(q, list(self.app_catalog.keys()), n=1, cutoff=0.6)
        if matches:
            return self.app_catalog[matches[0]]

        return None

    def launch_app(self, query: str) -> Tuple[bool, str]:
        """Launches an application by voice name."""
        app_info = self.find_app(query)
        if not app_info:
            return False, f"Maaf kijiye, mujhe '{query}' naam ka software aapke desktop par nahi mila."

        target = app_info["target"]
        name = app_info["name"]

        try:
            if app_info.get("is_uri"):
                os.system(target)
            elif app_info.get("is_shortcut"):
                os.startfile(target)
            else:
                subprocess.Popen(target, shell=True)
            return True, f"Maine {name} open kar diya hai sir."
        except Exception as e:
            logger.error(f"Error launching app {name}: {e}")
            return False, f"{name} ko launch karne me dikkat aayi: {e}"

    def close_app(self, query: str) -> Tuple[bool, str]:
        """Closes or terminates a running application by name."""
        import psutil
        q = query.lower().strip()
        app_info = self.find_app(q)
        target_name = app_info["name"].lower() if app_info else q

        closed_count = 0
        try:
            for proc in psutil.process_iter(['pid', 'name', 'exe']):
                p_name = (proc.info['name'] or "").lower()
                # Check if process name matches
                if q in p_name or target_name in p_name or (p_name.replace(".exe", "") in q):
                    try:
                        proc.terminate()
                        closed_count += 1
                    except Exception:
                        pass

            if closed_count > 0:
                return True, f"Maine {query} ko close kar diya hai ({closed_count} processes terminated)."
            else:
                return False, f"{query} abhi background ya foreground me run nahi ho raha hai."
        except Exception as e:
            return False, f"{query} ko band karne me error aaya: {e}"

    def list_installed_apps(self, limit: int = 50) -> List[str]:
        """Returns sorted list of installed app names."""
        names = sorted({info["name"] for info in self.app_catalog.values()})
        return names[:limit]


# Global Singleton
app_engine = AppDiscoveryEngine()
