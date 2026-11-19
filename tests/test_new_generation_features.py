"""Automated tests for New-Generation features:
1. Calling the Boss & Speed-Dialing Telephony
2. Email Assistant (checking unread inbox, search, drafting/sending)
3. Phone Remote Access Gateway & Mobile Companion
4. Executive Daily Briefing
5. Quick Notes & Voice Scratchpad
6. NLU and Command Processor Integration
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from jarvis.core.database import Database
from jarvis.core.telephony import TelephonyManager
from jarvis.core.email_assistant import EmailAssistant
from jarvis.core.remote_gateway import MobileCompanionServer, get_local_ip, generate_svg_qr
from jarvis.core.briefing import BriefingManager
from jarvis.core.notes import NotesManager
from jarvis.core.launcher import AppLauncher
from jarvis.core.command_processor import CommandProcessor
from jarvis.ai.provider import LocalNLUProvider
from jarvis.ai.tools import ToolRegistry


@pytest.fixture
def test_db():
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = Path(tmp_dir) / "test_next_gen.db"
        db = Database(db_path=db_path)
        yield db


# =========================================================================
# 1. Telephony & Calling the Boss
# =========================================================================

def test_telephony_default_contacts_and_lookup(test_db):
    """Verify default seeded contacts include 'The Boss' and alias lookup works."""
    telephony = TelephonyManager(test_db)
    contacts = telephony.list_contacts()
    assert len(contacts) >= 2

    # Lookup 'boss' alias
    boss = telephony.get_contact("boss")
    assert boss is not None
    assert "boss" in boss["name"].lower() or "the boss" in boss["name"].lower()
    assert boss["phone"] == "+91-8754251849"


def test_telephony_call_boss_phone_link(test_db):
    """Verify calling the boss triggers tel: protocol without errors."""
    telephony = TelephonyManager(test_db)
    with patch("webbrowser.open") as mock_open:
        res = telephony.call_contact("boss", channel="phone")
        assert res["success"] is True
        assert "The Boss" in res["message"]
        assert "+91-8754251849" in res["message"]
        mock_open.assert_called_once()
        assert "tel:" in mock_open.call_args[0][0]


def test_telephony_call_boss_whatsapp(test_db):
    """Verify calling boss via WhatsApp triggers wa.me URI."""
    telephony = TelephonyManager(test_db)
    with patch("webbrowser.open") as mock_open:
        res = telephony.call_contact("boss", channel="whatsapp")
        assert res["success"] is True
        assert res["channel"] == "whatsapp"
        mock_open.assert_called_once()
        assert "wa.me/918754251849" in mock_open.call_args[0][0]


def test_telephony_set_custom_contact(test_db):
    """Verify adding/updating a new contact."""
    telephony = TelephonyManager(test_db)
    res = telephony.set_contact("Elon", phone="+1-555-4321", alias="elon,chief")
    assert res["success"] is True
    contact = telephony.get_contact("elon")
    assert contact is not None
    assert contact["phone"] == "+1-555-4321"


# =========================================================================
# 2. Email Assistant
# =========================================================================

def test_email_assistant_default_inbox_and_summary(test_db):
    """Verify seeded sample unread emails and summary generation."""
    assistant = EmailAssistant(test_db)
    summary = assistant.check_unread_summary()
    assert summary["count"] >= 1
    assert "URGENT" in summary["formatted_report"] or "Boss" in summary["formatted_report"]

    # Filter by 'boss'
    boss_emails = assistant.get_emails(unread_only=True, sender_filter="boss")
    assert len(boss_emails) >= 1
    assert "boss" in boss_emails[0]["sender"].lower()


def test_email_assistant_send_draft(test_db):
    """Verify drafting and dispatching an email."""
    assistant = EmailAssistant(test_db)
    with patch("webbrowser.open") as mock_open:
        res = assistant.send_email(
            recipient="boss",
            subject="Status Report",
            body="Completed neural engine integration."
        )
        assert res["success"] is True
        assert "boss@executive.corp" in res["recipient"]
        mock_open.assert_called_once()
        assert "mailto:boss@executive.corp" in mock_open.call_args[0][0]


# =========================================================================
# 3. Mobile Companion & Remote Gateway
# =========================================================================

def test_mobile_companion_server_lifecycle(test_db):
    """Verify starting, querying, and stopping mobile companion HTTP daemon."""
    launcher = AppLauncher(db=test_db)
    processor = CommandProcessor(launcher=launcher, db=test_db)
    server = MobileCompanionServer(command_processor=processor, port=8799)

    start_res = server.start()
    assert start_res["success"] is True
    assert server.is_running is True
    assert "8799" in server.get_access_url()

    # Query local IP & SVG QR generator
    ip = get_local_ip()
    assert ip is not None
    svg_qr = generate_svg_qr(server.get_access_url())
    assert "<svg" in svg_qr

    server.stop()
    assert server.is_running is False


# =========================================================================
# 4. Executive Daily Briefing
# =========================================================================

def test_briefing_manager_generation(test_db):
    """Verify executive briefing report aggregates telemetry, inbox, and greeting."""
    mgr = BriefingManager(test_db)
    report = mgr.generate_briefing()
    assert report["success"] is True
    assert "O.M.E.N. EXECUTIVE BRIEFING" in report["report_text"]
    assert "CPU Utilization" in report["report_text"]
    assert "INBOX INTELLIGENCE" in report["report_text"]
    assert report["unread_emails"] >= 1
    assert len(report["spoken_summary"]) > 20


# =========================================================================
# 5. Quick Notes Scratchpad
# =========================================================================

def test_notes_manager_crud(test_db):
    """Verify taking, listing, and deleting quick voice memos."""
    notes = NotesManager(test_db)
    res = notes.add_note("Review quarterly deployment logs with the Boss")
    assert res["success"] is True
    nid = res["note_id"]

    all_notes = notes.list_notes()
    assert all_notes["success"] is True
    assert len(all_notes["notes"]) == 1
    assert "quarterly deployment logs" in all_notes["message"]

    del_res = notes.delete_note(nid)
    assert del_res["success"] is True
    assert len(notes.list_notes()["notes"]) == 0


# =========================================================================
# 6. Local NLU Intent Mapping
# =========================================================================

def test_local_nlu_new_generation_intents():
    """Verify Local NLU detects natural language commands for next-gen features."""
    nlu = LocalNLUProvider()

    # Calling Boss
    r_call = nlu.chat([{"role": "user", "content": "Call the boss"}])
    assert r_call.has_tool_calls is True
    assert r_call.tool_calls[0].name == "call_contact"
    assert "boss" in r_call.tool_calls[0].arguments["contact_name"].lower()

    # Calling Boss on WhatsApp
    r_wa = nlu.chat([{"role": "user", "content": "Call boss on whatsapp"}])
    assert r_wa.has_tool_calls is True
    assert r_wa.tool_calls[0].name == "call_contact"
    assert r_wa.tool_calls[0].arguments["channel"] == "whatsapp"

    # Checking Emails
    r_mail = nlu.chat([{"role": "user", "content": "Can you check my emails?"}])
    assert r_mail.has_tool_calls is True
    assert r_mail.tool_calls[0].name == "check_emails"

    # Phone Access
    r_phone = nlu.chat([{"role": "user", "content": "Access through phone"}])
    assert r_phone.has_tool_calls is True
    assert r_phone.tool_calls[0].name == "phone_companion"

    # Daily Briefing
    r_brief = nlu.chat([{"role": "user", "content": "Give me a morning briefing"}])
    assert r_brief.has_tool_calls is True
    assert r_brief.tool_calls[0].name == "daily_briefing"

    # Take a Note
    r_note = nlu.chat([{"role": "user", "content": "Take a note: meeting at 3 PM"}])
    assert r_note.has_tool_calls is True
    assert r_note.tool_calls[0].name == "manage_notes"
    assert "meeting at 3 pm" in r_note.tool_calls[0].arguments["content"].lower()


# =========================================================================
# 7. CommandProcessor Direct Directives
# =========================================================================

def test_command_processor_direct_directives(test_db):
    """Verify direct typed commands for call boss, emails, briefing, and notes."""
    launcher = AppLauncher(db=test_db)
    processor = CommandProcessor(launcher=launcher, db=test_db)

    with patch("webbrowser.open"):
        # Call Boss
        res_call = processor.process("call boss")
        assert res_call.success is True
        assert "The Boss" in res_call.text

        # Check Emails
        res_mail = processor.process("check emails")
        assert res_mail.success is True
        assert "INBOX INTELLIGENCE" in res_mail.text

        # Daily Briefing
        res_brief = processor.process("daily briefing")
        assert res_brief.success is True
        assert "EXECUTIVE BRIEFING" in res_brief.text

        # Take Note & Show Notes
        res_add_note = processor.process("take note submit executive report")
        assert res_add_note.success is True
        res_notes = processor.process("notes")
        assert res_notes.success is True
        assert "submit executive report" in res_notes.text

        # Phone Access
        res_phone = processor.process("phone access")
        assert res_phone.success is True
        assert "MOBILE COMPANION ONLINE" in res_phone.text
        if processor.tool_registry._mobile_server:
            processor.tool_registry._mobile_server.stop()
