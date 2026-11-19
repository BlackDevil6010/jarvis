"""AI Provider interfaces and implementations for JARVIS.

Supports Google Gemini, OpenAI-compatible APIs (Groq, DeepSeek, OpenRouter),
local Ollama, and a built-in intelligent offline Local NLU engine.
"""

import os
import json
import logging
import re
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional, Tuple

import requests

logger = logging.getLogger(__name__)


class ToolCall:
    """Represents a structured action call requested by the AI."""

    def __init__(self, name: str, arguments: Dict[str, Any], call_id: Optional[str] = None):
        self.name = name
        self.arguments = arguments or {}
        self.call_id = call_id or f"call_{name}"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "arguments": self.arguments,
            "call_id": self.call_id,
        }

    def __repr__(self) -> str:
        return f"<ToolCall name='{self.name}' args={self.arguments}>"


class AIResponse:
    """Standardized response from an AI provider."""

    def __init__(
        self,
        text: str,
        tool_calls: Optional[List[ToolCall]] = None,
        is_conversational: bool = True,
        needs_clarification: bool = False,
        provider_name: str = "unknown",
        raw_response: Optional[Dict[str, Any]] = None
    ):
        self.text = text
        self.tool_calls = tool_calls or []
        self.is_conversational = is_conversational
        self.needs_clarification = needs_clarification
        self.provider_name = provider_name
        self.raw_response = raw_response or {}

    @property
    def has_tool_calls(self) -> bool:
        return len(self.tool_calls) > 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "text": self.text,
            "tool_calls": [tc.to_dict() for tc in self.tool_calls],
            "is_conversational": self.is_conversational,
            "needs_clarification": self.needs_clarification,
            "provider_name": self.provider_name,
        }


class BaseAIProvider(ABC):
    """Abstract base class for all JARVIS AI providers."""

    @abstractmethod
    def chat(
        self,
        messages: List[Dict[str, str]],
        tools: Optional[List[Dict[str, Any]]] = None,
        system_prompt: Optional[str] = None
    ) -> AIResponse:
        """Process messages and return an AIResponse, optionally selecting tools."""
        pass

    @abstractmethod
    def is_configured(self) -> bool:
        """Check if required API credentials or service endpoints are ready."""
        pass

    @abstractmethod
    def get_provider_name(self) -> str:
        """Human-readable provider identifier."""
        pass


