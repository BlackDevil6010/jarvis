"""Central Task Orchestration and Multi-Turn Conversation Engine for JARVIS.

Bridges incoming user natural-language directives with AI providers,
the approved ToolRegistry, and verified operating system execution.
"""

import logging
from typing import Dict, List, Any, Optional, Tuple

from jarvis.ai.provider import BaseAIProvider, AIResponse, ToolCall, AIProviderFactory
from jarvis.ai.tools import ToolRegistry, ToolResult
from jarvis.core.database import Database

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are O.M.E.N., a tactical Windows desktop AI assistant.
Your directives:
1. Provide concise, professional, and intelligent conversational assistance.
2. When the user requests an action on their computer (e.g., opening an application, searching the web, checking system diagnostics, opening folders, or running automation workflows), select and call the appropriate approved tool.
3. If an application is referred to by category (e.g., "code editor", "music player", "browser"), pass that alias to launch_application.
4. If a request involves multiple steps (e.g. "Open VS Code and check system health"), select the corresponding tools in sequence.
5. If a requested application or capability is unavailable or not installed, explain that accurately.
6. For programming queries or errors, explain the root cause and provide clear code solutions.
7. Maintain awareness of previous conversation turns to handle follow-up queries naturally.
8. When the user requests to play a song, artist, album, playlist, or music (e.g. "in Spotify could you please play element", "play John Michael Howell", "play Bohemian Rhapsody"), call the play_music tool with the requested query and platform (default "spotify"). If the user follows up with just a song title or artist name after discussing music, recognize that context and call play_music.
9. When the user requests to pause, resume, skip, go back, stop, or change volume/mute media playback, call the control_media tool with the appropriate action.
10. When the user asks to set a timer or reminder (e.g. "set timer for 10 minutes", "remind me to check the oven in 5 minutes"), call the set_timer tool.
11. When the user asks to look at their screen or explain what is on the screen, call the analyze_screen tool.
12. When the user asks to lock their PC or show desktop/minimize all windows, call the windows_automation tool.
13. When the user asks to find or locate a file on their computer, call the find_files tool.
14. When the user asks to check their emails, read emails, or search for emails (e.g. "check my emails", "any emails from boss", "summarize unread emails"), call the check_emails tool.
15. When the user asks to send or draft an email, call the send_email tool.
16. When the user asks to call someone or speed-dial a contact (e.g. "call the boss", "call boss", "call mom", "dial 555-0199", "call boss on whatsapp"), call the call_contact tool with contact_name and optional channel.
17. When the user asks to message a contact on WhatsApp or SMS, call the message_contact tool.
18. When the user asks to access or connect through their phone or mobile companion (e.g. "access through phone", "phone access", "mobile link", "connect mobile"), call the phone_companion tool.
19. When the user asks for a daily or morning briefing (e.g. "give me a briefing", "daily briefing", "morning briefing"), call the daily_briefing tool.
20. When the user asks to take a note, record a voice memo, or view notes (e.g. "take a note: ...", "show notes"), call the manage_notes tool.
"""


class OrchestratorResult:
    """Consolidated outcome of an orchestrated user request."""

    def __init__(
        self,
        text: str,
        success: bool = True,
        action_type: str = "info",
        executed_tools: Optional[List[ToolResult]] = None,
        needs_clarification: bool = False,
        provider_name: str = "local"
    ):
        self.text = text
        self.success = success
        self.action_type = action_type  # "info", "launch", "error", "clarification"
        self.executed_tools = executed_tools or []
        self.needs_clarification = needs_clarification
        self.provider_name = provider_name

    def to_dict(self) -> Dict[str, Any]:
        return {
            "text": self.text,
            "success": self.success,
            "action_type": self.action_type,
            "executed_tools": [t.to_dict() for t in self.executed_tools],
            "needs_clarification": self.needs_clarification,
            "provider_name": self.provider_name,
        }


class AIOrchestrator:
    """Coordinates conversation context, AI inference, tool validation, and action execution."""

    def __init__(
        self,
        tool_registry: Optional[ToolRegistry] = None,
        provider: Optional[BaseAIProvider] = None,
        max_history_turns: int = 12
    ):
        self.db = Database()
        self.tool_registry = tool_registry or ToolRegistry(db=self.db)
        self.provider = provider or AIProviderFactory.get_provider()
        self.max_history_turns = max_history_turns
        self._conversation_history: List[Dict[str, str]] = []

    def set_provider(self, provider: BaseAIProvider) -> None:
        """Dynamically switch the active AI provider."""
        self.provider = provider

    def clear_history(self) -> None:
        """Reset conversation context."""
        self._conversation_history.clear()

    def process_query(self, user_query: str) -> OrchestratorResult:
        """
        Main entry point for handling natural language requests.
        Sequence:
          1. Record user turn in context.
          2. Send request to AI provider with tool schemas.
          3. If conversational response: return synthesized text.
          4. If tool call(s) requested: execute and verify each approved tool.
          5. Update history and return outcome.
        """
        clean_query = user_query.strip()
        if not clean_query:
            return OrchestratorResult(
                text="Awaiting instructions. How may I assist you, Sir?",
                success=True,
                action_type="info"
            )

        # Append to history
        self._conversation_history.append({"role": "user", "content": clean_query})
        if len(self._conversation_history) > self.max_history_turns * 2:
            self._conversation_history = self._conversation_history[-self.max_history_turns * 2:]

        # Query AI Provider
        tool_schemas = self.tool_registry.get_schemas()
        ai_resp: AIResponse = self.provider.chat(
            messages=self._conversation_history,
            tools=tool_schemas,
            system_prompt=SYSTEM_PROMPT
        )

        # Fallback to local NLU if cloud provider encountered an authentication or network error
        if not ai_resp.has_tool_calls and any(err_str in ai_resp.text.lower() for err_str in ["error (401)", "api key not valid", "unauthenticated", "network error communicating"]):
            from jarvis.ai.provider import LocalNLUProvider
            local_prov = LocalNLUProvider()
            local_resp = local_prov.chat(
                messages=self._conversation_history,
                tools=tool_schemas,
                system_prompt=SYSTEM_PROMPT
            )
            if local_resp.has_tool_calls or local_resp.text:
                ai_resp = local_resp

        # Case A: Pure Conversational Response
        if not ai_resp.has_tool_calls:
            self._conversation_history.append({"role": "assistant", "content": ai_resp.text})
            return OrchestratorResult(
                text=ai_resp.text,
                success=True,
                action_type="info",
                needs_clarification=ai_resp.needs_clarification,
                provider_name=ai_resp.provider_name
            )

        # Case B: Tool Calls Requested
        executed_results: List[ToolResult] = []
        overall_success = True
        result_messages: List[str] = []

        for tc in ai_resp.tool_calls:
            logger.info(f"AIOrchestrator: Executing tool '{tc.name}' with args {tc.arguments}")
            tool_res: ToolResult = self.tool_registry.execute_tool(tc.name, tc.arguments)
            executed_results.append(tool_res)

            if not tool_res.success:
                overall_success = False

            result_messages.append(tool_res.message)

        # Formulate final response text
        final_text = "\n\n".join(result_messages)
        if ai_resp.text and ai_resp.text not in final_text:
            final_text = f"{ai_resp.text}\n\n{final_text}"

        self._conversation_history.append({"role": "assistant", "content": final_text})

        # Determine action_type
        primary_tool_name = ai_resp.tool_calls[0].name if ai_resp.tool_calls else ""
        if "launch" in primary_tool_name:
            action_type = "launch" if overall_success else "error"
        else:
            action_type = "info" if overall_success else "error"

        return OrchestratorResult(
            text=final_text.strip(),
            success=overall_success,
            action_type=action_type,
            executed_tools=executed_results,
            provider_name=ai_resp.provider_name
        )
