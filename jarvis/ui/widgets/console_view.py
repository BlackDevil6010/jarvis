"""Rich console and conversation display widget for JARVIS."""

import html
from datetime import datetime
from PySide6.QtWidgets import QTextEdit
from PySide6.QtGui import QTextCursor, QTextOption
from jarvis.config import COLORS, LOGO_PATH


class ConsoleView(QTextEdit):
    """Futuristic terminal-style conversation and output log viewer."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("ConsoleView")
        self.setReadOnly(True)
        self.setAcceptRichText(True)
        self.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        self.setWordWrapMode(QTextOption.WrapMode.WordWrap)
        self.display_welcome_banner()

    def display_welcome_banner(self):
        """Initial welcome greeting upon startup with integrated logo."""
        logo_tag = ""
        if LOGO_PATH.exists():
            logo_uri = LOGO_PATH.as_uri()
            logo_tag = f"""<img src="{logo_uri}" width="48" height="48" style="vertical-align: middle; margin-right: 12px;" />"""

        banner_html = f"""
        <div style="font-family: 'Consolas', monospace; margin-bottom: 12px; color: {COLORS['text_secondary']};">
            <table cellpadding="0" cellspacing="0" border="0" style="margin-bottom: 8px;">
                <tr>
                    <td valign="middle" style="padding-right: 12px;">{logo_tag}</td>
                    <td valign="middle">
                        <div style="color: {COLORS['cyan_glow']}; font-weight: bold; font-size: 14px; letter-spacing: 2px;">
                            O.M.E.N. INTERFACE SYSTEM — ONLINE
                        </div>
                        <div style="color: {COLORS['text_secondary']}; font-size: 11px;">
                            TACTICAL WORKFLOW &amp; DESKTOP AUTOMATION CORE
                        </div>
                    </td>
                </tr>
            </table>
            <div style="margin-top: 6px; color: {COLORS['text_primary']};">
                Welcome, Sir. All local desktop monitoring, application launcher, and Skill Forge subsystems are active.
                <br>Ready for directives. Type <span style="color: {COLORS['cyan_glow']};">help</span>, <span style="color: {COLORS['cyan_glow']};">list skills</span>, or use the quick controls above.
            </div>
        </div>
        <hr style="border: none; border-top: 1px solid {COLORS['border_subtle']}; margin: 8px 0;" />
        """
        self.setHtml(banner_html)

    def append_user_message(self, message: str):
        """Append user directive with prompt styling."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        safe_msg = html.escape(message)

        user_html = f"""
        <div style="margin: 8px 0; font-family: 'Consolas', monospace;">
            <span style="color: {COLORS['text_muted']}; font-size: 11px;">[{timestamp}]</span>
            <span style="color: {COLORS['cyan_glow']}; font-weight: bold;"> USER &gt; </span>
            <span style="color: {COLORS['text_primary']}; font-weight: 500;">{safe_msg}</span>
        </div>
        """
        self.append(user_html)
        self.scroll_to_end()

    def _format_content_html(self, text: str) -> str:
        """Convert Markdown formatting to clean HTML without breaking word boundaries."""
        import re
        escaped = html.escape(text)

        # Code blocks ```code```
        escaped = re.sub(
            r'```(.*?)```',
            lambda m: f'<pre style="background: rgba(8, 14, 28, 0.9); border: 1px solid rgba(0, 240, 255, 0.35); border-radius: 6px; padding: 8px; color: #00f0ff; font-family: Consolas;">{m.group(1)}</pre>',
            escaped,
            flags=re.DOTALL
        )

        # Inline code `code`
        escaped = re.sub(
            r'`([^`]+)`',
            r'<code style="background: rgba(0, 240, 255, 0.15); color: #00f0ff; padding: 2px 5px; border-radius: 4px; font-family: Consolas;">\1</code>',
            escaped
        )

        # Bold **text**
        escaped = re.sub(r'\*\*([^*]+)\*\*', r'<strong style="color: #ffffff;">\1</strong>', escaped)

        # Italic *text*
        escaped = re.sub(r'(?<!\*)\*([^*]+)\*(?!\*)', r'<em style="color: #7b9ec7;">\1</em>', escaped)

        # Links [text](url)
        escaped = re.sub(
            r'\[([^\]]+)\]\(([^)]+)\)',
            r'<a href="\2" style="color: #00f0ff; text-decoration: underline;">\1</a>',
            escaped
        )

        # Preserve line breaks with normal word-wrapping (never replace normal spaces with &nbsp;)
        return escaped.replace("\n", "<br/>")

    def append_assistant_response(self, text: str, success: bool = True, action_type: str = "info"):
        """Append assistant response formatted according to outcome."""
        timestamp = datetime.now().strftime("%H:%M:%S")

        # Pick accent color
        if action_type == "error" or not success:
            accent_color = COLORS["status_error"]
            header_title = "ALERT"
        elif action_type == "launch":
            accent_color = COLORS["status_success"]
            header_title = "SYSTEM"
        elif action_type == "help":
            accent_color = COLORS["cyan_glow"]
            header_title = "DIRECTIVES"
        else:
            accent_color = COLORS["blue_hover"]
            header_title = "OMEN"

        body_html = self._format_content_html(text)

        response_html = f"""
        <div style="margin: 6px 0 14px 0; font-family: 'Consolas', monospace; word-wrap: break-word;">
            <div style="margin-bottom: 3px;">
                <span style="color: {COLORS['text_muted']}; font-size: 11px;">[{timestamp}]</span>
                <span style="color: {accent_color}; font-weight: bold;"> [{header_title}] </span>
            </div>
            <div style="color: {COLORS['text_primary']}; padding-left: 12px; border-left: 2px solid {accent_color}; line-height: 1.45;">
                {body_html}
            </div>
        </div>
        """
        self.append(response_html)
        self.scroll_to_end()

    def clear_console(self):
        """Flush the view and redisplay standard banner."""
        self.clear()
        self.display_welcome_banner()

    def scroll_to_end(self):
        """Ensure view scrolls to the latest output."""
        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.setTextCursor(cursor)
