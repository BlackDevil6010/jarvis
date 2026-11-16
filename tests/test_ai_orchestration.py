"""Automated tests for AI Provider, Structured Tool-Calling, and Orchestration."""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from jarvis.ai.provider import (
    BaseAIProvider,
    GeminiProvider,
    OpenAICompatibleProvider,
    LocalNLUProvider,
    AIProviderFactory,
    AIResponse,
    ToolCall
)
from jarvis.ai.tools import ToolRegistry, ToolResult
from jarvis.ai.orchestrator import AIOrchestrator, OrchestratorResult
from jarvis.core.launcher import AppLauncher
from jarvis.core.database import Database


@pytest.fixture
def test_orchestrator():
    with tempfile.TemporaryDirectory() as tmp_dir:
        db = Database(db_path=Path(tmp_dir) / "test_ai.db")
        launcher = AppLauncher(db=db)
        registry = ToolRegistry(launcher=launcher, db=db)
        provider = LocalNLUProvider()
        orchestrator = AIOrchestrator(tool_registry=registry, provider=provider)
        yield orchestrator, registry, launcher, db
        del orchestrator
        del registry
        del launcher
        del db
        import gc
        gc.collect()


def test_local_nlu_conversational_response():
    """Verify built-in Local NLU answers greetings and questions."""
    provider = LocalNLUProvider()
    resp = provider.chat([{"role": "user", "content": "Hello Jarvis"}])
    assert resp.is_conversational is True
    assert "jarvis" in resp.text.lower() or "greetings" in resp.text.lower()

    # Who are you query
    resp2 = provider.chat([{"role": "user", "content": "Who are you?"}])
    assert "o.m.e.n." in resp2.text.lower() or "j.a.r.v.i.s." in resp2.text.lower()


def test_local_nlu_programming_explanation():
    """Verify Local NLU explains common programming errors and concepts."""
    provider = LocalNLUProvider()
    resp = provider.chat([{"role": "user", "content": "Explain TypeError in Python"}])
    assert resp.is_conversational is True
    assert "typeerror" in resp.text.lower()

    resp_rec = provider.chat([{"role": "user", "content": "What is recursion?"}])
    assert "base case" in resp_rec.text.lower()


def test_local_nlu_intent_detection():
    """Verify natural language requests are mapped to approved tools."""
    provider = LocalNLUProvider()

    # Natural language application launch
    resp = provider.chat([{"role": "user", "content": "Can you open my code editor?"}])
    assert resp.has_tool_calls is True
    assert resp.tool_calls[0].name == "launch_application"
    assert "code" in resp.tool_calls[0].arguments["app_name"].lower()

    # System health
    resp_sys = provider.chat([{"role": "user", "content": "Check my system health"}])
    assert resp_sys.has_tool_calls is True
    assert resp_sys.tool_calls[0].name == "system_diagnostics"

    # Web search
    resp_search = provider.chat([{"role": "user", "content": "Search the web for PySide6 desktop applications"}])
    assert resp_search.has_tool_calls is True
    assert resp_search.tool_calls[0].name == "search_web"


def test_local_nlu_multi_step_requests():
    """Verify multi-action requests joined by 'and' produce sequential tool calls."""
    provider = LocalNLUProvider()
    resp = provider.chat([{"role": "user", "content": "Open Notepad and check my system health"}])
    assert resp.has_tool_calls is True
    assert len(resp.tool_calls) == 2
    tool_names = [tc.name for tc in resp.tool_calls]
    assert "launch_application" in tool_names
    assert "system_diagnostics" in tool_names


def test_tool_registry_security_blocks_unauthorized_tools(test_orchestrator):
    """Ensure arbitrary tool execution requested by an AI is strictly blocked."""
    _, registry, _, _ = test_orchestrator
    res = registry.execute_tool("arbitrary_hacker_command_execution", {})
    assert res.success is False
    assert "security alert" in res.message.lower()


def test_tool_registry_security_blocks_shell_operators_in_args(test_orchestrator):
    """Ensure dangerous shell tokens in arguments are rejected."""
    _, registry, _, _ = test_orchestrator
    res = registry.execute_tool("launch_application", {"app_name": "notepad; rm -rf /"})
    assert res.success is False
    assert "prohibited shell control characters" in res.message.lower()


def test_tool_registry_system_diagnostics(test_orchestrator):
    """Verify system diagnostics tool execution."""
    _, registry, _, _ = test_orchestrator
    res = registry.execute_tool("system_diagnostics", {})
    assert res.success is True
    assert "cpu" in res.message.lower()


def test_tool_registry_play_music_and_media_control(test_orchestrator):
    """Verify play_music and control_media tools execution."""
    _, registry, _, _ = test_orchestrator
    res = registry.execute_tool("play_music", {"query": "element", "platform": "spotify"})
    assert res.success is True
    assert "element" in res.message.lower()

    res_ctrl = registry.execute_tool("control_media", {"action": "play_pause"})
    assert res_ctrl.success is True
    assert "play/pause" in res_ctrl.message.lower() or "toggled" in res_ctrl.message.lower()


