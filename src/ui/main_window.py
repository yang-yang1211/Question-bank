"""
main_window.py - Main application window for QuizSysteam
"""
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QPushButton, QLabel, QStackedWidget, QFrame, QSizePolicy
)
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QFont, QIcon, QPalette, QColor

from src.ui.admin_panel import AdminPanel
from src.ui.generate_panel import GeneratePanel
from src.db.database import init_db
from src.core.llm_client import OllamaClient


NAV_ITEMS = [
    ("🎯", "出題", "generate"),
    ("📂", "管理來源", "admin"),
]

STYLESHEET = """
/* ─── Base ─────────────────────────────────────────────── */
QMainWindow, QWidget {
    background-color: #0f1117;
    color: #e0e6f0;
    font-family: "Microsoft JhengHei UI", "Segoe UI", sans-serif;
    font-size: 14px;
}

/* ─── Sidebar ───────────────────────────────────────────── */
#sidebar {
    background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
        stop:0 #1a1f2e, stop:1 #131720);
    border-right: 1px solid #2a2f45;
    min-width: 180px;
    max-width: 200px;
}

#appTitle {
    color: #7c9ef8;
    font-size: 18px;
    font-weight: bold;
    padding: 24px 16px 8px 16px;
    letter-spacing: 1px;
}

#appSubtitle {
    color: #4a5568;
    font-size: 11px;
    padding: 0 16px 20px 16px;
}

#navBtn {
    background: transparent;
    color: #8892a4;
    border: none;
    text-align: left;
    padding: 12px 16px;
    font-size: 14px;
    border-radius: 8px;
    margin: 2px 8px;
}
#navBtn:hover {
    background: #1e2436;
    color: #c8d0e0;
}
#navBtn[active="true"] {
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
        stop:0 #2d3f7c, stop:1 #1a2456);
    color: #7c9ef8;
    font-weight: bold;
    border-left: 3px solid #7c9ef8;
}

#sidebarDivider {
    background: #2a2f45;
    max-height: 1px;
    margin: 8px 16px;
}

#statusDot {
    font-size: 11px;
    padding: 4px 16px 16px 16px;
}

/* ─── Content Area ──────────────────────────────────────── */
#contentArea {
    background: #0f1117;
}

/* ─── Panel headers ─────────────────────────────────────── */
#panelHeader {
    font-size: 22px;
    font-weight: bold;
    color: #e8eeff;
    padding-bottom: 4px;
}
#panelDesc {
    color: #6b7a99;
    font-size: 13px;
    padding-bottom: 8px;
}
#subHeader {
    font-size: 15px;
    font-weight: bold;
    color: #aabbdd;
    padding-top: 4px;
}

/* ─── Frames ────────────────────────────────────────────── */
#addFrame {
    background: #171c2e;
    border: 1px solid #2a3050;
    border-radius: 12px;
    padding: 16px;
}
#resultFrame {
    background: #0d1f12;
    border: 1px solid #1a4a2a;
    border-radius: 12px;
    padding: 16px;
}

/* ─── Inputs ────────────────────────────────────────────── */
#inputField, #comboField, #spinField {
    background: #1e2436;
    color: #d0d8f0;
    border: 1px solid #2e3a55;
    border-radius: 8px;
    padding: 8px 12px;
    selection-background-color: #3a4a80;
}
#inputField:focus, #comboField:focus, #spinField:focus {
    border: 1px solid #4a6af0;
    background: #1e2844;
}
QSpinBox#spinField {
    padding: 6px 10px;
}
QComboBox#comboField::drop-down {
    border: none;
    width: 24px;
}
QComboBox#comboField QAbstractItemView {
    background: #1e2436;
    color: #d0d8f0;
    selection-background-color: #2d3f7c;
    border: 1px solid #2e3a55;
}

/* ─── Buttons ───────────────────────────────────────────── */
#primaryBtn, #generateBtn {
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
        stop:0 #3a5af0, stop:1 #2a40c0);
    color: white;
    border: none;
    border-radius: 8px;
    padding: 10px 20px;
    font-weight: bold;
    font-size: 14px;
}
#primaryBtn:hover, #generateBtn:hover {
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
        stop:0 #4a6aff, stop:1 #3a50d0);
}
#primaryBtn:disabled, #generateBtn:disabled {
    background: #2a2f45;
    color: #5a6080;
}
#generateBtn {
    padding: 14px 24px;
    font-size: 16px;
    border-radius: 10px;
}

#secondaryBtn {
    background: #1e2436;
    color: #7c9ef8;
    border: 1px solid #3a4a70;
    border-radius: 8px;
    padding: 8px 16px;
    font-weight: bold;
}
#secondaryBtn:hover {
    background: #252d45;
    border-color: #5a7aff;
}

#dangerBtn {
    background: #2e1820;
    color: #f87c7c;
    border: 1px solid #5a2a2a;
    border-radius: 8px;
    padding: 8px 16px;
    font-weight: bold;
}
#dangerBtn:hover {
    background: #3e2030;
    border-color: #f87c7c;
}

/* ─── Table ─────────────────────────────────────────────── */
#sourceTable {
    background: #171c2e;
    alternate-background-color: #1b2038;
    gridline-color: #2a3050;
    border: 1px solid #2a3050;
    border-radius: 8px;
    selection-background-color: #2d3f7c;
    color: #c8d0e0;
}
#sourceTable QHeaderView::section {
    background: #1e2436;
    color: #7c9ef8;
    padding: 8px;
    border: none;
    border-bottom: 1px solid #2a3050;
    font-weight: bold;
}

/* ─── Progress ──────────────────────────────────────────── */
#progressBar {
    background: #1e2436;
    border: none;
    border-radius: 6px;
    height: 10px;
    text-align: center;
    color: transparent;
}
#progressBar::chunk {
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
        stop:0 #3a5af0, stop:1 #7c9ef8);
    border-radius: 6px;
}

/* ─── Log box ───────────────────────────────────────────── */
#logBox {
    background: #0d1020;
    color: #7aef9a;
    border: 1px solid #1e2830;
    border-radius: 8px;
    font-family: "Cascadia Mono", "Consolas", monospace;
    font-size: 12px;
    padding: 8px;
}

/* ─── Labels ────────────────────────────────────────────── */
#fileLabelSmall {
    color: #6b7a99;
    font-size: 12px;
    font-style: italic;
}
#modelLabel {
    color: #5a8a7a;
    font-size: 12px;
}
#statusLabel {
    color: #8892b4;
    font-size: 12px;
    font-style: italic;
}
#resultLabel {
    color: #7af0a0;
    font-size: 13px;
}
"""


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        init_db()
        self._setup_window()
        self._setup_ui()
        self._nav_to("generate")

    def _setup_window(self):
        self.setWindowTitle("QuizSysteam — 智慧出題系統")
        self.setMinimumSize(1000, 680)
        self.resize(1200, 760)
        self.setStyleSheet(STYLESHEET)

    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Sidebar ──────────────────────────────────────────────────────────
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(0, 0, 0, 0)
        sidebar_layout.setSpacing(0)

        title = QLabel("QuizSysteam")
        title.setObjectName("appTitle")
        sidebar_layout.addWidget(title)

        subtitle = QLabel("智慧出題系統")
        subtitle.setObjectName("appSubtitle")
        sidebar_layout.addWidget(subtitle)

        div = QFrame()
        div.setObjectName("sidebarDivider")
        sidebar_layout.addWidget(div)

        self._nav_buttons: dict[str, QPushButton] = {}
        for icon, label, key in NAV_ITEMS:
            btn = QPushButton(f"{icon}  {label}")
            btn.setObjectName("navBtn")
            btn.setCheckable(False)
            btn.clicked.connect(lambda _, k=key: self._nav_to(k))
            sidebar_layout.addWidget(btn)
            self._nav_buttons[key] = btn

        sidebar_layout.addStretch()

        # Ollama status
        self._status_dot = QLabel("⬤ Ollama 未連線")
        self._status_dot.setObjectName("statusDot")
        self._status_dot.setStyleSheet("color: #f87c7c; font-size: 11px; padding: 4px 16px 16px 16px;")
        sidebar_layout.addWidget(self._status_dot)
        self._check_ollama()

        root.addWidget(sidebar)

        # ── Content stack ─────────────────────────────────────────────────────
        content = QFrame()
        content.setObjectName("contentArea")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)

        self._stack = QStackedWidget()

        self._generate_panel = GeneratePanel()
        self._admin_panel = AdminPanel()
        self._admin_panel.sources_changed.connect(self._generate_panel.refresh_chapters)

        self._stack.addWidget(self._generate_panel)
        self._stack.addWidget(self._admin_panel)
        content_layout.addWidget(self._stack)

        root.addWidget(content)

        # Init chapters
        self._generate_panel.refresh_chapters()

    def _nav_to(self, key: str):
        panel_map = {
            "generate": (0, self._generate_panel),
            "admin": (1, self._admin_panel),
        }
        idx, panel = panel_map[key]
        self._stack.setCurrentIndex(idx)

        for k, btn in self._nav_buttons.items():
            btn.setProperty("active", k == key)
            btn.style().unpolish(btn)
            btn.style().polish(btn)

        if key == "admin":
            self._admin_panel.refresh_table()
        elif key == "generate":
            self._generate_panel.refresh_chapters()

    def _check_ollama(self):
        client = OllamaClient()
        if client.is_available():
            self._status_dot.setText("⬤ Ollama 已連線")
            self._status_dot.setStyleSheet("color: #7af0a0; font-size: 11px; padding: 4px 16px 16px 16px;")
        else:
            self._status_dot.setText("⬤ Ollama 未連線")
            self._status_dot.setStyleSheet("color: #f87c7c; font-size: 11px; padding: 4px 16px 16px 16px;")
