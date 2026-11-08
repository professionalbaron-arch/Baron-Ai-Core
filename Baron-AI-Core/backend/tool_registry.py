"""
BARON CORE - Moltis-Inspired Extensible Tool & Function Registry
Provides unified schema-driven tool execution, inspection, and security guardrails.
Connects Qwen 2.5 and Gemini directly to the Windows OS Operator, App Discovery, and Coding Agent.
"""

import os
import sys
import json
import logging
from typing import Dict, Any, Callable, List, Optional

logger = logging.getLogger("BaronToolRegistry")

# Dangerous command keywords (Moltis-style security guardrail)
DANGEROUS_PATTERNS = [
    "format c:", "del /f /s /q c:", "rmdir /s /q c:\\windows",
    "drop database", "sudo rm -rf", "reg delete hklm"
]


class Tool:
    def __init__(self, name: str, description: str, parameters: Dict[str, Any], func: Callable, dangerous: bool = False):
        self.name = name
        self.description = description
        self.parameters = parameters
        self.func = func
        self.dangerous = dangerous

    def to_json_schema(self) -> Dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters
            }
        }


class ToolRegistry:
    """Central registry for all tools in Baron-AI-Core."""
    def __init__(self):
        self._tools: Dict[str, Tool] = {}

    def register(self, name: str, description: str, parameters: Dict[str, Any], dangerous: bool = False):
        def decorator(func: Callable):
            tool = Tool(name=name, description=description, parameters=parameters, func=func, dangerous=dangerous)
            self._tools[name] = tool
            return func
        return decorator

    def register_tool(self, tool: Tool):
        self._tools[tool.name] = tool

    def get_tool(self, name: str) -> Optional[Tool]:
        return self._tools.get(name)

    def list_tools(self) -> List[Dict[str, Any]]:
        return [tool.to_json_schema() for tool in self._tools.values()]

    def execute(self, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Executes a registered tool with guardrails."""
        tool = self.get_tool(name)
        if not tool:
            return {"success": False, "error": f"Tool '{name}' not found in registry."}

        # Guardrail check
        args_str = json.dumps(arguments).lower()
        for pattern in DANGEROUS_PATTERNS:
            if pattern in args_str:
                logger.warning(f"Blocked dangerous tool execution: {name} with args {arguments}")
                return {"success": False, "error": f"Action blocked: Potentially destructive command detected ('{pattern}')."}

        try:
            logger.info(f"Executing tool '{name}' with args: {arguments}")
            result = tool.func(**arguments)
            return {"success": True, "result": result}
        except Exception as e:
            logger.exception(f"Error executing tool '{name}': {e}")
            return {"success": False, "error": str(e)}


# Global Tool Registry Singleton
registry = ToolRegistry()


# ---------------- Register Applications & Windows Control ----------------
try:
    from backend.app_discovery import app_engine
    from backend.os_operator import os_operator
except ImportError:
    from app_discovery import app_engine
    from os_operator import os_operator


@registry.register(
    name="open_app",
    description="Opens any installed Windows software, application, utility, or game (e.g. Photoshop, AutoCAD, VS Code, Chrome, Filmora, VLC, Notepad, Settings, Calculator, 3ds Max).",
    parameters={
        "type": "object",
        "properties": {
            "app_name": {"type": "string", "description": "Name or common alias of the application to open."}
        },
        "required": ["app_name"]
    }
)
def tool_open_app(app_name: str) -> str:
    success, msg = app_engine.launch_app(app_name)
    return msg


@registry.register(
    name="close_app",
    description="Closes or terminates any running Windows application or process.",
    parameters={
        "type": "object",
        "properties": {
            "app_name": {"type": "string", "description": "Name of the app or process to close."}
        },
        "required": ["app_name"]
    }
)
def tool_close_app(app_name: str) -> str:
    success, msg = app_engine.close_app(app_name)
    return msg


@registry.register(
    name="list_installed_apps",
    description="Lists installed desktop applications discovered on the system.",
    parameters={
        "type": "object",
        "properties": {
            "limit": {"type": "integer", "description": "Maximum number of apps to return (default 30)."}
        }
    }
)
def tool_list_installed_apps(limit: int = 30) -> str:
    apps = app_engine.list_installed_apps(limit=limit)
    return f"Installed apps found: {', '.join(apps)}"


@registry.register(
    name="system_volume",
    description="Adjusts or mutes the system audio volume, or sets volume to an exact percentage.",
    parameters={
        "type": "object",
        "properties": {
            "action": {"type": "string", "enum": ["up", "down", "mute", "set"], "description": "Volume action to perform"},
            "percent": {"type": "integer", "description": "Volume percentage from 0 to 100 if action is 'set'."}
        },
        "required": ["action"]
    }
)
def tool_system_volume(action: str, percent: Optional[int] = None) -> str:
    if action == "set" and percent is not None:
        return os_operator.set_volume_percent(percent)
    elif action == "up":
        return os_operator.volume_up()
    elif action == "down":
        return os_operator.volume_down()
    elif action == "mute":
        return os_operator.volume_mute()
    return "Invalid volume action."


@registry.register(
    name="media_playback",
    description="Controls media playback (play/pause, next track, previous track).",
    parameters={
        "type": "object",
        "properties": {
            "action": {"type": "string", "enum": ["play_pause", "next", "prev"], "description": "Playback action"}
        },
        "required": ["action"]
    }
)
def tool_media_playback(action: str) -> str:
    if action == "play_pause":
        return os_operator.media_play_pause()
    elif action == "next":
        return os_operator.media_next()
    elif action == "prev":
        return os_operator.media_prev()
    return "Invalid media action."


@registry.register(
    name="window_control",
    description="Manages Windows desktop windows (snap left, snap right, maximize, minimize, show desktop, switch window, close window, or focus window by title).",
    parameters={
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["snap_left", "snap_right", "maximize", "minimize", "show_desktop", "switch", "close", "focus"],
                "description": "Window operation to perform"
            },
            "target": {"type": "string", "description": "Title or app name to focus if action is 'focus'."}
        },
        "required": ["action"]
    }
)
def tool_window_control(action: str, target: Optional[str] = None) -> str:
    if action == "snap_left":
        return os_operator.snap_left()
    elif action == "snap_right":
        return os_operator.snap_right()
    elif action == "maximize":
        return os_operator.maximize_window()
    elif action == "minimize":
        return os_operator.minimize_window()
    elif action == "show_desktop":
        return os_operator.show_desktop()
    elif action == "switch":
        return os_operator.switch_window()
    elif action == "close":
        return os_operator.close_active_window()
    elif action == "focus" and target:
        success, msg = os_operator.focus_window_by_name(target)
        return msg
    return "Unknown window operation."


@registry.register(
    name="list_open_windows",
    description="Lists all currently open and visible application windows on the desktop.",
    parameters={"type": "object", "properties": {}}
)
def tool_list_open_windows() -> str:
    windows = os_operator.list_open_windows()
    if windows:
        return f"Active open windows: {', '.join(windows)}"
    return "No active user windows found."


@registry.register(
    name="folder_control",
    description="Opens common user directories (Desktop, Downloads, Documents, Pictures, Screenshots, Videos, Music, C Drive).",
    parameters={
        "type": "object",
        "properties": {
            "folder_name": {"type": "string", "description": "Folder name (e.g. desktop, downloads, documents, pictures, c drive)"}
        },
        "required": ["folder_name"]
    }
)
def tool_folder_control(folder_name: str) -> str:
    success, msg = os_operator.open_known_folder(folder_name)
    return msg


@registry.register(
    name="create_desktop_folder",
    description="Creates a new folder on the user's Desktop.",
    parameters={
        "type": "object",
        "properties": {
            "folder_name": {"type": "string", "description": "Name of the new folder to create on the desktop"}
        },
        "required": ["folder_name"]
    }
)
def tool_create_desktop_folder(folder_name: str) -> str:
    success, msg = os_operator.create_desktop_folder(folder_name)
    return msg


@registry.register(
    name="empty_recycle_bin",
    description="Empties the Windows Recycle Bin to free up disk space.",
    parameters={"type": "object", "properties": {}}
)
def tool_empty_recycle_bin() -> str:
    return os_operator.empty_recycle_bin()


@registry.register(
    name="system_diagnostics",
    description="Retrieves real-time CPU, RAM, Disk, Battery, and top memory-consuming processes.",
    parameters={"type": "object", "properties": {}}
)
def tool_system_diagnostics() -> str:
    stats = os_operator.get_detailed_diagnostics()
    ram = stats.get('ram', {})
    disk = stats.get('disk_c', {})
    top_apps = ", ".join(stats.get('top_memory_apps', []))
    return (f"CPU: {stats.get('cpu_percent')}% ({stats.get('cpu_cores')} cores), "
            f"RAM: {ram.get('used_gb')}/{ram.get('total_gb')} GB ({ram.get('percent')}%), "
            f"C: Drive: {disk.get('free_gb')} GB free ({disk.get('percent')}% used), "
            f"Battery/Power: {stats.get('battery')}. "
            f"Top memory consumers: {top_apps}")


@registry.register(
    name="take_screenshot",
    description="Captures the desktop screen and saves it to Pictures/Screenshots.",
    parameters={
        "type": "object",
        "properties": {
            "filename": {"type": "string", "description": "Optional custom filename for screenshot."}
        }
    }
)
def tool_take_screenshot(filename: Optional[str] = None) -> str:
    success, path, msg = os_operator.take_screenshot(filename)
    return msg


@registry.register(
    name="power_control",
    description="Controls PC power (lock screen, sleep, shutdown, restart, abort).",
    parameters={
        "type": "object",
        "properties": {
            "action": {"type": "string", "enum": ["lock", "sleep", "restart", "shutdown", "cancel"], "description": "Power state action"}
        },
        "required": ["action"]
    },
    dangerous=True
)
def tool_power_control(action: str) -> str:
    if action == "lock":
        return os_operator.lock_workstation()
    elif action == "sleep":
        return os_operator.sleep_pc()
    elif action == "restart":
        return os_operator.restart_pc(30)
    elif action == "shutdown":
        return os_operator.shutdown_pc(60)
    elif action == "cancel":
        return os_operator.cancel_shutdown()
    return "Unknown power operation."


# ---------------- Register Coding Agent Tools ----------------
try:
    from backend import coding_agent
except ImportError:
    import coding_agent


@registry.register(
    name="code_scan_workspace",
    description="Recursively scans a workspace directory and returns file counts, structure, and languages.",
    parameters={
        "type": "object",
        "properties": {
            "max_depth": {"type": "integer", "description": "Max folder depth to traverse (default 3)"}
        }
    }
)
def tool_code_scan_workspace(max_depth: int = 3) -> str:
    res = coding_agent.agent.scan(max_depth=max_depth)
    if res.get("success"):
        return f"Scan complete: {res['total_files']} files, {res['total_directories']} directories across {len(res['languages'])} languages."
    return f"Scan failed: {res.get('error')}"


@registry.register(
    name="code_read_file",
    description="Reads a bounded line slice of a source code file in the workspace.",
    parameters={
        "type": "object",
        "properties": {
            "rel_path": {"type": "string", "description": "Relative file path from workspace root"},
            "start_line": {"type": "integer", "description": "Starting line number (default 1)"},
            "end_line": {"type": "integer", "description": "Ending line number (default 100)"}
        },
        "required": ["rel_path"]
    }
)
def tool_code_read_file(rel_path: str, start_line: int = 1, end_line: int = 100) -> str:
    res = coding_agent.agent.read(rel_path, start_line, end_line)
    if res.get("success"):
        return f"File '{rel_path}' lines {start_line}-{end_line}:\n{res['numbered_content']}"
    return f"Failed to read file: {res.get('error')}"


@registry.register(
    name="code_test_file",
    description="Executes a test file or script and analyzes runtime stdout/stderr with auto-fix diagnostics.",
    parameters={
        "type": "object",
        "properties": {
            "rel_path": {"type": "string", "description": "Relative path to test or script file"}
        },
        "required": ["rel_path"]
    }
)
def tool_code_test_file(rel_path: str) -> str:
    res = coding_agent.agent.test(rel_path)
    if res.get("success"):
        return f"Test passed on '{rel_path}' in {res['duration_ms']}ms."
    analysis = res.get("analysis", {})
    return f"Test failed: {analysis.get('error_category')} - {analysis.get('summary')}. Suggestion: {analysis.get('suggestion')}"


@registry.register(
    name="code_terminal_exec",
    description="Executes a terminal command safely in the workspace environment.",
    parameters={
        "type": "object",
        "properties": {
            "command": {"type": "string", "description": "Terminal command to run"}
        },
        "required": ["command"]
    },
    dangerous=True
)
def tool_code_terminal_exec(command: str) -> str:
    res = coding_agent.TerminalExecutor.run_command(command)
    if res.get("success"):
        return f"Command succeeded:\n{res.get('stdout')[:600]}"
    return f"Command failed:\n{res.get('stderr')[:600]}"


# ---------------- Register Deep Computer Use, Vision & Media Tools ----------------
try:
    from backend.computer_use import computer_use, screen_recorder
except ImportError:
    try:
        from computer_use import computer_use, screen_recorder
    except Exception:
        computer_use = None
        screen_recorder = None


@registry.register(
    name="analyze_screen",
    description="Captures the current desktop screen and uses Multimodal Vision AI to see and explain what is open, read text/errors, or answer questions about the active screen.",
    parameters={
        "type": "object",
        "properties": {
            "user_question": {"type": "string", "description": "Specific question about what's on the screen (e.g. 'What error is showing?', 'Describe the active window')."}
        }
    }
)
def tool_analyze_screen(user_question: Optional[str] = None) -> str:
    if computer_use:
        return computer_use.analyze_screen(user_question)
    return "Screen vision module unavailable."


@registry.register(
    name="photoshop_action",
    description="Executes deep inside-app actions in Adobe Photoshop (e.g. select brush/move/crop/type tool, new_document, save, export, undo, redo, duplicate_layer, transform).",
    parameters={
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["brush", "move", "crop", "eraser", "type", "zoom", "new_document", "save", "save_as", "export", "undo", "redo", "duplicate_layer", "transform"],
                "description": "Specific Photoshop action to perform"
            },
            "param": {"type": "string", "description": "Optional parameters"}
        },
        "required": ["action"]
    }
)
def tool_photoshop_action(action: str, param: Optional[str] = None) -> str:
    if computer_use:
        return computer_use.photoshop_action(action, param)
    return "Photoshop automation unavailable."


@registry.register(
    name="youtube_deep_action",
    description="Deep inside-browser YouTube control: searches and plays videos directly, controls playback (play, pause, fullscreen, mute, skip, rewind, next_video).",
    parameters={
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["search_and_play", "play_pause", "fullscreen", "mute", "skip", "rewind", "next_video"],
                "description": "YouTube action to execute"
            },
            "query": {"type": "string", "description": "Search query or video title if action is 'search_and_play'"}
        },
        "required": ["action"]
    }
)
def tool_youtube_deep_action(action: str, query: Optional[str] = None) -> str:
    if computer_use:
        return computer_use.youtube_deep_action(action, query)
    return "YouTube control unavailable."


@registry.register(
    name="browser_deep_action",
    description="Navigates browser tabs (new_tab, close_tab, switch_tab, reload) or opens Cloud AI platforms (chatgpt, gemini, claude, github).",
    parameters={
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["new_tab", "close_tab", "switch_tab", "reload", "chatgpt", "gemini", "claude", "github"],
                "description": "Browser action or Cloud AI destination"
            }
        },
        "required": ["action"]
    }
)
def tool_browser_deep_action(action: str) -> str:
    if computer_use:
        return computer_use.browser_deep_action(action)
    return "Browser action unavailable."


@registry.register(
    name="type_text",
    description="Types or pastes text into the currently active window, input box, editor, or search bar on the screen.",
    parameters={
        "type": "object",
        "properties": {
            "text": {"type": "string", "description": "The text to type or paste"},
            "press_enter": {"type": "boolean", "description": "Whether to press Enter key after typing (default False)"}
        },
        "required": ["text"]
    }
)
def tool_type_text(text: str, press_enter: bool = False) -> str:
    if computer_use:
        return computer_use.type_text(text, press_enter=press_enter)
    return "Typing automation unavailable."


@registry.register(
    name="screen_recording",
    description="Starts or stops high-FPS desktop screen video recording (saves to Videos/BaronRecordings).",
    parameters={
        "type": "object",
        "properties": {
            "action": {"type": "string", "enum": ["start", "stop"], "description": "Whether to start or stop screen recording"}
        },
        "required": ["action"]
    }
)
def tool_screen_recording(action: str) -> str:
    if screen_recorder:
        if action == "start":
            success, msg = screen_recorder.start_recording()
            return msg
        elif action == "stop":
            success, msg = screen_recorder.stop_recording()
            return msg
    return "Screen recorder unavailable."
