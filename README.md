# 經紀人刷題卡

不動產經紀人考試（專技普考）測驗題刷題網站。收錄 100–114 年四科測驗題共 1,920 題。題目與標準答案取自考選部公告的試題 PDF，已套用考選部更正答案。

## 功能
- **混合練習**：依科目、年度篩選，題目洗牌出題，一輪做完所有題目才重新洗牌
- **錯題本**：答錯自動收錄，答對一次就移出
- **整份模擬**：照原卷順序作答，交卷後計分（測驗題滿分 50 分）
- **紀錄**：各科進度、答對率、模擬成績

作答紀錄存在使用者自己的瀏覽器（localStorage），不會上傳。

## 新增年度
1. 從[考選部考畢試題查詢平臺](https://wwwq.moex.gov.tw/exam/wFrmExamQandASearch.aspx)下載試題與答案 PDF，原檔名放進 `pdf/`
   - 試題：`<考試代碼>_<科目代碼>_<科目>.pdf`
   - 答案：檔名含 `ANS`（標準答案）或 `MOD`（更正答案，會優先使用）
2. 執行：
   ```
   python3 tools/build_bank.py   # PDF → data/questions.json（需要 pdftotext、pymupdf）
   python3 tools/build_site.py   # 題庫 → index.html
   ```
3. commit 並 push，GitHub Pages 會自動更新。

## 檔案
- `pdf/`：考選部原始 PDF
- `data/questions.json`：解析後的題庫
- `data/overrides.json`：PDF 文字層讀不到、依原卷影像人工轉錄的內容（106 年部分選項是圖片）
- `src/app.html`：網頁樣板
- `index.html`：建置後的網站（GitHub Pages 讀這個）
- `tools/`：建置程式

依著作權法第 9 條，依法令舉辦之考試試題不得為著作權之標的。
