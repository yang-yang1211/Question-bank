"""
generate_panel.py - Quiz generation panel
"""
import os
from pathlib import Path
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QSpinBox, QProgressBar, QTextEdit, QFrame,
    QMessageBox, QSizePolicy, QGroupBox, QGridLayout
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QObject
from PyQt6.QtGui import QFont, QDesktopServices
from PyQt6.QtCore import QUrl

from src.db.database import get_all_chapters, get_pdf_sources_by_chapter, add_generation_log
from src.core.pdf_manager import extract_text_from_pdf
from src.core.llm_client import OllamaClient, QUIZ_MODEL, OCR_MODEL
from src.core.quiz_generator import QuizGenerator
from src.core.csv_exporter import export_to_csv

OUTPUT_DIR = Path(__file__).parent.parent.parent / "output"
OLLAMA_URL = "http://localhost:11434"


# ── Worker Thread ─────────────────────────────────────────────────────────────

class GenerationWorker(QObject):
    progress = pyqtSignal(int, str)    # (percent 0-100, message)
    finished = pyqtSignal(str, int)    # (output_file_path, question_count)
    error = pyqtSignal(str)

    def __init__(
        self,
        chapter: str,
        total: int,
        d1: int, d2: int, d3: int,
    ):
        super().__init__()
        self.chapter = chapter
        self.total = total
        self.difficulty_dist = {1: d1, 2: d2, 3: d3}

    def run(self):
        client = OllamaClient(OLLAMA_URL)
        if not client.is_available():
            self.error.emit("無法連線至 Ollama 服務，請確認 Ollama 是否已啟動（ollama serve）")
            return

        # Step 1: Get PDF sources
        sources = get_pdf_sources_by_chapter(self.chapter)
        if not sources:
            self.error.emit(f"找不到章節《{self.chapter}》的 PDF 來源，請先在管理員面板新增")
            return

        # Step 2: Extract text from all PDFs
        all_text_parts = []
        for i, src in enumerate(sources):
            file_path = src["file_path"]
            if not os.path.exists(file_path):
                self.progress.emit(5, f"⚠ 檔案不存在，跳過：{src['file_name']}")
                continue

            self.progress.emit(
                int(5 + (i / len(sources)) * 35),
                f"📖 正在讀取 PDF（{i+1}/{len(sources)}）：{src['file_name']}",
            )

            def pdf_progress(cur, total_p, msg):
                pct = int(5 + (i / len(sources)) * 35 + (cur / max(total_p, 1)) * (35 / len(sources)))
                self.progress.emit(pct, msg)

            text = extract_text_from_pdf(
                file_path,
                vision_model=OCR_MODEL,
                ollama_url=OLLAMA_URL,
                progress_callback=pdf_progress,
            )
            all_text_parts.append(text)

        combined_text = "\n\n".join(all_text_parts)
        if not combined_text.strip():
            self.error.emit(
                "無法從 PDF 中萃取文字內容。\n\n"
                "您的 PDF 為掃描圖片格式，需要具備圖像辨識能力（vision）的模型才能讀取。\n\n"
                "目前使用的模型「" + OCR_MODEL + "」無法處理圖片。\n\n"
                "解決方式：\n"
                "1. 在 Ollama 安裝支援視覺的模型，例如：\n"
                "   ollama pull llava:7b\n"
                "   ollama pull qwen2-vl:7b\n"
                "2. 安裝後在 src/core/llm_client.py 中將 OCR_MODEL 改為對應模型名稱\n\n"
                "或者，請改用包含可選取文字的 PDF（非掃描版）。"
            )
            return

        self.progress.emit(40, f"✅ PDF 讀取完成，共 {len(combined_text)} 字，開始出題...")

        # Step 3: Generate questions
        generator = QuizGenerator(client, model=QUIZ_MODEL)
        difficulty_dist = {k: v for k, v in self.difficulty_dist.items() if v > 0}

        def gen_progress(cur, total_t, msg):
            pct = int(40 + (cur / max(total_t, 1)) * 55)
            self.progress.emit(min(pct, 94), msg)

        questions = generator.generate(
            content=combined_text,
            chapter=self.chapter,
            total=self.total,
            difficulty_distribution=difficulty_dist,
            progress_callback=gen_progress,
        )

        if not questions:
            self.error.emit("LLM 未能生成有效題目，請稍後再試或確認模型設定")
            return

        # Step 4: Export CSV
        self.progress.emit(95, "💾 正在儲存 CSV 檔案...")
        output_path = export_to_csv(questions, OUTPUT_DIR, self.chapter)
        add_generation_log(self.chapter, output_path, len(questions), QUIZ_MODEL)

        self.progress.emit(100, f"🎉 出題完成！共 {len(questions)} 題")
        self.finished.emit(output_path, len(questions))


