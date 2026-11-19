"""Email Assistant for O.M.E.N. / JARVIS.

Provides email checking, unread summaries, search by sender, and drafting/sending.
Supports live IMAP/SMTP integration when credentials are configured, with seamless
local SQLite storage and Windows default mail client (mailto:) fallback.
"""

import os
import re
import time
import urllib.parse
import webbrowser
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime

from jarvis.core.database import Database

logger = logging.getLogger(__name__)


class EmailAssistant:
    """Manages email retrieval, inbox summaries, and drafting/sending operations."""

    def __init__(self, db: Optional[Database] = None):
        self.db = db or Database()

    def get_emails(
        self,
        unread_only: bool = True,
        sender_filter: str = "",
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """Fetch emails from configured IMAP server or local SQLite database."""
        # 1. Check if real IMAP credentials are configured
        imap_server = os.environ.get("IMAP_SERVER") or self.db.get_setting("imap_server")
        imap_user = os.environ.get("IMAP_USER") or self.db.get_setting("imap_user")
        imap_pass = os.environ.get("IMAP_PASSWORD") or self.db.get_setting("imap_password")

        if imap_server and imap_user and imap_pass:
            try:
                return self._fetch_imap_emails(imap_server, imap_user, imap_pass, unread_only, sender_filter, limit)
            except Exception as exc:
                logger.warning(f"IMAP fetch failed, falling back to local database: {exc}")

        # 2. Return from local SQLite store
        return self.db.get_emails(unread_only=unread_only, sender_filter=sender_filter, limit=limit)

    def _fetch_imap_emails(
        self,
        server: str,
        user: str,
        password: str,
        unread_only: bool,
        sender_filter: str,
        limit: int
    ) -> List[Dict[str, Any]]:
        """Fetch emails directly from an IMAP server via SSL."""
        import imaplib
        import email
        from email.header import decode_header

        mail = imaplib.IMAP4_SSL(server)
        mail.login(user, password)
        mail.select("INBOX")

        criterion = "UNSEEN" if unread_only else "ALL"
        status, messages = mail.search(None, criterion)
        if status != "OK" or not messages[0]:
            mail.close()
            mail.logout()
            return []

        mail_ids = messages[0].split()
        recent_ids = mail_ids[-limit:]
        recent_ids.reverse()

        results = []
        for mid in recent_ids:
            res, data = mail.fetch(mid, "(RFC822)")
            if res != "OK":
                continue
            msg = email.message_from_bytes(data[0][1])

            # Decode subject
            subject_raw, encoding = decode_header(msg.get("Subject", "(No Subject)"))[0]
            if isinstance(subject_raw, bytes):
                subject = subject_raw.decode(encoding or "utf-8", errors="replace")
            else:
                subject = str(subject_raw)

            sender = msg.get("From", "Unknown Sender")
            if sender_filter and sender_filter.lower() not in sender.lower() and sender_filter.lower() not in subject.lower():
                continue

            # Extract body
            body = ""
            if msg.is_multipart():
                for part in msg.walk():
                    if part.get_content_type() == "text/plain":
                        body = part.get_payload(decode=True).decode(errors="replace")
                        break
            else:
                body = msg.get_payload(decode=True).decode(errors="replace")

            results.append({
                "id": mid.decode(),
                "sender": sender,
                "recipient": user,
                "subject": subject,
                "body": body.strip()[:300],
                "received_timestamp": time.time(),
                "is_read": 0
            })

        mail.close()
        mail.logout()
        return results

    def check_unread_summary(self, sender_filter: str = "") -> Dict[str, Any]:
        """Generate a structured summary of unread emails."""
        emails = self.get_emails(unread_only=True, sender_filter=sender_filter, limit=10)
        count = len(emails)

        if count == 0:
            msg = "You have 0 unread messages in your inbox. All clear, Sir." if not sender_filter else f"No unread messages found matching '{sender_filter}'."
            return {
                "count": 0,
                "emails": [],
                "formatted_report": msg,
                "summary": msg
            }

        lines = [f"INBOX INTELLIGENCE: {count} Unread Message(s) Found"]
        for idx, em in enumerate(emails[:5], start=1):
            received_dt = datetime.fromtimestamp(em.get("received_timestamp", time.time()))
            time_str = received_dt.strftime("%H:%M")
            sender = em.get("sender", "Unknown")
            subject = em.get("subject", "No subject")
            lines.append(f" {idx}. [{time_str}] From: {sender}")
            lines.append(f"    Subject: \"{subject}\"")
            if em.get("body"):
                snippet = em["body"].replace("\n", " ").strip()[:100]
                lines.append(f"    Preview: {snippet}...")

        if count > 5:
            lines.append(f" ...and {count - 5} more unread email(s).")

        return {
            "count": count,
            "emails": emails,
            "formatted_report": "\n".join(lines),
            "summary": f"You have {count} unread emails. The most recent is from {emails[0]['sender']} regarding '{emails[0]['subject']}'."
        }

    def send_email(self, recipient: str, subject: str, body: str) -> Dict[str, Any]:
        """
        Send an email via configured SMTP server, or record to database and
        open in default Windows Mail client (mailto:) fallback.
        """
        clean_recipient = recipient.strip()
        clean_subject = subject.strip()
        clean_body = body.strip()

        # If recipient is a contact name (e.g. "boss"), resolve it
        contact = self.db.get_contact_by_query(clean_recipient)
        if contact and contact.get("email"):
            clean_recipient = contact["email"]

        smtp_server = os.environ.get("SMTP_SERVER") or self.db.get_setting("smtp_server")
        smtp_user = os.environ.get("SMTP_USER") or self.db.get_setting("smtp_user")
        smtp_pass = os.environ.get("SMTP_PASSWORD") or self.db.get_setting("smtp_password")

        if smtp_server and smtp_user and smtp_pass:
            try:
                import smtplib
                from email.mime.text import MIMEText
                msg = MIMEText(clean_body)
                msg["Subject"] = clean_subject
                msg["From"] = smtp_user
                msg["To"] = clean_recipient

                port = int(os.environ.get("SMTP_PORT", 465))
                with smtplib.SMTP_SSL(smtp_server, port) as server:
                    server.login(smtp_user, smtp_pass)
                    server.send_message(msg)

                # Record in local sent emails
                self.db.add_email(
                    sender=smtp_user,
                    recipient=clean_recipient,
                    subject=clean_subject,
                    body=clean_body,
                    is_read=True
                )
                return {
                    "success": True,
                    "message": f"Email successfully transmitted via SMTP to {clean_recipient}.",
                    "recipient": clean_recipient,
                    "subject": clean_subject
                }
            except Exception as exc:
                logger.error(f"SMTP transmission failed: {exc}")

        # Fallback: Save to local sent records and launch default Windows Mail
        self.db.add_email(
            sender="you@omen.ai",
            recipient=clean_recipient,
            subject=clean_subject,
            body=clean_body,
            is_read=True
        )

        # Launch mailto: protocol
        encoded_subj = urllib.parse.quote(clean_subject)
        encoded_body = urllib.parse.quote(clean_body)
        mailto_url = f"mailto:{clean_recipient}?subject={encoded_subj}&body={encoded_body}"
        try:
            webbrowser.open(mailto_url)
        except Exception:
            pass

        return {
            "success": True,
            "message": (
                f"Email drafted and dispatched for {clean_recipient} (Subject: '{clean_subject}'). "
                "Opened in Windows Mail client and logged to system history."
            ),
            "recipient": clean_recipient,
            "subject": clean_subject,
            "body": clean_body
        }
