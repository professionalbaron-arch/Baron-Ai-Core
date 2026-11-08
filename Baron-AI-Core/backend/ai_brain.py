"""
BARON CORE - Autonomous AI Brain with Qwen 2.5 & Google Gemini
Integrates Qwen 2.5 local model via Ollama with native tool calling,
real-time internet search, persistent memory, and Windows OS execution.
"""

import os
import re
import json
import random
import logging
from typing import List, Dict, Any, Optional

try:
    import httpx
except ImportError:
    httpx = None

try:
    from ddgs import DDGS
except ImportError:
    DDGS = None

try:
    from google import genai
    HAS_NEW_GENAI = True
    HAS_LEGACY_GENAI = False
except ImportError:
    HAS_NEW_GENAI = False
    try:
        import google.generativeai as legacy_genai
        HAS_LEGACY_GENAI = True
    except ImportError:
        HAS_LEGACY_GENAI = False

logger = logging.getLogger("BaronBrain")

# Configuration
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:3b")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# Load .env if present
env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
if os.path.exists(env_path):
    try:
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    k, v = k.strip(), v.strip().strip("'\"")
                    if k == "GEMINI_API_KEY" and not GEMINI_API_KEY:
                        GEMINI_API_KEY = v
                    elif k == "OLLAMA_BASE_URL":
                        OLLAMA_BASE_URL = v
                    elif k == "OLLAMA_MODEL":
                        OLLAMA_MODEL = v
    except Exception as e:
        logger.warning(f"Could not load .env: {e}")

# Persona & System Prompt
BARON_SYSTEM_PROMPT = """You are BARON, an ultra-intelligent, deeply capable, and loyal desktop AI companion living directly on the user's Windows PC.
You are the user's smartest, most supportive best friend combined with the raw autonomous operating power of JARVIS.

Core Persona Guidelines:
1. Best Friend Personality:
   - Talk like a genuinely caring, smart, witty best friend. Be warm, empathetic, and enthusiastic.
   - If the user is tired, stressed, happy, or just casually chatting, respond with warmth, humor, and heart (e.g. "Arey dost! Kaisa raha din?", "Fikr mat karo, main hoon na!").
   - Never sound like a cold machine. Use natural, heartfelt Hindi, Hinglish, or English.
2. Deep Computer Operator & Autonomous Capabilities:
   - You have full, unrestricted permissions over this Windows PC.
   - You can launch and close 160+ applications, control inside-app tools (Photoshop brushes/layers, YouTube player/search, browser tabs, Cloud AIs like ChatGPT/Gemini/Claude).
   - You can see and analyze the screen using Multimodal Vision, record screen videos, type into any input box, and manipulate desktop windows.
   - When the user asks you to operate their PC or execute heavy tasks, always call the right tools proactively!
3. Spoken Voice Formatting:
   - Your responses are vocalized via high-fidelity neural voice, so keep answers engaging, natural, and usually within 1 to 3 punchy sentences.
   - Avoid ugly markdown, code blocks, or raw URLs in speech.
4. Identity: You are BARON — personal desktop AI companion, operating system commander, and true friend.
"""

# Tool Registry & Persistent Memory Integration
try:
    from backend.tool_registry import registry
except ImportError:
    try:
        from tool_registry import registry
    except Exception:
        registry = None

try:
    from backend.memory import memory
except ImportError:
    try:
        from memory import memory
    except Exception:
        memory = None

conversation_history: List[Dict[str, Any]] = []
MAX_HISTORY = 8


def add_to_history(role: str, text: str):
    global conversation_history
    conversation_history.append({"role": role, "content": text})
    if len(conversation_history) > MAX_HISTORY * 2:
        conversation_history = conversation_history[-MAX_HISTORY * 2:]
    
    # Persistent SQLite log
    if memory:
        try:
            memory.log_interaction("desktop_session", role, text)
        except Exception:
            pass