def test_tool_registry_timers_and_automation(test_orchestrator):
    """Verify timers, windows automation, and file search tools."""
    _, registry, _, _ = test_orchestrator

    # Timer tool
    res_timer = registry.execute_tool("set_timer", {"minutes": 5, "label": "Tea break"})
    assert res_timer.success is True
    assert "5" in res_timer.message

    res_list = registry.execute_tool("list_timers", {})
    assert res_list.success is True
    assert "Tea break" in res_list.message

    # File search tool
    res_files = registry.execute_tool("find_files", {"pattern": "nonexistent_file_xyz_123.txt"})
    assert res_files.success is True

    # Windows automation tool
    res_auto = registry.execute_tool("windows_automation", {"action": "minimize_all"})
    assert res_auto.success is True


def test_orchestrator_multi_turn_history(test_orchestrator):
    """Verify conversation history is maintained across turns."""
    orchestrator, _, _, _ = test_orchestrator

    res1 = orchestrator.process_query("Hello Jarvis")
    assert res1.success is True
    assert len(orchestrator._conversation_history) == 2

    res2 = orchestrator.process_query("What can you do?")
    assert res2.success is True
    assert len(orchestrator._conversation_history) == 4


def test_ai_provider_factory():
    """Verify provider instantiation from environment or explicit arguments."""
    p_local = AIProviderFactory.get_provider(preferred_provider="local")
    assert isinstance(p_local, LocalNLUProvider)

    p_gemini = AIProviderFactory.get_provider(preferred_provider="gemini", api_key="dummy_key")
    assert isinstance(p_gemini, GeminiProvider)
    assert p_gemini.is_configured() is True


def test_gemini_provider_unconfigured():
    """Verify unconfigured Gemini provider returns a helpful prompt."""
    provider = GeminiProvider(api_key="")
    assert provider.is_configured() is False
    resp = provider.chat([{"role": "user", "content": "Hello"}])
    assert "GEMINI_API_KEY" in resp.text


def test_gemini_provider_sdk_chat_response():
    """Verify GeminiProvider handles conversational text responses from google-genai SDK."""
    provider = GeminiProvider(api_key="mock_test_key", model="gemini-2.5-flash")
    mock_client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.text = "Good afternoon, Sir. How may I assist you?"
    mock_resp.function_calls = None
    mock_resp.candidates = []
    mock_client.models.generate_content.return_value = mock_resp
    provider._client = mock_client

    resp = provider.chat([{"role": "user", "content": "Greetings"}])
    assert resp.is_conversational is True
    assert "assist you" in resp.text
    mock_client.models.generate_content.assert_called_once()


def test_gemini_provider_sdk_function_calls():
    """Verify GeminiProvider parses tool/function calls returned by google-genai SDK."""
    provider = GeminiProvider(api_key="mock_test_key", model="gemini-2.5-flash")
    mock_client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.text = ""
    mock_fc = MagicMock()
    mock_fc.name = "launch_application"
    mock_fc.args = {"app_name": "notepad"}
    mock_resp.function_calls = [mock_fc]
    mock_resp.candidates = []
    mock_client.models.generate_content.return_value = mock_resp
    provider._client = mock_client

    tools_schema = [{
        "name": "launch_application",
        "description": "Launch app",
        "parameters": {"type": "object", "properties": {"app_name": {"type": "string"}}}
    }]
    resp = provider.chat([{"role": "user", "content": "Open Notepad"}], tools=tools_schema)
    assert resp.has_tool_calls is True
    assert len(resp.tool_calls) == 1
    assert resp.tool_calls[0].name == "launch_application"
    assert resp.tool_calls[0].arguments["app_name"] == "notepad"


def test_gemini_provider_sdk_grounding_citations():
    """Verify GeminiProvider extracts search grounding citations into response text."""
    provider = GeminiProvider(api_key="mock_test_key", model="gemini-2.5-flash")
    mock_client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.text = "Python 3.12 introduces improved error messages."
    mock_resp.function_calls = None

    mock_chunk = MagicMock()
    mock_chunk.web = MagicMock()
    mock_chunk.web.title = "Python Release Notes"
    mock_chunk.web.uri = "https://docs.python.org/3/whatsnew/3.12.html"

    mock_cand = MagicMock()
    mock_cand.grounding_metadata = MagicMock()
    mock_cand.grounding_metadata.grounding_chunks = [mock_chunk]
    mock_resp.candidates = [mock_cand]

    mock_client.models.generate_content.return_value = mock_resp
    provider._client = mock_client

    resp = provider.chat([{"role": "user", "content": "What is new in Python 3.12?"}])
    assert resp.is_conversational is True
    assert "Grounding Sources:" in resp.text
    assert "https://docs.python.org/3/whatsnew/3.12.html" in resp.text


def test_gemini_provider_sdk_fallback_on_404():
    """Verify GeminiProvider falls back to 1.5-flash if 2.5-flash is not available on endpoint."""
    provider = GeminiProvider(api_key="mock_test_key", model="gemini-2.5-flash")
    mock_client = MagicMock()

    mock_fallback_resp = MagicMock()
    mock_fallback_resp.text = "Fallback model response succeeded."
    mock_fallback_resp.function_calls = None
    mock_fallback_resp.candidates = []

    def mock_generate_content(*args, **kwargs):
        if kwargs.get("model") == "gemini-2.5-flash":
            raise Exception("404 Model Not Found")
        return mock_fallback_resp

    mock_client.models.generate_content.side_effect = mock_generate_content
    provider._client = mock_client

    resp = provider.chat([{"role": "user", "content": "Test fallback"}])
    assert resp.is_conversational is True
    assert resp.text == "Fallback model response succeeded."

