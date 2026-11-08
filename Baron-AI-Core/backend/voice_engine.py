"""
BARON CORE - Voice Engine Module (Studio-Quality Neural Edge-TTS + Pygame Mixer + Barge-In)
Provides crystal-clear 44.1kHz human voice output using Microsoft Edge Neural TTS,
Pygame Mixer low-latency playback with instant Barge-In interruption,
and dual-language SpeechRecognition (en-IN, hi-IN).
"""

import os
import re
import sys
import time
import queue
import ctypes
import asyncio
import logging
import tempfile
import threading
from typing import Optional

try:
    import winsound
except ImportError:
    winsound = None

try:
    import pygame
    HAS_PYGAME = True
    pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)
except Exception:
    HAS_PYGAME = False

try:
    import edge_tts
    HAS_EDGE_TTS = True
except ImportError:
    HAS_EDGE_TTS = False

try:
    import pyttsx3
    HAS_PYTTSX3 = True
except ImportError:
    HAS_PYTTSX3 = False

try:
    import speech_recognition as sr
    HAS_SR = True
except ImportError:
    HAS_SR = False

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("BaronVoice")

# Voice selection
NEURAL_VOICE_HI = "hi-IN-SwaraNeural"     # Crystal-clear, expressive Hindi/Hinglish
NEURAL_VOICE_EN = "en-IN-NeerjaNeural"    # Charismatic Indian English
JARVIS_VOICE_EN = "en-US-ChristopherNeural" # Deep cinematic JARVIS English


def _prefer_feminine_voice(engine) -> None:
    """Selects a feminine voice from the SAPI5 engine if available."""
    voices = engine.getProperty('voices')
    if not voices:
        return

    preferred_names = ("zira", "aria", "jenny", "samantha", "hazel", "susan", "female")
    female_voices = [
        voice for voice in voices
        if any(name in f"{getattr(voice, 'name', '')} {getattr(voice, 'id', '')}".lower()
               for name in preferred_names)
    ]
    if female_voices:
        engine.setProperty('voice', female_voices[0].id)
    else:
        logger.warning("No preferred feminine TTS voice found; using default.")


def play_chime():
    """Plays an activation chime."""
    if winsound:
        try:
            winsound.Beep(987, 70)
            winsound.Beep(1318, 110)
        except Exception:
            pass


def play_dismiss_chime():
    """Plays a subtle dismiss chime."""
    if winsound:
        try:
            winsound.Beep(1046, 60)
            winsound.Beep(784, 80)
        except Exception:
            pass


