"""
BARON CORE - Autonomous Native Desktop Assistant Service
Features:
- Siri-like animated pop-up overlay with curved edges & frosted glass transparency
- Deep glowing shadows on orb, listening pill, and typing dock
- Background passive wake-word detection ("Baron" / "Hey Baron")
- Global keyboard hotkey (Ctrl + Shift + B)
- System Tray integration with custom glowing icon
- Full system control (Apps, Volume, Power, Screenshots, Clipboard)
- Friendly Conversational AI like ChatGPT & Gemini with real-time web search
"""

import os
import sys
import time
import json
import re
import logging
import threading
import ctypes
from ctypes import wintypes
from urllib.parse import quote_plus

# Ensure backend folder is in Python path
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.join(CURRENT_DIR, "backend")
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

import webview
import keyboard
import pystray
from PIL import Image

# Import internal Baron components
from backend import system_control
from backend import ai_brain
from backend import voice_engine
from backend.tool_registry import registry as tool_registry
from backend.memory import memory
from backend.scheduler import scheduler

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] [BARON-SERVICE] %(message)s")
logger = logging.getLogger("BaronService")

OVERLAY_HTML = os.path.join(CURRENT_DIR, "overlay", "index.html")
ICON_PATH = os.path.join(CURRENT_DIR, "baron_icon.ico")


class MARGINS(ctypes.Structure):
    _fields_ = [
        ('cxLeftWidth', ctypes.c_int),
        ('cxRightWidth', ctypes.c_int),
        ('cyTopHeight', ctypes.c_int),
        ('cyBottomHeight', ctypes.c_int)
    ]


def apply_win32_window_effects(title="BARON AI Assistant", width=480, height=340):
    """
    Applies Windows DWM glass frame extension and curves window edges.
    Eliminates rectangular black box and enables true transparent glass.
    """
    for _ in range(25):
        time.sleep(0.08)
        hwnd = ctypes.windll.user32.FindWindowW(None, title)
        if hwnd:
            try:
                # 1. Extend DWM Glass Frame across client area
                margins = MARGINS(-1, -1, -1, -1)
                ctypes.windll.dwmapi.DwmExtendFrameIntoClientArea(hwnd, ctypes.byref(margins))

                # 2. Windows 11 DWM Rounded Corner Preference (DWMWCP_ROUND = 2)
                corner_pref = ctypes.c_int(2)
                ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 33, ctypes.byref(corner_pref), ctypes.sizeof(corner_pref))

                # 3. Clip window region to smooth rounded rectangle (radius 36px)
                rgn = ctypes.windll.gdi32.CreateRoundRectRgn(0, 0, width, height, 36, 36)
                ctypes.windll.user32.SetWindowRgn(hwnd, rgn, True)

                logger.info(f"Win32 glass & rounded corner effects applied to HWND {hwnd}")
                return hwnd
            except Exception as e:
                logger.warning(f"Error applying Win32 window effects: {e}")
                return hwnd
    return None


class BridgeAPI:
    """Lightweight JavaScript-to-Python Bridge exposed via pywebview."""
    def __init__(self, on_close, on_listen, on_submit):
        self._on_close = on_close
        self._on_listen = on_listen
        self._on_submit = on_submit

    def close_overlay(self):
        """Called when overlay dismiss animation ends or user hits Escape."""
        if self._on_close:
            self._on_close()

    def trigger_listen(self):
        """Called when user clicks the orb to start listening."""
        if self._on_listen:
            return self._on_listen()
        return False

    def submit_text(self, text: str):
        """Called when user submits a typed command."""
        if self._on_submit:
            return self._on_submit(text)
        return False


