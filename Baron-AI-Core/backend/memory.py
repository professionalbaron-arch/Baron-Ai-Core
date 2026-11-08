"""
BARON CORE - Persistent Hybrid Memory & Knowledge Vault
Inspired by Moltis 'moltis-memory' and 'moltis-vault'.
Features:
- SQLite persistent storage with WAL mode
- Full-Text Search (FTS5) for cross-session knowledge and recall
- Key-value preferences/facts store (user profile, notes, memory tags)
- Session conversation snapshots with auto-indexing
"""

import os
import sys
import sqlite3
import json
import time
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger("BaronMemory")

DB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
os.makedirs(DB_DIR, exist_ok=True)
DB_PATH = os.path.join(DB_DIR, "baron_memory.db")


class BaronMemoryStore:
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        # Enable WAL mode for high concurrent throughput
        conn.execute("PRAGMA journal_mode=WAL;")
        return conn

    def _init_db(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            # 1. Facts / User Preferences key-value table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS memory_facts (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                category TEXT DEFAULT 'general',
                updated_at REAL NOT NULL
            );
            """)

            # 2. Session history messages table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS conversation_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                timestamp REAL NOT NULL
            );
            """)

            # 3. Full-Text Search (FTS5) virtual table for high-speed indexing & recall
            try:
                cursor.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS memory_fts USING fts5(
                    content,
                    category,
                    metadata
                );
                """)
            except Exception as e:
                logger.warning(f"FTS5 initialization notice: {e}")

            conn.commit()
            logger.info("Baron Hybrid Memory DB initialized successfully at %s", self.db_path)

    def set_fact(self, key: str, value: str, category: str = "general") -> bool:
        """Stores a persistent user preference or fact."""
        now = time.time()
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                INSERT INTO memory_facts (key, value, category, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    value=excluded.value,
                    category=excluded.category,
                    updated_at=excluded.updated_at;
                """, (key, value, category, now))

                # Index into FTS
                try:
                    cursor.execute("""
                    INSERT INTO memory_fts (content, category, metadata)
                    VALUES (?, ?, ?);
                    """, (f"{key}: {value}", category, json.dumps({"key": key})))
                except Exception:
                    pass

                conn.commit()
                return True
        except Exception as e:
            logger.exception("Failed to store memory fact: %s", e)
            return False

    def get_fact(self, key: str) -> Optional[str]:
        """Fetches a stored fact by key."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT value FROM memory_facts WHERE key = ?;", (key,))
                row = cursor.fetchone()
                return row["value"] if row else None
        except Exception as e:
            logger.exception("Failed to retrieve fact %s: %s", key, e)
            return None

    def search_memory(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Moltis-style hybrid/FTS recall search across past conversations & facts."""
        clean_q = query.replace('"', '').replace("'", "").strip()
        if not clean_q:
            return []

        results = []
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                # Search FTS5
                try:
                    cursor.execute("""
                    SELECT content, category, metadata FROM memory_fts
                    WHERE memory_fts MATCH ?
                    LIMIT ?;
                    """, (f'"{clean_q}"*', limit))
                    for row in cursor.fetchall():
                        results.append({
                            "content": row["content"],
                            "category": row["category"],
                            "metadata": row["metadata"]
                        })
                except Exception:
                    # Fallback to LIKE query on facts
                    cursor.execute("""
                    SELECT key, value, category FROM memory_facts
                    WHERE key LIKE ? OR value LIKE ?
                    LIMIT ?;
                    """, (f"%{clean_q}%", f"%{clean_q}%", limit))
                    for row in cursor.fetchall():
                        results.append({
                            "content": f"{row['key']}: {row['value']}",
                            "category": row["category"],
                            "metadata": json.dumps({"key": row["key"]})
                        })
        except Exception as e:
            logger.error("Error during memory search: %s", e)

        return results

    def log_interaction(self, session_id: str, role: str, content: str):
        """Logs chat interaction persistently."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                INSERT INTO conversation_logs (session_id, role, content, timestamp)
                VALUES (?, ?, ?, ?);
                """, (session_id, role, content, time.time()))

                # Add meaningful user/assistant interactions to FTS index
                if len(content) > 10 and not content.startswith("/"):
                    try:
                        cursor.execute("""
                        INSERT INTO memory_fts (content, category, metadata)
                        VALUES (?, ?, ?);
                        """, (content, f"chat_{role}", json.dumps({"session_id": session_id})))
                    except Exception:
                        pass
                conn.commit()
        except Exception as e:
            logger.error("Could not log interaction: %s", e)

    def get_recent_history(self, session_id: str = "default", limit: int = 6) -> List[Dict[str, str]]:
        """Returns recent interactions for context assembly."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                SELECT role, content FROM conversation_logs
                WHERE session_id = ?
                ORDER BY id DESC LIMIT ?;
                """, (session_id, limit))
                rows = cursor.fetchall()
                # Return in chronological order
                return [{"role": r["role"], "content": r["content"]} for r in reversed(rows)]
        except Exception as e:
            logger.error("Could not fetch history: %s", e)
            return []


# Global memory singleton
memory = BaronMemoryStore()
