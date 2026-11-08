"""
BARON CORE - Deep Windows OS Operating Engine (JARVIS Operator)
Provides complete voice-driven control over Windows windows, files, processes, power, and audio.
"""

import os
import sys
import time
import glob
import ctypes
import logging
import subprocess
import webbrowser
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any

try:
    import psutil
except ImportError:
    psutil = None

try:
    import pyautogui
except ImportError:
    pyautogui = None

try:
    import pyperclip
except ImportError:
    pyperclip = None

logger = logging.getLogger("BaronOSOperator")

# Virtual key codes
VK_VOLUME_MUTE = 0xAD
VK_VOLUME_DOWN = 0xAE
VK_VOLUME_UP = 0xAF
VK_MEDIA_NEXT_TRACK = 0xB0
VK_MEDIA_PREV_TRACK = 0xB1
VK_MEDIA_PLAY_PAUSE = 0xB3


def _send_vk(vk_code: int):
    """Sends a virtual key event."""
    ctypes.windll.user32.keybd_event(vk_code, 0, 0, 0)
    time.sleep(0.04)
    ctypes.windll.user32.keybd_event(vk_code, 0, 2, 0)


class WindowsOSOperator:
    """Master controller for Windows Desktop actions."""

    # ---------------- Window Management ----------------
    @staticmethod
    def snap_left() -> str:
        if pyautogui:
            pyautogui.hotkey('win', 'left')
            return "Window ko left screen par snap kar diya hai."
        return "Window control module unavailable."

    @staticmethod
    def snap_right() -> str:
        if pyautogui:
            pyautogui.hotkey('win', 'right')
            return "Window ko right screen par snap kar diya hai."
        return "Window control module unavailable."

    @staticmethod
    def maximize_window() -> str:
        if pyautogui:
            pyautogui.hotkey('win', 'up')
            return "Active window ko maximize kar diya hai."
        return "Window control module unavailable."

    @staticmethod
    def minimize_window() -> str:
        if pyautogui:
            pyautogui.hotkey('win', 'down')
            return "Active window ko minimize kar diya hai."
        return "Window control module unavailable."

    @staticmethod
    def show_desktop() -> str:
        if pyautogui:
            pyautogui.hotkey('win', 'd')
            return "Desktop dikha diya gaya hai."
        return "Desktop action unavailable."

    @staticmethod
    def switch_window() -> str:
        if pyautogui:
            pyautogui.hotkey('alt', 'tab')
            return "Window switch kar di hai."
        return "Window switch action unavailable."

    @staticmethod
    def close_active_window() -> str:
        if pyautogui:
            pyautogui.hotkey('alt', 'f4')
            return "Current active window ko close kar diya hai."
        return "Close window action unavailable."

    @staticmethod
    def list_open_windows() -> List[str]:
        """Lists titles of all visible on-screen application windows."""
        windows = []
        def enum_handler(hwnd, extra):
            if ctypes.windll.user32.IsWindowVisible(hwnd):
                length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
                if length > 0:
                    buff = ctypes.create_unicode_buffer(length + 1)
                    ctypes.windll.user32.GetWindowTextW(hwnd, buff, length + 1)
                    title = buff.value.strip()
                    # Filter out empty or invisible tool windows
                    if title and title not in ["Program Manager", "Settings", "Default IME", "MSCTFIME UI"]:
                        windows.append(title)
            return True

        WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_int, ctypes.c_int)
        ctypes.windll.user32.EnumWindows(WNDENUMPROC(enum_handler), 0)
        return list(dict.fromkeys(windows))[:12]

    @staticmethod
    def focus_window_by_name(title_query: str) -> Tuple[bool, str]:
        """Brings an application window to front matching title_query."""
        q = title_query.lower()
        target_hwnd = None
        matched_title = ""

        def enum_handler(hwnd, extra):
            nonlocal target_hwnd, matched_title
            if ctypes.windll.user32.IsWindowVisible(hwnd):
                length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
                if length > 0:
                    buff = ctypes.create_unicode_buffer(length + 1)
                    ctypes.windll.user32.GetWindowTextW(hwnd, buff, length + 1)
                    title = buff.value.strip()
                    if q in title.lower():
                        target_hwnd = hwnd
                        matched_title = title
                        return False
            return True

        WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_int, ctypes.c_int)
        ctypes.windll.user32.EnumWindows(WNDENUMPROC(enum_handler), 0)

        if target_hwnd:
            # Restore if minimized
            ctypes.windll.user32.ShowWindow(target_hwnd, 9) # SW_RESTORE
            ctypes.windll.user32.SetForegroundWindow(target_hwnd)
            return True, f"'{matched_title}' window ko samne le aaya hoon."
        return False, f"'{title_query}' se match karti hui koi active window nahi mili."

    # ---------------- File & Folder Operations ----------------
    @staticmethod
    def open_known_folder(folder_name: str) -> Tuple[bool, str]:
        """Opens user folders like Desktop, Downloads, Documents, etc."""
        f_lower = folder_name.lower().strip()
        user_home = os.path.expanduser("~")

        folder_mapping = {
            "desktop": os.path.join(user_home, "Desktop"),
            "downloads": os.path.join(user_home, "Downloads"),
            "documents": os.path.join(user_home, "Documents"),
            "pictures": os.path.join(user_home, "Pictures"),
            "screenshots": os.path.join(user_home, "Pictures", "Screenshots"),
            "videos": os.path.join(user_home, "Videos"),
            "music": os.path.join(user_home, "Music"),
            "c drive": "C:\\",
            "d drive": "D:\\",
            "root": "C:\\",
            "baron": os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        }

        target = folder_mapping.get(f_lower)
        if not target:
            # Check if it exists directly
            potential = os.path.join(user_home, folder_name)
            if os.path.isdir(potential):
                target = potential

        if target and os.path.exists(target):
            try:
                os.startfile(target)
                return True, f"Maine {folder_name} folder khol diya hai."
            except Exception as e:
                return False, f"Folder kholne me error: {e}"
        return False, f"'{folder_name}' folder nahi mila."

    @staticmethod
    def search_user_files(query: str, search_in: str = "Desktop", max_results: int = 5) -> List[str]:
        """Finds files matching query in Desktop, Downloads, or Documents."""
        user_home = os.path.expanduser("~")
        target_dir = os.path.join(user_home, search_in)
        if not os.path.isdir(target_dir):
            target_dir = os.path.join(user_home, "Desktop")

        results = []
        q = query.lower()
        for root, _, files in os.walk(target_dir):
            for f in files:
                if q in f.lower():
                    results.append(os.path.join(root, f))
                    if len(results) >= max_results:
                        return results
        return results

    @staticmethod
    def create_desktop_folder(folder_name: str) -> Tuple[bool, str]:
        """Creates a new folder on the Desktop."""
        desk = os.path.join(os.path.expanduser("~"), "Desktop")
        new_dir = os.path.join(desk, folder_name)
        try:
            os.makedirs(new_dir, exist_ok=True)
            return True, f"Desktop par '{folder_name}' folder bana diya gaya hai."
        except Exception as e:
            return False, f"Folder banane me dikkat aayi: {e}"

    @staticmethod
    def empty_recycle_bin() -> str:
        """Empties the Windows Recycle Bin silently."""
        try:
            # SHERB_NOCONFIRMATION = 0x00000001, SHERB_NOPROGRESSUI = 0x00000002, SHERB_NOSOUND = 0x00000004
            flags = 7
            result = ctypes.windll.shell32.SHEmptyRecycleBinW(None, None, flags)
            if result == 0:
                return "Recycle Bin ko safalta-poorvak empty kar diya gaya hai."
            return "Recycle Bin pehle se hi empty hai."
        except Exception as e:
            return f"Recycle Bin empty karne me error: {e}"

    # ---------------- Audio & Media Control ----------------
    @staticmethod
    def set_volume_percent(level: int) -> str:
        """Approximates setting volume to given percentage (0-100)."""
        target = max(0, min(100, level))
        # First mute/zero out by pressing Volume Down 50 times
        for _ in range(50):
            _send_vk(VK_VOLUME_DOWN)
        # Then press Volume Up target / 2 times (each press is ~2%)
        steps = target // 2
        for _ in range(steps):
            _send_vk(VK_VOLUME_UP)
        return f"Volume {target}% par set kar diya hai."

    @staticmethod
    def volume_up() -> str:
        for _ in range(3):
            _send_vk(VK_VOLUME_UP)
        return "Volume badha diya gaya hai."

    @staticmethod
    def volume_down() -> str:
        for _ in range(3):
            _send_vk(VK_VOLUME_DOWN)
        return "Volume kam kar diya gaya hai."

    @staticmethod
    def volume_mute() -> str:
        _send_vk(VK_VOLUME_MUTE)
        return "Mute toggle kar diya gaya hai."

    @staticmethod
    def media_play_pause() -> str:
        _send_vk(VK_MEDIA_PLAY_PAUSE)
        return "Media play/pause toggle kiya gaya."

    @staticmethod
    def media_next() -> str:
        _send_vk(VK_MEDIA_NEXT_TRACK)
        return "Next track play kiya gaya."

    @staticmethod
    def media_prev() -> str:
        _send_vk(VK_MEDIA_PREV_TRACK)
        return "Previous track play kiya gaya."

    # ---------------- System Power & Diagnostics ----------------
    @staticmethod
    def lock_workstation() -> str:
        ctypes.windll.user32.LockWorkStation()
        return "System screen lock kar di gayi hai."

    @staticmethod
    def sleep_pc() -> str:
        try:
            # SetSuspendState(Hibernate=False, ForceCritical=False, DisableWakeEvent=False)
            ctypes.windll.PowrProf.SetSuspendState(0, 1, 0)
            return "PC ko sleep mode me daal diya gaya hai."
        except Exception as e:
            return f"Sleep command error: {e}"

    @staticmethod
    def restart_pc(delay_seconds: int = 30) -> str:
        subprocess.run(f"shutdown /r /t {delay_seconds}", shell=True)
        return f"PC {delay_seconds} seconds me restart hoga. Cancel karne ke liye 'Cancel shutdown' boliye."

    @staticmethod
    def shutdown_pc(delay_seconds: int = 60) -> str:
        subprocess.run(f"shutdown /s /t {delay_seconds}", shell=True)
        return f"PC {delay_seconds} seconds me band hoga. Cancel karne ke liye 'Cancel shutdown' boliye."

    @staticmethod
    def cancel_shutdown() -> str:
        subprocess.run("shutdown /a", shell=True)
        return "Shutdown/Restart process cancel kar diya gaya hai."

    @staticmethod
    def get_detailed_diagnostics() -> Dict[str, Any]:
        """Provides in-depth system metrics."""
        cpu_usage = psutil.cpu_percent(interval=0.2) if psutil else 0
        cpu_count = psutil.cpu_count(logical=True) if psutil else 1
        
        ram_info = {}
        if psutil:
            ram = psutil.virtual_memory()
            ram_info = {
                "percent": ram.percent,
                "used_gb": round(ram.used / (1024**3), 2),
                "total_gb": round(ram.total / (1024**3), 2)
            }

        disk_info = {}
        if psutil:
            disk = psutil.disk_usage("C:\\")
            disk_info = {
                "percent": disk.percent,
                "free_gb": round(disk.free / (1024**3), 1)
            }

        battery_info = "Desktop / AC Power"
        if psutil and psutil.sensors_battery():
            batt = psutil.sensors_battery()
            plugged = "Charging" if batt.power_plugged else "Discharging"
            battery_info = f"{batt.percent}% ({plugged})"

        # Top 3 Memory processes
        top_procs = []
        if psutil:
            for p in sorted(psutil.process_iter(['name', 'memory_percent']), key=lambda x: x.info.get('memory_percent') or 0, reverse=True)[:3]:
                top_procs.append(f"{p.info['name']} ({round(p.info['memory_percent'], 1)}%)")

        return {
            "cpu_percent": cpu_usage,
            "cpu_cores": cpu_count,
            "ram": ram_info,
            "disk_c": disk_info,
            "battery": battery_info,
            "top_memory_apps": top_procs
        }

    # ---------------- Screenshots & Vision ----------------
    @staticmethod
    def take_screenshot(filename: Optional[str] = None) -> Tuple[bool, str, str]:
        """Captures full screen screenshot and returns file path."""
        try:
            screenshots_dir = os.path.join(os.path.expanduser("~"), "Pictures", "Screenshots")
            os.makedirs(screenshots_dir, exist_ok=True)
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            fname = filename or f"Baron_Screen_{ts}.png"
            out_path = os.path.join(screenshots_dir, fname)

            if pyautogui:
                shot = pyautogui.screenshot()
                shot.save(out_path)
                return True, out_path, f"Screenshot save kar diya gaya hai: Pictures\\Screenshots\\{fname}"
            return False, "", "PyAutoGUI not available."
        except Exception as e:
            return False, "", f"Screenshot lene me error: {e}"


# Global Singleton
os_operator = WindowsOSOperator()
