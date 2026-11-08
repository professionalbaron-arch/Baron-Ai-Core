"""
BARON CORE - Central FastAPI & WebSockets Hub
Coordinates Frontend 3D HUD, AI Brain (Ollama), and Vocal Engine
"""

import os
import sys
import json
import time
import asyncio
import logging
from typing import List, Dict, Any
from datetime import datetime

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# Ensure backend directory is in sys.path
_current_dir = os.path.dirname(os.path.abspath(__file__))
if _current_dir not in sys.path:
    sys.path.insert(0, _current_dir)

# Import internal BARON modules
try:
    from backend.ai_brain import ask_baron_async, MODEL_NAME, OLLAMA_BASE_URL
    from backend.voice_engine import speak, listen
except ImportError:
    from ai_brain import ask_baron_async, MODEL_NAME, OLLAMA_BASE_URL
    from voice_engine import speak, listen

# Setup structured logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] [BARON-CORE] %(message)s")
logger = logging.getLogger("BaronServer")

app = FastAPI(
    title="BARON CORE Autonomous System",
    description="Zero-latency neural bridge between 3D HUD and local AI compute",
    version="2.0.0"
)

# Enable permissive CORS for cross-platform Web/PWA access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -------------------------------------------------------------
# WebSocket Connection Manager
# -------------------------------------------------------------
class ConnectionManager:
    def __init__(self):
           self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"HUD Client connected. Active nodes: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            logger.info(f"HUD Client disconnected. Active nodes: {len(self.active_connections)}")

    async def send_json(self, websocket: WebSocket, data: Dict[str, Any]):
        try:
            await websocket.send_json(data)
        except Exception as e:
            logger.error(f"Failed to transmit packet to client: {e}")

    async def broadcast(self, data: Dict[str, Any]):
        for connection in list(self.active_connections):
            try:
                await connection.send_json(data)
            except Exception:
                self.disconnect(connection)

manager = ConnectionManager()

# -------------------------------------------------------------
# REST Diagnostic Endpoints
# -------------------------------------------------------------
@app.get("/")
async def root():
    return {
        "system": "BARON CORE",
        "status": "ONLINE",
        "timestamp": datetime.utcnow().isoformat(),
        "model": MODEL_NAME,
        "ollama_endpoint": OLLAMA_BASE_URL,
        "websocket_route": "/ws"
    }

@app.get("/health")
async def health():
    return {"status": "healthy", "core_load": "optimal", "modules": ["ai_brain", "system_control", "tool_registry", "memory", "scheduler", "mcp_client", "coding_agent"]}

@app.get("/api/tools")
async def list_tools_endpoint():
    """Returns Moltis-style tools inventory."""
    try:
        from backend.tool_registry import registry
    except ImportError:
        from tool_registry import registry
    return {"tools": registry.list_tools()}

@app.get("/api/memory")
async def search_memory_endpoint(q: str = ""):
    """Returns matching memory items from SQLite + FTS."""
    try:
        from backend.memory import memory
    except ImportError:
        from memory import memory
    if q:
        results = memory.search_memory(q)
    else:
        results = memory.get_recent_history("desktop_session", limit=10)
    return {"query": q, "results": results}

# -------------------------------------------------------------
# Module 1: Autonomous Coding Agent Endpoints
# -------------------------------------------------------------
@app.get("/api/code/index")
async def code_index_endpoint():
    """Returns locally indexed project architecture and symbols."""
    try:
        from backend.coding_agent import agent
    except ImportError:
        from coding_agent import agent
    return agent.index()

@app.post("/api/code/scan")
async def code_scan_endpoint(payload: Dict[str, Any] = None):
    """Scans workspace directory recursively."""
    payload = payload or {}
    max_depth = payload.get("max_depth", 5)
    try:
        from backend.coding_agent import agent
    except ImportError:
        from coding_agent import agent
    return agent.scan(max_depth=max_depth)

@app.post("/api/code/read")
async def code_read_endpoint(payload: Dict[str, Any]):
    """Reads source file safely with optional start/end line bounds."""
    file_path = payload.get("file_path", "")
    if not file_path:
        raise HTTPException(status_code=400, detail="file_path required.")
    start_line = payload.get("start_line")
    end_line = payload.get("end_line")
    try:
        from backend.coding_agent import agent
    except ImportError:
        from coding_agent import agent
    return agent.read(file_path, start_line=start_line, end_line=end_line)

@app.post("/api/code/patch")
async def code_patch_endpoint(payload: Dict[str, Any]):
    """Patches content or lines in a workspace file with automatic backup."""
    file_path = payload.get("file_path", "")
    if not file_path:
        raise HTTPException(status_code=400, detail="file_path required.")
    try:
        from backend.coding_agent import agent
    except ImportError:
        from coding_agent import agent

    if "start_line" in payload and "end_line" in payload:
        return agent.patch_lines(
            file_path,
            start_line=int(payload["start_line"]),
            end_line=int(payload["end_line"]),
            replacement=payload.get("replacement", "")
        )
    elif "target" in payload:
        return agent.patch_content(
            file_path,
            target=payload["target"],
            replacement=payload.get("replacement", ""),
            allow_multiple=payload.get("allow_multiple", False)
        )
    else:
        raise HTTPException(status_code=400, detail="Provide either target content or start_line & end_line.")

@app.post("/api/code/test")
async def code_test_endpoint(payload: Dict[str, Any]):
    """Runs compiler or interpreter tests and returns stdout/stderr analysis."""
    file_path = payload.get("file_path", "")
    if not file_path:
        raise HTTPException(status_code=400, detail="file_path required.")
    try:
        from backend.coding_agent import agent
    except ImportError:
        from coding_agent import agent
    return agent.test(file_path)

