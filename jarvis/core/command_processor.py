"""Command parser and execution engine for JARVIS.

Integrates AI Orchestration, structured tool execution, and Windows Application
Discovery while enforcing strict safety rules against arbitrary shell execution.
"""

import re
from typing import Dict, Any, Optional
from jarvis.core.launcher import AppLauncher, LaunchResult
from jarvis.core.system_info import SystemInfoCollector
from jarvis.core.database import Database


class CommandResponse:
    """Standardized response from the command processor."""
    def __init__(self, text: str, success: bool = True, action_type: str = "info", metadata: Optional[Dict[str, Any]] = None):
        self.text = text
        self.success = success
        self.action_type = action_type  # "launch", "info", "error", "clear", "help"
        self.metadata = metadata or {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "text": self.text,
            "success": self.success,
            "action_type": self.action_type,
            "metadata": self.metadata,
        }


class CommandProcessor:
    """Parses, validates, and dispatches user typed commands and natural-language queries."""

    def __init__(
        self,
        launcher: Optional[AppLauncher] = None,
        db: Optional[Database] = None,
        orchestrator: Optional[Any] = None
    ):
        self.db = db or Database()
        self.launcher = launcher or AppLauncher(self.db)

        # Lazy import AI components to avoid circular dependencies
        from jarvis.ai.tools import ToolRegistry
        from jarvis.ai.orchestrator import AIOrchestrator
        self.tool_registry = ToolRegistry(launcher=self.launcher, db=self.db)
        self.orchestrator = orchestrator or AIOrchestrator(tool_registry=self.tool_registry)

    def process(self, raw_input: str) -> CommandResponse:
        """Process a typed or spoken string safely without arbitrary shell evaluation."""
        if not raw_input or not raw_input.strip():
            return CommandResponse(
                text="Awaiting command. Type 'help' to review available directives.",
                success=False,
                action_type="info"
            )

        cmd = raw_input.strip()
        cmd_lower = cmd.lower()

        # 1. Check for dangerous shell metacharacters or arbitrary terminal execution attempts
        dangerous_patterns = [
            r"&&", r"\|\|", r"\|", r";", r"`", r"\$\(", r">", r"<",
            r"\brmdir\b", r"\bdel\b", r"\bformat\b", r"\bpowershell\b",
            r"\bcmd\b\s+/[ck]", r"\bcurl\b", r"\bwget\b", r"\bpython\s+-c\b"
        ]
        for pattern in dangerous_patterns:
            if re.search(pattern, cmd, re.IGNORECASE):
                self.db.record_command(cmd, "BLOCKED_SECURITY")
                return CommandResponse(
                    text=(
                        "SECURITY PROTOCOL ACTIVATED: Arbitrary terminal and shell command execution "
                        "is strictly prohibited. Direct system modification commands are blocked."
                    ),
                    success=False,
                    action_type="error"
                )

        # 2. Immediate Directives: Clear conversation
        if cmd_lower in ["clear", "cls", "clear screen", "clear log"]:
            return CommandResponse(
                text="Console display cleared.",
                success=True,
                action_type="clear"
            )

        # 3. Help / manual
        if cmd_lower in ["help", "commands", "?", "man", "directives"]:
            prov_name = self.orchestrator.provider.get_provider_name()
            help_text = (
                f"O.M.E.N. DIRECTIVES & PROTOCOLS [Active AI: {prov_name}]:\n"
                " • Natural Language       : Ask questions or describe tasks in plain English\n"
                "                           (e.g., 'Can you open my code editor?', 'Explain Python TypeError')\n"
                " • Call <Contact>         : Speed-dial (e.g., 'Call Boss', 'Call Mom', 'Call Boss on WhatsApp')\n"
                " • Check Emails           : Inspect unread inbox intelligence and messages from Boss\n"
                " • Daily Briefing         : Executive morning briefing (time, telemetry, inbox, reminders)\n"
                " • Phone Access           : Launch mobile companion gateway with QR pairing for smartphone\n"
                " • Open <Application>     : Launch any application (e.g., 'Open Spotify', 'Launch Discord', 'Open Chrome')\n"
                " • Show system information: Display hardware telemetry, memory, and CPU metrics\n"
                " • List apps              : Display discovered and registered applications\n"
                " • List skills            : Display all Skill Forge multi-step workflows\n"
                " • Run skill <name>       : Execute an automated workflow by name\n"
                " • Test skill <name>      : Dry-run simulate a workflow without side-effects\n"
                " • Test mic               : Run microphone hardware health check & diagnostics\n"
                " • Take note <text>       : Record a quick voice memo or idea to scratchpad\n"
                " • Contacts               : List or configure speed-dial communications directory\n"
                " • Set key <gemini|openai>: Configure AI provider API key securely\n"
                " • Status                 : Check system health and active AI intelligence engine\n"
                " • Clear                  : Flush console display"
            )
            return CommandResponse(text=help_text, success=True, action_type="help")

        # 4. Skill Forge directives: list skills
        if cmd_lower in ["list skills", "show skills", "skills", "skill forge"]:
            from jarvis.skills.storage import SkillStorage
            storage = SkillStorage(db=self.db)
            skills = storage.get_all_skills()
            if not skills:
                return CommandResponse(
                    text="No skills registered in Skill Forge. Create workflows in the Skill Forge view.",
                    success=True,
                    action_type="info"
                )
            lines = ["SKILL FORGE - REGISTERED WORKFLOWS:"]
            for s in skills:
                status_tag = "ENABLED" if s.enabled else "DISABLED"
                lines.append(f" • {s.name:<24} [{status_tag}] - {len(s.steps)} step(s)")
                if s.description:
                    lines.append(f"   Description: {s.description}")
            lines.append("\nTip: Type 'run skill <name>' to execute, or 'test skill <name>' for dry-run preview.")
            return CommandResponse(text="\n".join(lines), success=True, action_type="info")

        # 5. Run / Execute skill
        run_skill_match = re.match(r"^(?:run\s+skill|execute\s+skill)\s+(.+)$", cmd, re.IGNORECASE)
        if run_skill_match:
            skill_target = run_skill_match.group(1).strip()
            from jarvis.skills.storage import SkillStorage
            from jarvis.skills.engine import SkillExecutionEngine
            storage = SkillStorage(db=self.db)
            skill = storage.get_skill_by_name(skill_target)
            if not skill:
                return CommandResponse(
                    text=f"Skill '{skill_target}' not found in Skill Forge registry. Type 'list skills' to view available workflows.",
                    success=False,
                    action_type="error"
                )
            engine = SkillExecutionEngine(storage=storage)
            result = engine.execute_skill(skill, dry_run=False)
            res_lines = [f"SKILL EXECUTION REPORT: {skill.name} [{result.status}]"]
            for sr in result.step_results:
                icon = "✓" if sr.status == "SUCCEEDED" else "✗"
                res_lines.append(f" [{icon}] Step {sr.step_order} ({sr.label or sr.action_type}): {sr.message}")
            if result.error_message:
                res_lines.append(f"\nALERT: {result.error_message}")
            return CommandResponse(
                text="\n".join(res_lines),
                success=result.success,
                action_type="launch" if result.success else "error",
                metadata=result.to_dict()
            )

        # 6. Test / Dry run skill
        test_skill_match = re.match(r"^(?:test\s+skill|dry\s+run\s+skill)\s+(.+)$", cmd, re.IGNORECASE)
        if test_skill_match:
            skill_target = test_skill_match.group(1).strip()
            from jarvis.skills.storage import SkillStorage
            from jarvis.skills.engine import SkillExecutionEngine
            storage = SkillStorage(db=self.db)
            skill = storage.get_skill_by_name(skill_target)
            if not skill:
                return CommandResponse(
                    text=f"Skill '{skill_target}' not found in Skill Forge registry.",
                    success=False,
                    action_type="error"
                )
            engine = SkillExecutionEngine(storage=storage)
            result = engine.execute_skill(skill, dry_run=True)
            res_lines = [f"SKILL DRY-RUN PREVIEW: {skill.name} [{result.status}]"]
            for sr in result.step_results:
                res_lines.append(f" [PREVIEW] Step {sr.step_order} ({sr.label or sr.action_type}): {sr.message}")
            return CommandResponse(
                text="\n".join(res_lines),
                success=result.success,
                action_type="info",
                metadata=result.to_dict()
            )

        # 7. Status check
        if cmd_lower in ["status", "ping", "diagnostics status"]:
            prov_name = self.orchestrator.provider.get_provider_name()
            return CommandResponse(
                text=f"STATUS: All primary subsystems operational. Neural Engine: [{prov_name}] is active and ready for instructions.",
                success=True,
                action_type="info"
            )

        # 8. System info
        sysinfo_triggers = [
            "show system information", "system information", "system info",
            "sysinfo", "specs", "hardware info"
        ]
        if cmd_lower in sysinfo_triggers or cmd_lower == "diagnostics":
            report = SystemInfoCollector.get_formatted_report()
            self.db.record_command(cmd, "SUCCESS_SYSINFO")
            return CommandResponse(
                text=report,
                success=True,
                action_type="info"
            )

        # 9. List registered applications
        if cmd_lower in ["list apps", "show apps", "registered apps", "applications", "apps"]:
            apps = self.launcher.list_registered_applications()
            lines = ["REGISTERED APPLICATION SHORTCUTS:"]
            for a in apps:
                status_icon = "✓" if a["available"] else "✗ (Path missing)"
                aliases = ", ".join(a["aliases"])
                lines.append(f" • {a['name']:<15} [{status_icon}] - Aliases: {aliases}")
            lines.append("\nTip: Type 'open <name>' to launch any of the verified items above.")
            return CommandResponse(text="\n".join(lines), success=True, action_type="info")

        # 10. Microphone Diagnostics
        if cmd_lower in ["test mic", "mic test", "diagnostics mic", "check mic"]:
            from jarvis.voice.stt import SpeechRecognitionEngine
            stt = SpeechRecognitionEngine()
            diag = stt.run_diagnostics()
            lines = [
                "MICROPHONE SUBSYSTEM DIAGNOSTICS:",
                f" • Status           : {diag.get('status_message')}",
                f" • Default Device   : {diag.get('default_device') or 'None detected'}",
                f" • Audio Devices    : {diag.get('device_count')}",
                f" • Sample Rate      : {diag.get('sample_rate')} Hz",
                f" • Offline Vosk     : {'Installed' if diag.get('offline_model') else 'Not installed (Uses Google STT)'}",
            ]
            return CommandResponse(text="\n".join(lines), success=diag.get("microphone_available", False), action_type="info")

        # 11. Secure AI Configuration Directives (set key / set provider)
        key_match = re.match(r"^set\s+key\s+(gemini|openai|groq)\s+(.+)$", cmd, re.IGNORECASE)
        if key_match:
            provider_type = key_match.group(1).lower()
            api_key = key_match.group(2).strip()
            self.db.set_setting(f"{provider_type}_api_key", api_key)
            from jarvis.ai.provider import AIProviderFactory
            new_prov = AIProviderFactory.get_provider(preferred_provider=provider_type, api_key=api_key)
            self.orchestrator.set_provider(new_prov)
            return CommandResponse(
                text=f"Successfully configured and activated {new_prov.get_provider_name()}.",
                success=True,
                action_type="info"
            )

        provider_match = re.match(r"^set\s+provider\s+(gemini|openai|ollama|local)$", cmd, re.IGNORECASE)
        if provider_match:
            p_type = provider_match.group(1).lower()
            self.db.set_setting("ai_provider", p_type)
            from jarvis.ai.provider import AIProviderFactory
            new_prov = AIProviderFactory.get_provider(preferred_provider=p_type)
            self.orchestrator.set_provider(new_prov)
            return CommandResponse(
                text=f"Switched active AI provider to: {new_prov.get_provider_name()}.",
                success=True,
                action_type="info"
            )

        # 12. Phone Remote Access Gateway (Mobile Companion)
        if cmd_lower in ["phone access", "mobile companion", "phone", "mobile", "phone link", "qr code", "mobile link", "start mobile server"]:
            if not self.tool_registry._mobile_server:
                from jarvis.core.remote_gateway import MobileCompanionServer
                self.tool_registry._mobile_server = MobileCompanionServer(command_processor=self)
            else:
                self.tool_registry._mobile_server.command_processor = self
            res = self.tool_registry._mobile_server.start()
            url = self.tool_registry._mobile_server.get_access_url()
            out_text = (
                f"MOBILE COMPANION ONLINE:\n"
                f" • Connect Phone Browser: {url}\n"
                f" • Directives Supported : Voice Mic, 'Call Boss', 'Check Emails', 'Lock PC', Telemetry\n"
                f"Open the link above in your mobile browser (Safari/Chrome) to control O.M.E.N. from your phone."
            )
            self.db.record_command(cmd, "SUCCESS_MOBILE")
            return CommandResponse(text=out_text, success=True, action_type="launch", metadata={"url": url})

        # 13. Calling Directives (Speed-Dial: Call Boss, Call Mom, Dial)
        call_match = re.match(r"^(?:call|dial|phone\s+contact)\s+(?:the\s+)?([a-zA-Z0-9_\-\+]+(?:\s+[a-zA-Z0-9_\-\+]+)?)(?:\s+(?:on|via)\s+(whatsapp|teams|skype|phone))?$", cmd, re.IGNORECASE)
        if call_match:
            target_name = call_match.group(1).strip()
            ch = call_match.group(2) or ("whatsapp" if "whatsapp" in cmd_lower else "phone")
            from jarvis.core.telephony import TelephonyManager
            telephony = TelephonyManager(self.db)
            res = telephony.call_contact(target=target_name, channel=ch)
            self.db.record_command(cmd, "SUCCESS_CALL" if res["success"] else "FAILED_CALL")
            return CommandResponse(text=res["message"], success=res["success"], action_type="launch" if res["success"] else "error", metadata=res)

        # 14. Email Directives (Check emails, inbox)
        if cmd_lower in ["check emails", "check the emails", "emails", "inbox", "check inbox", "check my emails", "read emails", "unread emails"]:
            from jarvis.core.email_assistant import EmailAssistant
            assistant = EmailAssistant(self.db)
            summary = assistant.check_unread_summary()
            self.db.record_command(cmd, "SUCCESS_EMAIL")
            return CommandResponse(text=summary["formatted_report"], success=True, action_type="info", metadata=summary)

        # 15. Executive Daily Briefing
        if cmd_lower in ["daily briefing", "morning briefing", "executive briefing", "briefing", "brief me", "morning report"]:
            from jarvis.core.briefing import BriefingManager
            mgr = BriefingManager(self.db)
            briefing = mgr.generate_briefing()
            self.db.record_command(cmd, "SUCCESS_BRIEFING")
            return CommandResponse(text=briefing["report_text"], success=True, action_type="info", metadata=briefing)

        # 16. Quick Notes Directives
        note_match = re.match(r"^(?:take\s+a?\s*note|new\s+note|record\s+memo|note\s+down)\s*[:\-]?\s*(.+)$", cmd, re.IGNORECASE)
        if note_match:
            from jarvis.core.notes import NotesManager
            mgr = NotesManager(self.db)
            res = mgr.add_note(note_match.group(1).strip())
            self.db.record_command(cmd, "SUCCESS_NOTE")
            return CommandResponse(text=res["message"], success=res["success"], action_type="info", metadata=res)
        if cmd_lower in ["notes", "show notes", "list notes", "my notes"]:
            from jarvis.core.notes import NotesManager
            mgr = NotesManager(self.db)
            res = mgr.list_notes()
            return CommandResponse(text=res["message"], success=True, action_type="info", metadata=res)

        # 17. Contacts Directory Directives
        if cmd_lower in ["contacts", "list contacts", "show contacts"]:
            from jarvis.core.telephony import TelephonyManager
            telephony = TelephonyManager(self.db)
            contacts = telephony.list_contacts()
            lines = [f"COMMUNICATIONS DIRECTORY ({len(contacts)} contacts):"]
            for c in contacts:
                aliases = f" (Aliases: {c['alias']})" if c.get('alias') else ""
                lines.append(f" • {c['name']:<16} | Phone: {c.get('phone') or 'N/A'}{aliases} | Channel: {c.get('preferred_channel')}")
            lines.append("\nTip: Type 'call <name>' or 'call boss' to speed dial, or 'set contact <name> phone <num>' to update.")
            return CommandResponse(text="\n".join(lines), success=True, action_type="info")

        set_contact_match = re.match(r"^set\s+contact\s+([a-zA-Z0-9_]+)\s+phone\s+([\+\d\-\(\)\s]+)$", cmd, re.IGNORECASE)
        if set_contact_match:
            c_name = set_contact_match.group(1).strip()
            c_phone = set_contact_match.group(2).strip()
            from jarvis.core.telephony import TelephonyManager
            telephony = TelephonyManager(self.db)
            res = telephony.set_contact(name=c_name, phone=c_phone, alias=c_name.lower())
            return CommandResponse(text=res["message"], success=res["success"], action_type="info", metadata=res)

        # 18. Direct application launcher commands (e.g., 'Open Notepad', 'Open Chrome', 'notepad')
        explicit_launch = re.match(r"^(?:open|launch|start|run)\s+(.+)$", cmd, re.IGNORECASE)
        if explicit_launch:
            app_target = explicit_launch.group(1).strip()
            result: LaunchResult = self.launcher.launch(app_target)
            self.db.record_command(cmd, "SUCCESS_LAUNCH" if result.success else "FAILED_LAUNCH")
            return CommandResponse(
                text=result.message,
                success=result.success,
                action_type="launch" if result.success else "error",
                metadata=result.to_dict()
            )

        app = self.db.get_application_by_name(cmd)
        if app:
            result: LaunchResult = self.launcher.launch(app["name"])
            self.db.record_command(cmd, "SUCCESS_LAUNCH" if result.success else "FAILED_LAUNCH")
            return CommandResponse(
                text=result.message,
                success=result.success,
                action_type="launch" if result.success else "error",
                metadata=result.to_dict()
            )

        # 13. Check for known naked shell command attempts
        known_shell_cmds = [
            "dir", "ls", "cd", "echo", "type", "mkdir", "md", "copy", "move", "ren",
            "ipconfig", "ifconfig", "ping", "netstat", "tasklist", "taskkill", "whoami"
        ]
        tokens = cmd_lower.split()
        first_token = tokens[0] if tokens else ""
        if first_token in known_shell_cmds and len(tokens) <= 3 and not any(w in cmd_lower for w in ["open", "search", "how", "what", "why", "explain", "code"]):
            self.db.record_command(cmd, "REJECTED_SHELL")
            return CommandResponse(
                text=(
                    f"Command '{first_token}' unrecognized. "
                    "Arbitrary terminal commands are disallowed by safety architecture. "
                    "Type 'help' to see authorized directives."
                ),
                success=False,
                action_type="error"
            )

        # 14. Dispatch Natural Language Query to AI Orchestrator
        try:
            orch_result = self.orchestrator.process_query(cmd)
            self.db.record_command(cmd, "SUCCESS_AI" if orch_result.success else "FAILED_AI")
            return CommandResponse(
                text=orch_result.text,
                success=orch_result.success,
                action_type=orch_result.action_type,
                metadata=orch_result.to_dict()
            )
        except Exception as exc:
            self.db.record_command(cmd, "ERROR_AI")
            return CommandResponse(
                text=f"Task orchestration error: {exc}",
                success=False,
                action_type="error"
            )
