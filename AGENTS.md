# NTU Journalism Graduate Services

This file provides guidance to Codex (Codex.ai/code) when working with code in this repository.

## 專案概述

台大新聞所學生服務平台（NTU Journalism Services Portal），提供課程資訊、指導教師資源、活動時程等整合性服務。公開頁是靜態網站；課程與指導學生管理介面由 Cloud Run 提供受保護的 JSON 編輯 API。

本專案位於工作區的 `content-platform/graduate-services/`。它同時包含學生 Portal 與內容管理後台，因為兩者仍共用部署與資料發布流程；不要在沒有獨立遷移計畫的情況下拆分它們。

## 部署網址

- **管理平台**: https://graduate-course-admin-sb2s54rpvq-de.a.run.app/
- **ChatGPT Sites 網站入口**: https://ntujour-site-directory.jirlong.chatgpt.site
- **系友問卷**: https://graduate-alumni-form-sb2s54rpvq-de.a.run.app/
- **主站首頁**: https://homepage.ntu.edu.tw/~jour/
- **公開首頁**: https://storage.googleapis.com/ntujour-graduate/index.html
- **開課規劃**: https://storage.googleapis.com/ntujour-graduate/courseplan.html
- **課程地圖**: https://storage.googleapis.com/ntujour-graduate/courses.html
- **指導學生狀態**: https://storage.googleapis.com/ntujour-graduate/advisee.html
- **公開 bucket**: `gs://ntujour-graduate`

## 技術架構

- **前端框架**: 原生 HTML + Tailwind CSS (CDN) + D3.js (視覺化)
- **正式資料來源**: `data/courses.json`、`data/advisees.json`
- **匯入來源**: Google Sheets CSV、Word 檔或本機 CSV；匯入後需轉成 JSON，公開頁不直接讀匯入來源
- **資料同步**: Python 腳本 (`update_forms.py`) 從 Google Sheets 下載 CSV
- **公開表單代理**: `alumni_form.html` 應搭配獨立的公開 Cloud Run 提交 API 使用；系友資料應寫入私有 GCS bucket，敏感設定只放在後端環境變數，不能放前端 JS
- **系友收件後台**: `course_admin.html` 已新增 `系友收件` 分頁與 `/api/alumni-submissions`，可在同一個後台檢視與標註系友回覆；實際寫入目標由 `ALUMNI_STORAGE_BUCKET` / `ALUMNI_STORAGE_PREFIX` 控制
- **教師管理**: 教師管理已加入同一個 `graduate-course-admin` 的 `/faculty/`；草稿放獨立私有 bucket，公開資料放 `ntujour-graduate/faculty-pilot/v1`，正式中英文網站已接入並保留靜態備援。

### 設計系統
- CSS 變數定義於各頁面 `:root`，統一使用 `--portal-*` 命名
- 共用樣式放在 `style.css`，部分頁面有內嵌樣式
- 圓角統一使用 `--portal-radius: 3px`，避免過度圓潤

## 主要頁面

| 檔案 | 功能 | 資料來源 |
|------|------|----------|
| `index.html` | 首頁/入口 | `data/office.csv` |
| `advisee.html` | 指導學生狀態 | `data/advisees.json` |
| `courses.html` | 課程地圖（互動式拖拉規劃）| `data/courses.json` |
| `courseplan.html` | 開課規劃（學期課程表）| `data/courses.json` |
| `events.html` | 活動年表 | `data/regular_event.json` |
| `alumni_form.html` | 系友資料庫公開問卷（未掛首頁） | Cloud Run alumni submit API -> 私有 GCS bucket |
| `course_admin.html` | 課程 / 指導學生 / 常態活動 / 系友收件後台 | `data/courses.json`、`data/advisees.json`、`data/regular_event.json`、`/api/alumni-submissions` |

## 資料更新指令

