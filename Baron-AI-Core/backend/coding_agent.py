"""
BARON CORE - Module 1: Local Autonomous Coding Agent (VS Code Integration)
Phase 1 Execution Engine:
1. Directory & File Traversal: Recursive workspace scanning, line-bounded source reading, local architectural indexing.
2. Multi-Language Code Modification: Code parsing & rewriting across Python, JavaScript, C++, HTML/CSS.
3. Workspace Auto-Patching: Autonomous file edits, line-range patching, atomic backups, rollback checkpoints.
4. Terminal Execution & Testing: Compiler/interpreter execution, automated stdout/stderr feedback analysis.
"""

import os
import re
import sys
import ast
import json
import time
import shutil
import hashlib
import tempfile
import subprocess
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple, Union

logger = logging.getLogger("BaronCodingAgent")

# Default folders and files to ignore during traversal
DEFAULT_IGNORES = {
    ".git", ".svn", ".hg", "__pycache__", ".pytest_cache", ".venv", "venv",
    "node_modules", ".idea", ".vscode", "dist", "build", "target", "bin",
    "obj", ".next", ".nuxt", "coverage", ".baron_backups"
}

# Recognized programming and markup languages
LANGUAGE_EXTENSIONS = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".c": "c",
    ".cpp": "cpp",
    ".cc": "cpp",
    ".cxx": "cpp",
    ".h": "c_header",
    ".hpp": "cpp_header",
    ".html": "html",
    ".htm": "html",
    ".css": "css",
    ".scss": "scss",
    ".json": "json",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".toml": "toml",
    ".md": "markdown",
    ".sh": "bash",
    ".bat": "batch",
    ".ps1": "powershell"
}


# =====================================================================
# 1. DIRECTORY & FILE TRAVERSAL
# =====================================================================

