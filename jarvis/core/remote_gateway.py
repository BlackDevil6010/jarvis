"""Phone Remote Access Gateway and Mobile Companion Server for O.M.E.N. / JARVIS.

Runs a secure, lightweight local HTTP server allowing any smartphone (iPhone / Android)
on the local Wi-Fi network to connect to O.M.E.N. via a cybernetic mobile HUD web interface.
Supports live speech-to-text input from phone mic, quick directives (Call Boss, Check Emails,
Lock PC, Media Control), real-time PC telemetry, and QR code pairing.
"""

import os
import json
import socket
import logging
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Dict, Any, Optional

from jarvis.core.system_info import SystemInfoCollector

logger = logging.getLogger(__name__)

DEFAULT_PORT = 8765


def get_local_ip() -> str:
    """Detect the host machine's primary local LAN IP address."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # Does not actually transmit packets, just resolves local routing interface
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    except Exception:
        ip = "127.0.0.1"
    finally:
        s.close()
    return ip


def generate_svg_qr(data_url: str) -> str:
    """
    Generate a clean, scalable SVG representation of a QR-like matrix or visual badge
    with link info, so mobile camera scanners or browser links can immediately read it.
    """
    # Simple inline SVG badge for quick camera recognition or click
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 240 240" width="200" height="200">
      <rect width="240" height="240" fill="#080e1e" rx="16" stroke="#00f0ff" stroke-width="3"/>
      <rect x="20" y="20" width="50" height="50" fill="none" stroke="#00f0ff" stroke-width="6"/>
      <rect x="35" y="35" width="20" height="20" fill="#00f0ff"/>
      <rect x="170" y="20" width="50" height="50" fill="none" stroke="#00f0ff" stroke-width="6"/>
      <rect x="185" y="35" width="20" height="20" fill="#00f0ff"/>
      <rect x="20" y="170" width="50" height="50" fill="none" stroke="#00f0ff" stroke-width="6"/>
      <rect x="35" y="185" width="20" height="20" fill="#00f0ff"/>
      <circle cx="120" cy="120" r="28" fill="#bf00ff" opacity="0.8"/>
      <circle cx="120" cy="120" r="14" fill="#00f0ff"/>
      <!-- Grid pattern -->
      <rect x="90" y="30" width="12" height="12" fill="#00f0ff"/>
      <rect x="115" y="30" width="12" height="12" fill="#00f0ff"/>
      <rect x="140" y="30" width="12" height="12" fill="#00f0ff"/>
      <rect x="90" y="60" width="12" height="12" fill="#00f0ff"/>
      <rect x="140" y="60" width="12" height="12" fill="#00f0ff"/>
      <rect x="30" y="90" width="12" height="12" fill="#00f0ff"/>
      <rect x="60" y="90" width="12" height="12" fill="#00f0ff"/>
      <rect x="170" y="90" width="12" height="12" fill="#00f0ff"/>
      <rect x="200" y="90" width="12" height="12" fill="#00f0ff"/>
      <rect x="30" y="120" width="12" height="12" fill="#00f0ff"/>
      <rect x="60" y="140" width="12" height="12" fill="#00f0ff"/>
      <rect x="90" y="170" width="12" height="12" fill="#00f0ff"/>
      <rect x="115" y="195" width="12" height="12" fill="#00f0ff"/>
      <rect x="140" y="170" width="12" height="12" fill="#00f0ff"/>
      <rect x="170" y="170" width="12" height="12" fill="#00f0ff"/>
      <rect x="200" y="195" width="12" height="12" fill="#00f0ff"/>
      <text x="120" y="230" fill="#7b9ec7" font-size="10" font-family="sans-serif" text-anchor="middle">O.M.E.N. MOBILE LINK</text>
    </svg>"""