```bash
# 從 Google Sheets 同步所有 CSV 資料
python update_forms.py

# 從 live Google Sheet CSV 產生課程 JSON，並保留本機 CSV 補充欄位
python build_courses_json.py \
  --source "https://docs.google.com/spreadsheets/d/e/2PACX-1vQHsu0mwJHBxfuSwglE4PsC2G_F8atdcFZ_j1SSvaNA1QuLlBfVnFXQmYX5Hb5Qp3f1PdtTjQ_4ngi9/pub?gid=504100079&single=true&output=csv" \
  --merge-missing data/courses.csv \
  --output data/courses.json

# 啟動課程 JSON 管理介面
python course_admin.py
```

此腳本會下載以下資料：
- `office.csv` - 相關表單/公告
- `advisee.csv` - 指導學生資料
- `courses.csv` - 課程資訊
- `regular_event.csv` - 活動年表匯入來源

## JSON 管理

- `data/courses.json` 是課程頁面的主要讀取格式
- `courses-data.js` 提供 `courses.html` 與 `courseplan.html` 共用的 JSON 載入與 legacy row 轉換
- `data/advisees.json` 是指導學生頁面的主要讀取格式
- `advisees-data.js` 提供 `advisee.html` 與 `advisee_faculty.html` 共用的 JSON 載入與 legacy row 轉換
- `course_admin.py` 啟動本機管理伺服器，預設網址為 `http://127.0.0.1:8765/`
- `course_admin.html` 可管理課程、指導學生、常態活動與系友收件，並寫回 `data/courses.json`、`data/advisees.json`、`data/regular_event.json` 或 alumni 私有 bucket
- 本機與 Cloud Run 管理 API 在覆寫 JSON 前會先備份舊檔：`backup/courses-YYYYMMDD-HHMMSS.json`、`backup/advisees-YYYYMMDD-HHMMSS.json`
- Google Cloud Storage 發布流程記錄於 `docs/courses-json-cloud.md`
- alumni 提交檔案預設讀寫前綴為 `alumni/raw-submissions/`，可用 `ALUMNI_STORAGE_BUCKET`、`ALUMNI_STORAGE_PREFIX` 調整；若未設定 bucket，本機 admin 只會是唯讀模式

### 管理帳號新增

- `ADMIN_EMAILS` 是 Cloud Run 的必要環境變數，格式為逗號分隔的管理員 email；空白名單會拒絕所有後台請求。
- `IAP_JWT_AUDIENCE` 也是必要環境變數，Cloud Run 格式為 `/projects/PROJECT_NUMBER/locations/REGION/services/SERVICE_NAME`。後台只信任驗證簽章、issuer、audience 後的 `X-Goog-IAP-JWT-Assertion`，絕不以 `X-Goog-Authenticated-User-Email` 作為權限依據。
- 新增或移除帳號時，必須同時更新 `ADMIN_EMAILS` 與 IAP allowlist；後者角色為 `IAP-secured Web App User` / `roles/iap.httpsResourceAccessor`。重新部署 revision 後才會生效。

## 目錄結構

```
graduate-services/
├── data/           # CSV 資料檔案
├── docs/           # 說明文件
├── backup/         # 舊版檔案備份
├── output/         # 教師初始匯入備援與歷史 QA 證據，不是正式發布來源
├── plans/          # 專案內歷史規劃與評估記錄
├── knownews/       # 「媒聽說」子專案
└── *_old.html      # 舊版頁面
```

## 開發注意事項

1. **CSV 編碼**: 使用 UTF-8 with BOM (`utf-8-sig`)，確保中文正確顯示
2. **資料欄位**: 修改資料結構前，需同步更新對應的 HTML 中的 JavaScript 解析邏輯
3. **課程類別**: `courses.csv` 中的 `category` 欄位決定課程分類（必修、必選修-方法、必選修-實務等）
4. **D3.js 互動**: `courses.html` 使用 D3.js 實作課程拖拉功能，邏輯較複雜
5. **課程 JSON**: `courses.html` 與 `courseplan.html` 已改讀 `data/courses.json`；`source` 應標示 canonical JSON，Google Sheet / CSV 放在 `importSource`
6. **指導學生 JSON**: `advisee.html` 與 `advisee_faculty.html` 已改讀 `data/advisees.json`；Word / Google Sheet / CSV 僅作為匯入來源，不能視為正式資料
7. **活動年表 JSON**: `events.html` 已改讀 `data/regular_event.json` 並按年份與日期排序；`regular_event.csv` 僅作為匯入來源，不能視為正式資料

