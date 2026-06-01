"""
pdf_manager.py - PDF text extraction using PyMuPDF + Ollama vision model (if available)
Handles scanned (image-based) PDFs.
"""
import base64
import fitz  # PyMuPDF
from typing import Callable, Optional, List

# Phrases that indicate the vision model cannot see images (text-only fallback response)
_OCR_FAILURE_PHRASES = [
    "無法直接查看",
    "無法解析圖片",
    "無法直接看圖",
    "無法讀取圖",
    "cannot see",
    "can't see",
    "unable to view",
    "unable to process image",
    "I cannot view",
]


def _page_to_base64(page: fitz.Page, dpi: int = 150) -> str:
    """Render a PDF page to a base64-encoded PNG string."""
    mat = fitz.Matrix(dpi / 72, dpi / 72)
    pix = page.get_pixmap(matrix=mat)
    img_bytes = pix.tobytes("png")
    return base64.b64encode(img_bytes).decode("utf-8")


def _ocr_failed(response_text: str) -> bool:
    """Return True if the vision model's response indicates it cannot see the image."""
    lower = response_text.lower()
    for phrase in _OCR_FAILURE_PHRASES:
        if phrase.lower() in lower:
            return True
    return False


def extract_text_from_pdf(
    file_path: str,
    vision_model: str = "qwen2:7b",
    ollama_url: str = "http://localhost:11434",
    progress_callback: Optional[Callable[[int, int, str], None]] = None,
) -> str:
    """
    Extract all text from a PDF file.
    - If the PDF has selectable text → use PyMuPDF directly (fast).
    - If the PDF is image-based (scanned) → try Ollama vision model OCR.
    - If vision model cannot see images → return empty string (caller handles error).

    progress_callback(current_page, total_pages, message)
    Returns:
        str: extracted text content, or "" if OCR failed (use caller to handle)
    """
    import requests

    doc = fitz.open(file_path)
    total_pages = doc.page_count
    all_text_parts: List[str] = []
    ocr_failed_pages = 0

    for page_num, page in enumerate(doc):
        if progress_callback:
            progress_callback(page_num + 1, total_pages, f"正在讀取第 {page_num+1}/{total_pages} 頁...")

        # Try selectable text first (fast path)
        text = page.get_text().strip()
        if text:
            all_text_parts.append(f"[第 {page_num+1} 頁]\n{text}")
            continue

        # Fallback: vision model OCR
        if progress_callback:
            progress_callback(page_num + 1, total_pages,
                              f"第 {page_num+1} 頁為圖片，嘗試 OCR 辨識...")

        b64_img = _page_to_base64(page, dpi=150)
        prompt = (
            "請仔細閱讀這張數學教材圖片，將圖片中所有文字、數學算式、題目、"
            "說明文字完整以繁體中文輸出。請保留原始排版結構（標題、段落、例題等），"
            "不要省略任何內容。只輸出圖片中的文字內容，不要加入任何額外說明。"
        )
        try:
            resp = requests.post(
                f"{ollama_url}/api/generate",
                json={
                    "model": vision_model,
                    "prompt": prompt,
                    "images": [b64_img],
                    "stream": False,
                    "options": {"temperature": 0.1},
                },
                timeout=120,
            )
            resp.raise_for_status()
            ocr_text = resp.json().get("response", "").strip()

            # Detect if vision model refused or failed to read the image
            if _ocr_failed(ocr_text):
                ocr_failed_pages += 1
                if progress_callback:
                    progress_callback(page_num + 1, total_pages,
                                      f"⚠ 第 {page_num+1} 頁 OCR 失敗：模型無法辨識圖片")
                # Don't append the failure message as content
            else:
                all_text_parts.append(f"[第 {page_num+1} 頁]\n{ocr_text}")

        except Exception as e:
            if progress_callback:
                progress_callback(page_num + 1, total_pages,
                                  f"⚠ 第 {page_num+1} 頁 OCR 出錯：{e}")

    doc.close()

    result = "\n\n".join(all_text_parts).strip()

    # If all pages were image-based but OCR failed for all of them, result will be ""
    # The caller (generate_panel) should check for this and show a clear error.
    return result