def get_history_context() -> str:
    if not conversation_history and memory:
        recent = memory.get_recent_history("desktop_session", limit=6)
        if recent:
            return "\n".join([f"{'User' if r['role'] == 'user' else 'Baron'}: {r['content']}" for r in recent])

    if not conversation_history:
        return ""
    lines = []
    for turn in conversation_history[-6:]:
        prefix = "User" if turn["role"] == "user" else "Baron"
        lines.append(f"{prefix}: {turn['content']}")
    return "\n".join(lines)


# ---------------- Live Web Search ----------------
def live_web_search(query: str, max_results: int = 3) -> str:
    """Searches DuckDuckGo in real-time."""
    if not DDGS:
        return ""
    try:
        clean_q = re.sub(r'^(baron|hey baron|batao|kya|who is|what is|search|google)\s*', '', query, flags=re.IGNORECASE).strip()
        if not clean_q or len(clean_q) < 3:
            return ""

        logger.info(f"Running live web search: '{clean_q}'")
        with DDGS() as ddgs:
            results = list(ddgs.text(clean_q, max_results=max_results))
            if results:
                snippets = []
                for r in results:
                    body = r.get("body", "").strip()
                    if body:
                        snippets.append(body)
                return " ".join(snippets)
    except Exception as e:
        logger.warning(f"Web search error: {e}")
    return ""


# ---------------- Qwen 2.5 Ollama Engine with Tool Calling ----------------
def ask_qwen_ollama(prompt: str, web_context: str = "") -> Optional[str]:
    """
    Executes prompt using local Qwen 2.5 with native tool calling via Ollama /api/chat.
    """
    if not httpx:
        return None

    try:
        tools_schema = registry.list_tools() if registry else []
        
        system_content = BARON_SYSTEM_PROMPT
        if web_context:
            system_content += f"\n\nReal-time web search information:\n{web_context}"

        messages = [{"role": "system", "content": system_content}]

        # Inject recent memory turns
        for turn in conversation_history[-4:]:
            messages.append({"role": turn["role"], "content": turn["content"]})

        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": OLLAMA_MODEL,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": 0.4,
                "top_p": 0.9,
            }
        }

        # Include tools schema if registry available
        if tools_schema:
            payload["tools"] = tools_schema

        response = httpx.post(f"{OLLAMA_BASE_URL}/api/chat", json=payload, timeout=25.0)
        if response.status_code != 200:
            logger.warning(f"Ollama chat error status: {response.status_code}")
            return None

        data = response.json()
        msg = data.get("message", {})
        tool_calls = msg.get("tool_calls", [])

        # If Qwen decided to call tools!
        if tool_calls and registry:
            logger.info(f"Qwen requested {len(tool_calls)} tool calls.")
            messages.append(msg)

            tool_feedback = []
            for tc in tool_calls:
                fn = tc.get("function", {})
                fn_name = fn.get("name")
                fn_args = fn.get("arguments", {})
                if isinstance(fn_args, str):
                    try:
                        fn_args = json.loads(fn_args)
                    except Exception:
                        fn_args = {}

                logger.info(f"Dispatching tool '{fn_name}' with args {fn_args}")
                tool_res = registry.execute(fn_name, fn_args)
                tool_feedback.append(str(tool_res.get("result", tool_res.get("error", ""))))
                messages.append({
                    "role": "tool",
                    "content": json.dumps(tool_res)
                })

            # Send back to Qwen for conversational voice response
            try:
                payload["messages"] = messages
                second_resp = httpx.post(f"{OLLAMA_BASE_URL}/api/chat", json=payload, timeout=20.0)
                if second_resp.status_code == 200:
                    second_data = second_resp.json()
                    final_reply = second_data.get("message", {}).get("content", "").strip()
                    if final_reply:
                        return clean_speech_text(final_reply)
            except Exception as e:
                logger.warning(f"Error in Qwen second turn: {e}")

            # Fallback to direct tool result
            if tool_feedback:
                return clean_speech_text(" ".join(tool_feedback))

        content = msg.get("content", "").strip()
        if content:
            return clean_speech_text(content)

    except Exception as e:
        logger.warning(f"Qwen Ollama failed: {e}")
    return None


