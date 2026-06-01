"""
admin_panel.py - Admin panel for managing PDF sources
"""
import os
from pathlib import Path
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QFileDialog,
    QLineEdit, QMessageBox, QAbstractItemView, QFrame, QSizePolicy
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QIcon, QColor

from src.db.database import (
    add_pdf_source, delete_pdf_source, get_all_pdf_sources
)


class AdminPanel(QWidget):
    sources_changed = pyqtSignal()  # emitted when sources are added/deleted

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
        self.refresh_table()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(20, 20, 20, 20)

        # ── Header ──────────────────────────────────────────────────────────
        header = QLabel("📂 PDF 來源管理")
        header.setObjectName("panelHeader")
        layout.addWidget(header)

        desc = QLabel("新增教材 PDF 並指定章節名稱，作為 LLM 出題的知識來源。")
        desc.setObjectName("panelDesc")
        desc.setWordWrap(True)
        layout.addWidget(desc)

        # ── Add section ─────────────────────────────────────────────────────
        add_frame = QFrame()
        add_frame.setObjectName("addFrame")
        add_layout = QVBoxLayout(add_frame)
        add_layout.setSpacing(10)

        add_title = QLabel("新增 PDF 來源")
        add_title.setObjectName("subHeader")
        add_layout.addWidget(add_title)

        row1 = QHBoxLayout()
        self.chapter_input = QLineEdit()
        self.chapter_input.setPlaceholderText("章節名稱（例：1-3 應用問題的列式與求解）")
        self.chapter_input.setObjectName("inputField")
        row1.addWidget(self.chapter_input)
        add_layout.addLayout(row1)

        row2 = QHBoxLayout()
        self.file_label = QLabel("尚未選擇檔案")
        self.file_label.setObjectName("fileLabelSmall")
        self.file_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        row2.addWidget(self.file_label)

        self.browse_btn = QPushButton("📂  選擇 PDF")
        self.browse_btn.setObjectName("secondaryBtn")
        self.browse_btn.clicked.connect(self._browse_pdf)
        row2.addWidget(self.browse_btn)
        add_layout.addLayout(row2)

        self.add_btn = QPushButton("➕  新增來源")
        self.add_btn.setObjectName("primaryBtn")
        self.add_btn.clicked.connect(self._add_source)
        add_layout.addWidget(self.add_btn)

        layout.addWidget(add_frame)

        # ── Table ───────────────────────────────────────────────────────────
        table_header = QLabel("已匯入的 PDF 來源")
        table_header.setObjectName("subHeader")
        layout.addWidget(table_header)

        self.table = QTableWidget()
        self.table.setObjectName("sourceTable")
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["ID", "章節名稱", "檔案名稱", "建立時間"])
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        layout.addWidget(self.table)

        # ── Delete button ────────────────────────────────────────────────────
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self.delete_btn = QPushButton("🗑  刪除選取")
        self.delete_btn.setObjectName("dangerBtn")
        self.delete_btn.clicked.connect(self._delete_selected)
        btn_row.addWidget(self.delete_btn)
        layout.addLayout(btn_row)

        self._selected_file = ""

    # ── Actions ──────────────────────────────────────────────────────────────

    def _browse_pdf(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "選擇 PDF 檔案", "", "PDF 文件 (*.pdf)"
        )
        if path:
            self._selected_file = path
            self.file_label.setText(Path(path).name)

    def _add_source(self):
        chapter = self.chapter_input.text().strip()
        if not chapter:
            QMessageBox.warning(self, "提示", "請輸入章節名稱")
            return
        if not self._selected_file:
            QMessageBox.warning(self, "提示", "請選擇 PDF 檔案")
            return
        if not os.path.exists(self._selected_file):
            QMessageBox.warning(self, "錯誤", "找不到所選檔案，請重新選擇")
            return

        add_pdf_source(chapter, self._selected_file)
        self.chapter_input.clear()
        self.file_label.setText("尚未選擇檔案")
        self._selected_file = ""
        self.refresh_table()
        self.sources_changed.emit()
        QMessageBox.information(self, "成功", f"已新增《{chapter}》的 PDF 來源")

    def _delete_selected(self):
        selected = self.table.selectedItems()
        if not selected:
            QMessageBox.warning(self, "提示", "請先選取要刪除的資料列")
            return

        row = self.table.currentRow()
        source_id = int(self.table.item(row, 0).text())
        chapter = self.table.item(row, 1).text()

        reply = QMessageBox.question(
            self,
            "確認刪除",
            f"確定要刪除《{chapter}》的 PDF 來源嗎？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            delete_pdf_source(source_id)
            self.refresh_table()
            self.sources_changed.emit()

    def refresh_table(self):
        sources = get_all_pdf_sources()
        self.table.setRowCount(len(sources))
        for row, src in enumerate(sources):
            self.table.setItem(row, 0, QTableWidgetItem(str(src["id"])))
            self.table.setItem(row, 1, QTableWidgetItem(src["chapter_name"]))
            self.table.setItem(row, 2, QTableWidgetItem(src["file_name"]))
            self.table.setItem(row, 3, QTableWidgetItem(src["created_at"]))