## Project 提醒

1. **獨立內容 section 要有 `id`**: 凡是頁面中可被單獨定位、連結、導覽或後續腳本存取的內容區塊，都應加上穩定且語意明確的 `id`
2. **重複 section 要有語意 class**: 凡是頁面中會重複出現的 section / block / card / row，都應加上可辨識用途的 class，例如 `student-card`、`event-section`、`faculty-group`，不能只依賴 `mt-4`、`grid`、`border-b` 這類 styling class
3. **命名優先反映內容角色**: `id` 與語意 class 應優先描述內容角色與結構用途，而不是視覺效果，避免後續 DOM 操作、維護與回歸檢查失去穩定錨點

## Harness Operating Model

- `content-edit`: 靜態頁面文案、版面、結構調整
- `data-sync`: Google Sheets、CSV、Word 來源轉成 canonical JSON
- `admin-ui`: `course_admin.html`、`course_admin.py`、`cloudrun_admin.py` 相關行為
- `deploy`: GCS 上傳、cache、公開 URL 驗證
- `incident-recovery`: JSON 損壞、部署錯誤、快取過期、儲存失敗

每次工作先判定 task class，再依類別確認 source of truth、預期輸出、驗證方式與 rollback 來源。

## Memory and State

- 開始工作時，先確認 task class、目標檔案、目標環境與 rollback 來源
- canonical 資料只看 `data/courses.json`、`data/advisees.json`、`data/regular_event.json`
- `Google Sheets`、`CSV`、`Word` 只算 import source，不算正式來源
- 多步驟工作保持簡短狀態記錄，至少包含 `goal`、`current step`、`verification pending`、`rollback path`
- 如果工作尚未完成，寫入 `Pending Tasks` 與 `LOG.md`

## Tool Use Policy

- 先讀本機檔案，再決定是否需要瀏覽器或遠端操作
- 只有在無法靠靜態檢查確認行為時才用瀏覽器
- 只有在本機驗證通過後才做部署或遠端寫入
- 做資料修改前，先看 consumer 再改 schema
- 工具失敗時先分類為 `auth`、`network`、`schema`、`render` 或 `deploy`，再決定是否重試
- 避免無限重試；若是遠端問題，先停下來記錄阻塞點與 fallback

## Execution Loop

1. 判定 task class
2. 確認 source of truth 與 downstream consumers
3. 檢查目標檔案與相依檔案
4. 做最小且一致的修改
5. 跑本機或靜態驗證
6. 若涉及 UI，再跑瀏覽器驗證
7. 若涉及發布，再做部署與公開 URL 驗證
8. 確認結果是否真的落在正式資料層
9. 把完成情況記到 `LOG.md`

## Evaluation Checklist

- `content-edit`: 版面結構保留、文字符合來源、沒有 broken link 或 asset
- `data-sync`: JSON 可解析、必要欄位保留、頁面 loader 正常、`source` 與 `importSource` 語義正確
- `admin-ui`: 可載入、可編輯、可儲存、覆寫前有備份
- `deploy`: 目標物件正確上傳、metadata 正確、cache 行為合理、公開 URL 已更新
- `incident-recovery`: 失敗可重現或已定位、fallback 來源明確、可回復到安全狀態

## Recovery and Rollback

- 覆寫 canonical JSON 前，先確認 `backup/` 會產生備份
- 若公開頁面錯誤但本機檔案正確，先把 deploy state 與 content state 分開看
- 若是快取問題，先查 cache 再考慮重建資料
- 若是 admin 儲存失敗，先分辨 IAP/auth 與 JSON 寫入邏輯
- 遠端寫入失敗時，只做有限次重試，之後改走人工 fallback
- 每次發佈前必須先比對本機與遠端資料物件；若遠端資料已更新、或無法明確確認差異，禁止將 `data/` 一起覆蓋，只能發布已確認的 HTML/CSS/JS 頁面檔

