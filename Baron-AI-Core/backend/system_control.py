"""
BARON CORE - Comprehensive Windows System Controller
Provides deep system-level control over applications, volume, media, power,
windows, screenshots, clipboard, and hardware diagnostics.
"""

import os
import re
import sys
import time
import ctypes
import webbrowser
import subprocess
import logging
from datetime import datetime
from urllib.parse import urlencode, quote_plus
from typing import Optional, Tuple, Dict, Any

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

try:
    from backend.app_discovery import app_engine
    from backend.os_operator import os_operator
except ImportError:
    try:
        from app_discovery import app_engine
        from os_operator import os_operator
    except Exception:
        app_engine = None
        os_operator = None

logger = logging.getLogger("BaronSystemControl")

# Windows Virtual-Key Codes for Volume & Media
VK_VOLUME_MUTE = 0xAD
VK_VOLUME_DOWN = 0xAE
VK_VOLUME_UP = 0xAF
VK_MEDIA_NEXT_TRACK = 0xB0
VK_MEDIA_PREV_TRACK = 0xB1
VK_MEDIA_PLAY_PAUSE = 0xB3


def _send_key(vk_code: int):
    """Sends a Windows virtual key press and release event."""
    ctypes.windll.user32.keybd_event(vk_code, 0, 0, 0)
    time.sleep(0.05)
    ctypes.windll.user32.keybd_event(vk_code, 0, 2, 0)


# Common application mapping
APP_MAP = {
    # Browsers
    "chrome": "chrome.exe",
    "google chrome": "chrome.exe",
    "edge": "msedge.exe",
    "microsoft edge": "msedge.exe",
    "firefox": "firefox.exe",
    "brave": "brave.exe",

    # Editors & IDEs
    "vscode": "code",
    "vs code": "code",
    "code": "code",
    "visual studio code": "code",
    "notepad": "notepad.exe",
    "notes": "notepad.exe",
    "sublime": "subl.exe",

    # Utilities
    "calculator": "calc.exe",
    "calc": "calc.exe",
    "hisaab": "calc.exe",
    "task manager": "taskmgr.exe",
    "taskmgr": "taskmgr.exe",
    "settings": "ms-settings:",
    "control panel": "control.exe",
    "command prompt": "cmd.exe",
    "cmd": "cmd.exe",
    "powershell": "powershell.exe",
    "terminal": "powershell.exe",
    "paint": "mspaint.exe",
    "snipping tool": "snippingtool.exe",

    # Explorers & Shell folders
    "file explorer": "explorer.exe",
    "explorer": "explorer.exe",
    "files": "explorer.exe",
    "my computer": "explorer.exe",
    "this pc": "explorer.exe",
    "downloads": "shell:Downloads",
    "documents": "shell:Personal",
    "desktop": "shell:Desktop",
    "pictures": "shell:My Pictures",
    "music": "shell:My Music",
    "videos": "shell:My Video",

    # Communication & Social
    "spotify": "spotify.exe",
    "whatsapp": "whatsapp:",
    "telegram": "telegram.exe",
    "discord": "discord.exe",
}


def open_application(app_name: str) -> Tuple[bool, str]:
    """Opens a Windows application, folder, or setting."""
    app_lower = app_name.strip().lower()

    websites = {
        "youtube": "https://www.youtube.com",
        "you tube": "https://www.youtube.com",
        "google": "https://www.google.com",
        "gmail": "https://mail.google.com",
    }
    if app_lower in websites:
        return open_url(websites[app_lower])

    # 1. Check exact APP_MAP first
    target = APP_MAP.get(app_lower)
    if not target:
        for key, val in APP_MAP.items():
            if key == app_lower:
                target = val
                break

    # 2. If not found in standard APP_MAP, try Dynamic App Discovery (160+ PC apps)
    if not target and app_engine:
        success, msg = app_engine.launch_app(app_name)
        if success:
            return True, msg

    if not target:
        # Check partial match in APP_MAP
        for key, val in APP_MAP.items():
            if key in app_lower or app_lower in key:
                target = val
                break

    if not target:
        target = f"{app_lower}.exe"

    try:
        if target.startswith("shell:"):
            subprocess.Popen(["explorer.exe", target])
        elif target.startswith("ms-settings:") or target.endswith(":"):
            if sys.platform == "win32":
                os.startfile(target)
            else:
                return False, f"{app_name.capitalize()} sirf Windows par open ho sakta hai."
        elif sys.platform == "win32":
            os.startfile(target)
        else:
            subprocess.Popen([target])
        return True, f"{app_name.capitalize()} khol diya hai."
    except Exception as e:
        logger.error(f"Failed to open app {app_name}: {e}")
        return False, f"{app_name} open karne me dikkat aayi: {e}"


