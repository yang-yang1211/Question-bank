"""
quiz_generator.py - Core quiz generation logic using Ollama LLM
Generates Traditional Chinese single-choice questions matching the CSV output format.
"""
import re
import json
from dataclasses import dataclass, field
from typing import Callable, Optional, List, Dict

from .llm_client import OllamaClient, QUIZ_MODEL


@dataclass
class Question:
    question_id: str = ""
    difficulty: int = 1
    image_data: str = "無"
    question: str = ""
    options: dict = field(default_factory=lambda: {"A": "", "B": "", "C": "", "D": ""})
    answer: str = ""
    key_point: str = ""
    knowledge_point: str = ""
    explanation: str = ""


SYSTEM_PROMPT = """你是一位資深的「108 課綱素養導向 K–12 原創教材命題專家」，專門製作國小數學科的素養導向選擇題。

【命題核心原則】
1. 絕對原創：所有題幹情境、選項內容皆須全新創作，禁止引用任何現成題型
2. 使用台灣繁體中文，難度與內容符合 108 課綱國小數學科範圍
3. 每題必須同時符合：
   - 情境真實化：題幹來自生活情境、社會現象或公共議題
   - 任務導向：要求學生進行判斷、分析、比較或推論，不可只靠背誦作答
   - 概念應用：將數學概念放入情境中應用，不直接考名詞定義

【絕對禁止】
- 不考名詞定義或條文內容
- 不出無情境的知識敘述題
- 不讓學生「不看情境也能作答」
- 選項不可只是名詞排列，必須有推論差異
- 禁止使用 LaTeX 數學符號（如 \\( \\) \\frac \\times \\sqrt）；數學算式請用純文字表示（例如：3×5=15，1/2，√9）

你必須嚴格遵守輸出格式，每道題目都是 JSON 格式，不要輸出任何額外說明文字。"""

QUESTION_PROMPT_TEMPLATE = """請根據以下教材內容，產出 {count} 道難度 {difficulty} 的素養導向繁體中文單選題。

【難度定義】
- 難度1（基礎素養）：單一知識點的生活情境應用，考查基礎判斷能力
- 難度2（應用素養）：結合多個知識點或較複雜情境，需要比較與分析
- 難度3（高層次素養）：整合多線索、多 KP 的推論或價值判斷題，不可透過單一步驟作答

【知識點章節】{chapter}

【教材內容】
{content}

【試題輸出格式】（請直接輸出 JSON 陣列，不要有任何前言或後語）
[
  {{
    "question": "含生活情境的完整題幹",
    "A": "選項A（有意義的干擾項）",
    "B": "選項B",
    "C": "選項C",
    "D": "選項D",
    "answer": "A",
    "key_point": "素養能力描述（含判斷類型）",
    "explanation": "1. 第一步說明。2. 第二步說明。3. 為何排除其他選項。"
  }}
]

【產出要求】
- 四個選項都必須是合理的干擾項，不可有明顯錯誤的選項
- 詳解須逐步條列，清楚說明推論過程與排除理由
- 數學算式使用純文字（例如：3×5=15，1/2，2的平方），禁止使用 LaTeX 語法（如 \\( \\)）
- 只輸出 JSON 陣列，不要輸出任何前言、後語或說明"""


# ── JSON Parsing Utilities ────────────────────────────────────────────────────

def _strip_wrapper(text: str) -> str:
    """Remove common LLM wrappers and fix multiple classes of invalid JSON syntax."""
    # Strip <think>...</think> (qwen3 thinking mode)
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    # Strip markdown code fences: ```json ... ``` or ``` ... ```
    text = re.sub(r"```(?:json)?\s*", "", text)
    text = text.replace("```", "")
    # Fix invalid JSON backslash escapes from LaTeX math notation.
    # Valid JSON escapes after backslash: " \ / b f n r t u
    # LaTeX sequences like \( \) \times \frac \cdot produce invalid JSON.
    # Replace \X (where X is not a valid JSON escape char) by removing the backslash.
    # This turns \(3×5=15\) into (3×5=15) safely.
    text = re.sub(r'\\(?!["\\\x2fbfnrtu])', '', text)
    # Fix JavaScript-style string concatenation: "part1" + "part2" → "part1part2"
    # LLMs sometimes split explanation strings with JS + operator
    text = re.sub(r'"\s*\+\s*"', '', text)
    # Fix trailing commas before } or ] (e.g. {"key": "val",})
    # This is invalid in JSON but common in LLM output
    text = re.sub(r',\s*([}\]])', r'\1', text)
    return text.strip()