class DirectoryTraversal:
    """Recursively scans workspaces, reads files safely, and indexes project architecture."""

    @staticmethod
    def scan_workspace(
        workspace_path: str,
        max_depth: int = 5,
        include_hidden: bool = False,
        custom_ignores: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Recursively scans the workspace directory.
        Returns total file count, directories, files by language, and directory tree.
        """
        root = Path(workspace_path).resolve()
        if not root.exists() or not root.is_dir():
            return {"success": False, "error": f"Path '{workspace_path}' does not exist or is not a directory."}

        ignores = set(DEFAULT_IGNORES)
        if custom_ignores:
            ignores.update(custom_ignores)

        files_list = []
        dirs_list = []
        language_distribution = {}
        total_size_bytes = 0

        def _traverse(current: Path, depth: int):
            nonlocal total_size_bytes
            if depth > max_depth:
                return

            try:
                entries = sorted(current.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
            except PermissionError:
                return

            for entry in entries:
                if entry.name in ignores:
                    continue
                if not include_hidden and entry.name.startswith(".") and entry.name not in {".env"}:
                    continue

                rel_path = str(entry.relative_to(root)).replace("\\", "/")

                if entry.is_dir():
                    dirs_list.append(rel_path)
                    _traverse(entry, depth + 1)
                elif entry.is_file():
                    ext = entry.suffix.lower()
                    lang = LANGUAGE_EXTENSIONS.get(ext, "other")
                    try:
                        sz = entry.stat().st_size
                    except OSError:
                        sz = 0

                    total_size_bytes += sz
                    language_distribution[lang] = language_distribution.get(lang, 0) + 1

                    files_list.append({
                        "path": rel_path,
                        "name": entry.name,
                        "extension": ext,
                        "language": lang,
                        "size_bytes": sz
                    })

        _traverse(root, 0)

        return {
            "success": True,
            "workspace_root": str(root),
            "total_files": len(files_list),
            "total_directories": len(dirs_list),
            "total_size_kb": round(total_size_bytes / 1024, 2),
            "languages": language_distribution,
            "files": files_list,
            "directories": dirs_list
        }

    @staticmethod
    def read_source_file(
        file_path: str,
        start_line: Optional[int] = None,
        end_line: Optional[int] = None,
        max_bytes: int = 256 * 1024
    ) -> Dict[str, Any]:
        """
        Safely reads source file with line-number boundaries and multiple encoding fallbacks.
        """
        p = Path(file_path).resolve()
        if not p.exists() or not p.is_file():
            return {"success": False, "error": f"File '{file_path}' does not exist or is not a file."}

        # Size guard
        try:
            file_size = p.stat().st_size
            if file_size > max_bytes and start_line is None:
                return {
                    "success": False,
                    "error": f"File size ({file_size} bytes) exceeds limit of {max_bytes} bytes. Specify start_line & end_line."
                }
        except OSError as e:
            return {"success": False, "error": str(e)}

        # Encoding fallback list
        encodings = ["utf-8", "utf-8-sig", "cp1252", "latin-1"]
        content = None
        used_encoding = None

        for enc in encodings:
            try:
                with open(p, "r", encoding=enc) as f:
                    content = f.read()
                used_encoding = enc
                break
            except (UnicodeDecodeError, OSError):
                continue

        if content is None:
            return {"success": False, "error": f"Failed to decode '{file_path}' with supported encodings."}

        lines = content.splitlines(keepends=True)
        total_lines = len(lines)

        s_line = max(1, start_line) if start_line is not None else 1
        e_line = min(total_lines, end_line) if end_line is not None else total_lines

        if s_line > total_lines:
            selected_lines = []
        else:
            selected_lines = lines[s_line - 1 : e_line]

        numbered_content = "".join(f"{i + s_line:4d} | {line}" for i, line in enumerate(selected_lines))
        raw_slice = "".join(selected_lines)

        ext = p.suffix.lower()
        lang = LANGUAGE_EXTENSIONS.get(ext, "plaintext")

        return {
            "success": True,
            "file_path": str(p),
            "file_name": p.name,
            "language": lang,
            "encoding": used_encoding,
            "total_lines": total_lines,
            "start_line": s_line,
            "end_line": e_line,
            "content": raw_slice,
            "numbered_content": numbered_content
        }

    @staticmethod
    def find_files(workspace_path: str, pattern: str) -> List[str]:
        """Searches files in workspace matching a glob or substring pattern."""
        root = Path(workspace_path).resolve()
        if not root.exists():
            return []

        results = []
        is_glob = any(char in pattern for char in ["*", "?", "["])
        for p in root.rglob("*" if is_glob else f"*{pattern}*"):
            if any(ign in p.parts for ign in DEFAULT_IGNORES):
                continue
            if p.is_file():
                if is_glob and p.match(pattern):
                    results.append(str(p.relative_to(root)).replace("\\", "/"))
                elif not is_glob and pattern.lower() in p.name.lower():
                    results.append(str(p.relative_to(root)).replace("\\", "/"))
        return sorted(results)

    @classmethod
    def index_project_architecture(cls, workspace_path: str) -> Dict[str, Any]:
        """
        Builds a comprehensive local architecture index:
        - Hierarchy breakdown
        - Key entrypoints (main.py, index.html, app.js, etc.)
        - Symbols extracted across Python, JS, C++
        - Architecture summary map
        """
        scan = cls.scan_workspace(workspace_path)
        if not scan.get("success"):
            return scan

        root = Path(workspace_path).resolve()
        files = scan.get("files", [])

        symbols_catalog = {}
        entrypoints = []

        # Common entrypoint signatures
        known_entrypoints = {
            "main.py", "app.py", "baron_server.py", "baron_service.py",
            "index.html", "index.js", "app.js", "main.cpp", "main.c", "server.js"
        }

        for file_info in files:
            rel_path = file_info["path"]
            fname = file_info["name"]
            lang = file_info["language"]

            if fname.lower() in known_entrypoints:
                entrypoints.append(rel_path)

            full_p = root / rel_path
            # Extract symbols for major languages if file is moderate size
            if file_info["size_bytes"] < 100 * 1024 and lang in {"python", "javascript", "typescript", "cpp", "c"}:
                syms = MultiLanguageCodeEngine.extract_symbols_from_file(str(full_p), lang)
                if syms:
                    symbols_catalog[rel_path] = syms

        architecture_index = {
            "success": True,
            "project_name": root.name,
            "workspace_root": str(root),
            "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "total_files": scan["total_files"],
            "total_directories": scan["total_directories"],
            "languages": scan["languages"],
            "entrypoints": entrypoints,
            "symbols_indexed_files": len(symbols_catalog),
            "symbols_catalog": symbols_catalog,
            "directory_layout": scan["directories"][:30]
        }

        # Cache index locally inside .baron_architecture.json for zero-latency retrieval
        cache_file = root / ".baron_architecture.json"
        try:
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(architecture_index, f, indent=2)
        except OSError as e:
            logger.warning(f"Could not save local architecture cache: {e}")

        return architecture_index


# =====================================================================
# 2. MULTI-LANGUAGE CODE MODIFICATION
# =====================================================================

class MultiLanguageCodeEngine:
    """Parses, extracts symbols, validates, and transforms multi-language code."""

    @staticmethod
    def detect_language(file_path: str) -> str:
        """Determines programming language from file path extension."""
        ext = Path(file_path).suffix.lower()
        return LANGUAGE_EXTENSIONS.get(ext, "plaintext")

    @staticmethod
    def validate_syntax(code: str, language: str) -> Dict[str, Any]:
        """
        Validates syntax for Python, JSON, JS/HTML basic structures, and C++ brace matching.
        """
        if language == "python":
            try:
                ast.parse(code)
                return {"valid": True, "error": None}
            except SyntaxError as e:
                return {
                    "valid": False,
                    "error": f"SyntaxError on line {e.lineno}: {e.msg}",
                    "line": e.lineno,
                    "offset": e.offset
                }
        elif language == "json":
            try:
                json.loads(code)
                return {"valid": True, "error": None}
            except json.JSONDecodeError as e:
                return {
                    "valid": False,
                    "error": f"JSONDecodeError on line {e.lineno}: {e.msg}",
                    "line": e.lineno
                }
        elif language in {"javascript", "typescript", "c", "cpp"}:
            # Balanced bracket & quote check
            stack = []
            brackets = {')': '(', '}': '{', ']': '['}
            lines = code.splitlines()
            for line_no, line in enumerate(lines, 1):
                # Ignore simple single-line comments
                clean_line = re.sub(r'//.*$', '', line)
                for ch in clean_line:
                    if ch in "({[":
                        stack.append((ch, line_no))
                    elif ch in ")}]":
                        if not stack:
                            return {"valid": False, "error": f"Unmatched closing '{ch}' on line {line_no}", "line": line_no}
                        top_ch, top_line = stack.pop()
                        if brackets[ch] != top_ch:
                            return {
                                "valid": False,
                                "error": f"Mismatched bracket '{ch}' on line {line_no} (opened '{top_ch}' on line {top_line})",
                                "line": line_no
                            }
            if stack:
                top_ch, top_line = stack.pop()
                return {"valid": False, "error": f"Unclosed bracket '{top_ch}' opened on line {top_line}", "line": top_line}
            return {"valid": True, "error": None}

        # Other languages pass default heuristic
        return {"valid": True, "error": None}

    @staticmethod
    def extract_symbols_from_file(file_path: str, language: str) -> Dict[str, List[str]]:
        """Extracts top-level functions, classes, and structs from a source file."""
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
        except OSError:
            return {}

        symbols: Dict[str, List[str]] = {"classes": [], "functions": []}

        if language == "python":
            try:
                tree = ast.parse(content)
                for node in tree.body:
                    if isinstance(node, ast.ClassDef):
                        symbols["classes"].append(node.name)
                    elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        symbols["functions"].append(node.name)
            except SyntaxError:
                pass
        elif language in {"javascript", "typescript"}:
            # Regex extraction for JS functions & classes
            classes = re.findall(r'class\s+([A-Za-z0-9_$]+)', content)
            functions = re.findall(r'(?:function\s+([A-Za-z0-9_$]+)|(?:const|let|var)\s+([A-Za-z0-9_$]+)\s*=\s*(?:async\s*)?(?:\([^)]*\)|[A-Za-z0-9_$]+)\s*=>)', content)
            symbols["classes"] = list(set(classes))
            fn_names = []
            for fn in functions:
                name = fn[0] if fn[0] else fn[1]
                if name:
                    fn_names.append(name)
            symbols["functions"] = sorted(list(set(fn_names)))
        elif language in {"cpp", "c"}:
            classes = re.findall(r'(?:class|struct)\s+([A-Za-z0-9_]+)\s*\{', content)
            functions = re.findall(r'([A-Za-z0-9_:]+)\s+([A-Za-z0-9_]+)\s*\([^)]*\)\s*\{', content)
            symbols["classes"] = list(set(classes))
            symbols["functions"] = sorted(list(set(f[1] for f in functions if f[1] not in {"if", "for", "while", "switch"})))

        return symbols

    @classmethod
    def generate_or_modify_code(
        cls,
        prompt: str,
        file_path: Optional[str] = None,
        language: Optional[str] = None,
        existing_code: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Parses requirements and generates or modifies code via local LLM reasoning (Ollama / Gemini).
        Falls back to intelligent local template synthesis if no LLM is online.
        """
        lang = language or (cls.detect_language(file_path) if file_path else "python")

        # Read existing code if path provided and code not passed
        if file_path and existing_code is None and os.path.exists(file_path):
            read_res = DirectoryTraversal.read_source_file(file_path)
            if read_res.get("success"):
                existing_code = read_res.get("content")

        system_instruction = (
            f"You are Baron's Autonomous Coding Agent specializing in {lang}.\n"
            f"Analyze the user's task and return ONLY the modified or new valid code.\n"
            f"Do not include unnecessary conversational filler. Return code formatted directly."
        )

        llm_prompt = f"Target Language: {lang}\n"
        if existing_code:
            llm_prompt += f"Existing Code Context:\n```{lang}\n{existing_code[:2000]}\n```\n\n"
        llm_prompt += f"Task / Modification Request: {prompt}\nProvide complete, working code."

        generated_code = ""

        # 1. Try local Ollama or Gemini via ai_brain
        try:
            from backend import ai_brain
            if hasattr(ai_brain, "ask_ollama") and ai_brain.OLLAMA_BASE_URL:
                llm_res = ai_brain.ask_ollama(llm_prompt, system_prompt=system_instruction)
                if llm_res and len(llm_res.strip()) > 10:
                    generated_code = cls._extract_code_from_markdown(llm_res, lang)
            if not generated_code and hasattr(ai_brain, "ask_gemini") and getattr(ai_brain, "GEMINI_API_KEY", ""):
                llm_res = ai_brain.ask_gemini(llm_prompt, system_prompt=system_instruction)
                if llm_res and len(llm_res.strip()) > 10:
                    generated_code = cls._extract_code_from_markdown(llm_res, lang)
        except Exception as e:
            logger.info(f"LLM integration deferred or offline: {e}")

        # 2. Local fallback synthesis if LLM not responding
        if not generated_code:
            generated_code = cls._synthesize_local_code_fallback(prompt, lang, existing_code)

        # Validate syntax
        syntax_check = cls.validate_syntax(generated_code, lang)

        return {
            "success": True,
            "language": lang,
            "file_path": file_path,
            "code": generated_code,
            "syntax_valid": syntax_check["valid"],
            "syntax_error": syntax_check.get("error")
        }

    @staticmethod
    def _extract_code_from_markdown(text: str, language: str) -> str:
        """Extracts code block from markdown responses."""
        match = re.search(r'```(?:[a-zA-Z0-9_\-+]*)\n(.*?)```', text, re.DOTALL)
        if match:
            return match.group(1).strip()
        return text.strip()

    @staticmethod
    def _synthesize_local_code_fallback(prompt: str, language: str, existing_code: Optional[str]) -> str:
        """Generates clean boilerplate or appends requested function when working completely offline."""
        clean_name = re.sub(r'[^a-zA-Z0-9_]', '_', prompt.lower().split()[0] if prompt.split() else "baron_task")

        if language == "python":
            if existing_code:
                return existing_code + f"\n\n# Autonomous addition: {prompt}\ndef {clean_name}():\n    \"\"\"{prompt}\"\"\"\n    print(\"Executed {clean_name} successfully.\")\n    return True\n"
            return f"\"\"\"\nModule generated autonomously by Baron AI\nTask: {prompt}\n\"\"\"\n\ndef {clean_name}():\n    print(\"Baron Autonomous Execution: {prompt}\")\n    return True\n\nif __name__ == '__main__':\n    {clean_name}()\n"

        elif language in {"javascript", "typescript"}:
            if existing_code:
                return existing_code + f"\n\n// Autonomous addition: {prompt}\nfunction {clean_name}() {{\n  console.log('Executed {clean_name} successfully.');\n  return true;\n}}\n"
            return f"// Baron Autonomous JS Module\n// Task: {prompt}\n\nfunction {clean_name}() {{\n  console.log('Baron Autonomous Execution: {prompt}');\n  return true;\n}}\n\nmodule.exports = {{ {clean_name} }};\n"

        elif language in {"cpp", "c"}:
            if existing_code:
                return existing_code + f"\n\n// Autonomous addition: {prompt}\nvoid {clean_name}() {{\n    // {prompt}\n}}\n"
            return f"#include <iostream>\n\n// Baron Autonomous C++ Module: {prompt}\nint main() {{\n    std::cout << \"Baron Autonomous Execution: {prompt}\" << std::endl;\n    return 0;\n}}\n"

        elif language == "html":
            return f"<!DOCTYPE html>\n<html>\n<head>\n  <title>{prompt}</title>\n</head>\n<body>\n  <h1>Baron AI: {prompt}</h1>\n</body>\n</html>\n"

        return existing_code or f"# Baron Task: {prompt}\n"


# =====================================================================
# 3. WORKSPACE AUTO-PATCHING
# =====================================================================

class AutoPatcher:
    """Applies direct file edits, line-range drop-ins, and maintains rollback checkpoints."""

    BACKUP_DIR_NAME = ".baron_backups"

    @classmethod
    def _get_backup_dir(cls, file_path: Path) -> Path:
        """Locates or creates backup directory relative to the file's repository root."""
        parent = file_path.parent
        # Walk up to find workspace root or stop at 3 levels
        cur = parent
        for _ in range(3):
            if (cur / ".git").exists() or (cur / "requirements.txt").exists():
                b_dir = cur / cls.BACKUP_DIR_NAME
                b_dir.mkdir(parents=True, exist_ok=True)
                return b_dir
            if cur.parent == cur:
                break
            cur = cur.parent

        b_dir = parent / cls.BACKUP_DIR_NAME
        b_dir.mkdir(parents=True, exist_ok=True)
        return b_dir

    @classmethod
    def create_backup_checkpoint(cls, file_path: str) -> Optional[str]:
        """Creates a timestamped snapshot of a file before patching."""
        p = Path(file_path).resolve()
        if not p.exists() or not p.is_file():
            return None

        b_dir = cls._get_backup_dir(p)
        timestamp = int(time.time() * 1000)
        h = hashlib.md5(str(p).encode()).hexdigest()[:6]
        backup_id = f"{timestamp}_{h}"
        backup_name = f"{p.name}.{backup_id}.bak"
        dest = b_dir / backup_name

        try:
            shutil.copy2(p, dest)
            # Record manifest
            manifest = {
                "original_path": str(p),
                "backup_path": str(dest),
                "timestamp": timestamp,
                "backup_id": backup_id
            }
            manifest_file = b_dir / f"{backup_name}.meta.json"
            with open(manifest_file, "w", encoding="utf-8") as f:
                json.dump(manifest, f, indent=2)
            return manifest["backup_id"]
        except OSError as e:
            logger.warning(f"Failed to create backup checkpoint: {e}")
            return None

    @classmethod
    def write_file_atomic(
        cls,
        file_path: str,
        content: str,
        create_backup: bool = True
    ) -> Dict[str, Any]:
        """
        Atomically writes full content to file using temporary file swap.
        Automatically takes a backup snapshot.
        """
        p = Path(file_path).resolve()
        p.parent.mkdir(parents=True, exist_ok=True)

        backup_id = None
        if create_backup and p.exists():
            backup_id = cls.create_backup_checkpoint(str(p))

        # Write to temporary file in same folder to guarantee atomic rename
        temp_file = None
        try:
            with tempfile.NamedTemporaryFile("w", dir=p.parent, delete=False, encoding="utf-8") as tf:
                tf.write(content)
                temp_file = Path(tf.name)

            # Atomic swap
            temp_file.replace(p)
            return {
                "success": True,
                "file_path": str(p),
                "backup_id": backup_id,
                "bytes_written": len(content.encode("utf-8")),
                "lines_written": len(content.splitlines())
            }
        except Exception as e:
            if temp_file and temp_file.exists():
                try:
                    temp_file.unlink()
                except OSError:
                    pass
            return {"success": False, "error": f"Atomic write failed: {e}"}

    @classmethod
    def patch_file_content(
        cls,
        file_path: str,
        target_content: str,
        replacement_content: str,
        allow_multiple: bool = False
    ) -> Dict[str, Any]:
        """
        Applies a precise search-and-replace patch to file content.
        """
        p = Path(file_path).resolve()
        if not p.exists() or not p.is_file():
            return {"success": False, "error": f"File '{file_path}' does not exist."}

        read_res = DirectoryTraversal.read_source_file(str(p))
        if not read_res.get("success"):
            return read_res

        current_content = read_res["content"]

        occurrences = current_content.count(target_content)
        if occurrences == 0:
            return {
                "success": False,
                "error": "Target content not found in file. Ensure exact match including whitespace."
            }
        if occurrences > 1 and not allow_multiple:
            return {
                "success": False,
                "error": f"Target content found {occurrences} times. Set allow_multiple=True to replace all."
            }

        new_content = current_content.replace(target_content, replacement_content, -1 if allow_multiple else 1)
        write_res = cls.write_file_atomic(str(p), new_content, create_backup=True)

        if write_res.get("success"):
            write_res["replacements_count"] = occurrences if allow_multiple else 1
        return write_res

    @classmethod
    def patch_file_lines(
        cls,
        file_path: str,
        start_line: int,
        end_line: int,
        replacement_content: str
    ) -> Dict[str, Any]:
        """
        Replaces lines in the range [start_line, end_line] (1-indexed, inclusive).
        """
        p = Path(file_path).resolve()
        if not p.exists() or not p.is_file():
            return {"success": False, "error": f"File '{file_path}' does not exist."}

        read_res = DirectoryTraversal.read_source_file(str(p))
        if not read_res.get("success"):
            return read_res

        lines = read_res["content"].splitlines(keepends=True)
        total_lines = len(lines)

        if start_line < 1 or end_line < start_line or start_line > total_lines:
            return {
                "success": False,
                "error": f"Invalid line range [{start_line}, {end_line}] for file with {total_lines} lines."
            }

        # Normalize replacement lines
        if replacement_content and not replacement_content.endswith("\n"):
            replacement_content += "\n"

        before = lines[: start_line - 1]
        after = lines[end_line:]

        new_content = "".join(before) + replacement_content + "".join(after)
        return cls.write_file_atomic(str(p), new_content, create_backup=True)

    @classmethod
    def rollback_patch(cls, file_path: str, backup_id: Optional[str] = None) -> Dict[str, Any]:
        """Rolls back a file to its latest (or specified) backup checkpoint."""
        p = Path(file_path).resolve()
        b_dir = cls._get_backup_dir(p)
        if not b_dir.exists():
            return {"success": False, "error": "No backup directory found for this workspace."}

        # Find matching backup
        backups = sorted(b_dir.glob(f"{p.name}.*.bak"), key=lambda f: f.stat().st_mtime, reverse=True)
        if not backups:
            return {"success": False, "error": f"No backups available for file '{p.name}'."}

        target_backup = None
        if backup_id:
            for b in backups:
                if backup_id in b.name:
                    target_backup = b
                    break
            if not target_backup:
                return {"success": False, "error": f"Backup ID '{backup_id}' not found."}
        else:
            target_backup = backups[0]

        try:
            shutil.copy2(target_backup, p)
            return {
                "success": True,
                "file_path": str(p),
                "restored_from": str(target_backup),
                "message": f"Successfully restored '{p.name}' from backup."
            }
        except OSError as e:
            return {"success": False, "error": f"Failed to restore backup: {e}"}


# =====================================================================
# 4. TERMINAL EXECUTION & TESTING
# =====================================================================

class TerminalExecutor:
    """Executes compiler/interpreter commands and parses stderr/stdout feedback."""

    @staticmethod
    def run_command(
        command: Union[str, List[str]],
        cwd: Optional[str] = None,
        timeout: int = 30,
        env: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        Executes a shell command safely with stdout/stderr capture and timeout limits.
        """
        target_cwd = cwd or os.getcwd()
        cmd_env = os.environ.copy()
        if env:
            cmd_env.update(env)

        start_t = time.time()
        try:
            is_windows = sys.platform == "win32"
            shell_needed = isinstance(command, str)

            process = subprocess.Popen(
                command,
                cwd=target_cwd,
                env=cmd_env,
                shell=shell_needed,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace"
            )

            stdout, stderr = process.communicate(timeout=timeout)
            duration_ms = round((time.time() - start_t) * 1000, 2)

            return {
                "success": process.returncode == 0,
                "returncode": process.returncode,
                "stdout": stdout,
                "stderr": stderr,
                "duration_ms": duration_ms,
                "timed_out": False
            }

        except subprocess.TimeoutExpired:
            process.kill()
            stdout, stderr = process.communicate()
            duration_ms = round((time.time() - start_t) * 1000, 2)
            return {
                "success": False,
                "returncode": -1,
                "stdout": stdout or "",
                "stderr": stderr or "Command execution timed out.",
                "duration_ms": duration_ms,
                "timed_out": True
            }
        except Exception as e:
            return {
                "success": False,
                "returncode": -1,
                "stdout": "",
                "stderr": str(e),
                "duration_ms": round((time.time() - start_t) * 1000, 2),
                "timed_out": False
            }

    @classmethod
    def test_code_file(
        cls,
        file_path: str,
        test_type: str = "auto",
        cwd: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Runs compilation or interpreter tests on a specific file based on its language:
        - Python: py_compile, pytest, or script execution
        - C/C++: gcc / g++ compile test
        - JavaScript: node execution / syntax check
        """
        p = Path(file_path).resolve()
        if not p.exists():
            return {"success": False, "error": f"File '{file_path}' does not exist."}

        target_cwd = cwd or str(p.parent)
        lang = MultiLanguageCodeEngine.detect_language(str(p))

        cmd = None

        if lang == "python":
            if test_type == "test" or "test" in p.name.lower():
                cmd = [sys.executable, "-m", "unittest", str(p)]
            else:
                cmd = [sys.executable, "-m", "py_compile", str(p)]

        elif lang in {"cpp", "c"}:
            compiler = "g++" if lang == "cpp" else "gcc"
            out_bin = str(p.parent / f"{p.stem}_test_bin.exe")
            cmd = f"{compiler} \"{str(p)}\" -o \"{out_bin}\""

        elif lang in {"javascript", "typescript"}:
            cmd = f"node --check \"{str(p)}\""

        else:
            return {"success": False, "error": f"No native compiler/tester configured for '{lang}'."}

        exec_res = cls.run_command(cmd, cwd=target_cwd)

        # Clean up temporary test binary if compiled
        if lang in {"cpp", "c"} and 'out_bin' in locals():
            try:
                if os.path.exists(out_bin):
                    os.remove(out_bin)
            except OSError:
                pass

        # Perform automated feedback analysis
        analysis = cls.analyze_execution_feedback(
            returncode=exec_res["returncode"],
            stdout=exec_res["stdout"],
            stderr=exec_res["stderr"],
            language=lang
        )

        return {
            "success": exec_res["success"],
            "file_path": str(p),
            "language": lang,
            "command": cmd if isinstance(cmd, str) else " ".join(cmd),
            "returncode": exec_res["returncode"],
            "stdout": exec_res["stdout"],
            "stderr": exec_res["stderr"],
            "duration_ms": exec_res["duration_ms"],
            "analysis": analysis
        }

    @staticmethod
    def analyze_execution_feedback(
        returncode: int,
        stdout: str,
        stderr: str,
        language: str
    ) -> Dict[str, Any]:
        """
        Analyzes stdout/stderr to detect error types, tracebacks, line numbers, and diagnosis.
        """
        if returncode == 0:
            return {
                "status": "PASSED",
                "error_category": None,
                "line_number": None,
                "summary": "Execution succeeded with zero errors.",
                "suggestion": None
            }

        combined_err = f"{stderr}\n{stdout}".strip()
        category = "UNKNOWN_ERROR"
        line_num = None
        suggestion = "Review the stderr logs above for details."

        if language == "python":
            if "SyntaxError" in combined_err:
                category = "SYNTAX_ERROR"
                m = re.search(r'line\s+(\d+)', combined_err)
                if m:
                    line_num = int(m.group(1))
                suggestion = "Check for missing colons, mismatched quotes, or indentation errors."
            elif "ModuleNotFoundError" in combined_err or "ImportError" in combined_err:
                category = "IMPORT_ERROR"
                m = re.search(r"No module named\s+'([^']+)'", combined_err)
                missing_mod = m.group(1) if m else "package"
                suggestion = f"Install the missing package with: pip install {missing_mod}"
            elif "IndentationError" in combined_err:
                category = "INDENTATION_ERROR"
                suggestion = "Standardize tab and space indentation."
            elif "Traceback" in combined_err:
                category = "RUNTIME_EXCEPTION"
                lines = re.findall(r'line\s+(\d+)', combined_err)
                if lines:
                    line_num = int(lines[-1])
                suggestion = "Inspect the line that triggered the exception."

        elif language in {"cpp", "c"}:
            if "error:" in combined_err:
                category = "COMPILER_ERROR"
                m = re.search(r':(\d+):\d+:\s+error:', combined_err)
                if m:
                    line_num = int(m.group(1))
                suggestion = "Verify types, missing semicolons, or unresolved headers."
            elif "undefined reference" in combined_err:
                category = "LINKER_ERROR"
                suggestion = "Ensure all required libraries and object files are linked."

        elif language in {"javascript", "typescript"}:
            if "SyntaxError" in combined_err:
                category = "SYNTAX_ERROR"
                suggestion = "Check JavaScript bracket closures, punctuation, and ES module syntax."
            elif "Cannot find module" in combined_err:
                category = "MODULE_NOT_FOUND"
                suggestion = "Run npm install to verify dependencies."

        return {
            "status": "FAILED",
            "error_category": category,
            "line_number": line_num,
            "summary": combined_err.splitlines()[-1] if combined_err else "Non-zero exit code.",
            "suggestion": suggestion
        }


# =====================================================================
# 5. HIGH-LEVEL AUTONOMOUS CONTROLLER
# =====================================================================

class CodingAgent:
    """Unified entrypoint orchestrating all Phase 1 autonomous coding tools."""

    def __init__(self, workspace_path: Optional[str] = None):
        self.workspace_path = workspace_path or os.getcwd()
        self.traversal = DirectoryTraversal()
        self.code_engine = MultiLanguageCodeEngine()
        self.patcher = AutoPatcher()
        self.executor = TerminalExecutor()

    def scan(self, max_depth: int = 5) -> Dict[str, Any]:
        """Scans workspace directory recursively."""
        return self.traversal.scan_workspace(self.workspace_path, max_depth=max_depth)

    def read(self, relative_file_path: str, start_line: Optional[int] = None, end_line: Optional[int] = None) -> Dict[str, Any]:
        """Reads file within workspace."""
        full_path = Path(self.workspace_path) / relative_file_path
        return self.traversal.read_source_file(str(full_path), start_line, end_line)

    def index(self) -> Dict[str, Any]:
        """Indexes local project architecture."""
        return self.traversal.index_project_architecture(self.workspace_path)

    def patch_content(self, relative_file_path: str, target: str, replacement: str, allow_multiple: bool = False) -> Dict[str, Any]:
        """Patches content in a workspace file."""
        full_path = Path(self.workspace_path) / relative_file_path
        return self.patcher.patch_file_content(str(full_path), target, replacement, allow_multiple)

    def patch_lines(self, relative_file_path: str, start_line: int, end_line: int, replacement: str) -> Dict[str, Any]:
        """Replaces lines in a workspace file."""
        full_path = Path(self.workspace_path) / relative_file_path
        return self.patcher.patch_file_lines(str(full_path), start_line, end_line, replacement)

    def rollback(self, relative_file_path: str, backup_id: Optional[str] = None) -> Dict[str, Any]:
        """Rolls back a patched file."""
        full_path = Path(self.workspace_path) / relative_file_path
        return self.patcher.rollback_patch(str(full_path), backup_id)

    def test(self, relative_file_path: str) -> Dict[str, Any]:
        """Runs test/compiler on a workspace file."""
        full_path = Path(self.workspace_path) / relative_file_path
        return self.executor.test_code_file(str(full_path), cwd=self.workspace_path)

    def run_cmd(self, command: str, timeout: int = 30) -> Dict[str, Any]:
        """Executes a terminal command within the workspace directory."""
        return self.executor.run_command(command, cwd=self.workspace_path, timeout=timeout)

    def modify_or_create(self, prompt: str, relative_file_path: str) -> Dict[str, Any]:
        """Autonomously analyzes prompt, generates code, and writes it to file."""
        full_path = Path(self.workspace_path) / relative_file_path
        code_res = self.code_engine.generate_or_modify_code(prompt, file_path=str(full_path))
        if not code_res.get("success"):
            return code_res

        write_res = self.patcher.write_file_atomic(str(full_path), code_res["code"], create_backup=True)
        return {
            "success": write_res.get("success"),
            "file_path": relative_file_path,
            "language": code_res["language"],
            "syntax_valid": code_res["syntax_valid"],
            "syntax_error": code_res.get("syntax_error"),
            "backup_id": write_res.get("backup_id")
        }


# Global CodingAgent Singleton
agent = CodingAgent()