def close_application(app_name: str) -> Tuple[bool, str]:
    """Terminates a process matching the app name."""
    # 1. Try Dynamic App Discovery Engine
    if app_engine:
        success, msg = app_engine.close_app(app_name)
        if success:
            return True, msg

    if not psutil:
        return False, "psutil install nahi hai."

    target = app_name.strip().lower().replace(".exe", "")
    closed = 0

    for proc in psutil.process_iter(['name', 'pid']):
        try:
            pname = (proc.info.get('name') or '').lower().replace(".exe", "")
            if target == pname or target in pname:
                proc.terminate()
                closed += 1
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    if closed > 0:
        return True, f"{app_name.capitalize()} band kar diya hai ({closed} process closed)."
    return False, f"{app_name} chalte hue nahi mila."


# ---------------- Media & Volume ----------------
def volume_up(steps: int = 5) -> str:
    for _ in range(steps):
        _send_key(VK_VOLUME_UP)
    return "Volume badha diya."

def volume_down(steps: int = 5) -> str:
    for _ in range(steps):
        _send_key(VK_VOLUME_DOWN)
    return "Volume kam kar diya."

def volume_mute() -> str:
    _send_key(VK_VOLUME_MUTE)
    return "Volume mute ya unmute toggle kiya."

def media_play_pause() -> str:
    _send_key(VK_MEDIA_PLAY_PAUSE)
    return "Media play/pause toggle kiya."

def media_next() -> str:
    _send_key(VK_MEDIA_NEXT_TRACK)
    return "Next track chala diya."

def media_prev() -> str:
    _send_key(VK_MEDIA_PREV_TRACK)
    return "Previous track kiya."


# ---------------- Power Operations ----------------
def lock_screen() -> str:
    ctypes.windll.user32.LockWorkStation()
    return "Screen lock kar diya hai."

def sleep_pc() -> str:
    subprocess.Popen(["rundll32.exe", "powrprof.dll,SetSuspendState", "0,1,0"], creationflags=subprocess.CREATE_NO_WINDOW)
    return "System sleep mode me daal diya hai."

def restart_pc(seconds: int = 10) -> str:
    subprocess.Popen(["shutdown", "/r", "/t", str(seconds)], creationflags=subprocess.CREATE_NO_WINDOW)
    return f"System {seconds} seconds me restart hoga."

def shutdown_pc(seconds: int = 10) -> str:
    subprocess.Popen(["shutdown", "/s", "/t", str(seconds)], creationflags=subprocess.CREATE_NO_WINDOW)
    return f"System {seconds} seconds me shut down hoga."

def cancel_shutdown() -> str:
    subprocess.Popen(["shutdown", "/a"], creationflags=subprocess.CREATE_NO_WINDOW)
    return "Shutdown cancel kar diya hai."


# ---------------- Window Management ----------------
def minimize_all() -> str:
    if pyautogui:
        pyautogui.hotkey('win', 'd')
        return "Sabhi windows minimize kar di hain."
    return "PyAutoGUI available nahi hai."

def minimize_active() -> str:
    if pyautogui:
        pyautogui.hotkey('win', 'down')
        return "Active window minimize kiya."
    return "PyAutoGUI available nahi hai."

def maximize_active() -> str:
    if pyautogui:
        pyautogui.hotkey('win', 'up')
        return "Active window maximize kiya."
    return "PyAutoGUI available nahi hai."

def close_active_window() -> str:
    if pyautogui:
        pyautogui.hotkey('alt', 'f4')
        return "Window close kar di hai."
    return "PyAutoGUI available nahi hai."

def switch_window() -> str:
    if pyautogui:
        pyautogui.hotkey('alt', 'tab')
        return "Window switch kiya."
    return "PyAutoGUI available nahi hai."


# ---------------- Screenshot & Clipboard ----------------
def take_screenshot() -> Tuple[bool, str]:
    try:
        pictures_dir = os.path.join(os.path.expanduser("~"), "Pictures", "Screenshots")
        os.makedirs(pictures_dir, exist_ok=True)
        filename = f"Baron_Screenshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        filepath = os.path.join(pictures_dir, filename)

        if pyautogui:
            shot = pyautogui.screenshot()
            shot.save(filepath)
            # Open screenshot
            os.system(f'start "" "{filepath}"')
            return True, f"Screenshot le liya hai aur Pictures/Screenshots me save kar diya hai."
        return False, "Screenshot tool available nahi hai."
    except Exception as e:
        return False, f"Screenshot lene me error: {e}"