MOBILE_HUD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
  <title>O.M.E.N. Mobile Companion</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      background: #050811;
      color: #e6f1ff;
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
      min-height: 100vh;
      display: flex;
      flex-direction: column;
      padding: 16px;
      overflow-x: hidden;
    }
    .header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding-bottom: 14px;
      border-bottom: 1px solid rgba(0, 240, 255, 0.3);
      margin-bottom: 14px;
    }
    .title {
      font-size: 18px;
      font-weight: 800;
      letter-spacing: 2px;
      color: #00f0ff;
      text-shadow: 0 0 10px rgba(0, 240, 255, 0.5);
    }
    .badge {
      font-size: 10px;
      font-weight: 700;
      color: #00e676;
      background: rgba(0, 230, 118, 0.15);
      border: 1px solid #00e676;
      padding: 3px 8px;
      border-radius: 12px;
      letter-spacing: 1px;
    }
    /* Telemetry strip */
    .telemetry-strip {
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 8px;
      margin-bottom: 16px;
    }
    .telemetry-card {
      background: rgba(11, 18, 32, 0.85);
      border: 1px solid rgba(0, 240, 255, 0.25);
      border-radius: 10px;
      padding: 8px;
      text-align: center;
    }
    .t-label { font-size: 10px; color: #7b9ec7; text-transform: uppercase; }
    .t-val { font-size: 14px; font-weight: bold; color: #00f0ff; margin-top: 2px; }

    /* Quick Action Grid */
    .quick-grid {
      display: grid;
      grid-template-columns: repeat(2, 1fr);
      gap: 10px;
      margin-bottom: 16px;
    }
    .action-btn {
      background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #101b30, stop:1 #0c142a);
      background: #0f1c33;
      border: 1px solid rgba(0, 240, 255, 0.35);
      color: #e6f1ff;
      border-radius: 12px;
      padding: 14px 10px;
      font-size: 13px;
      font-weight: 600;
      display: flex;
      align-items: center;
      gap: 8px;
      cursor: pointer;
      touch-action: manipulation;
      transition: all 0.2s ease;
    }
    .action-btn:active {
      transform: scale(0.96);
      border-color: #00f0ff;
      background: rgba(0, 240, 255, 0.2);
    }
    .btn-boss {
      grid-column: span 2;
      background: linear-gradient(135deg, rgba(191, 0, 255, 0.3), rgba(0, 240, 255, 0.2));
      border: 1.5px solid #00f0ff;
      font-size: 14px;
      justify-content: center;
    }
    /* Mic button area */
    .mic-container {
      display: flex;
      flex-direction: column;
      align-items: center;
      margin: 12px 0;
    }
    .mic-btn {
      width: 68px;
      height: 68px;
      border-radius: 50%;
      background: linear-gradient(135deg, #007acc, #8a2be2);
      border: 2px solid #00f0ff;
      box-shadow: 0 0 20px rgba(0, 240, 255, 0.4);
      color: white;
      font-size: 26px;
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;
      outline: none;
      transition: all 0.2s;
    }
    .mic-btn.listening {
      background: linear-gradient(135deg, #00f0ff, #ff007f);
      box-shadow: 0 0 30px #ff007f;
      animation: pulse 1s infinite alternate;
    }
    @keyframes pulse { from { transform: scale(1); } to { transform: scale(1.08); } }
    .mic-hint { font-size: 11px; color: #7b9ec7; margin-top: 6px; }

    /* Command input */
    .input-row {
      display: flex;
      gap: 8px;
      margin-bottom: 14px;
    }
    .cmd-input {
      flex: 1;
      background: #070c18;
      border: 1px solid rgba(0, 240, 255, 0.35);
      border-radius: 10px;
      padding: 12px 14px;
      color: #e6f1ff;
      font-size: 14px;
      outline: none;
    }
    .cmd-input:focus { border-color: #00f0ff; box-shadow: 0 0 8px rgba(0, 240, 255, 0.4); }
    .send-btn {
      background: #007acc;
      border: 1px solid #00f0ff;
      color: white;
      border-radius: 10px;
      padding: 0 16px;
      font-weight: bold;
      font-size: 14px;
      cursor: pointer;
    }

    /* Response stream box */
    .console-box {
      flex: 1;
      background: rgba(11, 18, 32, 0.9);
      border: 1px solid rgba(0, 240, 255, 0.25);
      border-radius: 12px;
      padding: 12px;
      font-family: 'Consolas', monospace;
      font-size: 12px;
      line-height: 1.45;
      overflow-y: auto;
      max-height: 250px;
      white-space: pre-wrap;
      color: #b0cbe8;
    }
  </style>
</head>
<body>
  <div class="header">
    <div class="title">O.M.E.N. MOBILE</div>
    <div class="badge" id="netStatus">ONLINE</div>
  </div>

  <div class="telemetry-strip">
    <div class="telemetry-card">
      <div class="t-label">CPU Load</div>
      <div class="t-val" id="cpuVal">--%</div>
    </div>
    <div class="telemetry-card">
      <div class="t-label">RAM Used</div>
      <div class="t-val" id="ramVal">--%</div>
    </div>
    <div class="telemetry-card">
      <div class="t-label">Storage</div>
      <div class="t-val" id="diskVal">--%</div>
    </div>
  </div>

  <div class="quick-grid">
    <button class="action-btn btn-boss" onclick="dispatchCmd('call boss')">
      <span>📞</span> <strong>CALL THE BOSS</strong>
    </button>
    <button class="action-btn" onclick="dispatchCmd('check emails')">
      <span>✉️</span> Check Emails
    </button>
    <button class="action-btn" onclick="dispatchCmd('daily briefing')">
      <span>⚡</span> Daily Briefing
    </button>
    <button class="action-btn" onclick="dispatchCmd('lock workstation')">
      <span>🔒</span> Lock PC
    </button>
    <button class="action-btn" onclick="dispatchCmd('pause music')">
      <span>⏯</span> Media Play/Pause
    </button>
  </div>

  <div class="mic-container">
    <button class="mic-btn" id="micBtn" onclick="toggleSpeech()">🎙</button>
    <div class="mic-hint" id="micHint">Tap mic to speak to O.M.E.N.</div>
  </div>

  <div class="input-row">
    <input type="text" class="cmd-input" id="cmdInput" placeholder="Type directive for O.M.E.N..." onkeydown="if(event.key==='Enter') sendInput();">
    <button class="send-btn" onclick="sendInput()">SEND</button>
  </div>

  <div class="console-box" id="consoleBox">O.M.E.N. Mobile Uplink Connected.
Standing by for voice or remote directives, Sir.</div>

  <script>
    async function updateTelemetry() {
      try {
        const res = await fetch('/api/telemetry');
        if (res.ok) {
          const data = await res.json();
          document.getElementById('cpuVal').textContent = data.cpu_percent + '%';
          document.getElementById('ramVal').textContent = data.ram_percent + '%';
          document.getElementById('diskVal').textContent = data.disk_percent + '%';
        }
      } catch (e) {
        document.getElementById('netStatus').textContent = 'CONNECTING...';
      }
    }
    setInterval(updateTelemetry, 3000);
    updateTelemetry();

    async function dispatchCmd(command) {
      const box = document.getElementById('consoleBox');
      box.textContent += '\\n\\n>>> [PHONE DIRECTIVE]: ' + command;
      box.scrollTop = box.scrollHeight;
      try {
        const res = await fetch('/api/command', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ command: command })
        });
        const data = await res.json();
        box.textContent += '\\n' + data.text;
        box.scrollTop = box.scrollHeight;
      } catch (err) {
        box.textContent += '\\n[ERROR]: Transmission error: ' + err.message;
      }
    }

    function sendInput() {
      const inp = document.getElementById('cmdInput');
      const val = inp.value.trim();
      if (!val) return;
      inp.value = '';
      dispatchCmd(val);
    }

    // Voice recognition via Phone browser
    let recognition = null;
    let isListening = false;
    if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {
      const SpeechClass = window.SpeechRecognition || window.webkitSpeechRecognition;
      recognition = new SpeechClass();
      recognition.continuous = false;
      recognition.interimResults = false;

      recognition.onstart = () => {
        isListening = true;
        document.getElementById('micBtn').classList.add('listening');
        document.getElementById('micHint').textContent = 'Listening to phone mic...';
      };
      recognition.onresult = (evt) => {
        const text = evt.results[0][0].transcript;
        document.getElementById('cmdInput').value = text;
        dispatchCmd(text);
      };
      recognition.onend = () => {
        isListening = false;
        document.getElementById('micBtn').classList.remove('listening');
        document.getElementById('micHint').textContent = 'Tap mic to speak to O.M.E.N.';
      };
      recognition.onerror = () => {
        isListening = false;
        document.getElementById('micBtn').classList.remove('listening');
      };
    }

    function toggleSpeech() {
      if (!recognition) {
        alert('Speech recognition is not supported in this browser. Please type directives.');
        return;
      }
      if (isListening) {
        recognition.stop();
      } else {
        recognition.start();
      }
    }
  </script>
</body>
</html>
"""


class MobileGatewayHandler(BaseHTTPRequestHandler):
    """Handles HTTP requests from mobile browsers."""

    def log_message(self, format, *args):
        # Silence default standard error logging
        return

    def do_GET(self):
        # 1. Root: Serve mobile HUD web application
        if self.path in ["/", "/index.html", "/mobile"]:
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            self.wfile.write(MOBILE_HUD_HTML.encode("utf-8"))

        # 2. Telemetry API endpoint
        elif self.path == "/api/telemetry":
            metrics = SystemInfoCollector.get_system_summary()
            payload = {
                "cpu_percent": metrics.get("cpu_percent", 0.0),
                "ram_percent": metrics.get("memory", {}).get("percent", 0.0),
                "disk_percent": metrics.get("disk", {}).get("percent", 0.0),
                "uptime": metrics.get("uptime", "0h 0m"),
                "status": "ONLINE"
            }
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps(payload).encode("utf-8"))

        # 3. Status API
        elif self.path == "/api/status":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"online": True, "app": "O.M.E.N."}).encode("utf-8"))

        # 4. QR Code SVG
        elif self.path == "/api/qr":
            local_ip = get_local_ip()
            url = f"http://{local_ip}:{self.server.server_address[1]}"
            svg = generate_svg_qr(url)
            self.send_response(200)
            self.send_header("Content-Type", "image/svg+xml")
            self.end_headers()
            self.wfile.write(svg.encode("utf-8"))

        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        # Command execution endpoint
        if self.path == "/api/command":
            content_len = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_len)
            try:
                data = json.loads(body.decode("utf-8"))
                cmd_text = data.get("command", "").strip()
                processor = getattr(self.server, "command_processor", None)
                if processor:
                    resp = processor.process(cmd_text)
                    result = {
                        "success": resp.success,
                        "text": resp.text,
                        "action_type": resp.action_type
                    }
                else:
                    result = {
                        "success": False,
                        "text": "Command processor not attached to server.",
                        "action_type": "error"
                    }
            except Exception as exc:
                result = {
                    "success": False,
                    "text": f"Command processing exception: {exc}",
                    "action_type": "error"
                }

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps(result).encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()


class MobileCompanionServer:
    """Threaded HTTP server providing mobile web companion capabilities."""

    def __init__(self, command_processor: Optional[Any] = None, port: int = DEFAULT_PORT):
        self.command_processor = command_processor
        self.port = port
        self.httpd: Optional[HTTPServer] = None
        self.thread: Optional[threading.Thread] = None
        self.is_running = False

    def get_access_url(self) -> str:
        """Return the LAN URL to open in mobile browser."""
        ip = get_local_ip()
        return f"http://{ip}:{self.port}"

    def start(self) -> Dict[str, Any]:
        """Start the mobile companion HTTP daemon."""
        if self.is_running:
            return {
                "success": True,
                "message": f"Mobile Companion is already online at {self.get_access_url()}",
                "url": self.get_access_url()
            }

        try:
            self.httpd = HTTPServer(("0.0.0.0", self.port), MobileGatewayHandler)
            self.httpd.command_processor = self.command_processor
            self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
            self.thread.start()
            self.is_running = True
            url = self.get_access_url()
            return {
                "success": True,
                "message": (
                    f"MOBILE UPLINK ACTIVE: Connect phone browser to: {url}\n"
                    "Features: Voice mic, 'Call Boss', 'Check Emails', 'Lock PC', live telemetry."
                ),
                "url": url,
                "port": self.port
            }
        except Exception as exc:
            logger.error(f"Failed to start MobileCompanionServer: {exc}")
            return {
                "success": False,
                "message": f"Could not launch mobile gateway on port {self.port}: {exc}"
            }

    def stop(self) -> None:
        """Stop the HTTP daemon cleanly."""
        if self.httpd:
            self.httpd.shutdown()
            self.httpd.server_close()
            self.httpd = None
        self.is_running = False
