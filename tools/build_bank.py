#!/usr/bin/env python3
"""從考選部試題與答案 PDF 建立題庫 questions.json。

用法：python3 tools/build_bank.py
- 試題檔：pdf/<年度考試代碼>_<科目代碼>_<科目>.pdf，例如 114180_1201_民法概要.pdf
- 答案檔：檔名含 ANS（標準答案）或 MOD（更正答案，優先使用）
新增年度時把 PDF 放進 pdf/ 再執行一次即可。
"""
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PDF_DIR = ROOT / "pdf"
OUT = ROOT / "data" / "questions.json"

# 考選部 PDF 用私用區字元當選項框 (A)(B)(C)(D)
MARKS = ["", "", "", ""]
LETTERS = "ABCD"

SUBJECTS = {
    "民法": "民法概要",
    "估價": "不動產估價概要",
    "土地法": "土地法與土地相關稅法概要",
    "經紀": "不動產經紀相關法規概要",
}


def subject_of(name):
    for key, full in SUBJECTS.items():
        if key in name:
            return full
    raise ValueError(f"無法判斷科目：{name}")


def pdftotext(path, layout=False):
    args = ["pdftotext"] + (["-layout"] if layout else []) + [str(path), "-"]
    return subprocess.run(args, capture_output=True, text=True, check=True).stdout


def join_lines(lines):
    out = ""
    for ln in lines:
        ln = ln.strip()
        if not ln:
            continue
        if out and re.match(r"[A-Za-z0-9%]", out[-1]) and re.match(r"[A-Za-z0-9]", ln[0]):
            out += " "
        out += ln
    return out


def clean(s):
    lines = [
        ln for ln in s.split("\n")
        if not re.fullmatch(r"\s*(代號：\s*\d+|頁次：.*|（請接背面）|（背面）|（正面）|全一張)\s*", ln)
    ]
    return join_lines(lines)


def parse_questions(path):
    text = pdftotext(path)
    start = text.find("乙、測驗題部分")
    if start < 0:
        raise ValueError(f"{path.name}：找不到測驗題部分")
    body = text[start:]
    questions = []
    pos = body.find("\n1 ")
    n = 1
    while pos >= 0:
        a = body.find(MARKS[0], pos)
        if a < 0:
            break
        stem = clean(body[pos + len(f"\n{n} "):a])
        opts = []
        cur = a
        for i in range(4):
            nxt_mark = body.find(MARKS[i + 1], cur + 1) if i < 3 else -1
            if i < 3:
                end = nxt_mark
            else:
                nq = body.find(f"\n{n + 1} ", cur)
                end = nq if nq >= 0 else len(body)
            opts.append(clean(body[cur + 1:end]))
            cur = end
        questions.append({"no": n, "q": stem, "options": opts})
        n += 1
        pos = body.find(f"\n{n} ", cur - 1) if cur < len(body) else -1
        if pos >= 0 and body.find(MARKS[0], pos) < 0:
            break
    return questions


def parse_answers(path):
    text = pdftotext(path, layout=True)
    answers = []
    for ln in text.split("\n"):
        if ln.strip().startswith("答案"):
            answers += re.findall(r"[A-DＡ-Ｄ#＃]", ln[ln.index("答案") + 2:])
    norm = {"Ａ": "A", "Ｂ": "B", "Ｃ": "C", "Ｄ": "D", "＃": "#"}
    answers = [norm.get(a, a) for a in answers]
    notes = {}
    remark = text[text.find("備"):] if "備" in text else ""
    remark = remark.translate(str.maketrans("ＡＢＣＤ", "ABCD"))
    for m in re.finditer(r"第\s*(\d+)\s*題([^。；\n]*)", remark):
        no, desc = int(m.group(1)), m.group(2)
        if "一律給分" in desc:
            notes[no] = {"accept": list(LETTERS), "note": "一律給分"}
        else:
            acc = re.findall(r"[ABCD]", desc.split("者")[0])
            if acc:
                notes[no] = {"accept": acc, "note": f"更正：答{'或'.join(acc)}均給分"}
    result = []
    for i, a in enumerate(answers, 1):
        if i in notes:
            result.append(notes[i])
        elif a == "#":
            raise ValueError(f"{path.name} 第{i}題標註#但備註無法解析")
        else:
            result.append({"accept": [a]})
    return result


def main():
    bank = []
    problems = []
    for qpdf in sorted(PDF_DIR.glob("*.pdf")):
        m = re.match(r"(\d{6})_(\d{4})_(.+)\.pdf$", qpdf.name)
        if not m:
            continue
        exam, code, _ = m.groups()
        year = int(exam[:3])
        subj = subject_of(qpdf.name)
        ans_file = None
        for kind in ("MOD", "ANS"):
            cands = list(PDF_DIR.glob(f"{exam}_{kind}{code}_*.pdf"))
            if cands:
                ans_file = cands[0]
                break
        if not ans_file:
            problems.append(f"{qpdf.name}：找不到答案檔")
            continue
        qs = parse_questions(qpdf)
        ans = parse_answers(ans_file)
        if len(qs) != len(ans):
            problems.append(f"{qpdf.name}：題數 {len(qs)} 與答案數 {len(ans)} 不符")
            continue
        for q, a in zip(qs, ans):
            if not q["q"] or any(not o for o in q["options"]):
                problems.append(f"{qpdf.name} 第{q['no']}題：題目或選項為空")
            item = {
                "id": f"{year}-{code[-2:]}-{q['no']:02d}",
                "year": year,
                "subject": subj,
                "no": q["no"],
                "q": q["q"],
                "options": q["options"],
                "answer": a["accept"],
            }
            if "note" in a:
                item["note"] = a["note"]
            bank.append(item)
        print(f"{year} {subj}: {len(qs)} 題（答案：{ans_file.name}）")
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(bank, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"共 {len(bank)} 題 → {OUT.relative_to(ROOT)}")
    if problems:
        print("\n需要檢查：")
        for p in problems:
            print(" -", p)
        sys.exit(1)


if __name__ == "__main__":
    main()