@app.post("/api/code/exec")
async def code_exec_endpoint(payload: Dict[str, Any]):
    """Executes a build or test command in the workspace directory."""
    command = payload.get("command", "")
    if not command:
        raise HTTPException(status_code=400, detail="command required.")
    timeout = payload.get("timeout", 30)
    try:
        from backend.coding_agent import agent
    except ImportError:
        from coding_agent import agent
    return agent.run_cmd(command, timeout=timeout)

@app.post("/api/chat")
async def chat_rest(payload: Dict[str, Any]):
    prompt = payload.get("prompt", "")
    if not prompt:
        raise HTTPException(status_code=400, detail="Empty prompt provided.")
    
    reply = await ask_baron_async(prompt)
    if payload.get("speak", False):
        speak(reply)
    return {"prompt": prompt, "response": reply, "timestamp": time.time()}


# -------------------------------------------------------------
# Full-Duplex WebSocket Endpoint
# -------------------------------------------------------------
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)

    # Initial Welcome Handshake
    welcome_payload = {
        "type": "handshake",
        "status": "ONLINE",
        "system": "BARON CORE v2.0",
        "message": "Neural link established. Baron 3D HUD online and awaiting commands.",
        "timestamp": time.time()
    }
    await manager.send_json(websocket, welcome_payload)

    try:
        while True:
            raw_data = await websocket.receive_text()
            try:
                data = json.loads(raw_data)
            except json.JSONDecodeError:
                # If plain text is sent, wrap as prompt
                data = {"type": "prompt", "data": raw_data}

            msg_type = data.get("type", "prompt")
            logger.info(f"Incoming packet: type='{msg_type}'")

            # Heartbeat ping
            if msg_type == "ping":
                await manager.send_json(websocket, {"type": "pong", "timestamp": time.time()})
                continue

            # Speech to Text Trigger command from Frontend HUD
            elif msg_type == "voice_listen":
                await manager.send_json(websocket, {
                    "type": "status",
                    "status": "listening",
                    "message": "Vocal receptor active. Speak now..."
                })
                
                # Run STT in thread executor to avoid stalling async loop
                loop = asyncio.get_event_loop()
                transcribed_text = await loop.run_in_executor(None, listen, 6, 8)

                if transcribed_text:
                    await manager.send_json(websocket, {
                        "type": "stt_result",
                        "text": transcribed_text
                    })
                    
                    # Direct transcribed speech straight to AI Brain
                    await process_ai_query(websocket, transcribed_text)
                else:
                    await manager.send_json(websocket, {
                        "type": "status",
                        "status": "idle",
                        "message": "No vocal input detected. Reverting to standby."
                    })
                continue

            # Standard text prompt or command
            elif msg_type == "prompt":
                user_prompt = data.get("data") or data.get("prompt") or data.get("text") or ""
                await process_ai_query(websocket, user_prompt)

            # Telemetry or gesture notification from frontend
            elif msg_type == "gesture_telemetry":
                # Acknowledged (can log or route to system automations)
                pass

            else:
                logger.warning(f"Unrecognized packet signature: {msg_type}")

    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"Critical WebSocket loop anomaly: {e}")
        manager.disconnect(websocket)


async def process_ai_query(websocket: WebSocket, prompt: str):
    """
    Handles AI inference with real-time HUD status changes and vocalization.
    """
    if not prompt or not prompt.strip():
        await manager.send_json(websocket, {
            "type": "error",
            "message": "Tactical prompt empty. No operation executed."
        })
        return

    # 1. Notify HUD that Core is Thinking (triggers 3D Core pulse state)
    await manager.send_json(websocket, {
        "type": "status",
        "status": "thinking",
        "message": f"Processing query: '{prompt[:32]}...'"
    })

    # 2. Check System Command first
    start_time = time.time()
    try:
        from system_control import execute_system_command
        sys_res = execute_system_command(prompt)
    except Exception:
        logger.exception("System command execution failed for: '%s'", prompt)
        reply = "Command chalane me error aaya. Application setup ya Windows permission check kijiye."
    else:
        if sys_res is not None:
            reply = sys_res
        else:
            # Asynchronous inference (Friendly Brain + Web Search)
            reply = await ask_baron_async(prompt)

    latency_ms = round((time.time() - start_time) * 1000, 2)

    # 3. Transmit complete response to Frontend HUD
    await manager.send_json(websocket, {
        "type": "response",
        "prompt": prompt,
        "text": reply,
        "latency_ms": latency_ms,
        "timestamp": time.time()
    })

    # 4. Trigger Vocal Synthesis asynchronously (pyttsx3 runs in background thread)
    speak(reply)

    # 5. Notify HUD that Baron is actively speaking / synthesizing
    await manager.send_json(websocket, {
        "type": "status",
        "status": "speaking",
        "message": "Vocal payload transmitting."
    })


if __name__ == "__main__":
    import uvicorn
    print("\n==================================================")
    print("      INITIALIZING BARON CORE SERVER (v2.0)       ")
    print("==================================================")
    print(">> Fast-API WebSocket server loading on port 8000")
    print(">> Direct interface: http://localhost:8000")
    print(">> WebSocket endpoint: ws://localhost:8000/ws")
    print("==================================================\n")
    uvicorn.run("baron_server:app", host="0.0.0.0", port=8000, reload=True)
