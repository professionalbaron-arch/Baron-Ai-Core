"""
BARON CORE - Background Task Scheduler & Automation Engine
Inspired by Moltis 'moltis-cron'.
Features:
- Periodic background cron jobs (interval & scheduled tasks)
- Automated desktop health monitors & reminders
- Safe task threading with graceful shutdown
"""

import os
import sys
import time
import threading
import logging
from typing import Callable, Dict, Any, List

logger = logging.getLogger("BaronScheduler")


class ScheduledTask:
    def __init__(self, name: str, interval_seconds: int, func: Callable, args=None, kwargs=None):
        self.name = name
        self.interval_seconds = interval_seconds
        self.func = func
        self.args = args or ()
        self.kwargs = kwargs or {}
        self.last_run = 0.0
        self.enabled = True


class BaronScheduler:
    """Cron & Automation Task Scheduler for Baron."""
    def __init__(self):
        self.tasks: Dict[str, ScheduledTask] = {}
        self.running = False
        self._thread: threading.Thread = None

    def add_task(self, name: str, interval_seconds: int, func: Callable, *args, **kwargs):
        task = ScheduledTask(name, interval_seconds, func, args, kwargs)
        self.tasks[name] = task
        logger.info(f"Registered scheduled task: '{name}' every {interval_seconds}s")

    def remove_task(self, name: str):
        if name in self.tasks:
            del self.tasks[name]

    def _loop(self):
        logger.info("Baron Scheduler background worker loop started.")
        while self.running:
            now = time.time()
            for name, task in list(self.tasks.items()):
                if task.enabled and (now - task.last_run >= task.interval_seconds):
                    task.last_run = now
                    try:
                        logger.debug(f"Executing scheduled task '{name}'")
                        task.func(*task.args, **task.kwargs)
                    except Exception as e:
                        logger.exception(f"Scheduled task '{name}' error: {e}")
            time.sleep(1.0)

    def start(self):
        if not self.running:
            self.running = True
            self._thread = threading.Thread(target=self._loop, daemon=True)
            self._thread.start()
            logger.info("Baron Scheduler started.")

    def stop(self):
        self.running = False
        if self._thread:
            self._thread.join(timeout=2.0)
            logger.info("Baron Scheduler stopped.")


# Global scheduler singleton
scheduler = BaronScheduler()


# Built-in tasks: periodic RAM/CPU monitoring logger
def _monitor_system_health():
    try:
        from backend import system_control
        stats = system_control.get_system_diagnostics()
        if stats.get("ram_percent", 0) > 92:
            logger.warning(f"High Memory Usage Alert: {stats.get('ram_percent')}%")
    except Exception:
        pass

scheduler.add_task("system_health_check", 300, _monitor_system_health)
