"""Telephony and Contact Communications System for O.M.E.N. / JARVIS.

Enables speed-dialing contacts (such as 'The Boss'), calling via Windows Phone Link
(tel: protocol), WhatsApp desktop/web, Microsoft Teams, and Skype, plus contact management.
"""

import os
import re
import urllib.parse
import webbrowser
import logging
from typing import Dict, List, Any, Optional

from jarvis.core.database import Database

logger = logging.getLogger(__name__)


class TelephonyManager:
    """Handles contact directory lookup, voice calling protocols, and messaging dispatch."""

    def __init__(self, db: Optional[Database] = None):
        self.db = db or Database()

    def get_contact(self, query: str) -> Optional[Dict[str, Any]]:
        """Look up contact by name or alias (e.g. 'boss', 'the boss', 'mom')."""
        return self.db.get_contact_by_query(query)

    def list_contacts(self) -> List[Dict[str, Any]]:
        """Return all stored contacts."""
        return self.db.get_all_contacts()

    def set_contact(
        self,
        name: str,
        phone: str = "",
        alias: str = "",
        email: str = "",
        preferred_channel: str = "phone"
    ) -> Dict[str, Any]:
        """Add or update a contact in the communications directory."""
        clean_name = name.strip()
        if not clean_name:
            return {"success": False, "message": "Contact name cannot be empty."}

        cid = self.db.upsert_contact(
            name=clean_name,
            phone=phone.strip(),
            alias=alias.strip(),
            email=email.strip(),
            preferred_channel=preferred_channel.strip() or "phone"
        )
        return {
            "success": True,
            "message": f"Contact '{clean_name}' successfully configured (Phone: {phone or 'N/A'}, Alias: {alias or 'N/A'}).",
            "contact_id": cid,
            "name": clean_name,
            "phone": phone
        }

    def call_contact(
        self,
        target: str,
        channel: str = "phone",
        custom_phone: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Initiate a call to a named contact (e.g. 'boss') or a direct phone number.
        Supported channels: 'phone' (tel: protocol / Windows Phone Link), 'whatsapp', 'teams', 'skype'.
        """
        target_clean = target.strip()
        resolved_name = target_clean
        phone_number = custom_phone or ""
        email_addr = ""

        # Check if target is a known contact
        contact = self.get_contact(target_clean)
        if contact:
            resolved_name = contact["name"]
            phone_number = contact.get("phone") or phone_number
            email_addr = contact.get("email") or ""
            if not channel or channel == "phone":
                channel = contact.get("preferred_channel", "phone")

        # If phone_number is still empty and target looks like a phone number
        if not phone_number and re.search(r"[\d\+\-\(\)\s]{7,}", target_clean):
            phone_number = target_clean

        if not phone_number and channel in ["phone", "whatsapp"]:
            return {
                "success": False,
                "message": (
                    f"No phone number on record for '{target_clean}'. "
                    f"You can register one by typing: 'set contact {target_clean} phone <number>'."
                ),
                "contact": target_clean
            }

        # Normalize digits for phone protocols
        digits_only = re.sub(r"[^\d\+]", "", phone_number) if phone_number else ""

        channel_lower = (channel or "phone").lower()

        # 1. WhatsApp Call / Direct Chat Link
        if "whatsapp" in channel_lower or "wa" in channel_lower:
            wa_num = digits_only.lstrip("+")
            wa_url = f"https://wa.me/{wa_num}"
            try:
                webbrowser.open(wa_url)
                return {
                    "success": True,
                    "message": f"COMM-LINK ACTIVATED: Connecting to {resolved_name} ({phone_number}) via WhatsApp Web/Desktop.",
                    "channel": "whatsapp",
                    "target": resolved_name,
                    "phone": phone_number
                }
            except Exception as exc:
                return {"success": False, "message": f"Failed to launch WhatsApp: {exc}"}

        # 2. Microsoft Teams Call
        elif "teams" in channel_lower:
            call_target = email_addr or phone_number
            teams_url = f"msteams:/l/call/0/0?users={urllib.parse.quote(call_target)}"
            try:
                os.startfile(teams_url)
                return {
                    "success": True,
                    "message": f"COMM-LINK ACTIVATED: Initiating Microsoft Teams call to {resolved_name} ({call_target}).",
                    "channel": "teams",
                    "target": resolved_name
                }
            except Exception as exc:
                return {"success": False, "message": f"Failed to launch Microsoft Teams: {exc}"}

        # 3. Skype Call
        elif "skype" in channel_lower:
            skype_target = digits_only or email_addr or resolved_name
            skype_url = f"skype:{skype_target}?call"
            try:
                os.startfile(skype_url)
                return {
                    "success": True,
                    "message": f"COMM-LINK ACTIVATED: Initiating Skype call to {resolved_name} ({skype_target}).",
                    "channel": "skype",
                    "target": resolved_name
                }
            except Exception as exc:
                return {"success": False, "message": f"Failed to launch Skype: {exc}"}

        # 4. Standard Phone / Windows Phone Link (tel: protocol)
        else:
            tel_url = f"tel:{digits_only}"
            try:
                # On Windows, tel: URL activates Windows Phone Link or default dialer
                webbrowser.open(tel_url)
                return {
                    "success": True,
                    "message": (
                        f"COMM-LINK ACTIVATED: Dialing {resolved_name} at {phone_number} "
                        "via Windows Phone Link / System Dialer."
                    ),
                    "channel": "phone",
                    "target": resolved_name,
                    "phone": phone_number
                }
            except Exception as exc:
                return {"success": False, "message": f"Failed to trigger telephone protocol: {exc}"}

    def message_contact(
        self,
        target: str,
        message: str,
        channel: str = "whatsapp"
    ) -> Dict[str, Any]:
        """Send or draft an instant message to a contact via WhatsApp or default protocols."""
        target_clean = target.strip()
        msg_clean = message.strip()
        contact = self.get_contact(target_clean)

        resolved_name = contact["name"] if contact else target_clean
        phone_number = (contact.get("phone") if contact else "") or ""
        if not phone_number and re.search(r"[\d\+\-\(\)\s]{7,}", target_clean):
            phone_number = target_clean

        if not phone_number:
            return {
                "success": False,
                "message": f"Cannot send message: no phone number found for '{target_clean}'."
            }

        digits_only = re.sub(r"[^\d\+]", "", phone_number).lstrip("+")
        encoded_msg = urllib.parse.quote(msg_clean)
        wa_url = f"https://wa.me/{digits_only}?text={encoded_msg}"

        try:
            webbrowser.open(wa_url)
            return {
                "success": True,
                "message": f"DISPATCH: Prepared WhatsApp transmission to {resolved_name} ({phone_number}): \"{msg_clean}\"",
                "channel": "whatsapp",
                "target": resolved_name,
                "message": msg_clean
            }
        except Exception as exc:
            return {"success": False, "message": f"Failed to dispatch message: {exc}"}