def _find_json_arrays(text: str) -> List[list]:
    """
    Find all top-level JSON arrays in text using bracket counting.
    More reliable than regex for nested JSON with Chinese characters.
    """
    results = []
    i = 0
    while i < len(text):
        if text[i] == '[':
            depth = 0
            in_string = False
            escape = False
            start = i
            found_end = False
            for j in range(i, len(text)):
                ch = text[j]
                if escape:
                    escape = False
                    continue
                if ch == '\\' and in_string:
                    escape = True
                    continue
                if ch == '"':
                    in_string = not in_string
                    continue
                if in_string:
                    continue
                if ch == '[':
                    depth += 1
                elif ch == ']':
                    depth -= 1
                    if depth == 0:
                        candidate = text[start:j + 1]
                        try:
                            parsed = json.loads(candidate)
                            if isinstance(parsed, list) and parsed:
                                results.append(parsed)
                        except json.JSONDecodeError:
                            pass
                        i = j + 1
                        found_end = True
                        break
            if not found_end:
                i += 1
        else:
            i += 1
    return results


def _extract_json_array(text: str) -> list:
    """
    Robustly extract a JSON array from LLM response text.
    Handles: <think> tags, markdown fences, partial output, nested JSON.
    """
    text = _strip_wrapper(text)

    # 1. Try bracket-matching to find all JSON arrays
    arrays = _find_json_arrays(text)
    if arrays:
        # Return the largest array found (most likely the full question list)
        return max(arrays, key=len)

    # 2. Fallback: try parsing the whole cleaned text
    try:
        parsed = json.loads(text)
        if isinstance(parsed, list):
            return parsed
    except json.JSONDecodeError:
        pass

    return []


# ── Question Parser ───────────────────────────────────────────────────────────

def _parse_question(raw: object, chapter: str, difficulty: int, idx: int) -> Optional[Question]:
    """Parse a raw dict into a Question object, validating required fields with high tolerance."""
    # Guard: LLM may return strings or other types inside the array
    if not isinstance(raw, dict):
        return None
    # Normalize keys to uppercase for case-insensitive lookup
    norm = {}
    for k, v in raw.items():
        if isinstance(k, str):
            norm[k.strip().upper()] = v
        else:
            norm[k] = v

    # Extract question text robustly
    question_text = norm.get("QUESTION") or norm.get("QUESTION_TEXT") or norm.get("題幹") or norm.get("題目")
    if not question_text or not str(question_text).strip():
        return None

    # Extract options robustly
    opt_A = norm.get("A") or norm.get("OPTION_A") or norm.get("OPTIONA") or norm.get("選項A")
    opt_B = norm.get("B") or norm.get("OPTION_B") or norm.get("OPTIONB") or norm.get("選項B")
    opt_C = norm.get("C") or norm.get("OPTION_C") or norm.get("OPTIONC") or norm.get("選項C")
    opt_D = norm.get("D") or norm.get("OPTION_D") or norm.get("OPTIOND") or norm.get("選項D")
    
    if not (opt_A and opt_B and opt_C and opt_D):
        return None

    # Extract answer robustly
    ans_raw = norm.get("ANSWER") or norm.get("CORRECT_ANSWER") or norm.get("正確答案") or norm.get("答案")
    if not ans_raw:
        return None
        
    ans_str = str(ans_raw).strip()
    # Search for first A, B, C, D (case-insensitive) in the answer string
    match = re.search(r"\b([A-D])\b|([A-D])", ans_str, re.IGNORECASE)
    if not match:
        return None
    answer = (match.group(1) or match.group(2)).upper()

    # Extract key point and explanation robustly
    key_point = norm.get("KEY_POINT") or norm.get("KEYPOINT") or norm.get("考題重點") or norm.get("重點") or "無"
    explanation = norm.get("EXPLANATION") or norm.get("EXPLAIN") or norm.get("詳解") or norm.get("說明") or "無"

    if isinstance(key_point, list):
        key_point = "，".join(str(item).strip() for item in key_point)
    else:
        key_point = str(key_point).strip()

    if isinstance(explanation, list):
        formatted_items = []
        for i, item in enumerate(explanation):
            item_str = str(item).strip()
            if re.match(r"^\d+[\.\s、：]", item_str):
                formatted_items.append(item_str)
            else:
                formatted_items.append(f"{i+1}. {item_str}")
        explanation = "\n".join(formatted_items)
    else:
        explanation = str(explanation).strip()

    return Question(
        question_id=str(idx).zfill(3),
        difficulty=difficulty,
        image_data="無",
        question=str(question_text).strip(),
        options={
            "A": str(opt_A).strip(),
            "B": str(opt_B).strip(),
            "C": str(opt_C).strip(),
            "D": str(opt_D).strip(),
        },
        answer=answer,
        key_point=key_point,
        knowledge_point=chapter,
        explanation=explanation,
    )


