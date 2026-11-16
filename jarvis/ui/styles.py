"""Futuristic Holographic Glassmorphism Theme for JARVIS (Deep Navy, Cyber Cyan, Neon Violet)."""

from jarvis.config import COLORS

CYBER_STYLE = f"""
QMainWindow {{
    background-color: {COLORS['bg_root']};
}}

QWidget#CentralWidget {{
    background-color: transparent;
}}

/* Universal Scrollbar */
QScrollBar:vertical {{
    background: rgba(8, 14, 30, 0.6);
    width: 6px;
    margin: 0px;
    border-radius: 3px;
}}

QScrollBar::handle:vertical {{
    background: rgba(0, 240, 255, 0.3);
    min-height: 20px;
    border-radius: 3px;
}}

QScrollBar::handle:vertical:hover {{
    background: {COLORS['cyan_glow']};
}}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0px;
}}

/* Console View in Glassmorphism Card */
QFrame#ConsoleCard {{
    background: rgba(14, 22, 45, 0.75);
    border: 1px solid rgba(0, 240, 255, 0.35);
    border-radius: 16px;
    padding: 6px;
}}

QTextEdit#ConsoleView {{
    background-color: transparent;
    border: none;
    color: {COLORS['text_primary']};
    font-family: 'Consolas', 'Courier New', monospace;
    font-size: 12px;
    line-height: 1.5;
    padding: 8px;
    selection-background-color: {COLORS['blue_accent']};
    selection-color: #ffffff;
}}

/* Status Badge Frame */
QFrame#StatusBadge {{
    background: rgba(16, 26, 52, 0.8);
    border: 1px solid rgba(0, 240, 255, 0.3);
    border-radius: 12px;
    padding: 2px 10px;
}}

QLabel#StatusText {{
    font-family: 'Consolas', monospace;
    font-size: 11px;
    font-weight: bold;
}}

/* Skill Forge Theme Integration */
QFrame#SkillForgeContainer {{
    background: rgba(12, 18, 40, 0.85);
    border: 1.5px solid rgba(0, 240, 255, 0.35);
    border-radius: 18px;
    margin: 10px 14px;
}}

QListWidget {{
    background: rgba(10, 16, 32, 0.8);
    border: 1px solid rgba(0, 240, 255, 0.25);
    border-radius: 10px;
    color: {COLORS['text_primary']};
    padding: 6px;
}}

QListWidget::item:selected {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 rgba(0, 122, 204, 0.6), stop:1 rgba(138, 43, 226, 0.6));
    border: 1px solid {COLORS['cyan_glow']};
    border-radius: 6px;
    color: #ffffff;
}}

QTableWidget {{
    background: rgba(10, 16, 32, 0.8);
    border: 1px solid rgba(0, 240, 255, 0.25);
    border-radius: 10px;
    color: {COLORS['text_primary']};
    gridline-color: rgba(23, 43, 77, 0.6);
}}

QHeaderView::section {{
    background: rgba(16, 26, 52, 0.9);
    color: {COLORS['cyan_glow']};
    border: 1px solid rgba(0, 240, 255, 0.2);
    font-weight: bold;
    padding: 6px;
}}
"""
