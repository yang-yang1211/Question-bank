import sys
sys.stdout.reconfigure(encoding='utf-8')
import json
from src.core.quiz_generator import _extract_json_array, _parse_question

# 1. Existing robust extractor tests
q_json = '{"question":"小明有一塊扇形蛋糕","A":"選項A","B":"選項B","C":"選項C","D":"選項D","answer":"A","key_point":"測試重點","explanation":"1.步驟一 2.步驟二"}'

tests = [
    ("markdown fence", f"```json\n[{q_json}]\n```"),
    ("think tags",     f"<think>thinking content here</think>\n[{q_json}]"),
    ("plain array",    f"[{q_json},{q_json}]"),
    ("with preamble",  f"好的，以下是題目：\n[{q_json}]"),
    ("empty",          "這是一段無JSON的文字"),
]

all_pass = True
for label, text in tests:
    result = _extract_json_array(text)
    status = "OK" if result else "FAIL"
    if not result and label != "empty":
        all_pass = False
    print(f"[{status}] Extraction - {label}: got {len(result)} items")

# 2. Test standard _parse_question
raw = json.loads(q_json)
q = _parse_question(raw, "測試章節", 1, 1)
print(f"[{'OK' if q else 'FAIL'}] Parse - Standard: id={q.question_id if q else None}")
if not q: all_pass = False

# 3. Test Chinese Keys
chinese_q_json = '{"題目":"這是一題中文欄位題目","選項A":"選項A描述","選項B":"選項B描述","選項C":"選項C描述","選項D":"選項D描述","正確答案":"C","考題重點":"中文重點","詳解":"中文步驟"}'
raw_chinese = json.loads(chinese_q_json)
q_chinese = _parse_question(raw_chinese, "測試章節", 1, 2)
print(f"[{'OK' if q_chinese and q_chinese.answer == 'C' else 'FAIL'}] Parse - Chinese Keys: answer={q_chinese.answer if q_chinese else None}")
if not q_chinese or q_chinese.answer != 'C': all_pass = False

# 4. Test Lowercase and lenient answers
lenient_json = '{"question_text":"這是一題小寫與寬鬆答案題目","option_a":"選項A描述","option_b":"選項B描述","option_c":"選項C描述","option_d":"選項D描述","correct_answer":"(D)","keypoint":"重點","explain":"步驟"}'
raw_lenient = json.loads(lenient_json)
q_lenient = _parse_question(raw_lenient, "測試章節", 1, 3)
print(f"[{'OK' if q_lenient and q_lenient.answer == 'D' else 'FAIL'}] Parse - Lowercase/Lenient: answer={q_lenient.answer if q_lenient else None}")
if not q_lenient or q_lenient.answer != 'D': all_pass = False

# 5. Test another lenient answer style (like "A.")
lenient_json_2 = '{"question":"這是一題小寫與寬鬆答案題目","A":"A描述","B":"B描述","C":"C描述","D":"D描述","answer":"選項B","key_point":"重點","explanation":"步驟"}'
raw_lenient_2 = json.loads(lenient_json_2)
q_lenient_2 = _parse_question(raw_lenient_2, "測試章節", 1, 4)
print(f"[{'OK' if q_lenient_2 and q_lenient_2.answer == 'B' else 'FAIL'}] Parse - Lenient Option B: answer={q_lenient_2.answer if q_lenient_2 else None}")
if not q_lenient_2 or q_lenient_2.answer != 'B': all_pass = False

# 6. Test list types for key_point and explanation
list_type_json = '{"question":"測試列表題","A":"A","B":"B","C":"C","D":"D","answer":"A","key_point":["重點一", "重點二"],"explanation":["步驟一", "2. 步驟二"]}'
raw_list_type = json.loads(list_type_json)
q_list_type = _parse_question(raw_list_type, "測試章節", 1, 5)
if q_list_type:
    has_list_kp = q_list_type.key_point == "重點一，重點二"
    has_list_exp = q_list_type.explanation == "1. 步驟一\n2. 步驟二"
    status = "OK" if (has_list_kp and has_list_exp) else "FAIL"
    print(f"[{status}] Parse - List Types:\n  key_point: {q_list_type.key_point}\n  explanation:\n{q_list_type.explanation}")
    if status == "FAIL": all_pass = False
else:
    print("[FAIL] Parse - List Types failed to parse entirely")
    all_pass = False

print("\n所有測試全部通過!" if all_pass else "\n部分測試失敗!")
