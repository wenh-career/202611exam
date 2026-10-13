#!/usr/bin/env python3
"""把 data/questions.json 嵌入 src/app.html，輸出：
- index.html：GitHub Pages 用的完整網頁
- dist/artifact.html：發布成 Claude 網頁用的片段（不含 <html>/<head>/<body>）
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
bank = json.loads((ROOT / "data" / "questions.json").read_text(encoding="utf-8"))
src = (ROOT / "src" / "app.html").read_text(encoding="utf-8")
data = json.dumps(bank, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
page = src.replace("/*__QUESTIONS__*/[]", data)
assert page != src, "找不到 /*__QUESTIONS__*/[] 標記"

(ROOT / "dist").mkdir(exist_ok=True)
(ROOT / "dist" / "artifact.html").write_text(page, encoding="utf-8")

head, sep, rest = page.partition("</style>")
full = (
    '<!doctype html>\n<html lang="zh-Hant">\n<head>\n<meta charset="utf-8">\n'
    '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
    + head + sep + "\n</head>\n<body>\n" + rest + "\n</body>\n</html>\n"
)
(ROOT / "index.html").write_text(full, encoding="utf-8")
print(f"{len(bank)} 題 → index.html、dist/artifact.html")