def read_clipboard() -> str:
    if pyperclip:
        content = pyperclip.paste()
        if content and content.strip():
            preview = content.strip()[:150]
            return f"Clipboard me yeh hai: {preview}"
        return "Clipboard abhi empty hai."
    return "Pyperclip available nahi hai."

def write_clipboard(text: str) -> str:
    if pyperclip:
        pyperclip.copy(text)
        return f"Clipboard me copy kar diya: '{text[:50]}...'"
    return "Pyperclip available nahi hai."


# ---------------- System Diagnostics ----------------
def get_system_diagnostics() -> str:
    if not psutil:
        return "System diagnostics ke liye psutil module zaroori hai."

    cpu = psutil.cpu_percent(interval=0.5)
    mem = psutil.virtual_memory()
    mem_used_gb = round((mem.total - mem.available) / (1024 ** 3), 1)
    mem_total_gb = round(mem.total / (1024 ** 3), 1)
    mem_pct = mem.percent

    disk = psutil.disk_usage("C:\\")
    disk_free_gb = round(disk.free / (1024 ** 3), 1)

    battery_info = ""
    battery = psutil.sensors_battery()
    if battery:
        plugged = "charging pe hai" if battery.power_plugged else "battery par chal raha hai"
        battery_info = f" Battery: {battery.percent}% ({plugged})."

    return (
        f"System Status: CPU usage {cpu}%, "
        f"RAM: {mem_used_gb} GB used out of {mem_total_gb} GB ({mem_pct}%), "
        f"C Drive free space: {disk_free_gb} GB.{battery_info}"
    )

def get_running_apps() -> str:
    if not psutil:
        return "psutil available nahi hai."

    names = set()
    ignored = {"svchost", "csrss", "system", "runtimebroker", "conhost", "dllhost",
               "sihost", "fontdrvhost", "taskhostw", "services", "lsass", "smss"}

    for proc in psutil.process_iter(['name']):
        try:
            n = proc.info.get('name', '')
            if n:
                clean_name = n.lower().replace(".exe", "")
                if clean_name not in ignored and not clean_name.startswith("system"):
                    names.add(clean_name)
        except Exception:
            continue

    top = sorted(list(names))[:8]
    if top:
        return f"Filhal yeh apps chal rahe hain: {', '.join(top)} aur background services."
    return "Koi major app run hote hue nahi mila."


# ---------------- Web & Online Searches ----------------
def search_google(query: str) -> str:
    url = f"https://www.google.com/search?q={quote_plus(query)}"
    if webbrowser.open(url, new=2):
        return f"Google par '{query}' search kar raha hoon."
    return "Google search open nahi ho payi. Default browser check kijiye."

def play_youtube(song_or_video: str) -> str:
    query = quote_plus(song_or_video)
    url = f"https://www.youtube.com/results?search_query={query}"
    if webbrowser.open(url, new=2):
        return f"YouTube par '{song_or_video}' ke results khol raha hoon."
    return "YouTube open nahi ho paya. Default browser check kijiye."

def open_url(url: str) -> str:
    if not url.startswith("http://") and not url.startswith("https://"):
        url = "https://" + url
    if webbrowser.open(url, new=2):
        return f"Website open kar di hai: {url}"
    return f"Website open nahi ho payi: {url}. Default browser check kijiye."