class BaronService:
    def __init__(self):
        self.window = None
        self.is_visible = False
        self.is_processing = False
        self.processing_lock = threading.Lock()
        self.running = True
        self.win_w = 540
        self.win_h = 380
        self.api = BridgeAPI(
            on_close=self.hide_overlay,
            on_listen=self.start_listening,
            on_submit=self.start_command
        )

    # ---------------- Window Overlay Lifecycle ----------------
    def create_window(self):
        # Calculate bottom-center screen position
        screen_w, screen_h = 1920, 1080
        try:
            import pyautogui
            sz = pyautogui.size()
            screen_w, screen_h = sz.width, sz.height
        except Exception:
            pass

        win_x = (screen_w - self.win_w) // 2
        win_y = screen_h - self.win_h - 50  # Floating above Windows taskbar

        html_url = "file:///" + OVERLAY_HTML.replace("\\", "/")

        self.window = webview.create_window(
            title="BARON AI Assistant",
            url=html_url,
            width=self.win_w,
            height=self.win_h,
            x=win_x,
            y=win_y,
            frameless=True,
            transparent=True,
            on_top=True,
            easy_drag=True,
            js_api=self.api
        )

    def show_overlay(self):
        if not self.window:
            return
        self.is_visible = True
        self.window.show()
        self.window.restore()
        threading.Thread(
            target=apply_win32_window_effects, 
            args=("BARON AI Assistant", self.win_w, self.win_h), 
            daemon=True
        ).start()
        voice_engine.play_chime()
        # Reset UI to listening
        try:
            self.window.evaluate_js("window.setListeningState('Listening for command...');")
        except Exception:
            pass

    def hide_overlay(self):
        if not self.window:
            return
        self.is_visible = False
        self.window.hide()

    def update_ui_thinking(self, prompt: str):
        if self.window and self.is_visible:
            try:
                self.window.evaluate_js(f"window.setThinkingState({json.dumps(prompt)});")
            except Exception:
                logger.exception("Could not update the overlay thinking state.")

    def update_ui_speaking(self, prompt: str, reply: str):
        if self.window and self.is_visible:
            try:
                self.window.evaluate_js(
                    f"window.setSpeakingState({json.dumps(prompt)}, {json.dumps(reply)});"
                )
            except Exception:
                logger.exception("Could not update the overlay response.")

    def update_ui_error(self, message: str):
        if self.window and self.is_visible:
            try:
                self.window.evaluate_js(f"window.setErrorState({json.dumps(message)});")
            except Exception:
                logger.exception("Could not update the overlay error state.")

    # ---------------- Command Execution ----------------
    def start_listening(self):
        if not self.processing_lock.acquire(blocking=False):
            return False
        self.is_processing = True
        try:
            threading.Thread(target=self._listen_reserved, daemon=True).start()
        except Exception:
            self.is_processing = False
            self.processing_lock.release()
            logger.exception("Could not start the voice-listening task.")
            return False
        return True

    def start_command(self, command_text: str):
        if not command_text or not command_text.strip():
            return False
        if not self.processing_lock.acquire(blocking=False):
            return False
        self.is_processing = True
        try:
            threading.Thread(
                target=self._process_reserved,
                args=(command_text.strip(),),
                daemon=True
            ).start()
        except Exception:
            self.is_processing = False
            self.processing_lock.release()
            logger.exception("Could not start command processing.")
            return False
        return True

    def _process_reserved(self, command_text: str):
        try:
            self._process_command_locked(command_text)
        finally:
            self.is_processing = False
            self.processing_lock.release()

    def process_command(self, command_text: str):
        """Processes voice or typed commands."""
        if not command_text or not command_text.strip():
            return
        if not self.processing_lock.acquire(blocking=False):
            self.update_ui_error("Baron is busy. Please try again in a moment.")
            return

        cmd = command_text.strip()
        self.is_processing = True
        try:
            self._process_command_locked(cmd)
        finally:
            self.is_processing = False
            self.processing_lock.release()

    def _process_command_locked(self, cmd: str):
        logger.info(f"Processing command: '{cmd}'")

        try:
            self.update_ui_thinking(cmd)
            system_reply = system_control.execute_system_command(cmd)
            reply = system_reply or ai_brain.ask_baron_intelligence(cmd)
            self.update_ui_speaking(cmd, reply)
            voice_engine.speak(reply)
        except Exception:
            logger.exception("Failed to process command: '%s'", cmd)
            self.update_ui_error("Baron could not complete that request. Please try again.")
            try:
                voice_engine.speak("Kripya dobara boliye.")
            except Exception:
                pass

    def listen_and_respond(self, prompt_prefix: str = ""):
        """Listens from the microphone and processes the captured phrase."""
        if not self.processing_lock.acquire(blocking=False):
            self.update_ui_error("Baron is busy. Please try again in a moment.")
            return
        self.is_processing = True
        try:
            self._listen_locked(prompt_prefix)
        finally:
            self.is_processing = False
            self.processing_lock.release()

    def _listen_reserved(self):
        try:
            self._listen_locked("")
        finally:
            self.is_processing = False
            self.processing_lock.release()

    def _listen_locked(self, prompt_prefix: str):
        try:
            if not self.is_visible:
                self.show_overlay()
            # Record voice
            transcription = voice_engine.listen(timeout=5, phrase_time_limit=7)

            if transcription and transcription.strip():
                full_cmd = f"{prompt_prefix} {transcription}".strip()
                self._process_command_locked(full_cmd)
            else:
                self.update_ui_error("No speech detected. Press play and try again.")
        except Exception as e:
            logger.error(f"Error during listen_and_respond: {e}")
            self.update_ui_error("Microphone unavailable. Please check your audio device and try again.")

    # ---------------- Background Passive Wake Word Listener ----------------
    def run_wake_word_listener(self):
        """Continuously listens in background for 'Baron' or 'Hey Baron'."""
        try:
            import speech_recognition as sr
        except ImportError:
            logger.warning("speech_recognition not found. Wake word passive listening disabled.")
            return

        recognizer = sr.Recognizer()
        recognizer.dynamic_energy_threshold = True
        recognizer.pause_threshold = 0.6

        logger.info("Background Wake Word receptor initialized (Waiting for 'Baron')...")
        last_stt_warning = 0.0

        while self.running:
            if self.is_visible or self.is_processing:
                time.sleep(0.5)
                continue

            try:
                with sr.Microphone() as source:
                    recognizer.adjust_for_ambient_noise(source, duration=0.3)
                    audio = recognizer.listen(source, timeout=3, phrase_time_limit=4)
                    
                    try:
                        text = recognizer.recognize_google(audio, language="en-IN").lower()
                    except sr.UnknownValueError:
                        try:
                            text = recognizer.recognize_google(audio, language="hi-IN").lower()
                        except sr.UnknownValueError:
                            continue
                        except sr.RequestError as e:
                            if time.time() - last_stt_warning > 30:
                                logger.warning("Wake-word recognition unavailable: %s", e)
                                last_stt_warning = time.time()
                            continue
                    except sr.RequestError as e:
                        if time.time() - last_stt_warning > 30:
                            logger.warning("Wake-word recognition unavailable: %s", e)
                            last_stt_warning = time.time()
                        continue

                    # Check for wake word variants
                    wake_words = ("hey baron", "baron", "bairan", "barun", "varun", "बारन", "बैरन", "बरन")
                    if any(re.search(r"(?<!\w)" + re.escape(word) + r"(?!\w)", text) for word in wake_words):
                        logger.info(f"Wake word detected in phrase: '{text}'")

                        wake_pattern = r"(?<!\w)(?:hey\s+baron|baron|bairan|barun|varun|बारन|बैरन|बरन)(?!\w)"
                        cleaned = re.sub(wake_pattern, "", text).strip(" \t,.:;!-")

                        self.show_overlay()

                        if len(cleaned.split()) >= 1:
                            threading.Thread(target=self.process_command, args=(cleaned,), daemon=True).start()
                        else:
                            threading.Thread(target=self.listen_and_respond, daemon=True).start()

            except sr.WaitTimeoutError:
                continue
            except Exception as e:
                logger.warning("Wake-word microphone error: %s", e)
                time.sleep(1.0)
                continue

    # ---------------- System Tray Icon ----------------
    def run_system_tray(self):
        """Creates the Windows System Tray icon."""
        try:
            if os.path.exists(ICON_PATH):
                icon_img = Image.open(ICON_PATH)
            else:
                icon_img = Image.new('RGB', (64, 64), color=(56, 189, 248))

            def on_activate(icon, item):
                voice_engine.stop_speaking()
                self.show_overlay()
                threading.Thread(target=self.listen_and_respond, daemon=True).start()

            def on_launch_hud(icon, item):
                hud_html = os.path.join(CURRENT_DIR, "frontend", "index.html")
                if os.path.exists(hud_html):
                    os.startfile(hud_html)

            def on_exit(icon, item):
                self.running = False
                scheduler.stop()
                icon.stop()
                if self.window:
                    self.window.destroy()
                os._exit(0)

            menu = pystray.Menu(
                pystray.MenuItem("Activate Baron (Ctrl+Shift+B)", on_activate, default=True),
                pystray.MenuItem("Launch 3D Tactical HUD", on_launch_hud),
                pystray.MenuItem("Voice: Listening for 'Baron'", None, enabled=False),
                pystray.MenuItem("Desktop Apps: 161+ Indexed", None, enabled=False),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("Exit Baron", on_exit)
            )

            tray_icon = pystray.Icon("baron_core", icon_img, "BARON AI Assistant", menu)
            tray_icon.run()
        except Exception as e:
            logger.warning(f"System Tray could not be loaded: {e}")

    # ---------------- Global Keyboard Hotkey ----------------
    def setup_hotkeys(self):
        """Registers Ctrl+Shift+B global shortcut."""
        try:
            def on_hotkey():
                logger.info("Global hotkey Ctrl+Shift+B pressed!")
                voice_engine.stop_speaking()
                self.show_overlay()
                threading.Thread(target=self.listen_and_respond, daemon=True).start()

            keyboard.add_hotkey("ctrl+shift+b", on_hotkey)
            logger.info("Registered global hotkey: Ctrl + Shift + B")
        except Exception as e:
            logger.warning(f"Could not bind global hotkey: {e}")

    # ---------------- Main Service Entry ----------------
    def start(self):
        logger.info("Initializing BARON Core Autonomous Desktop Service...")

        # 1. Register Hotkeys
        self.setup_hotkeys()

        # 2. Start Background Threads
        scheduler.start()
        threading.Thread(target=self.run_wake_word_listener, daemon=True).start()
        threading.Thread(target=self.run_system_tray, daemon=True).start()

        # 3. Create pywebview window
        self.create_window()

        def on_started():
            threading.Thread(
                target=apply_win32_window_effects, 
                args=("BARON AI Assistant", self.win_w, self.win_h), 
                daemon=True
            ).start()
            # Initially hide the overlay so it waits quietly
            time.sleep(0.5)
            self.hide_overlay()
            logger.info("BARON Service Online: Running silently in background.")
            voice_engine.play_chime()

        # 4. Start webview GUI loop
        webview.start(on_started)


if __name__ == "__main__":
    service = BaronService()
    service.start()
