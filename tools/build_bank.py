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
SPLIT = ""     # 內部用：選項分隔
IMG_TEXT = ""  # 內部用：此處文字是圖片，需人工轉錄
OVERRIDES = ROOT / "data" / "overrides.json"

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


NOISE = re.compile(r"\s*(代號：\s*\d+|頁次：.*|（請接背面）|（背面）|（正面）|全一張|\d+\s*－\s*\d+)\s*")


def clean(s):
    lines = [re.sub(r"\s{2,}", " ", ln) for ln in s.split("\n") if not NOISE.fullmatch(ln)]
    return join_lines(lines)


def layout_from_images(path):
    """106 年等卷：選項框是圖片而非文字。依座標重建版面文字，圖片位置換成標記字元。"""
    import pymupdf
    doc = pymupdf.open(path)
    pages = []
    for pg in doc:
        items = []
        for b in pg.get_text("dict")["blocks"]:
            for l in b.get("lines", []):
                for s in l["spans"]:
                    if s["text"].strip():
                        x0, y0, x1, y1 = s["bbox"]
                        items.append((x0, (y0 + y1) / 2, s["text"], False))
        for im in pg.get_image_info():
            x0, y0, x1, y1 = im["bbox"]
            if y1 - y0 > 16:
                continue
            if x1 - x0 <= 24:  # 只有選項框
                items.append((x0, (y0 + y1) / 2, "", True))
            else:  # 選項框連同選項文字一起是圖片，需人工轉錄（data/overrides.json）
                items.append((x0, (y0 + y1) / 2, "" + IMG_TEXT, True))
        items.sort(key=lambda t: (t[1], t[0]))
        lines = []
        for it in items:
            if lines and abs(lines[-1][0] - it[1]) < 5:
                lines[-1][1].append(it)
            else:
                lines.append([it[1], [it]])
        for _, row in lines:
            row.sort(key=lambda t: t[0])
            indent = int(row[0][0] / 6)
            txt = ""
            prev_x1 = None
            for x0, _, t, is_mark in row:
                if prev_x1 is not None and x0 - prev_x1 > 8:
                    txt += "  "
                txt += t
                prev_x1 = x0 + (22 if is_mark else len(t) * 5)
            pages.append(" " * indent + txt)
        pages.append("\f")
    text = "\n".join(pages)
    # 依出現順序把  指定為 A、B、C、D（每題由題號切開後再編號）
    return text


def split_blocks(text, name):
    """依題號（縮排最淺、編號連續）把測驗題切成一題一塊。"""
    start = text.find("測驗題部分")
    if start < 0:
        raise ValueError("找不到測驗題部分")
    lines = text[start:].replace("\f", "\n").split("\n")[1:]
    num_re = re.compile(r"^(\s*)(\d{1,2})(?:\s+(.*))?$")
    blocks, cur, base, n = [], None, None, 1
    for ln in lines:
        m = num_re.match(ln)
        if m and int(m.group(2)) == n:
            ind = len(m.group(1))
            # 題號行：縮排不比第 1 題深太多，且題號後空白或接題幹
            if base is None or ind <= base + 3:
                if base is None:
                    base = ind
                cur = [m.group(3) or ""]
                blocks.append(cur)
                n += 1
                continue
        if cur is not None:
            cur.append(ln)
    return blocks


def parse_questions(path):
    text = pdftotext(path, layout=True)
    if not any(m in text for m in MARKS):
        text = layout_from_images(path)
    questions = []
    for i, block in enumerate(split_blocks(text, path.name), 1):
        body = "\n".join(block)
        # 圖片模式：依序把通用標記換成 A–D
        k = 0
        def repl(_):
            nonlocal k
            ch = MARKS[k] if k < 4 else ""
            k += 1
            return ch
        body = re.sub("", repl, body)
        # 依序找 A→B→C→D：標記須在行首或前有空白才算選項開頭；
        # 選項內文引用的「(A)」「(B)」等則還原成文字
        out, expect = [], 0
        for idx, ch in enumerate(body):
            if ch in MARKS or ch == "":
                prev = body[idx - 1] if idx else "\n"
                if expect < 4 and ch == MARKS[expect] and prev in " \n":
                    out.append(SPLIT)
                    expect += 1
                elif ch in MARKS:
                    out.append(f"({LETTERS[MARKS.index(ch)]})")
                else:
                    out.append(ch)
            else:
                out.append(ch)
        parts = "".join(out).split(SPLIT)
        if len(parts) != 5:
            raise ValueError(f"第{i}題只找到 {len(parts) - 1} 個選項")
        stem = clean(parts[0])
        opts = [clean(p) for p in parts[1:]]
        questions.append({"no": i, "q": stem, "options": opts})
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
    # 例：「第19題答Ｂ給分，第27題答Ａ或Ｄ者均給分」「第17題一律給分」「第19題答Ａ或Ｂ或AB者均給分」
    for m in re.finditer(r"第\s*(\d+)\s*題([^。；，,、\n]*)", remark):
        no, desc = int(m.group(1)), m.group(2)
        if "一律給分" in desc:
            notes[no] = {"accept": list(LETTERS), "note": "一律給分"}
        elif "給分" in desc:
            acc = sorted(set(re.findall(r"[ABCD]", desc.split("者")[0].split("給分")[0])))
            if acc:
                note = f"更正答案為 {acc[0]}" if len(acc) == 1 else f"更正：答{'或'.join(acc)}均給分"
                notes[no] = {"accept": acc, "note": note}
    result = []
    for i, a in enumerate(answers, 1):
        if i in notes:
            result.append(notes[i])
        elif a == "#":
            raise ValueError(f"{path.name} 第{i}題標註#但備註無法解析：{remark.strip()[:80]}")
        else:
            result.append({"accept": [a]})
    return result


def main():
    overrides = {}
    if OVERRIDES.exists():
        overrides = {k: v for k, v in json.loads(OVERRIDES.read_text(encoding="utf-8")).items() if not k.startswith("_")}
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
        try:
            qs = parse_questions(qpdf)
            ans = parse_answers(ans_file)
        except Exception as e:
            problems.append(f"{qpdf.name}：{e}")
            continue
        if len(qs) != len(ans):
            problems.append(f"{qpdf.name}：題數 {len(qs)} 與答案數 {len(ans)} 不符")
            continue
        for q, a in zip(qs, ans):
            qid = f"{year}-{code[-2:]}-{q['no']:02d}"
            fix = overrides.pop(qid, None)
            if fix:
                q["q"] = fix.get("q", q["q"])
                q["options"] = fix.get("options", q["options"])
            if IMG_TEXT in q["q"] or any(IMG_TEXT in o for o in q["options"]):
                problems.append(f"{qpdf.name} 第{q['no']}題（{qid}）：選項是圖片，需在 overrides.json 轉錄")
            if not q["q"] or any(not o for o in q["options"]):
                problems.append(f"{qpdf.name} 第{q['no']}題（{qid}）：題目或選項為空")
            item = {
                "id": qid,
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
    for qid in overrides:
        problems.append(f"overrides.json 的 {qid} 沒有對應的題目")
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
