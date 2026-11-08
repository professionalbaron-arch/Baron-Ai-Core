"""
BARON CORE - Deep Computer Use, Vision & Application Operator
Provides deep inside-app automation (Photoshop, Chrome, YouTube, Cloud AIs),
multimodal screen vision analysis, screen video recording, and keyboard/mouse emulation.
"""

import os
import sys
import time
import base64
import logging
import threading
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

try:
    import pyautogui
    pyautogui.FAILSAFE = False
except ImportError:
    pyautogui = None

try:
    import pyperclip
except ImportError:
    pyperclip = None

try:
    import cv2
    import numpy as np
    import mss
    HAS_CV2_MSS = True
except ImportError:
    HAS_CV2_MSS = False

logger = logging.getLogger("BaronComputerUse")

# Load Gemini API if available for Screen Vision
GEMINI_KEY = os.getenv("GEMINI_API_KEY", "")


class ScreenRecorder:
    """Records high-framerate desktop video silently in the background."""
    def __init__(self):
        self._recording = False
        self._thread: Optional[threading.Thread] = None
        self._output_path: Optional[str] = None

    def start_recording(self, output_path: Optional[str] = None, fps: int = 20) -> Tuple[bool, str]:
        if not HAS_CV2_MSS:
            return False, "Screen recording requires cv2 and mss."
        if self._recording:
            return False, "Screen recording pehle se hi chal rahi hai."

        recordings_dir = os.path.join(os.path.expanduser("~"), "Videos", "BaronRecordings")
        os.makedirs(recordings_dir, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        self._output_path = output_path or os.path.join(recordings_dir, f"Baron_Record_{ts}.mp4")

        self._recording = True
        self._thread = threading.Thread(target=self._record_loop, args=(fps,), daemon=True)
        self._thread.start()
        return True, f"Screen recording start ho gayi hai: {self._output_path}"

    def _record_loop(self, fps: int):
        with mss.mss() as sct:
            monitor = sct.monitors[1]
            width, height = monitor["width"], monitor["height"]
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            out = cv2.VideoWriter(self._output_path, fourcc, fps, (width, height))

            delay = 1.0 / fps
            try:
                while self._recording:
                    t0 = time.time()
                    frame = np.array(sct.grab(monitor))
                    frame_bgr = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
                    out.write(frame_bgr)
                    elapsed = time.time() - t0
                    sleep_time = max(0.001, delay - elapsed)
                    time.sleep(sleep_time)
            finally:
                out.release()
                logger.info(f"Screen recording saved to {self._output_path}")

    def stop_recording(self) -> Tuple[bool, str]:
        if not self._recording:
            return False, "Koi screen recording active nahi hai."
        self._recording = False
        if self._thread:
            self._thread.join(timeout=3.0)
        saved_file = self._output_path
        self._output_path = None
        return True, f"Screen recording complete ho gayi hai aur save ho chuki hai: {saved_file}"


screen_recorder = ScreenRecorder()


class ComputerUseOperator:
    """Master controller for inside-app and vision automation."""

    # ---------------- Multimodal Screen Vision ----------------
    @staticmethod
    def analyze_screen(user_question: Optional[str] = None) -> str:
        """Takes a screenshot and analyzes active screen contents with Gemini Vision."""
        if not pyautogui:
            return "Vision module me pyautogui available nahi hai."

        screenshots_dir = os.path.join(os.path.expanduser("~"), "Pictures", "Screenshots")
        os.makedirs(screenshots_dir, exist_ok=True)
        temp_screen = os.path.join(screenshots_dir, "vision_temp.png")

        try:
            shot = pyautogui.screenshot()
            shot.save(temp_screen)

            # Try Gemini Vision
            from google import genai
            client = genai.Client()
            
            with open(temp_screen, "rb") as f:
                img_bytes = f.read()

            q = user_question or "Describe what application is on the screen, active windows, text, and any visible errors."
            prompt = (
                f"You are Baron AI companion. Analyze this Windows desktop screenshot and answer concisely in friendly Hindi/Hinglish.\n"
                f"User Question: {q}\n"
                f"Keep your response natural, helpful, and under 3-4 spoken sentences."
            )

            resp = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=[
                    genai.types.Part.from_bytes(data=img_bytes, mime_type='image/png'),
                    prompt
                ]
            )
            if resp and resp.text:
                return resp.text.strip()
            return "Screen image capture ho gayi par analysis response empty aaya."
        except Exception as e:
            logger.warning(f"Screen vision error: {e}")
            return f"Maine screen dekhi, par vision engine me error aaya: {e}"
        finally:
            if os.path.exists(temp_screen):
                try:
                    os.remove(temp_screen)
                except Exception:
                    pass

    # ---------------- Photoshop Inside-App Automation ----------------
    @staticmethod
    def photoshop_action(action: str, param: Optional[str] = None) -> str:
        """Executes deep inside-app actions in Adobe Photoshop."""
        if not pyautogui:
            return "PyAutoGUI unavailable."

        act = action.lower().strip()

        # Tools shortcuts in Photoshop
        tool_shortcuts = {
            "brush": "b",
            "move": "v",
            "marquee": "m",
            "lasso": "l",
            "crop": "c",
            "eraser": "e",
            "gradient": "g",
            "type": "t",
            "text": "t",
            "pen": "p",
            "hand": "h",
            "zoom": "z"
        }

        if act in tool_shortcuts:
            key = tool_shortcuts[act]
            pyautogui.press(key)
            return f"Photoshop me '{act.capitalize()}' tool select kar diya hai."

        if act == "new_document":
            pyautogui.hotkey('ctrl', 'n')
            time.sleep(0.3)
            pyautogui.press('enter')
            return "Photoshop me naya canvas create kar diya hai."

        elif act == "save":
            pyautogui.hotkey('ctrl', 's')
            return "Photoshop file save trigger kar diya hai."

        elif act == "save_as":
            pyautogui.hotkey('ctrl', 'shift', 's')
            return "Save As dialog open kar diya hai."

        elif act == "export":
            pyautogui.hotkey('ctrl', 'alt', 'shift', 's')
            return "Save for Web / Export dialog open kar diya hai."

        elif act == "undo":
            pyautogui.hotkey('ctrl', 'z')
            return "Photoshop me action undo kar diya hai."

        elif act == "redo":
            pyautogui.hotkey('ctrl', 'shift', 'z')
            return "Photoshop me action redo kar diya hai."

        elif act == "duplicate_layer":
            pyautogui.hotkey('ctrl', 'j')
            return "Layer duplicate kar di gayi hai (Ctrl + J)."

        elif act == "deselect":
            pyautogui.hotkey('ctrl', 'd')
            return "Selection deselect kar di gayi hai."

        elif act == "transform":
            pyautogui.hotkey('ctrl', 't')
            return "Free Transform active kar diya hai (Ctrl + T)."

        return f"Photoshop action '{action}' execute kar diya hai."

    # ---------------- Chrome & YouTube Deep Operations ----------------
    @staticmethod
    def youtube_deep_action(action: str, query: Optional[str] = None) -> str:
        """Controls YouTube video playback and navigation inside Chrome."""
        act = action.lower().strip()

        if act == "search_and_play" and query:
            import webbrowser
            encoded = query.replace(" ", "+")
            url = f"https://www.youtube.com/results?search_query={encoded}"
            webbrowser.open(url)
            # Give Chrome a moment to open, then press Tab and Enter to play first result
            time.sleep(2.5)
            if pyautogui:
                # Press 'k' or space or click
                pyautogui.press('/')
                time.sleep(0.1)
                pyautogui.press('enter')
            return f"YouTube par '{query}' search karke video open kar di hai."

        if not pyautogui:
            return "PyAutoGUI unavailable."

        if act in ["play", "pause", "play_pause"]:
            pyautogui.press('k')
            return "YouTube video play/pause toggle kiya gaya."
        elif act in ["fullscreen", "full_screen"]:
            pyautogui.press('f')
            return "YouTube fullscreen toggle kiya gaya."
        elif act in ["mute", "unmute"]:
            pyautogui.press('m')
            return "YouTube video mute toggle kiya gaya."
        elif act in ["forward", "skip"]:
            pyautogui.press('l')
            return "Video 10 seconds aage skip ki gayi."
        elif act in ["rewind", "back"]:
            pyautogui.press('j')
            return "Video 10 seconds peeche rewind ki gayi."
        elif act in ["next_video", "next"]:
            pyautogui.hotkey('shift', 'n')
            return "Next video play kar di gayi hai."
        elif act in ["captions", "subtitles"]:
            pyautogui.press('c')
            return "Subtitles toggle kar diye gaye hain."

        return f"YouTube action '{action}' execute kiya gaya."

    @staticmethod
    def browser_deep_action(action: str, target: Optional[str] = None) -> str:
        """Manages browser tabs, navigation, and cloud AI platforms."""
        import webbrowser
        act = action.lower().strip()

        # Direct Cloud AI Shortcuts
        ai_platforms = {
            "chatgpt": "https://chatgpt.com",
            "gemini": "https://gemini.google.com",
            "claude": "https://claude.ai",
            "github": "https://github.com",
            "gmail": "https://mail.google.com"
        }

        if act in ai_platforms:
            webbrowser.open(ai_platforms[act])
            return f"{act.capitalize()} browser me open kar diya hai sir."

        if not pyautogui:
            return "PyAutoGUI unavailable."

        if act == "new_tab":
            pyautogui.hotkey('ctrl', 't')
            return "Browser me naya tab khol diya hai."
        elif act == "close_tab":
            pyautogui.hotkey('ctrl', 'w')
            return "Browser tab close kar diya gaya hai."
        elif act == "switch_tab":
            pyautogui.hotkey('ctrl', 'tab')
            return "Next tab par switch kar diya hai."
        elif act == "reopen_tab":
            pyautogui.hotkey('ctrl', 'shift', 't')
            return "Recently closed tab wapas open kar diya hai."
        elif act == "reload":
            pyautogui.hotkey('ctrl', 'r')
            return "Webpage reload kar diya gaya hai."
        elif act == "bookmark":
            pyautogui.hotkey('ctrl', 'd')
            return "Page bookmark dialog open kiya gaya."

        return f"Browser action '{action}' execute kiya gaya."

    # ---------------- Universal Typing & Interaction ----------------
    @staticmethod
    def type_text(text: str, press_enter: bool = False) -> str:
        """Pastes or types natural text into the currently active window or input box."""
        if not text:
            return "Typing text khali hai."

        if pyperclip and pyautogui:
            # Use clipboard for instant, accurate Unicode typing in Hindi/English
            old_clip = ""
            try:
                old_clip = pyperclip.paste()
            except Exception:
                pass

            pyperclip.copy(text)
            time.sleep(0.05)
            pyautogui.hotkey('ctrl', 'v')
            time.sleep(0.05)

            if press_enter:
                pyautogui.press('enter')

            # Restore old clipboard
            try:
                if old_clip:
                    pyperclip.copy(old_clip)
            except Exception:
                pass

            return f"Maine active window me type kar diya hai: '{text[:50]}...'"
        elif pyautogui:
            pyautogui.write(text, interval=0.02)
            if press_enter:
                pyautogui.press('enter')
            return f"Typed text: '{text[:50]}...'"
        return "Typing module unavailable."

    @staticmethod
    def press_hotkey(keys: List[str]) -> str:
        """Presses arbitrary keyboard hotkey combination (e.g. ['ctrl', 'c'])."""
        if pyautogui and keys:
            pyautogui.hotkey(*keys)
            return f"Hotkey combo {' + '.join(keys)} press kiya gaya."
        return "Hotkey execution failed."


# Global Singleton
computer_use = ComputerUseOperator()
