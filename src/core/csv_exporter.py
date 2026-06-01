"""
csv_exporter.py - Export questions to CSV in the exact format of 範例檔.csv
"""
import csv
import io
from pathlib import Path
from datetime import datetime
from typing import List, Union

from .quiz_generator import Question


def questions_to_csv_text(questions: List[Question]) -> str:
    """
    Convert questions to CSV string matching the exact format of 範例檔.csv.
    Each question is written as multiple rows (label: value style).
    """
    output = io.StringIO()
    writer = csv.writer(output, lineterminator="\r\n")

    for q in questions:
        writer.writerow([f"題目ID：{q.question_id}"])
        writer.writerow([f"難度：{q.difficulty}"])
        writer.writerow([f"圖片／資料：{q.image_data}"])
        writer.writerow([f"題目：{q.question}"])
        writer.writerow([f"(A)：{q.options['A']}"])
        writer.writerow([f"(B)：{q.options['B']}"])
        writer.writerow([f"(C)：{q.options['C']}"])
        writer.writerow([f"(D)：{q.options['D']}"])
        writer.writerow([f"正確答案：{q.answer}"])
        writer.writerow([f"考題重點：{q.key_point}"])
        writer.writerow([f"知識點：{q.knowledge_point}"])
        # Explanation may contain newlines → wrap in quotes via csv module
        writer.writerow([f"詳解：{q.explanation}"])

    return output.getvalue()


def export_to_csv(
    questions: List[Question],
    output_dir: Union[str, Path],
    chapter_name: str,
) -> str:
    """
    Write questions to a CSV file in output_dir.
    Returns the absolute path of the written file.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    # Sanitize chapter name for filename
    safe_chapter = "".join(c if c.isalnum() or c in "-_ " else "_" for c in chapter_name)
    filename = f"{safe_chapter}_{timestamp}.csv"
    file_path = output_dir / filename

    csv_text = questions_to_csv_text(questions)
    file_path.write_text(csv_text, encoding="utf-8-sig")  # utf-8-sig for Excel compatibility

    return str(file_path)