# ---------------- Master System Command Router ----------------
def execute_system_command(command_text: str) -> Optional[str]:
    """
    Checks if the user command is a direct Windows system command.
    Returns response string if handled, or None if it should be sent to AI Brain.
    """
    t = command_text.strip().lower()

    # Clean leading filler
    t = re.sub(r'^(baron|hey baron|bairan|barun)\s*[,:\s]*', '', t).strip()
    t = re.sub(r'[!?.,]+$', '', t).strip()

    # 1. Volume & Audio
    if re.search(r'\b(volume up|awaz badhao|sound badhao|volume badha|volume bada)\b', t):
        return volume_up()
    if re.search(r'\b(volume down|awaz kam karo|sound kam karo|volume ghatao)\b', t):
        return volume_down()
    if re.search(r'\b(mute|unmute|awaz band karo|silent karo|mute karo)\b', t):
        return volume_mute()
    if re.search(r'\b(play|pause|gana roko|chalao|pause karo|play karo)\b', t) and not re.search(r'(youtube|yt|on youtube)', t):
        return media_play_pause()
    if re.search(r'\b(next song|next track|agla gana|change song)\b', t):
        return media_next()
    if re.search(r'\b(previous song|prev track|purana gana)\b', t):
        return media_prev()

    # 2. YouTube Play / Website
    yt_match = re.search(r'(?:play|chalao|bajao)\s+(.+?)\s+(?:on|par|pe)\s+(?:youtube|yt)', t)
    if yt_match:
        return play_youtube(yt_match.group(1))

    yt_match2 = re.search(r'(?:youtube|yt)\s+(?:pe|par|on)?\s*(.+?)\s*(?:chalao|play karo|bajao)', t)
    if yt_match2 and yt_match2.group(1).strip():
        return play_youtube(yt_match2.group(1).strip())

    if re.search(r'^(?:open|kholo|खोलो|खोलिए|खोल दीजिए)\s+(?:youtube|you tube|yt)(?:\s+(?:website|site))?$', t) or re.search(
        r'^(?:youtube|you tube|yt)(?:\s+(?:ko|को|website|site))?\s+(?:open|kholo|खोलो|खोलिए|open karo|खोल दीजिए)$', t
    ):
        return open_url("https://www.youtube.com")

    # 3. Google Search
    g_match = re.search(
        r'^(?:google\s+(?:par|pe|me)\s+)?search(?:\s+(?:for|karo))?\s+(.+)$', t
    )
    if not g_match:
        g_match = re.search(r'google\s+(?:par|pe|me)\s+(.+?)\s+search(?:\s+karo)?$', t)
    if g_match and not re.search(r'(youtube|file|folder)', t):
        query = re.sub(r'\s+(?:on|in)\s+google$', '', g_match.group(1)).strip()
        return search_google(query)

    # 4. Power Operations
    if re.search(r'\b(lock screen|lock pc|lock computer|screen lock|pc lock karo|system lock karo)\b', t):
        return lock_screen()
    if re.search(r'\b(sleep mode|pc sulao|sleep karo|sleep pc|hibernate)\b', t):
        return sleep_pc()
    if re.search(r'\b(restart pc|restart karo|system restart|reboot)\b', t):
        return restart_pc()
    if re.search(r'\b(cancel shutdown|shutdown cancel|band mat karo)\b', t):
        return cancel_shutdown()
    if re.search(r'\b(shutdown|shut down|pc band karo|system band karo|power off)\b', t):
        return shutdown_pc()

    # 5. Screenshots
    if re.search(r'\b(take screenshot|screenshot lo|screenshot khicho|capture screen|screen capture)\b', t):
        _, msg = take_screenshot()
        return msg

    # 6. Window Management
    if os_operator and re.search(r'\b(snap (?:window )?left|left snap|left me karo)\b', t):
        return os_operator.snap_left()
    if os_operator and re.search(r'\b(snap (?:window )?right|right snap|right me karo)\b', t):
        return os_operator.snap_right()
    if os_operator and re.search(r'\b(empty recycle bin|recycle bin khali karo|kachra saaf karo)\b', t):
        return os_operator.empty_recycle_bin()
    if os_operator and re.search(r'\b(open (?:the )?(?:downloads|documents|desktop|pictures|videos|music|screenshots) folder|(?:downloads|documents|desktop|pictures|videos|music|screenshots) folder kholo)\b', t):
        f_match = re.search(r'(downloads|documents|desktop|pictures|videos|music|screenshots)', t)
        if f_match:
            _, msg = os_operator.open_known_folder(f_match.group(1))
            return msg

    if re.search(r'\b(minimize all|show desktop|desktop dikhao|sab minimize karo)\b', t):
        return minimize_all()
    if re.search(r'\b(minimize window|minimize karo|isse minimize karo)\b', t):
        return minimize_active()
    if re.search(r'\b(maximize window|maximize karo|full screen karo)\b', t):
        return maximize_active()
    if re.search(r'\b(close window|window band karo|ye band karo)\b', t):
        return close_active_window()
    if re.search(r'\b(switch window|app switch|app badlo|dusri window)\b', t):
        return switch_window()

    # 7. Clipboard
    if re.search(r'\b(clipboard me kya hai|what is in clipboard|read clipboard|clipboard read karo)\b', t):
        return read_clipboard()

    # 8. Diagnostics
    if re.search(r'\b(system status|pc status|system condition|cpu usage|ram usage|battery status|battery kitni hai)\b', t):
        return get_system_diagnostics()
    if re.search(r'\b(running apps|kya chal raha hai|kaunsi app chal rahi hai|running processes)\b', t):
        return get_running_apps()

    # 9. Time & Date
    if re.search(r'\b(time kya hai|what is the time|current time|kitne baje hai|samay kya hua)\b', t):
        now = datetime.now()
        return f"Abhi time hai {now.strftime('%I:%M %p')}."
    if re.search(r'\b(aaj kya date hai|what is today\'s date|aaj ki tarikh|current date)\b', t):
        now = datetime.now()
        return f"Aaj date hai {now.strftime('%A, %d %B %Y')}."

    # 10. Close Application
    close_m = re.search(r'^(?:close|band karo|hatao)\s+(.+)$', t)
    if not close_m:
        close_m = re.search(r'^(.+?)\s+(?:(?:ko|को)\s+)?(?:band karo|close(?: karo)?|बंद करो)$', t)
    if close_m:
        app_target = re.sub(r'\b(?:app|ko)\b|को', '', close_m.group(1)).strip()
        if app_target in APP_MAP or any(app_target in k for k in APP_MAP):
            _, msg = close_application(app_target)
            return msg

    # 11. Open Application
    open_m = re.search(r'^(?:open|start|launch|kholo|खोलो|खोलिए)\s+(.+)$', t)
    if not open_m:
        open_m = re.search(
            r'^(.+?)\s+(?:(?:ko|को)\s+)?(?:kholo|खोलो|खोलिए|खोल दीजिए|open(?: karo)?|launch(?: karo)?)$', t
        )
    if open_m:
        app_target = re.sub(r'\b(?:app|ko)\b|को', '', open_m.group(1)).strip()
        # Ensure it's not a generic word
        if app_target and app_target not in {"something", "anything", "mouth", "door", "eyes"}:
            _, msg = open_application(app_target)
            return msg

    # 12. Autonomous Coding Agent Commands (Module 1: Phase 1)
    if re.search(r'\b(scan workspace|scan project|project scan|workspace scan|code scan)\b', t):
        try:
            from backend import coding_agent
        except ImportError:
            import coding_agent
        res = coding_agent.agent.scan()
        if res.get("success"):
            langs = ", ".join(f"{k}: {v}" for k, v in res.get("languages", {}).items())
            return f"Workspace scan complete! Total {res['total_files']} files and {res['total_directories']} folders found. Languages: {langs}."
        return f"Scan error: {res.get('error')}"

    if re.search(r'\b(index architecture|index project|project architecture|code index|index code)\b', t):
        try:
            from backend import coding_agent
        except ImportError:
            import coding_agent
        res = coding_agent.agent.index()
        if res.get("success"):
            return f"Project architecture indexed! Project: {res['project_name']}, Entrypoints: {', '.join(res['entrypoints'][:4])}, Symbols indexed in {res['symbols_indexed_files']} files."
        return f"Indexing error: {res.get('error')}"

    # Read File command: "read file app.js", "read source baron_service.py"
    read_m = re.search(r'\b(?:read file|read source|file padho|source padho)\s+([a-zA-Z0-9_\-./\\]+)', t)
    if read_m:
        target_f = read_m.group(1).strip()
        try:
            from backend import coding_agent
        except ImportError:
            import coding_agent
        res = coding_agent.agent.read(target_f, start_line=1, end_line=30)
        if res.get("success"):
            return f"File '{res['file_name']}' ({res['language']}, {res['total_lines']} lines) read successfully. Showing first {min(30, res['total_lines'])} lines:\n{res['numbered_content'][:400]}..."
        return f"Could not read file: {res.get('error')}"

    # Test File command: "test file test_voice.py", "run tests"
    test_m = re.search(r'\b(?:test file|run test on|code test karo)\s+([a-zA-Z0-9_\-./\\]+)', t)
    if test_m:
        target_f = test_m.group(1).strip()
        try:
            from backend import coding_agent
        except ImportError:
            import coding_agent
        res = coding_agent.agent.test(target_f)
        if res.get("success"):
            return f"Test passed on '{target_f}'! Execution time: {res['duration_ms']}ms."
        analysis = res.get("analysis", {})
        return f"Test failed on '{target_f}'. Category: {analysis.get('error_category')}. Summary: {analysis.get('summary')}. Suggestion: {analysis.get('suggestion')}"

    # If not a recognized direct system command, return None to send to AI Brain
    return None