class TTSWorker:
    """
    Dedicated worker thread handling neural and local TTS with instant Barge-In interruption.
    """
    def __init__(self, rate: int = 165, volume: float = 1.0):
        self.rate = rate
        self.volume = volume
        self.speech_queue = queue.Queue()
        self.is_speaking = False
        self._interrupted = threading.Event()
        self._stop_event = threading.Event()

        # Initialize pyttsx3 fallback
        self.fallback_engine = None
        if HAS_PYTTSX3:
            try:
                self.fallback_engine = pyttsx3.init()
                self.fallback_engine.setProperty('rate', self.rate)
                self.fallback_engine.setProperty('volume', self.volume)
                _prefer_feminine_voice(self.fallback_engine)
            except Exception as e:
                logger.warning(f"Could not init pyttsx3 fallback: {e}")

        self.worker_thread = threading.Thread(target=self._run_loop, daemon=True)
        self.worker_thread.start()
        logger.info(f"TTS Worker initialized. Pygame Mixer: {HAS_PYGAME}, Neural Edge-TTS: {HAS_EDGE_TTS}")

    def interrupt(self):
        """Instantly cuts off current speech (Barge-In)."""
        self._interrupted.set()
        if HAS_PYGAME:
            try:
                pygame.mixer.music.stop()
            except Exception:
                pass
        self.is_speaking = False
        logger.info("Speech interrupted by user (Barge-In).")

    def _clean_for_speech(self, text: str) -> str:
        t = re.sub(r'[*_#`~]', '', text)
        t = re.sub(r'https?://\S+', '', t)
        t = re.sub(r'\s+', ' ', t).strip()
        return t

    def _speak_neural(self, text: str) -> bool:
        """Synthesizes and plays crystal-clear audio using Edge-TTS + Pygame."""
        if not HAS_EDGE_TTS or not HAS_PYGAME:
            return False

        temp_path = None
        try:
            self._interrupted.clear()
            voice = NEURAL_VOICE_HI if re.search(r'[\u0900-\u097F]|(hai|karo|batao|kholo|chalao|kya|kaise|sir|ji)', text, re.IGNORECASE) else NEURAL_VOICE_EN

            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tf:
                temp_path = tf.name

            async def _generate():
                communicate = edge_tts.Communicate(text, voice)
                await communicate.save(temp_path)

            asyncio.run(_generate())

            if os.path.exists(temp_path) and os.path.getsize(temp_path) > 500:
                pygame.mixer.music.load(temp_path)
                pygame.mixer.music.play()

                # Non-blocking wait loop with barge-in check
                while pygame.mixer.music.get_busy():
                    if self._interrupted.is_set():
                        pygame.mixer.music.stop()
                        break
                    time.sleep(0.03)

                pygame.mixer.music.unload()
                return True
        except Exception as e:
            logger.warning(f"Edge-TTS playback failed: {e}")
        finally:
            if temp_path and os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except Exception:
                    pass
        return False

    def _run_loop(self):
        while not self._stop_event.is_set():
            try:
                text = self.speech_queue.get(timeout=0.2)
                if text is None:
                    break

                self.is_speaking = True
                clean_text = self._clean_for_speech(text)

                if clean_text:
                    logger.info(f"BARON Vocalizing: '{clean_text[:60]}...'")
                    success = self._speak_neural(clean_text)
                    if not success and self.fallback_engine and not self._interrupted.is_set():
                        try:
                            self.fallback_engine.say(clean_text)
                            self.fallback_engine.runAndWait()
                        except Exception as e:
                            logger.error(f"Fallback TTS failed: {e}")

                self.is_speaking = False
                self.speech_queue.task_done()
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"TTS Worker error: {e}")
                self.is_speaking = False

    def enqueue(self, text: str):
        if text and text.strip():
            self._interrupted.clear()
            self.speech_queue.put(text.strip())

    def stop(self):
        self._stop_event.set()
        self.interrupt()
        self.speech_queue.put(None)


# Global TTS Worker Singleton
_tts_worker_instance: Optional[TTSWorker] = None
_tts_lock = threading.Lock()


def get_tts_worker() -> TTSWorker:
    global _tts_worker_instance
    with _tts_lock:
        if _tts_worker_instance is None:
            _tts_worker_instance = TTSWorker()
        return _tts_worker_instance


def speak(text: str):
    worker = get_tts_worker()
    worker.enqueue(text)


def stop_speaking():
    """Cuts off active speech immediately."""
    worker = get_tts_worker()
    worker.interrupt()


def listen(timeout: int = 5, phrase_time_limit: int = 7) -> Optional[str]:
    """Listens from the microphone and transcribes with Google Speech API."""
    if not HAS_SR:
        logger.warning("SpeechRecognition is not installed.")
        return None

    recognizer = sr.Recognizer()
    recognizer.dynamic_energy_threshold = True
    recognizer.pause_threshold = 0.8

    try:
        with sr.Microphone() as source:
            recognizer.adjust_for_ambient_noise(source, duration=0.2)
            audio = recognizer.listen(source, timeout=timeout, phrase_time_limit=phrase_time_limit)

            # Primary: Indian English
            try:
                text = recognizer.recognize_google(audio, language="en-IN")
                return text
            except sr.UnknownValueError:
                pass

            # Secondary: Hindi
            try:
                text = recognizer.recognize_google(audio, language="hi-IN")
                return text
            except sr.UnknownValueError:
                return None

    except sr.WaitTimeoutError:
        return None
    except Exception as e:
        logger.error(f"Microphone recognition error: {e}")
        return None