## Pending Tasks
- [x] 關閉 Cloud Run `/links/` 網站入口及管理頁返回按鈕，改用私人 ChatGPT Sites 網站入口。
- [x] 建立網站管理入口，集中連結六個管理頁與主站、英文站、學生服務 Portal、系友問卷，並讓現有管理頁可返回入口。
- [x] 將教師與最新消息編輯頁的中英文切換從下拉選單改為分頁按鈕。
- [x] 將消息與活動的標籤欄改為可按 Enter 建立、推薦歷史標籤並以 × 刪除的互動式編輯器。
- [x] 補齊 Cloud Run 部署映像中的 `news_portal` 與管理頁，重新部署並確認 Admin 與消息資料載入正常。
- [x] 修正最新消息後台既有 `/images/news/*` 圖片預覽在 Cloud Run 管理頁回傳 404 的問題。
- [x] 修正教師英文 JSON 索引，使英文站只列專任教師，暫不接正式站。
- [x] 在既有 Cloud Run 後台完成最新消息管理、圖片上傳、草稿與發布。
- [x] 讓中文首頁、中文消息頁與英文首頁讀取雲端消息 JSON，並保留靜態備援。
- [x] 將 59 筆活動資訊納入雲端 JSON 與消息後台，讓首頁、Archive、活動列表及活動內頁即時讀取並保留靜態備援。
- [x] 實際運作並確認消息發布與備援穩定。
- [x] 讓中文及英文教師頁接入教師 JSON，並保留靜態備援。

- [x] 將教師管理改為清單優先介面，清單顯示主站卡片資料、中文／英文站狀態及聯絡資訊，點選後才進入完整編輯。
- [x] 將教師管理併入既有後台共用選單，移除可見的「試用」字樣並支援其他資料分頁的直接連結。
- [x] 新增教師照片上傳與取代流程，圖片經驗證與縮圖後寫入既有公開教師圖片區，草稿儲存前保留未儲存提示。
- [x] 新增教師類別與排序編輯，加入「歷任實務教師」類別並保留退休／名譽教授的不同語意。
- [x] 逐位審查教師雲端資料與中英文試用預覽，並切換正式中文及英文網站。
- [x] 讓教師管理以中文／英文獨立勾選控制公開名單，隱藏時仍保留完整雙語資料與照片。
- [x] 讓教師可保留主要分類並額外列入退休教師，並將谷玲玲、張錦華加入退休教師列表。
- [x] 新增教師建立流程：預設合聘教師與雙語隱藏，支援首次草稿建立、照片上傳、預覽及公開前完整性檢查。
- [x] 強化 Cloud Run 管理權限：空白管理員名單拒絕存取，並驗證 IAP JWT 的簽章、issuer 與服務 audience；保留既有管理員與 IAP allowlist。
- [ ] 改善教師長文編輯體驗。
- [ ] 使用瀏覽器完成 `graduate-course-admin` 的「指導學生」分頁 IAP 登入實測，確認修改學生資料與儲存 JSON 正常
- [x] 部署公開的 `graduate-alumni-form` 服務，填入私有 GCS bucket env vars，並維持暫時不掛首頁入口
- [ ] 部署並驗證 `系友收件` 後台在 Cloud Run / IAP 下可讀寫私有 alumni bucket，並確認不影響 `data/advisees.json`
- [x] 依 Harness Engineering 補強 `AGENTS.md`，加入 memory/state、tool use、execution loop、evaluation、recovery 規範
- [x] 規劃並草擬 `graduate-data-canonicalization`、`graduate-admin-regression-check`、`graduate-deploy-verify` 三個核心 skills
- [x] 為三個核心 skills 準備 2 到 3 個測試 prompts 與簡單驗證標準
- [x] 為三個核心 skills 補上 assertions，並執行 `graduate-data-canonicalization` 第一輪 eval
- [x] 草擬 `graduate-page-editing` skill 與初版 evals
- [x] 建立並推送 Graduate Services `stable-0921` Git 版本，排除本機依賴、輸出與測試暫存。
---
*Last updated: 2026-09-21*