# ── Generate Panel ────────────────────────────────────────────────────────────

class GeneratePanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._thread = None
        self._worker = None
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(20, 20, 20, 20)

        # ── Header ──────────────────────────────────────────────────────────
        header = QLabel("🎯 出題設定")
        header.setObjectName("panelHeader")
        layout.addWidget(header)

        desc = QLabel("選擇章節與題目設定後，LLM 將自動生成繁體中文單選題並輸出為 CSV。")
        desc.setObjectName("panelDesc")
        desc.setWordWrap(True)
        layout.addWidget(desc)

        # ── Settings group ───────────────────────────────────────────────────
        settings_frame = QFrame()
        settings_frame.setObjectName("addFrame")
        settings_layout = QGridLayout(settings_frame)
        settings_layout.setSpacing(12)

        # Chapter selection
        settings_layout.addWidget(QLabel("選擇章節："), 0, 0)
        self.chapter_combo = QComboBox()
        self.chapter_combo.setObjectName("comboField")
        self.chapter_combo.setMinimumWidth(300)
        self.chapter_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        settings_layout.addWidget(self.chapter_combo, 0, 1, 1, 3)

        # Total questions
        settings_layout.addWidget(QLabel("總題數："), 1, 0)
        self.total_spin = QSpinBox()
        self.total_spin.setRange(1, 100)
        self.total_spin.setValue(20)
        self.total_spin.setObjectName("spinField")
        self.total_spin.valueChanged.connect(self._auto_distribute)
        settings_layout.addWidget(self.total_spin, 1, 1)

        # Difficulty distribution
        diff_label = QLabel("難度分配：")
        settings_layout.addWidget(diff_label, 2, 0)

        self.d1_spin = QSpinBox()
        self.d1_spin.setRange(0, 100)
        self.d1_spin.setValue(5)
        self.d1_spin.setObjectName("spinField")
        self.d1_spin.setPrefix("難度1 基礎素養: ")

        self.d2_spin = QSpinBox()
        self.d2_spin.setRange(0, 100)
        self.d2_spin.setValue(7)
        self.d2_spin.setObjectName("spinField")
        self.d2_spin.setPrefix("難度2 應用素養: ")

        self.d3_spin = QSpinBox()
        self.d3_spin.setRange(0, 100)
        self.d3_spin.setValue(8)
        self.d3_spin.setObjectName("spinField")
        self.d3_spin.setPrefix("難度3 高層次: ")

        settings_layout.addWidget(self.d1_spin, 2, 1)
        settings_layout.addWidget(self.d2_spin, 2, 2)
        settings_layout.addWidget(self.d3_spin, 2, 3)

        # Model info
        settings_layout.addWidget(QLabel("使用模型："), 3, 0)
        model_label = QLabel(f"PDF讀取: {OCR_MODEL}　｜　出題: {QUIZ_MODEL}")
        model_label.setObjectName("modelLabel")
        settings_layout.addWidget(model_label, 3, 1, 1, 3)

        layout.addWidget(settings_frame)

        # ── Generate button ──────────────────────────────────────────────────
        self.generate_btn = QPushButton("⚡  開始出題")
        self.generate_btn.setObjectName("generateBtn")
        self.generate_btn.clicked.connect(self._start_generation)
        layout.addWidget(self.generate_btn)

        # ── Progress ─────────────────────────────────────────────────────────
        self.progress_bar = QProgressBar()
        self.progress_bar.setObjectName("progressBar")
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        self.status_label = QLabel("")
        self.status_label.setObjectName("statusLabel")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        # ── Log output ────────────────────────────────────────────────────────
        log_label = QLabel("執行紀錄")
        log_label.setObjectName("subHeader")
        layout.addWidget(log_label)

        self.log_text = QTextEdit()
        self.log_text.setObjectName("logBox")
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(180)
        layout.addWidget(self.log_text)

        # ── Output section ────────────────────────────────────────────────────
        self.result_frame = QFrame()
        self.result_frame.setObjectName("resultFrame")
        self.result_frame.setVisible(False)
        result_layout = QVBoxLayout(self.result_frame)

        self.result_label = QLabel()
        self.result_label.setObjectName("resultLabel")
        self.result_label.setWordWrap(True)
        result_layout.addWidget(self.result_label)

        open_btn = QPushButton("📁  開啟輸出資料夾")
        open_btn.setObjectName("secondaryBtn")
        open_btn.clicked.connect(self._open_output_dir)
        result_layout.addWidget(open_btn)

        layout.addWidget(self.result_frame)
        layout.addStretch()

        self._output_file = ""

    # ── Public ────────────────────────────────────────────────────────────────

    def refresh_chapters(self):
        """Reload chapter list from DB."""
        current = self.chapter_combo.currentText()
        self.chapter_combo.clear()
        chapters = get_all_chapters()
        self.chapter_combo.addItems(chapters)
        if current in chapters:
            self.chapter_combo.setCurrentText(current)

    # ── Actions ───────────────────────────────────────────────────────────────

    def _auto_distribute(self, total: int):
        # 指令3預設配置比例：難度1約25%, 難度2約35%, 難度3約40%
        d1 = max(1, round(total * 0.25))
        d3 = max(1, round(total * 0.40))
        d2 = max(0, total - d1 - d3)
        self.d1_spin.setValue(d1)
        self.d2_spin.setValue(d2)
        self.d3_spin.setValue(d3)

    def _start_generation(self):
        if self._thread and self._thread.isRunning():
            return

        chapter = self.chapter_combo.currentText().strip()
        if not chapter:
            QMessageBox.warning(self, "提示", "請先在管理員面板新增 PDF 來源，然後選擇章節")
            return

        total = self.total_spin.value()
        d1 = self.d1_spin.value()
        d2 = self.d2_spin.value()
        d3 = self.d3_spin.value()

        if d1 + d2 + d3 == 0:
            QMessageBox.warning(self, "提示", "難度分配合計必須大於 0")
            return

        # UI state
        self.generate_btn.setEnabled(False)
        self.generate_btn.setText("⏳  出題中...")
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(True)
        self.result_frame.setVisible(False)
        self.log_text.clear()
        self.status_label.setText("準備中...")

        # Worker thread
        self._thread = QThread()
        self._worker = GenerationWorker(chapter, total, d1, d2, d3)
        self._worker.moveToThread(self._thread)

        self._thread.started.connect(self._worker.run)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_finished)
        self._worker.error.connect(self._on_error)
        self._worker.finished.connect(self._thread.quit)
        self._worker.error.connect(self._thread.quit)
        self._thread.finished.connect(self._on_thread_done)

        self._thread.start()

    def _on_progress(self, percent: int, message: str):
        self.progress_bar.setValue(percent)
        self.status_label.setText(message)
        self.log_text.append(message)

    def _on_finished(self, output_file: str, count: int):
        self._output_file = output_file
        self.result_label.setText(
            f"✅ 成功生成 <b>{count}</b> 題，已儲存至：<br>"
            f"<code>{output_file}</code>"
        )
        self.result_frame.setVisible(True)

    def _on_error(self, message: str):
        QMessageBox.critical(self, "出題失敗", message)
        self.status_label.setText(f"❌ {message}")
        self.log_text.append(f"[錯誤] {message}")

    def _on_thread_done(self):
        self.generate_btn.setEnabled(True)
        self.generate_btn.setText("⚡  開始出題")

    def _open_output_dir(self):
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(OUTPUT_DIR)))