# ── Quiz Generator ────────────────────────────────────────────────────────────

class QuizGenerator:
    def __init__(self, ollama_client: OllamaClient, model: str = QUIZ_MODEL):
        self.client = ollama_client
        self.model = model

    def generate(
        self,
        content: str,
        chapter: str,
        total: int = 20,
        difficulty_distribution: Optional[Dict[int, int]] = None,
        start_id: int = 1,
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
        max_retries: int = 3,
        batch_size: int = 3,
    ) -> List[Question]:
        """
        Generate quiz questions from extracted PDF text.

        Uses small-batch generation (batch_size questions per LLM call) to
        maximise parse yield — asking for fewer questions per call keeps the
        LLM output short and well-formed.

        difficulty_distribution: {1: n, 2: n, 3: n}
            defaults to {1:5, 2:7, 3:8} (matching 指令三)
        batch_size: questions per LLM call (default 3 — reliable for 4b models)
        progress_callback(current_batch, total_batches, message)
        """
        if difficulty_distribution is None:
            d1 = max(1, round(total * 0.25))
            d3 = max(1, round(total * 0.40))
            d2 = max(0, total - d1 - d3)
            difficulty_distribution = {1: d1, 2: d2, 3: d3}

        all_questions: List[Question] = []
        current_id = start_id

        tasks = [
            (diff, count)
            for diff, count in sorted(difficulty_distribution.items())
            if count > 0
        ]

        # Pre-calculate total number of batches for progress bar
        total_batches = sum(
            -(-count // batch_size)  # ceiling division
            for _, count in tasks
        )
        batch_done = 0

        # Truncate content to avoid token overflow (~5000 chars keeps context clean)
        truncated = content[:5000] if len(content) > 5000 else content

        for difficulty, count in tasks:
            parsed_for_diff: List[Question] = []
            needed = count
            fail_streak = 0  # consecutive failed batches — stop after max_retries

            while len(parsed_for_diff) < needed and fail_streak < max_retries:
                remaining = needed - len(parsed_for_diff)
                ask_count = min(batch_size, remaining)

                if progress_callback:
                    progress_callback(
                        batch_done,
                        total_batches,
                        f"難度{difficulty}｜已生成 {len(parsed_for_diff)}/{needed} 題，"
                        f"本批次請求 {ask_count} 題...",
                    )

                prompt = QUESTION_PROMPT_TEMPLATE.format(
                    count=ask_count,
                    difficulty=difficulty,
                    chapter=chapter,
                    content=truncated,
                )

                try:
                    response = self.client.generate(
                        model=self.model,
                        prompt=prompt,
                        system=SYSTEM_PROMPT,
                        temperature=0.75,
                        timeout=300,
                    )

                    raw_list = _extract_json_array(response)
                    got = 0
                    for raw in raw_list:
                        q = _parse_question(raw, chapter, difficulty, current_id)
                        if q:
                            parsed_for_diff.append(q)
                            current_id += 1
                            got += 1
                        if len(parsed_for_diff) >= needed:
                            break

                    batch_done += 1

                    if got == 0:
                        fail_streak += 1
                        preview = response[:300].replace("\n", " ")
                        if progress_callback:
                            progress_callback(
                                batch_done, total_batches,
                                f"⚠ 難度{difficulty} 本批次解析失敗"
                                f"（連續失敗 {fail_streak}/{max_retries}）"
                                f" LLM回應：{preview}..."
                            )
                    else:
                        fail_streak = 0  # reset streak on any success

                except Exception as e:
                    fail_streak += 1
                    batch_done += 1
                    if progress_callback:
                        progress_callback(
                            batch_done, total_batches,
                            f"❌ 難度{difficulty} 生成出錯"
                            f"（{fail_streak}/{max_retries}）: {e}"
                        )

            all_questions.extend(parsed_for_diff)
            if progress_callback:
                progress_callback(
                    batch_done, total_batches,
                    f"✅ 難度{difficulty} 完成：{len(parsed_for_diff)}/{needed} 題"
                )

        if progress_callback:
            progress_callback(
                total_batches, total_batches,
                f"🎉 出題完成，共 {len(all_questions)} 題"
            )

        return all_questions