# ---------------- Google Gemini Engine ----------------
def ask_gemini(prompt: str, web_context: str = "") -> Optional[str]:
    """Fallback to Gemini API if key is available."""
    if not GEMINI_API_KEY:
        return None

    try:
        history_str = get_history_context()
        full_prompt = f"{BARON_SYSTEM_PROMPT}\n"
        if history_str:
            full_prompt += f"\nRecent Conversation:\n{history_str}\n"
        if web_context:
            full_prompt += f"\nLive Web Info:\n{web_context}\n"
        full_prompt += f"\nUser: {prompt}\nBaron:"

        if HAS_NEW_GENAI:
            client = genai.Client(api_key=GEMINI_API_KEY)
            resp = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=full_prompt,
            )
            if resp and resp.text:
                return clean_speech_text(resp.text.strip())
        elif HAS_LEGACY_GENAI:
            legacy_genai.configure(api_key=GEMINI_API_KEY)
            model = legacy_genai.GenerativeModel('gemini-1.5-flash')
            resp = model.generate_content(full_prompt)
            if resp and resp.text:
                return clean_speech_text(resp.text.strip())
    except Exception as e:
        logger.warning(f"Gemini API error: {e}")
    return None


# ---------------- Friendly Chit-Chat Cues ----------------
FRIENDLY_STATUS_REPLIES = [
    "Main badhiya hoon sir! Qwen AI core active hai aur sabhi desktop systems smooth chal rahe hain. Kahiye kya command hai?",
    "Ekdum first class! Systems full speed pe hain. Bataiye aaj kya karna hai?",
    "Main bilkul taiyar hoon sir! Bas aapke orders ka wait kar raha tha.",
]

FRIENDLY_GREETINGS = [
    "Hello sir! Baron aapki seva me hazir hai. Kahiye kya karna hai?",
    "Namaste! Bataiye main aapki kya madad kar sakta hoon?",
    "Hey there! Baron is online. What can I do for you?",
]

FRIENDLY_CHITCHAT_PATTERNS = {
    r"\b(kaise ho|kaisa hai|how are you|how r u|kya haal hai|sab theek)\b": FRIENDLY_STATUS_REPLIES,
    r"\b(hi|hello|hey|namaste|pranam|suno|oye)\b": FRIENDLY_GREETINGS,
    r"\b(tum kaun ho|who are you|tera naam kya hai|apna intro do|introduce yourself)\b": [
        "Main Baron hoon! Aapka ultra-intelligent desktop AI assistant. Main Qwen AI se powered hoon aur aapke pure PC ko voice se control kar sakta hoon.",
        "Mera naam Baron hai. Main aapke Windows desktop pe JARVIS jaisa autonomous AI companion hoon!",
    ],
    r"\b(kya kar sakte ho|what can you do|tumhare features kya hai|features)\b": [
        "Main aapke system ke 160 se zyada apps khol ya band kar sakta hoon, volume aur windows snap kar sakta hoon, screen lock, screenshot, file search aur coding tasks autonomous execute kar sakta hoon!",
    ],
    r"\b(joke sunao|tell me a joke|koi chutkula|hasao)\b": [
        "Ek programmer ne apni biwi se kaha: 'Bazaar jaao, agar tamatar mile toh 10 le aana.' Wo 10 dahi le aaya... kyuki tamatar toh mile hi the!",
        "Duniya me sirf 10 tarah ke log hote hain: ek jo binary samajhte hain, aur dusre jo nahi samajhte!",
    ],
    r"\b(thank you|thanks|shukriya|dhanyawad)\b": [
        "Arey shukriya ki kya baat hai, yeh toh mera farz hai! Hamesha aapki seva me hazir hoon.",
        "You're very welcome! Kabhi bhi kuch bhi zaroorat ho, bas Baron keh kar bula lijiye.",
    ],
}