class GeminiProvider(BaseAIProvider):
    """Google Gemini AI provider using official google-genai SDK with grounding & tool calling."""

    DEFAULT_MODEL = "gemini-2.5-flash"
    FALLBACK_MODEL = "gemini-1.5-flash"

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        timeout: float = 30.0,
        enable_grounding: Optional[bool] = None,
    ):
        if api_key is not None:
            raw_key = api_key
        else:
            raw_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY") or ""
            if not raw_key:
                try:
                    from jarvis.core.database import Database
                    raw_key = Database().get_setting("gemini_api_key") or ""
                except Exception:
                    pass
        self.api_key = raw_key.strip().strip("'").strip('"')
        self.model = model or os.environ.get("GEMINI_MODEL") or os.environ.get("LLM_MODEL") or self.DEFAULT_MODEL
        self.timeout = timeout
        if enable_grounding is not None:
            self.enable_grounding = enable_grounding
        else:
            self.enable_grounding = os.environ.get("GEMINI_SEARCH_GROUNDING", "true").lower() in ("true", "1", "yes")

        self.base_url = "https://generativelanguage.googleapis.com/v1beta/models"
        self._client = None
        if self.is_configured():
            try:
                from google import genai
                self._client = genai.Client(api_key=self.api_key)
            except Exception as e:
                logger.warning(f"Could not initialize google-genai Client: {e}")

    def is_configured(self) -> bool:
        return bool(self.api_key and self.api_key.strip())

    def get_provider_name(self) -> str:
        return f"Google Gemini ({self.model})"

    def _convert_tools_to_gemini(self, tools: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Translate OpenAI-style tool definitions to Gemini functionDeclarations."""
        function_declarations = []
        for t in tools:
            func = t.get("function", t)
            fn_decl = {
                "name": func.get("name"),
                "description": func.get("description", ""),
                "parameters": func.get("parameters", {"type": "object", "properties": {}})
            }
            function_declarations.append(fn_decl)
        return function_declarations

    def chat(
        self,
        messages: List[Dict[str, str]],
        tools: Optional[List[Dict[str, Any]]] = None,
        system_prompt: Optional[str] = None
    ) -> AIResponse:
        if not self.is_configured():
            return AIResponse(
                text="Google Gemini API key not configured. Set GEMINI_API_KEY in your .env file or type 'set key gemini <KEY>' in the console.",
                provider_name=self.get_provider_name()
            )

        # 1. Primary path: Official google-genai SDK
        if self._client is not None:
            try:
                from google.genai import types

                contents = []
                for msg in messages:
                    role = "model" if msg.get("role") == "assistant" else "user"
                    contents.append(types.Content(
                        role=role,
                        parts=[types.Part.from_text(text=msg.get("content", ""))]
                    ))

                genai_tools = []
                if tools:
                    decls = self._convert_tools_to_gemini(tools)
                    if decls:
                        genai_tools.append(types.Tool(function_declarations=decls))
                elif self.enable_grounding:
                    # Google Search grounding for open-ended knowledge queries (mutually exclusive with Function Calling in Gemini API)
                    genai_tools.append(types.Tool(google_search=types.GoogleSearch()))

                config_kwargs: Dict[str, Any] = {
                    "http_options": types.HttpOptions(timeout=int(self.timeout * 1000))
                }
                if system_prompt:
                    config_kwargs["system_instruction"] = system_prompt
                if genai_tools:
                    config_kwargs["tools"] = genai_tools

                config = types.GenerateContentConfig(**config_kwargs)

                try:
                    resp = self._client.models.generate_content(
                        model=self.model,
                        contents=contents,
                        config=config
                    )
                except Exception as model_err:
                    err_str = str(model_err)
                    if ("404" in err_str or "NOT_FOUND" in err_str or "unsupported" in err_str.lower()) and self.model != self.FALLBACK_MODEL:
                        logger.warning(f"Model {self.model} error, retrying with fallback {self.FALLBACK_MODEL}: {err_str}")
                        resp = self._client.models.generate_content(
                            model=self.FALLBACK_MODEL,
                            contents=contents,
                            config=config
                        )
                    else:
                        raise model_err

                tool_calls: List[ToolCall] = []
                response_text = ""

                if getattr(resp, "text", None):
                    response_text = resp.text or ""

                if getattr(resp, "function_calls", None):
                    for fc in resp.function_calls:
                        fn_name = getattr(fc, "name", "")
                        raw_args = getattr(fc, "args", {})
                        fn_args = dict(raw_args) if raw_args else {}
                        tool_calls.append(ToolCall(name=fn_name, arguments=fn_args))

                # Grounding citations extraction
                citations = []
                if getattr(resp, "candidates", None) and len(resp.candidates) > 0:
                    cand = resp.candidates[0]
                    gm = getattr(cand, "grounding_metadata", None)
                    if gm:
                        chunks = getattr(gm, "grounding_chunks", None) or []
                        for chunk in chunks:
                            web = getattr(chunk, "web", None)
                            if web:
                                title = getattr(web, "title", None) or getattr(web, "uri", "Source")
                                uri = getattr(web, "uri", "")
                                if uri:
                                    citations.append(f"[{title}]({uri})")

                if citations and not tool_calls:
                    unique_citations = list(dict.fromkeys(citations))[:5]
                    response_text += "\n\n*Grounding Sources:*\n- " + "\n- ".join(unique_citations)

                return AIResponse(
                    text=response_text.strip(),
                    tool_calls=tool_calls,
                    is_conversational=len(tool_calls) == 0,
                    provider_name=self.get_provider_name(),
                    raw_response={"sdk": "google-genai", "model": self.model}
                )

            except Exception as sdk_err:
                logger.warning(f"google-genai SDK failed: {sdk_err}, falling back to REST API")

        # 2. Resilient fallback path: Direct REST API
        url = f"{self.base_url}/{self.model}:generateContent?key={self.api_key}"
        contents = []
        for msg in messages:
            role = "model" if msg.get("role") == "assistant" else "user"
            contents.append({
                "role": role,
                "parts": [{"text": msg.get("content", "")}]
            })

        payload: Dict[str, Any] = {"contents": contents}

        if system_prompt:
            payload["systemInstruction"] = {
                "parts": [{"text": system_prompt}]
            }

        if tools:
            decls = self._convert_tools_to_gemini(tools)
            if decls:
                payload["tools"] = [{"functionDeclarations": decls}]

        try:
            resp = requests.post(url, json=payload, timeout=self.timeout)
            if resp.status_code != 200:
                err_detail = resp.json().get("error", {}).get("message", resp.text)
                return AIResponse(
                    text=f"Gemini API returned error ({resp.status_code}): {err_detail}",
                    provider_name=self.get_provider_name()
                )

            data = resp.json()
            candidates = data.get("candidates", [])
            if not candidates:
                return AIResponse(
                    text="No response candidates returned by Gemini model.",
                    provider_name=self.get_provider_name()
                )

            content = candidates[0].get("content", {})
            parts = content.get("parts", [])

            response_text = ""
            tool_calls = []

            for part in parts:
                if "text" in part:
                    response_text += part["text"]
                if "functionCall" in part:
                    fn_call = part["functionCall"]
                    fn_name = fn_call.get("name", "")
                    fn_args = fn_call.get("args", {})
                    tool_calls.append(ToolCall(name=fn_name, arguments=fn_args))

            return AIResponse(
                text=response_text.strip(),
                tool_calls=tool_calls,
                is_conversational=len(tool_calls) == 0,
                provider_name=self.get_provider_name(),
                raw_response=data
            )
        except requests.exceptions.RequestException as req_err:
            return AIResponse(
                text=f"Network error communicating with Gemini API: {req_err}",
                provider_name=self.get_provider_name()
            )


class OpenAICompatibleProvider(BaseAIProvider):
    """OpenAI, Groq, OpenRouter, DeepSeek, or local compatible API provider."""

    DEFAULT_BASE_URL = "https://api.openai.com/v1"
    DEFAULT_MODEL = "gpt-4o-mini"

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None
    ):
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY") or ""
        self.base_url = (base_url or os.environ.get("OPENAI_BASE_URL") or self.DEFAULT_BASE_URL).rstrip("/")
        self.model = model or os.environ.get("LLM_MODEL") or self.DEFAULT_MODEL

    def is_configured(self) -> bool:
        return bool(self.api_key and self.api_key.strip())

    def get_provider_name(self) -> str:
        domain = "OpenAI"
        if "groq" in self.base_url:
            domain = "Groq"
        elif "openrouter" in self.base_url:
            domain = "OpenRouter"
        elif "deepseek" in self.base_url:
            domain = "DeepSeek"
        return f"{domain} ({self.model})"

    def chat(
        self,
        messages: List[Dict[str, str]],
        tools: Optional[List[Dict[str, Any]]] = None,
        system_prompt: Optional[str] = None
    ) -> AIResponse:
        if not self.is_configured():
            return AIResponse(
                text=f"{self.get_provider_name()} API key not configured. Set OPENAI_API_KEY environment variable.",
                provider_name=self.get_provider_name()
            )

        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        formatted_messages = []
        if system_prompt:
            formatted_messages.append({"role": "system", "content": system_prompt})
        formatted_messages.extend(messages)

        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": formatted_messages,
        }

        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=25)
            if resp.status_code != 200:
                err_detail = resp.json().get("error", {}).get("message", resp.text)
                return AIResponse(
                    text=f"API error ({resp.status_code}): {err_detail}",
                    provider_name=self.get_provider_name()
                )

            data = resp.json()
            choices = data.get("choices", [])
            if not choices:
                return AIResponse(text="No choices returned from model.", provider_name=self.get_provider_name())

            message = choices[0].get("message", {})
            response_text = message.get("content") or ""
            raw_tool_calls = message.get("tool_calls") or []

            tool_calls = []
            for tc in raw_tool_calls:
                func = tc.get("function", {})
                fn_name = func.get("name", "")
                try:
                    fn_args = json.loads(func.get("arguments", "{}"))
                except json.JSONDecodeError:
                    fn_args = {}
                tool_calls.append(ToolCall(name=fn_name, arguments=fn_args, call_id=tc.get("id")))

            return AIResponse(
                text=response_text.strip(),
                tool_calls=tool_calls,
                is_conversational=len(tool_calls) == 0,
                provider_name=self.get_provider_name(),
                raw_response=data
            )
        except requests.exceptions.RequestException as req_err:
            return AIResponse(
                text=f"Network error communicating with {self.get_provider_name()}: {req_err}",
                provider_name=self.get_provider_name()
            )


class OllamaProvider(BaseAIProvider):
    """Local offline Ollama LLM provider (running on localhost:11434)."""

    def __init__(self, host: Optional[str] = None, model: Optional[str] = None):
        self.host = (host or os.environ.get("OLLAMA_HOST") or "http://localhost:11434").rstrip("/")
        self.model = model or os.environ.get("LLM_MODEL") or "llama3"

    def is_configured(self) -> bool:
        try:
            resp = requests.get(f"{self.host}/api/tags", timeout=1.0)
            return resp.status_code == 200
        except Exception:
            return False

    def get_provider_name(self) -> str:
        return f"Ollama Local ({self.model})"

    def chat(
        self,
        messages: List[Dict[str, str]],
        tools: Optional[List[Dict[str, Any]]] = None,
        system_prompt: Optional[str] = None
    ) -> AIResponse:
        url = f"{self.host}/api/chat"
        formatted_messages = []
        if system_prompt:
            formatted_messages.append({"role": "system", "content": system_prompt})
        formatted_messages.extend(messages)

        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": formatted_messages,
            "stream": False,
        }

        if tools:
            payload["tools"] = tools

        try:
            resp = requests.post(url, json=payload, timeout=30)
            if resp.status_code != 200:
                return AIResponse(
                    text=f"Ollama error ({resp.status_code}): {resp.text}",
                    provider_name=self.get_provider_name()
                )
            data = resp.json()
            message = data.get("message", {})
            response_text = message.get("content", "")
            raw_tools = message.get("tool_calls", [])

            tool_calls = []
            for tc in raw_tools:
                fn = tc.get("function", {})
                tool_calls.append(ToolCall(name=fn.get("name", ""), arguments=fn.get("arguments", {})))

            return AIResponse(
                text=response_text.strip(),
                tool_calls=tool_calls,
                is_conversational=len(tool_calls) == 0,
                provider_name=self.get_provider_name(),
                raw_response=data
            )
        except requests.exceptions.RequestException as req_err:
            return AIResponse(
                text=f"Unable to connect to local Ollama service at {self.host}. Is Ollama running?",
                provider_name=self.get_provider_name()
            )


class LocalNLUProvider(BaseAIProvider):
    """
    Intelligent built-in Offline NLU engine.
    Always available without internet connection or external API keys.
    Understands conversational intent, programming queries, and maps natural-language
    desktop automation requests to approved structured tools.
    """

    def is_configured(self) -> bool:
        return True

    def get_provider_name(self) -> str:
        return "OMEN Core Local NLU"

    def chat(
        self,
        messages: List[Dict[str, str]],
        tools: Optional[List[Dict[str, Any]]] = None,
        system_prompt: Optional[str] = None
    ) -> AIResponse:
        last_message = messages[-1]["content"] if messages else ""
        query = last_message.strip()
        query_lower = query.lower()

        # 1. Multi-Step Request Handling (e.g., "Open VS Code and launch Spotify", "Check system info and open downloads")
        multi_actions = self._detect_multi_step_intents(query)
        if multi_actions:
            return AIResponse(
                text=f"Identified {len(multi_actions)} sequential actions. Executing authorized directives...",
                tool_calls=multi_actions,
                is_conversational=False,
                provider_name=self.get_provider_name()
            )

        # 2. Check for Application Launching Intent
        app_launch_call = self._detect_application_launch_intent(query)
        if app_launch_call:
            return AIResponse(
                text=f"Preparing to launch {app_launch_call.arguments.get('app_name')}...",
                tool_calls=[app_launch_call],
                is_conversational=False,
                provider_name=self.get_provider_name()
            )

        # 3. Check for Music Playback & Track Intent (e.g. "play element", "in spotify play john michael howell", "play lofi beats")
        music_play_match = re.search(
            r"(?:in\s+(?:spotify|youtube)\s+)?(?:could\s+you\s+please\s+|please\s+)?play\s+(?:the\s+song\s+|the\s+track\s+|the\s+artist\s+|the\s+music\s+|the\s+)?(.+?)(?:\s+(?:in|on)\s+(spotify|youtube))?$",
            query_lower
        )
        if music_play_match and not any(w in query_lower for w in ["game", "video", "role", "animation"]):
            target_track = music_play_match.group(1).strip()
            specified_platform = music_play_match.group(2) or ("youtube" if "youtube" in query_lower else "spotify")
            # Filter out empty or filler targets
            target_track = re.sub(r"^(?:in|on)\s+(?:spotify|youtube)\s*", "", target_track).strip()
            if target_track and target_track not in ["music", "songs", "the"]:
                return AIResponse(
                    text=f"Searching and playing '{target_track}' on {specified_platform.capitalize()}...",
                    tool_calls=[ToolCall("play_music", {"query": target_track, "platform": specified_platform})],
                    is_conversational=False,
                    provider_name=self.get_provider_name()
                )

        # 4. Check for Media Playback Controls (pause, resume, next, skip, volume)
        media_ctrl_patterns = [
            (r"\b(pause|stop)\s+(?:the\s+)?(?:music|song|playback|spotify|audio)\b", "pause"),
            (r"\b(resume|continue)\s+(?:the\s+)?(?:music|song|playback|spotify|audio)\b", "resume"),
            (r"\b(next\s+track|next\s+song|skip\s+song|skip\s+track|skip)\b", "next"),
            (r"\b(previous\s+track|previous\s+song|prev\s+song|go\s+back)\b", "previous"),
            (r"\b(?:turn\s+up\s+volume|volume\s+up|louder|increase\s+volume)\b", "volume_up"),
            (r"\b(?:turn\s+down\s+volume|volume\s+down|quieter|decrease\s+volume|lower\s+volume)\b", "volume_down"),
            (r"\b(mute\s+audio|mute\s+volume|unmute\s+volume|mute)\b", "mute"),
        ]
        for pattern, action_name in media_ctrl_patterns:
            if re.search(pattern, query_lower):
                return AIResponse(
                    text=f"Executing media playback directive: {action_name.replace('_', ' ')}...",
                    tool_calls=[ToolCall("control_media", {"action": action_name})],
                    is_conversational=False,
                    provider_name=self.get_provider_name()
                )

        # 5. Check for Weather Intent
        if "weather" in query_lower:
            return AIResponse(
                text="Checking live local weather forecast...",
                tool_calls=[ToolCall("search_web", {"query": "current weather forecast today"})],
                is_conversational=False,
                provider_name=self.get_provider_name()
            )

        # 6. Check for Screen Analysis / Vision Intent
        if any(w in query_lower for w in ["look at my screen", "inspect my screen", "check my screen", "what's on my screen", "what is on my screen", "analyze my screen", "explain this error on screen", "screen analysis"]):
            return AIResponse(
                text="Capturing display and analyzing visible window context with Gemini Vision...",
                tool_calls=[ToolCall("analyze_screen", {"prompt": query})],
                is_conversational=False,
                provider_name=self.get_provider_name()
            )

        # 7. Check for Lock Workstation / Desktop Automation
        if any(w in query_lower for w in ["lock pc", "lock my pc", "lock computer", "lock workstation", "lock windows"]):
            return AIResponse(
                text="Locking workstation securely...",
                tool_calls=[ToolCall("windows_automation", {"action": "lock"})],
                is_conversational=False,
                provider_name=self.get_provider_name()
            )
        if any(w in query_lower for w in ["minimize all", "minimize windows", "show desktop", "hide all windows"]):
            return AIResponse(
                text="Minimizing open windows to display desktop...",
                tool_calls=[ToolCall("windows_automation", {"action": "minimize_all"})],
                is_conversational=False,
                provider_name=self.get_provider_name()
            )

        # 8. Check for Timers and Reminders
        timer_match = re.search(r"(?:set\s+a?\s*timer|remind\s+me)\s+(?:for|in)\s+(\d+(?:\.\d+)?)\s*(?:minute|minutes|min|mins|m)\b(?:\s+(?:to|for)\s+(.+))?", query_lower)
        if timer_match:
            mins = float(timer_match.group(1))
            label = timer_match.group(2) or "Timer"
            return AIResponse(
                text=f"Setting a countdown timer for {mins} minute(s) ({label})...",
                tool_calls=[ToolCall("set_timer", {"minutes": mins, "label": label.strip()})],
                is_conversational=False,
                provider_name=self.get_provider_name()
            )
        if any(w in query_lower for w in ["list timers", "show timers", "my timers", "active timers", "check timers"]):
            return AIResponse(
                text="Checking active countdown timers and pending reminders...",
                tool_calls=[ToolCall("list_timers", {})],
                is_conversational=False,
                provider_name=self.get_provider_name()
            )

        # 9. Check for File Search Intent
        file_search_match = re.search(r"(?:find|search\s+for|locate)\s+(?:file|document)?\s*['\"]?([a-zA-Z0-9_\-\.\*]+)['\"]?(?:\s+in\s+(downloads|documents|desktop))?", query_lower)
        if file_search_match and not any(w in query_lower for w in ["web", "online", "google"]):
            target_pattern = file_search_match.group(1).strip()
            folder_scope = file_search_match.group(2)
            if target_pattern and len(target_pattern) > 1:
                return AIResponse(
                    text=f"Searching for file '{target_pattern}' in your user directories...",
                    tool_calls=[ToolCall("find_files", {"pattern": target_pattern, "folder": folder_scope})],
                    is_conversational=False,
                    provider_name=self.get_provider_name()
                )

        # 10. Check for Phone Remote Access / Mobile Companion Intent
        if any(w in query_lower for w in ["access through phone", "access from phone", "phone access", "mobile companion", "connect phone", "connect mobile", "phone server", "mobile link", "phone link", "qr code for phone", "mobile qr"]):
            return AIResponse(
                text="Initializing O.M.E.N. Mobile Companion Gateway...",
                tool_calls=[ToolCall("phone_companion", {"action": "start"})],
                is_conversational=False,
                provider_name=self.get_provider_name()
            )

        # 11. Check for Calling Contacts / Speed Dial (e.g. "call the boss", "call boss", "call mom", "dial 555-0199")
        call_match = re.search(r"\b(?:call|dial|phone|ring)\s+(?:the\s+)?([a-zA-Z0-9_\-\+]+(?:\s+[a-zA-Z0-9_\-\+]+)?)(?:\s+(?:on|via)\s+(whatsapp|teams|skype|phone))?\b", query_lower)
        if call_match and not any(w in query_lower for w in ["api", "function", "tool", "method"]):
            contact_target = call_match.group(1).strip()
            channel = call_match.group(2) or ("whatsapp" if "whatsapp" in query_lower else "phone")
            return AIResponse(
                text=f"Initiating comm-link to {contact_target.title()}...",
                tool_calls=[ToolCall("call_contact", {"contact_name": contact_target, "channel": channel})],
                is_conversational=False,
                provider_name=self.get_provider_name()
            )

        # 12. Check for Email Checking / Inbox Intent
        if any(w in query_lower for w in ["check emails", "check the emails", "check email", "check my email", "check my emails", "read emails", "read my email", "show emails", "my emails", "unread emails", "inbox summary", "summarize emails", "summarize my emails", "check inbox"]):
            sender_search = None
            sender_match = re.search(r"emails?\s+from\s+([a-zA-Z0-9_]+)", query_lower)
            if sender_match:
                sender_search = sender_match.group(1).strip()
            return AIResponse(
                text="Scanning email inbox intelligence...",
                tool_calls=[ToolCall("check_emails", {"unread_only": True, "sender": sender_search})],
                is_conversational=False,
                provider_name=self.get_provider_name()
            )

        # 13. Check for Sending Email
        send_email_match = re.search(r"(?:send|draft|compose)\s+(?:an?\s+)?email\s+(?:to\s+([a-zA-Z0-9_@\.]+))?", query_lower)
        if send_email_match:
            recip = send_email_match.group(1) or "boss"
            return AIResponse(
                text=f"Preparing email draft for {recip}...",
                tool_calls=[ToolCall("send_email", {"recipient": recip, "subject": "Update from O.M.E.N.", "body": "Please review this directive."})],
                is_conversational=False,
                provider_name=self.get_provider_name()
            )

        # 14. Check for Messaging Contact (WhatsApp / SMS)
        msg_match = re.search(r"(?:send\s+a\s+)?(?:message|text|whatsapp)\s+([a-zA-Z0-9_]+)\s+(?:that\s+|to\s+say\s+)?(.+)", query_lower)
        if msg_match and not any(w in query_lower for w in ["system", "audio", "mic"]):
            target_person = msg_match.group(1).strip()
            text_body = msg_match.group(2).strip()
            return AIResponse(
                text=f"Dispatching message to {target_person}...",
                tool_calls=[ToolCall("message_contact", {"contact_name": target_person, "message": text_body, "channel": "whatsapp"})],
                is_conversational=False,
                provider_name=self.get_provider_name()
            )

        # 15. Check for Executive Daily Briefing
        if any(w in query_lower for w in ["daily briefing", "morning briefing", "executive briefing", "give me a briefing", "brief me", "morning report", "status briefing"]):
            return AIResponse(
                text="Compiling O.M.E.N. executive morning intelligence briefing...",
                tool_calls=[ToolCall("daily_briefing", {})],
                is_conversational=False,
                provider_name=self.get_provider_name()
            )

        # 16. Check for Notes / Memo Scratchpad
        note_take_match = re.search(r"(?:take\s+a?\s*note|new\s+note|record\s+memo|note\s+down)\s*[:\-]?\s*(.+)", query_lower)
        if note_take_match:
            note_content = note_take_match.group(1).strip()
            return AIResponse(
                text="Recording memo in system scratchpad...",
                tool_calls=[ToolCall("manage_notes", {"action": "create", "content": note_content})],
                is_conversational=False,
                provider_name=self.get_provider_name()
            )
        if any(w in query_lower for w in ["show notes", "show my notes", "list notes", "my notes", "scratchpad notes"]):
            return AIResponse(
                text="Retrieving recorded scratchpad notes...",
                tool_calls=[ToolCall("manage_notes", {"action": "list"})],
                is_conversational=False,
                provider_name=self.get_provider_name()
            )

        # 4. Check for Time & Date Intent
        if any(w in query_lower for w in ["what time", "current time", "what is the time", "time now"]):
            from datetime import datetime
            now_str = datetime.now().strftime("%I:%M %p")
            return AIResponse(
                text=f"The current local time is **{now_str}**, Sir.",
                is_conversational=True,
                provider_name=self.get_provider_name()
            )
        if any(w in query_lower for w in ["what date", "today's date", "what is the date", "what day is it"]):
            from datetime import datetime
            today_str = datetime.now().strftime("%A, %B %d, %Y")
            return AIResponse(
                text=f"Today is **{today_str}**, Sir.",
                is_conversational=True,
                provider_name=self.get_provider_name()
            )

        # 5. Check for System Diagnostics / Health Intent
        if any(w in query_lower for w in ["system health", "check health", "system diagnostics", "pc health", "hardware status", "computer performance", "cpu usage", "ram usage"]):
            return AIResponse(
                text="Gathering live hardware telemetry and host diagnostics...",
                tool_calls=[ToolCall("system_diagnostics", {})],
                is_conversational=False,
                provider_name=self.get_provider_name()
            )

        # 6. Check for Web Search Intent
        web_search_match = re.search(r"(?:search\s+(?:the\s+web|online|google)?\s*(?:for)?|look\s+up|google)\s+(.+)", query_lower)
        if web_search_match and not any(w in query_lower for w in ["open", "launch", "skill"]):
            search_query = web_search_match.group(1).strip()
            return AIResponse(
                text=f"Initiating web search for '{search_query}'...",
                tool_calls=[ToolCall("search_web", {"query": search_query})],
                is_conversational=False,
                provider_name=self.get_provider_name()
            )

        # 5. Check for Folder Opening Intent
        folder_match = re.search(r"(?:open|show|browse)\s+(?:my\s+)?(downloads|documents|desktop|pictures|music|videos|project|folder)\b", query_lower)
        if folder_match:
            folder_target = folder_match.group(1).strip()
            return AIResponse(
                text=f"Opening your {folder_target.capitalize()} directory...",
                tool_calls=[ToolCall("open_folder", {"folder_path": folder_target})],
                is_conversational=False,
                provider_name=self.get_provider_name()
            )

        # 6. Check for Skill Forge Workflow Intent
        if "workflow" in query_lower or "skill" in query_lower:
            # Check for run skill
            run_match = re.search(r"(?:run|execute|start)\s+(?:the\s+)?(?:skill|workflow)\s+['\"]?([^'\"]+)['\"]?", query_lower)
            if run_match:
                skill_name = run_match.group(1).strip()
                return AIResponse(
                    text=f"Triggering Skill Forge workflow: {skill_name}...",
                    tool_calls=[ToolCall("run_skill", {"skill_name": skill_name})],
                    is_conversational=False,
                    provider_name=self.get_provider_name()
                )
            # Check for list skills
            if any(w in query_lower for w in ["list", "show", "what", "available"]):
                return AIResponse(
                    text="Retrieving all registered Skill Forge automation workflows...",
                    tool_calls=[ToolCall("list_skills", {})],
                    is_conversational=False,
                    provider_name=self.get_provider_name()
                )

        # 7. Check for Listing Applications
        if any(w in query_lower for w in ["list applications", "show apps", "what apps", "installed applications", "list apps"]):
            return AIResponse(
                text="Scanning and listing all available applications...",
                tool_calls=[ToolCall("list_applications", {})],
                is_conversational=False,
                provider_name=self.get_provider_name()
            )

        # 8. Greetings & Assistant Identity
        identity_reply = self._handle_greetings_and_identity(query)
        if identity_reply:
            return AIResponse(
                text=identity_reply,
                is_conversational=True,
                provider_name=self.get_provider_name()
            )

        # 9. Programming Assistance & Error Explanations
        code_explanation = self._handle_programming_query(query)
        if code_explanation:
            return AIResponse(
                text=code_explanation,
                is_conversational=True,
                provider_name=self.get_provider_name()
            )

        # 10. Informational Question Resolution (Automatic Live Web Search)
        if any(query_lower.startswith(w) for w in ["what", "who", "when", "where", "why", "how", "tell me", "search for", "find me"]):
            return AIResponse(
                text=f"Searching web resources for: '{query}'...",
                tool_calls=[ToolCall("search_web", {"query": query})],
                is_conversational=False,
                provider_name=self.get_provider_name()
            )

        # 11. General Conversation & Knowledge Fallback
        conversational_reply = self._handle_general_conversation(query)
        return AIResponse(
            text=conversational_reply,
            is_conversational=True,
            provider_name=self.get_provider_name()
        )

    def _detect_application_launch_intent(self, query: str) -> Optional[ToolCall]:
        """Detect variations of opening, launching, or switching to applications."""
        q = query.lower().strip()

        # Phrases like: "can you open my code editor?", "i need to listen to music", "start discord", "launch spotify"
        patterns = [
            r"^(?:can\s+you\s+|please\s+|would\s+you\s+)?(?:open|launch|start|run|bring\s+up|switch\s+to)\s+(?:my\s+|the\s+)?(.+)$",
            r"^i\s+(?:want|need)\s+to\s+(?:listen\s+to\s+music|code|edit\s+code|play\s+games|browse\s+the\s+web)$",
            r"^let'?s\s+(?:code|listen\s+to\s+music|play\s+games)$",
        ]

        # Specific alias intent checks
        if "listen to music" in q or "play music" in q or "play songs" in q:
            return ToolCall("launch_application", {"app_name": "spotify"})
        if "edit code" in q or "code editor" in q or "write code" in q or "start coding" in q:
            return ToolCall("launch_application", {"app_name": "code editor"})
        if "browse the web" in q or "open the internet" in q or "open browser" in q:
            return ToolCall("launch_application", {"app_name": "browser"})

        # Avoid capturing "play <song/artist>" as an application launch
        if q.startswith("play ") or "play track" in q or "play song" in q:
            return None

        for pattern in patterns:
            match = re.match(pattern, q, re.IGNORECASE)
            if match and match.groups():
                target = match.group(1).strip()
                # Clean trailing filler words (e.g. "for me", "please")
                target = re.sub(r"\s+(?:for\s+me|please|right\s+now|now)\.?$", "", target).strip()
                if target:
                    return ToolCall("launch_application", {"app_name": target})

        return None

    def _detect_multi_step_intents(self, query: str) -> List[ToolCall]:
        """Detect sequential multi-step commands combined with 'and' or 'then'."""
        q = query.strip()
        # Look for conjunctions like "and", "then", "also"
        split_pattern = r"\s+(?:and(?:\s+also)?|then|also)\s+"
        parts = re.split(split_pattern, q, flags=re.IGNORECASE)
        if len(parts) <= 1:
            return []

        tools: List[ToolCall] = []
        for part in parts:
            part_clean = part.strip()
            if not part_clean:
                continue
            # Try app launch
            app_tc = self._detect_application_launch_intent(part_clean)
            if app_tc:
                tools.append(app_tc)
                continue
            # Try system diagnostics
            if any(w in part_clean.lower() for w in ["system health", "diagnostics", "check system", "performance"]):
                tools.append(ToolCall("system_diagnostics", {}))
                continue
            # Try folder
            folder_match = re.search(r"(?:open|show)\s+(?:my\s+)?(downloads|documents|desktop|folder)\b", part_clean.lower())
            if folder_match:
                tools.append(ToolCall("open_folder", {"folder_path": folder_match.group(1).strip()}))
                continue
            # Try web search
            if "search" in part_clean.lower() or "google" in part_clean.lower():
                s_query = re.sub(r"^(?:search\s+(?:for)?|google)\s+", "", part_clean.lower()).strip()
                tools.append(ToolCall("search_web", {"query": s_query}))

        return tools if len(tools) > 1 else []

    def _handle_programming_query(self, query: str) -> Optional[str]:
        """Recognize and explain common programming errors, concepts, and languages."""
        q = query.lower()

        # Error patterns
        if "typeerror" in q:
            return (
                "**Python TypeError Explanation:**\n\n"
                "A `TypeError` occurs when an operation or function is applied to an object of an inappropriate type.\n\n"
                "**Common Causes & Fixes:**\n"
                "1. **Mismatched types in arithmetic**: `\"hello\" + 5` fails. Fix by converting: `\"hello\" + str(5)`.\n"
                "2. **Calling a non-callable object**: e.g. `x = 5; x()`. Ensure variable names don't shadow functions.\n"
                "3. **Missing required positional arguments**: Verify function signature against the arguments you passed."
            )
        if "valueerror" in q:
            return (
                "**Python ValueError Explanation:**\n\n"
                "A `ValueError` occurs when a function receives an argument of the correct type but an invalid value.\n\n"
                "**Example:** `int(\"abc\")` fails because while `\"abc\"` is a string, it cannot be parsed as a base-10 integer.\n"
                "**Fix:** Add validation or wrap with `try-except ValueError:` before converting user inputs."
            )
        if "indexerror" in q:
            return (
                "**Python IndexError Explanation:**\n\n"
                "An `IndexError: list index out of range` occurs when accessing a sequence (list, tuple, string) with an index that exceeds its length.\n\n"
                "**Fix:** Check sequence length with `len(items)` or use safe slicing/getters: `items[0] if items else default`."
            )
        if "keyerror" in q:
            return (
                "**Python KeyError Explanation:**\n\n"
                "A `KeyError` occurs when trying to access a dictionary key that does not exist.\n\n"
                "**Fix:** Use `.get(key, default)` instead of direct brackets `dict[key]`, or verify existence using `if key in dict:`."
            )

        # Concept questions
        if "recursion" in q:
            return (
                "**Understanding Recursion:**\n\n"
                "Recursion is a programming technique where a function calls itself to solve smaller instances of the same problem.\n\n"
                "**Two essential components of every recursive algorithm:**\n"
                "1. **Base Case**: The termination condition where the function stops calling itself and returns a value.\n"
                "2. **Recursive Step**: Calling the function with an argument closer to the base case."
            )
        if "quicksort" in q or "quick sort" in q:
            return (
                "**Quicksort Algorithm Overview:**\n\n"
                "Quicksort is an efficient, divide-and-conquer sorting algorithm with an average time complexity of O(n log n).\n\n"
                "**How it works:**\n"
                "1. Select a **pivot** element from the array.\n"
                "2. **Partition** the remaining elements into two sub-arrays: elements smaller than pivot, and elements greater than pivot.\n"
                "3. Recursively apply the same logic to the sub-arrays."
            )

        return None

    def _handle_greetings_and_identity(self, query: str) -> Optional[str]:
        """Recognize greetings, identity, and status queries directly."""
        q = query.lower().strip()
        if q in ["hello", "hi", "hey", "greetings", "good morning", "good evening", "good afternoon", "hello omen", "hi omen", "hey omen", "hello jarvis", "hi jarvis", "hey jarvis"]:
            return (
                "Greetings, Sir. O.M.E.N. systems are fully operational and standing by.\n"
                "I can launch applications, execute Skill Forge workflows, monitor system telemetry, or assist with your desktop tasks."
            )
        if "who are you" in q or "what are you" in q or "your name" in q:
            return (
                "I am **O.M.E.N.**, your Windows AI tactical desktop assistant.\n"
                "I am designed to understand natural-language directives, automate desktop workflows, and execute computer tasks securely."
            )
        if "how are you" in q:
            return "All diagnostic subsystems report nominal performance. CPU, memory, and task execution pipelines are ready for your directives."
        if "thank you" in q or "thanks" in q:
            return "At your service, Sir. Let me know whenever you need further assistance."
        return None

    def _handle_general_conversation(self, query: str) -> str:
        """Provide polite, helpful conversational responses and configuration guidance."""
        identity = self._handle_greetings_and_identity(query)
        if identity:
            return identity

        # General question with clean context
        configured_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        if configured_key:
            return (
                f"Understood: **\"{query}\"**.\n\n"
                "*(Note: Your cloud AI provider encountered an authentication error. "
                "Operating in Local Intelligence Mode with access to all desktop automation tools, application discovery, and system diagnostics.)*"
            )
        return (
            f"Understood: **\"{query}\"**.\n\n"
            "Operating in **Local Intelligence Mode** with full desktop automation, application launcher, and system telemetry capabilities."
        )


class AIProviderFactory:
    """Factory to instantiate the appropriate AI provider based on environment and settings."""

    @staticmethod
    def get_provider(
        preferred_provider: Optional[str] = None,
        api_key: Optional[str] = None,
        model: Optional[str] = None
    ) -> BaseAIProvider:
        # Check environment or argument
        prov_type = (preferred_provider or os.environ.get("DEFAULT_AI_PROVIDER") or os.environ.get("AI_PROVIDER") or "").lower().strip()
        if not prov_type:
            try:
                from jarvis.core.database import Database
                prov_type = (Database().get_setting("ai_provider") or "").lower().strip()
            except Exception:
                pass

        # 1. Explicit Local
        if prov_type in ["local", "local_nlu", "offline"]:
            return LocalNLUProvider()

        # 2. Explicit Gemini
        if prov_type in ["gemini", "google"]:
            return GeminiProvider(api_key=api_key, model=model)

        # 3. Explicit OpenAI / Compatible
        if prov_type in ["openai", "groq", "openrouter", "deepseek"]:
            return OpenAICompatibleProvider(api_key=api_key, model=model)

        # 4. Explicit Ollama
        if prov_type in ["ollama", "local_llm"]:
            return OllamaProvider(model=model)

        # 4. Auto-detect from configured environment variables
        if os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY"):
            return GeminiProvider(model=model)

        if os.environ.get("OPENAI_API_KEY"):
            return OpenAICompatibleProvider(model=model)

        # 5. Default to robust Local NLU Provider
        return LocalNLUProvider()