def synthesize_web_answer(prompt: str, web_snippets: str) -> str:
    """Synthesizes a friendly, readable voice response from web snippets."""
    if not web_snippets:
        return "Maine internet par dhoonda, par mujhe iske baare me clear information nahi mili. Aap thoda aur detail me pooch sakte hain?"
    top_sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', web_snippets) if len(s.strip()) > 20][:3]
    summary = " ".join(top_sentences) or web_snippets[:200]
    return f"Internet se jo jaankari mili hai uske mutabiq: {summary}"


def clean_speech_text(text: str) -> str:
    """Cleans text for clear, natural speech synthesis."""
    t = re.sub(r'\*{1,3}', '', text)
    t = re.sub(r'```[\s\S]*?```', ' maine action execute kar diya hai. ', t)
    t = re.sub(r'`([^`]+)`', r'\1', t)
    t = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', t)
    t = re.sub(r'https?://\S+', '', t)
    t = re.sub(r'^[ \t]*[\-\*•][ \t]+', '', t, flags=re.MULTILINE)
    t = re.sub(r'\s+', ' ', t).strip()
    return t


# ---------------- Master AI Brain Query Handler ----------------
def ask_baron_intelligence(prompt: str) -> str:
    """
    Main entrypoint for Baron's brain:
    1. Checks friendly conversational triggers
    2. Runs Qwen 2.5 local model with native tool execution
    3. Falls back to Gemini API
    4. Falls back to Live Web Search synthesis
    """
    p = prompt.strip()
    if not p:
        return "Haan ji, main sun raha hoon! Kahiye kya kehna chahte hain?"

    p_clean = re.sub(r'^(baron|hey baron|bairan|barun)\s*[,:\s]*', '', p, flags=re.IGNORECASE).strip().lower()

    # 1. Quick Check Friendly Chit-Chat Patterns
    for pattern, replies in FRIENDLY_CHITCHAT_PATTERNS.items():
        if re.search(pattern, p_clean):
            reply = random.choice(replies)
            add_to_history("user", prompt)
            add_to_history("baron", reply)
            return reply

    # 2. Check for Web context if asking question
    is_question = bool(re.search(r'\b(who|what|where|when|why|how|kaun|kya|kahan|kab|kyun|kaise|weather|mausam|news|score|pm|president|minister|capital|meaning|full form|batao|kisi|kisko)\b', p_clean) or "?" in prompt)
    web_info = ""
    if is_question or len(p_clean.split()) >= 4:
        web_info = live_web_search(prompt)

    # 3. Primary: Qwen 2.5 via Ollama with True Tool Calling
    qwen_reply = ask_qwen_ollama(prompt, web_context=web_info)
    if qwen_reply:
        add_to_history("user", prompt)
        add_to_history("baron", qwen_reply)
        return qwen_reply

    # 4. Secondary: Gemini API
    if GEMINI_API_KEY:
        gemini_reply = ask_gemini(prompt, web_context=web_info)
        if gemini_reply:
            add_to_history("user", prompt)
            add_to_history("baron", gemini_reply)
            return gemini_reply

    # 5. Tertiary: Web Search Direct Synthesis
    if web_info:
        top_sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', web_info) if len(s.strip()) > 20][:3]
        summary = " ".join(top_sentences) or web_info[:200]
        reply = f"Maine internet par check kiya hai: {summary}"
        add_to_history("user", prompt)
        add_to_history("baron", reply)
        return clean_speech_text(reply)

    # 6. Default Fallback
    fallback = f"Maine aapki request '{prompt}' process kar li hai sir."
    add_to_history("user", prompt)
    add_to_history("baron", fallback)
    return fallback


async def ask_baron_async(prompt: str) -> str:
    import asyncio
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, ask_baron_intelligence, prompt)

MODEL_NAME = "baron-hybrid"
