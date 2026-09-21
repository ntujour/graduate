# Project Work Log

## 2026-02-01

- [開始] 專案初始化，建立 CLAUDE.md 與 LOG.md

## 2026-05-11

- [01:00] 提交 `data/courses.csv` 更新（課程 #32、#39 授課教師與開設資訊）並 push 至 GitHub。
- [01:05] 將 `regular_event.html` 改為直接從 Google Sheets 讀取（live 版）：
  - 移除對本機 `data/regular_event.csv` 的依賴，直接 fetch publish 過的 CSV URL
  - 加入 localStorage 快取（stale-while-revalidate）：先顯示快取版本，背景更新最新版
  - 加入頁面右上角狀態指示器（live/cached/refreshing），顯示資料更新時間
  - 改用更穩健的 CSV parser，正確處理引號內逗號
  - 原檔案備份至 `backup/regular_event.pre-live.html`
- [備註] 此為自動化試行第一頁。如成功運作，下一階段會將 `index.html`（office.csv）、`courses.html`、`courseplan.html`、`advisee.html` 都改為 live，最終即可退役 `update_forms.py` 與 `data/` 目錄。
- [01:30] `courseplan.html` 改為 live 模式並更新學期規劃：
  - 學期欄位由 `114-1/114-2/115-1/115-2` 改為 `115-1/115-2/116-1/116-2`（116 學年度欄位由系辦於 Google Sheet 補上）
  - 改為直接從 Google Sheets 讀取 courses.csv，加入 localStorage 快取（SWR）
  - 升級 CSV parser 處理引號內逗號
  - 修課指引第 5 點文案更新為「115-1 增開三門、改一門課名；115-2 增開一門、改一門課名」
  - 原檔備份至 `backup/courseplan.pre-live.html`
- [23:36] 建立課程 JSON 管理流程（使用 skill: build-web-apps:frontend-app-builder）：
  - 新增 `data/courses.json` 作為課程頁主要資料格式，內容由 live Google Sheet CSV 產生並合併本機 CSV 補充欄位
  - 新增 `build_courses_json.py`、`courses-data.js`、`course_admin.py`、`course_admin.html`
  - `courses.html` 與 `courseplan.html` 改為讀取 JSON loader
  - 新增 Google Cloud Storage 發布文件與 CORS 設定檔
  - 補上 `AGENTS.md` 的課程 JSON 管理說明與 Pending Tasks
- [23:58] 調整課程管理介面：
  - 新增大表編輯模式，可直接批次編輯課名、教師、類別、學分、狀態、學期與描述
  - 移除管理介面的排序欄位與備註欄位
  - 狀態新增「近三年未開」
  - 「停開 / 不可選」課程以灰色呈現並自動排到最下方，內部 `sequence` 由程式自動重編
- [00:06] 將課程管理介面改為模式切換：
  - 預設顯示課程查詢與逐課編輯
  - 右上角「重新載入」旁新增「批次修改」按鈕
  - 批次修改大表改為獨立模式，不再與課程查詢介面同時顯示
- [00:16] 精簡批次修改大表：
  - 週期與狀態整併為單一「週期」欄位
  - 週期欄可輸入每年、隔年、近三年未開、停開 / 不可選
  - 描述欄改為單行輸入
  - 欄位寬度依內容縮窄，批次修改模式加寬到接近全螢幕
  - 排序改為必修、必選修-方法、必選修-實務、其他類別，停開 / 不可選仍置底
- [00:20] 將逐課編輯的週期欄改為可編輯下拉（input + datalist），與批次修改大表一致
- [00:24] 更新課程管理排序規則：
  - 依課程類別排序：必選/必修、必選修-方法、必選修-實務、理論/方法、媒體公民意識、國際視野、數位知能、專業實作
  - 同一類別內每年開課排在隔年開課之前，其餘週期再往後
- [00:28] 將批次修改大表的週期欄改為原生下拉選單，保留既有自訂週期值作為該列選項
- [00:31] 將「近三年未開」課程標示為灰黃色，排序在停開 / 不可選之前；停開 / 不可選維持灰色置底
- [00:34] 課程排序加入最早開課學期：同類別、同週期內，較早學期（如 115-1）排在較晚學期（如 115-2）之前

## 2026-05-12

- [00:07] 更新 `courseplan.html` 依課程 JSON 直接計算開課規劃：
  - 改用 `data/courses.json` 的 `offerings`、`period`、`active`、`category` 產生表格
  - 學期欄位由 JSON 最新四個學期自動取得
  - 課程類別列改為必修、必選修-方法、必選修-實務、理論/方法、媒體公民意識、國際視野、數位知能、專業實作
  - 套用管理介面的排序邏輯與近三年未開 / 停開狀態樣式
- [00:16] `courseplan.html` 課程卡片移除每年 / 隔年週期顯示，只保留特殊狀態標示
- [00:20] 修正課程批次管理儲存穩定性：儲存 JSON 前會先從批次表格 DOM 重新同步所有可見欄位與學期 checkbox，避免取消勾選後漏寫
- [18:50] 新增 Cloud Run 課程管理部署原型：
  - 新增 `cloudrun_admin.py`，以 Flask 提供管理頁與 `/api/courses`，並可讀寫 GCS `data/courses.json`
  - 新增 `Dockerfile`、`requirements.txt`、`.gcloudignore`
  - 新增 `docs/cloud-run-admin.md`，記錄 Cloud Run + GCS + IAM/IAP 部署流程
  - Cloud Run 版管理服務支援 `COURSES_BUCKET`、`COURSES_OBJECT`、`ADMIN_EMAILS` 環境變數
- [19:43] 使用預設值部署公開網站與 Cloud Run 管理服務：
  - GCP project: `pacific-chalice-390913`
  - 公開 bucket: `ntu-journalism-graduate-services`
  - Cloud Run service: `graduate-course-admin`
  - 管理服務帳號: `graduate-course-admin-sa@pacific-chalice-390913.iam.gserviceaccount.com`
  - 公開頁面與課程 JSON 已上傳至 GCS
  - Cloud Run 管理 API 已部署並限制 `jirlong@gmail.com` 可 invoke
- [23:02] 切換正式公開 bucket 為 `ntujour-graduate`：
  - 建立並公開 `gs://ntujour-graduate`
  - 同步公開網站檔案與 `data/courses.json`
  - 授權 Cloud Run service account 可寫入新 bucket
  - 更新 Cloud Run `COURSES_BUCKET=ntujour-graduate`
  - 驗證公開 `courseplan.html` 與 Cloud Run `/api/courses` 讀寫正常
- [23:35] 整理 Cloud Run 管理介面啟用 IAP / Gmail 登入的操作流程與可能阻礙
- [23:47] 嘗試將部署搬移至 `ntujour` project：
  - 確認 `ntujour` project 存在，project number 為 `623280269212`
  - 確認 `ntujour-graduate` bucket 仍屬於舊 project `pacific-chalice-390913`
  - 已備份目前 `gs://ntujour-graduate` 內容至本機暫存目錄
  - 搬移卡在 billing：`ntujour` 無 billing，連結既有 billing account 時回覆 `Cloud billing quota exceeded`

## 2026-05-13

- [00:14] 完成部署搬移至 `ntujour` project：
  - 確認 `ntujour` billing 已啟用，並啟用 Cloud Run、Cloud Build、Artifact Registry 等 API
  - 移除舊 project `pacific-chalice-390913` 的 `ntujour-graduate` bucket，並在 `ntujour` 重建同名 bucket
  - 從本機公開網站檔案重新上傳至 `gs://ntujour-graduate`，維持公開 URL 不變
  - 建立 `graduate-course-admin-sa@ntujour.iam.gserviceaccount.com`
  - 部署 Cloud Run `graduate-course-admin` 至 `ntujour` / `asia-east1`
  - 設定公開 bucket 讀取、Cloud Run service account 寫入 bucket、`jirlong@gmail.com` 可 invoke 管理服務
  - 驗證公開頁、公開 JSON、未授權 403、授權 API 讀寫皆正常
- [00:25] 嘗試為 `ntujour` 的 Cloud Run 管理服務啟用 IAP：
  - 安裝 `gcloud beta` 並建立 IAP service agent
  - 授權 IAP service agent 可 invoke `graduate-course-admin`
  - 啟用 Cloud Run IAP 並將 `jirlong@gmail.com` 加入 `roles/iap.httpsResourceAccessor`
  - 驗證 IAP 已接管，但 project 缺 OAuth client，直接開管理 URL 會回 `Empty Google Account OAuth client ID(s)/secret(s)`；需到 Cloud Console 完成一次 OAuth/IAP 初始設定
- [01:07] 使用者完成 Google Auth Platform / OAuth client 設定後，重新驗證 Cloud Run IAP：
  - 管理 URL 已回 302 並導向 `accounts.google.com` OAuth 登入流程
  - IAP policy 保留 `jirlong@gmail.com` 的 `roles/iap.httpsResourceAccessor`
  - 一般 `gcloud auth print-identity-token` token 被 IAP 以 invalid JWT audience 拒絕，符合 IAP 模式預期
- [01:13] 更新 Cloud Run 管理介面：
  - 在管理頁工具列新增「公開首頁」連結按鈕，連到 `https://storage.googleapis.com/ntujour-graduate/index.html`
  - 重新部署 `graduate-course-admin` revision `graduate-course-admin-00003-f9l`
  - 驗證 IAP 仍啟用、公開首頁維持 200、Cloud Run env 保持指向 `ntujour-graduate/data/courses.json`
- [23:28] 完成指導學生 JSON 與管理介面整合：
  - 新增 `build_advisees_json.py`，由 Google Sheet `gid=972093279` 轉出 `data/advisees.json`
  - 新增 `advisees-data.js`，並將 `advisee.html`、`advisee_faculty.html` 改讀 JSON
  - `course_admin.html` 新增「課程資料 / 指導學生」分頁、指導學生大表、老師排序欄、新增與刪除列功能
  - 本機與 Cloud Run API 新增 `/api/advisees`
  - 上傳 `advisees` 公開檔案至 `gs://ntujour-graduate`
  - 重新部署 Cloud Run revision `graduate-course-admin-00004-l4d`，env 改為 `DATA_BUCKET`、`COURSES_OBJECT`、`ADVISEES_OBJECT`
  - 驗證公開 `data/advisees.json`、公開頁載入 JSON、IAP 仍啟用；IAP 登入後儲存需由瀏覽器 session 再實測
- [23:36] 強化指導學生管理頁：
  - 指導學生大表新增依屆次篩選 tab，預設顯示全部，屆次由 JSON 學生資料自動產生
  - 依論文類型為大表列與論文類型欄上色：研究組、專業組、專業組(影像)、專業組(多媒體)
  - 重新部署 Cloud Run revision `graduate-course-admin-00005-6wc`，驗證 IAP 與 env 設定維持正常
- [23:56] 指導學生管理新增進度 checkbox：
  - `data/advisees.json` 新增 `advised`、`proposal`、`final` 三個布林欄位
  - 管理頁大表新增 Advised、Proposal、Final checkbox 欄位
  - 套用自動規則：指導老師空白則三欄全空；正式論文題目則 Final/Proposal/Advised 皆勾選；「在學中」不勾 Final
  - 上傳新版 `data/advisees.json` 並設定 no-cache，重新部署 Cloud Run revision `graduate-course-admin-00006-wcm`

## 2026-05-14

- [00:13] 重新上傳指導學生公開頁：
  - `advisee.html` 與 `advisee_faculty.html` 的「學生指導中」badge 均顯示「學生姓名(屆次)」
  - 以 no-cache 重新上傳至 `gs://ntujour-graduate`
- [00:18] 調整指導學生公開頁 badge 格式：
  - `advisee.html` 與 `advisee_faculty.html` 的學生 badge 改為「(屆次) 學生姓名」
  - 以 no-cache 重新上傳並用 cache-busting URL 驗證遠端內容
- [19:17] 依據 `/Users/jirlong/Downloads/臺大新聞所碩士論文(全)_20260401版.doc` 更新指導學生 JSON：
  - 以 Word 文件轉出的 HTML 表格為準，重建第 28 至 35 屆資料，共 209 筆
  - 新增第 35 屆 22 筆，並修正第 28 至 34 屆的論文題目、指導教授、論文類型與狀態欄位
  - 將 `data/advisees.json` 上傳至 `gs://ntujour-graduate/data/advisees.json`，設定 no-cache，並驗證遠端 JSON 筆數與關鍵姓名
- [20:01] 更新 `courseplan.html` 專業組修課規劃文案：
  - 將多媒體採訪報導規則改為「採訪寫作一、二」或「影像報導一、二」二擇一
  - 上傳至 `gs://ntujour-graduate/courseplan.html`，設定 no-cache，並用 cache-busting URL 驗證遠端內容
- [20:37] 更新公開頁舊版入口與指導學生呈現：
  - 移除 `index.html`、`courses.html`、`courseplan.html`、`advisee.html`、`advisee_faculty.html` 的「回到舊版」連結
  - `advisee.html` 的專任教師與實務教師區塊改為單欄排列
  - `advisee.html` 的指導中學生改為依狀態分組顯示：`Proposal:`、`Advising:`，學生 badge 改為 `屆次-姓名`
  - 上傳更新後公開頁至 `gs://ntujour-graduate`，並以瀏覽器驗證雲端 `advisee.html` 沒有舊版連結、標籤為黑字且無空老師列
- [20:38] 調整 `advisee.html` 指導中學生狀態顯示：
  - 將每位老師列內重複的 `Proposal:` / `Advising:` 改為教師區塊上方欄名
  - 每列只保留老師姓名與學生 badge，降低 `Advising` 重複出現
  - 上傳至 `gs://ntujour-graduate/advisee.html`，並以瀏覽器驗證雲端頁面
- [20:40] 調整 `advisee.html` 狀態欄名字級：
  - `Proposal` / `Advising` 欄名改為 12px，與學生 badge 字級一致
  - 上傳至 `gs://ntujour-graduate/advisee.html`，並以瀏覽器驗證雲端 computed font-size
- [20:48] 調整 `advisee.html` 指導中學生狀態為單列呈現：
  - 移除 `Proposal` / `Advising` two-column 欄位版面
  - 每位老師改為同一列顯示 `Proposal: 33-XXX, Advising: 31-XXX, 32-XXX`
  - 學生 badge 之間加入逗號間隔，並上傳至 `gs://ntujour-graduate/advisee.html` 驗證
- [20:53] 調整 `advisee.html` 指導中學生標籤：
  - 移除公開頁上的 `Proposal` / `Advising` 文字
  - 已通過 proposal 的指導中學生改為 `P-屆次-姓名`，其餘維持 `屆次-姓名`
  - 移除學生 badge 間的逗號，並上傳至 `gs://ntujour-graduate/advisee.html` 驗證
- [22:48] 穩定 JSON 正式資料來源並新增備份機制：
  - `data/courses.json` 與 `data/advisees.json` 的 `source` 改為 canonical JSON，原 Google Sheet / Word 來源移至 `importSource`
  - `build_courses_json.py`、`build_advisees_json.py` 改為輸出 canonical `source` 與 `importSource`
  - 本機 `course_admin.py` 與 Cloud Run `cloudrun_admin.py` 在 PUT 覆寫 JSON 前會先備份舊檔至 `backup/courses-YYYYMMDD-HHMMSS.json` 或 `backup/advisees-YYYYMMDD-HHMMSS.json`
  - 更新 `AGENTS.md` 與 `docs/` 的資料來源規則；手動備份並上傳新版 JSON 至 `gs://ntujour-graduate`
  - 重新部署 Cloud Run revision `graduate-course-admin-00008-22n`；驗證 IAP 仍啟用、env 正常、未登入仍導向 Google OAuth
- [23:29] 清理課程 JSON 舊資料新聞課程與 courseplan 快取：
  - 從 `data/courses.json` 移除 `新聞資料處理與視覺呈現`、`資料新聞與視覺化`，保留新課名 `社會科學程式設計`
  - 將 `電視新聞雜誌` 的重複 id 改為 `course-tv-news-magazine`，確認課程 id 已無重複
  - 將 `courseplan.html` localStorage cache key 更新為 `courses_json_v2_20260514`
  - 上傳新版 `data/courses.json` 與 `courseplan.html` 至 `gs://ntujour-graduate`，並先備份原線上課程 JSON

## 2026-05-24

- [22:17] 更新 `AGENTS.md`：
  - 新增部署網址區塊，集中記錄 Cloud Run 管理平台、公開首頁、開課規劃、課程地圖、指導學生狀態與公開 bucket 連結

## 2026-06-09

- [21:10] 縮減 `courseplan.html` 的整體版面密度：
  - 壓低頁首、主內容、修課指引、表格欄位與課程卡片的 padding / margin
  - 以瀏覽器驗證桌機與手機版渲染正常，且無水平 overflow
  - 使用 skill: frontend-app-builder

## 2026-06-15

- [00:56] 在 `regular_event.html` 新增「2026 新生暑前座談」置頂 block，包含 Google Meet、Google Slide 與 Slido 連結。
- [01:06] 在 `index.html` 新增「活動訊息」section，將「2026 新生暑前座談」直接做成單一 block，並保留連到完整常態活動頁的入口。
- [01:48] 將首頁活動卡調整為與其他卡片一致的字級，移除下方描述文字，並以磚紅色強調活動名稱。

## 2026-06-16

- [23:56] 調整學生指導頁面的 `student-badge` box model，將 margin 統一為 `2px`、padding 統一為 `3px`，並移除 proposal 學生 badge 的 `P` 前綴顯示。

## 2026-06-17

- [00:17] 將更新後的 `advisee.html` 與 `advisee_faculty.html` 上傳至 `gs://ntujour-graduate`，並確認物件 metadata 已套用 `no-cache` 與 `text/html; charset=utf-8`。
- [00:22] 調整學生指導頁的 active 學生排序為純屆次排序，並在已完成 Proposal 口試的 badge 加上 hover 提示；重新上傳至 `gs://ntujour-graduate` 並用公開網址驗證。
- [00:29] 調整 `coursepath.html` 的欄寬與密度，讓部分分類欄位更窄、課程名稱字級更小，並用本機預覽確認版面可讀性。

## 2026-06-19

- [14:09] 補強 `graduate-data-canonicalization`、`graduate-admin-regression-check`、`graduate-deploy-verify` 三個 skills 的 assertions，並同步 `data/courses.json` 與最新 Google Sheet 對齊（使用 skill: graduate-data-canonicalization）
- [14:09] 草擬 `graduate-page-editing` skill 與初版 evals，將 section `id` 與語意 class 的頁面提醒納入正式規格（使用 skill: graduate-page-editing）
- [00:40] 將更新後的 `coursepath.html` 上傳至 `gs://ntujour-graduate`，並確認公開檔案已套用 `no-cache` 與 `text/html; charset=utf-8`。

## 2026-06-19

- [19:52] 依 web/頁面編修規範回顧前端結構：將首頁修業相關表單併入主服務區作為第六項服務，並補齊 `index.html`、`advisee.html`、`advisee_faculty.html`、`courses.html`、`courseplan.html`、`coursepath.html`、`events.html` 的穩定 section id 與語意 class（使用 skill: web-project-startup, graduate-page-editing）。
- [20:00] 依 Harness Engineering 定義整理專案規劃，新增 `plans/plan_harness_agents_skills_2026-06-19.md`（使用 skill: skill-creator）。
- [20:02] 將 Harness 對應工作加入 `AGENTS.md` Pending Tasks，後續分為 AGENTS 規格補強與核心 skills 草擬兩條線推進。
- [20:12] 將 Harness 規劃收斂為輕量版：明確排除通用 agent framework，優先處理 source of truth、verification loop、rollback 與三個核心 skills。
- [20:18] 在 `AGENTS.md` 新增 Project 提醒：要求所有獨立內容 section 具備穩定 `id`，所有重複 section 具備可辨識的語意 class，而非只使用 styling class。
- [20:25] 實作輕量 harness 的 Phase 1：在 `AGENTS.md` 補上 `Harness Operating Model`、`Memory and State`、`Tool Use Policy`、`Execution Loop`、`Evaluation Checklist`、`Recovery and Rollback`，並將對應待辦標記完成。
- [20:32] 完成三個核心 skills 草稿：`graduate-data-canonicalization`、`graduate-admin-regression-check`、`graduate-deploy-verify`，並將後續工作移到 eval prompts 準備。
- [20:36] 為三個核心 skills 建立初版 eval prompts，分別存放在 `skills/*/evals/evals.json`，作為後續 assertions 與試跑的基礎。
- [14:07] 進行 `graduate-data-canonicalization` 第一輪 eval 檢查；因 Word 匯出不在 repo 內而回報 blocked，並確認公開頁仍透過 `data/advisees.json` 讀取 canonical 資料。
- [20:44] 完成 `graduate-data-canonicalization` 的 `regular_event` eval 檢查，確認 `data/regular_event.json` 與 `data/regular_event.csv` 已對齊且 `regular_event.html` 可正常解析，並強化 `graduate-page-editing` 對 section `id` 與語意 class 的結構規則（使用 skill: graduate-data-canonicalization, graduate-page-editing）。
- [20:52] 完成 `graduate-data-canonicalization` 第一輪 eval 的正式 grading 與 benchmark，with-skill 與 baseline 皆為 8/9，並據此補強 skill 對 `source` / `importSource` 明確輸出的要求。

## 2026-06-22

- [16:53] 整理 `AGENTS.md`：移除 Google Sheets 相關規則，改成以線上正式 JSON 為準，並加入本機舊資料不得直接覆寫線上資料、覆寫課程／指導教師／活動資料前需先確認的保護機制（使用 skill: web-project-startup）
- [17:05] 補齊前後端版本保護：移除匯入腳本與文件中的 Google Sheets 入口，為 `course_admin.py` / `cloudrun_admin.py` 加上 `ETag` / `If-Match` 衝突檢查，並在 `course_admin.html` 的儲存流程加入確認與版本比對（使用 skill: web-project-startup）
- [17:18] 將本機管理介面收斂為單一真實來源模式：`course_admin.py` 啟動時先同步遠端正式 JSON，遠端不可用時自動改為唯讀，並將唯讀狀態傳到前端 UI 與按鈕控制（使用 skill: web-project-startup）
- [21:05] 更新首頁 `index.html`：移除學生活動 block，新增 `#curriculum-forms` 的修業相關表單 block，連到 NTU SPACE 修業規定、學位考試、論文大綱與寫作審查辦法頁面。
- [20:00] 將首頁第六項服務的修業相關表單卡片改回與其他服務一致的白底卡片版型，移除右上角 CTA 與特殊漸層，標題副標改為「修業相關表單 / FORMS」。
- [20:10] 將目前前端更新同步發布至 `gs://ntujour-graduate`，包含首頁與主要公開頁、共用 JS/CSS，以及 `data/courses.json`、`data/advisees.json`、`data/regular_event.json`、`data/regular_event.csv`，並確認公開 `index.html` 與 `events.html` 已套用 `no-cache`。（使用 skill: graduate-deploy-verify）
- [20:28] 更新首頁與活動頁文案與表格樣式：將「活動年表」改為「活動日程」，移除活動頁簡介句，並將活動日期、連結與說明的字級/間距調整為較精簡的版型。
- [20:32] 發佈本次 `index.html` 與 `events.html` 的前端改動至 `gs://ntujour-graduate`，刻意排除所有 `data/` 物件，以避免覆蓋線上已更新的資料；已驗證公開頁標題與 events 表格樣式更新成功。
- [20:33] 在 `events.html` 新增過期活動的淺灰底狀態，採用 `due` 與目前日期比較判斷，不變更資料來源與排序規則。
- [20:36] 於 `AGENTS.md` 新增發佈前資料比對規則：未確認遠端資料時禁止覆蓋 `data/`；重新發布 `index.html` 與 `events.html`，並再次確認公開頁與 metadata 已更新，未動到資料物件。
- [20:41] 在首頁與活動頁右上角加入低調的 `Admin` 外連入口，連至 Cloud Run 管理後台，不影響主導覽版面。
- [21:18] 將目前公開站靜態頁面同步到 `gs://ntujour-graduate`，並驗證 `index.html` 已更新為修業相關表單 block、`regular_event.html` 仍維持轉址頁，`index.html` header 套用 `no-cache`。
- [16:16] 將活動頁改為 `events.html` 年表視圖，`regular_event.html` 改為轉址頁，首頁與單一活動頁連結同步更新，並完成本機瀏覽驗證（使用 skill: frontend-testing-debugging）。
- [16:28] 將活動年表簡化為年份 tab + 表格視圖，加入活動超連結與相關資料欄位，並同步公開上傳至 `gs://ntujour-graduate`（使用 skill: frontend-testing-debugging）。
- [19:29] 在 `AGENTS.md` 補上 `ADMIN_EMAILS` / IAP 的新增帳號操作說明，明確記錄以逗號分隔 Gmail、需重部署 Cloud Run revision、以及 IAP allowlist 要同步更新。
- [21:32] 修正本機管理介面啟動後 API 讀取失敗：移除中文唯讀原因 header，改由 `/api/admin-state` 提供 JSON 狀態，避免 Python 內建 HTTP server 因 header 非 latin-1 字元而拋錯。
- [21:35] 將本機 `course_admin.py` 儲存流程補成真正的單一真實來源模式：每次操作先同步 `gs://ntujour-graduate`，儲存時直接寫回遠端 canonical JSON，並加上 GCS generation precondition、遠端備份與本機快照更新，避免 local 舊資料覆蓋線上新版（使用 skill: web-project-startup）。

## 2026-07-05

- [20:33] 新增 `alumni_form.html` 系友資料庫問卷頁，版型與台大社會系範例盡量貼近，但改為本 repo 的新聞所版本，且暫時不掛在首頁（使用 skill: web-project-startup）。
- [20:33] 新增 `cloudrun_alumni.py` 與 `docs/alumni-form-cloud-run.md`：改用獨立公開 Cloud Run service 代理 Airtable 寫入，將 Airtable token 移到後端環境變數，避免前端 JS 直接暴露 secret（使用 skill: web-project-startup）。
- [21:36] 補強 `cloudrun_admin.py` 的正式寫入保護：在 Cloud Run API 寫回 bucket 時加入 generation precondition，若遠端版本已變更則回傳 409，而不是覆蓋較新的線上資料。
- [21:37] 啟動並驗證本機管理介面：確認 `/api/admin-state`、`/api/courses`、`/api/advisees`、`/api/regular-events` 皆回 `200`、帶有 `ETag`，且 API 回傳 payload 與 bucket 正式 JSON 在 canonical 比對下完全一致；未執行正式資料寫入測試，因覆寫前仍需使用者確認。
- [22:10] 將系友資料庫表單收斂為新聞所版本：改為姓名主導、刪除學籍年次與傳承意願、加入電話與 Line ID 選填、調整資源選項與人際網絡欄位，並同步放寬後端對 Email 的必填限制（使用 skill: web-project-startup）。
- [22:28] 收斂系友表單欄位分工：移除「基本資訊」中重複的手機與 Line 欄位，保留聯絡設定頁作為唯一聯絡管道入口，減少重複與填寫混亂（使用 skill: web-project-startup）。

## 2026-07-06

- [01:18] 將系友表單提交後端從 Airtable 改為獨立的 Google Cloud Storage 私有 bucket 路徑，採每筆提交一個 JSON 檔的方式保留資料分離，並保留本機 local 模式作為開發驗證入口（使用 skill: web-project-startup）。
- [01:18] 更新系友表單部署文件與專案 `AGENTS.md`：明確把系友資料線與既有 `data/advisees.json` 分開，並把後續管理後台定位為獨立 private admin service（使用 skill: web-project-startup）。
- [01:26] 重現並修正系友表單送出失敗原因：`127.0.0.1:8017` 原本只是靜態伺服器，沒有 `/api/alumni-submissions`；改用 `cloudrun_alumni.py` 服務佔回同一埠後，提交 API 已可正常回應 200（使用 skill: web-project-startup）。
- [03:50] 在系友表單加入第六步送出確認頁，送出前先顯示所有填答摘要，避免使用者直接送出前無法檢視內容（使用 skill: web-project-startup）。
- [03:58] 將系友表單 review 頁改成只讀版的原始分頁樣貌：保留相同的卡片、toggle 與 checkbox 結構，未勾選項目以灰色呈現，讓使用者在送出前更容易核對實際填答內容（使用 skill: web-project-startup）。
- [04:05] 再收斂 review 頁的視覺狀態：有填或已勾選的欄位改以藍色 highlight 顯示，未填與未勾選維持灰色，讓送出前核對更接近原始填答流程（使用 skill: web-project-startup）。
- [14:31] 將 alumni 收件後台整合進既有 `course_admin`：新增 `/api/alumni-submissions` 讀取/寫入路由、在 `course_admin.html` 加入 `系友收件` 分頁與編輯面板，並完成本機 syntax 與 browser 驗證，確認列表可載入且無前端錯誤（使用 skill: web-project-startup）。
- [14:31] 更新專案文件與工作紀錄：`AGENTS.md` 補上 alumni admin、bucket env vars 與新的 pending task，`LOG.md` 記錄本次後台整合範圍與驗證結果（使用 skill: web-project-startup）。
- [14:34] 收斂 alumni 後台 header 版面：將管理 tab 改為單行不折行，避免 `系友收件` 掉到第二排，並驗證 4 個 tab 的 `top` 值一致（使用 skill: web-project-startup）。
- [14:39] 將課程後台收斂為 bulk-only：隱藏課程查詢／單筆表單、課程 tab 不再顯示 `重新載入`、`批次修改`、`新增課程`，並將 `常態活動` 等大表分頁切到寬版容器；已完成 browser 驗證（使用 skill: web-project-startup）。
- [16:17] 將 `系友收件` 後台改成和課程／指導學生一致的大表模式：移除左右分欄明細、改用單一寬表顯示收件內容，並把 `狀態`、`標籤`、`備註` 改成列內直接編輯；已完成 syntax 與 browser 驗證，確認 5 筆收件、23 欄表格可載入，dirty 狀態與待儲存筆數會同步更新（使用 skill: web-project-startup）。
- [16:38] 再收斂 `系友收件` 管理表：移除表內可變高度欄位，將多行摘要改成單行 readonly input，並把 `目前狀態`、`所在國家／地區`、`偏好聯絡方式` 改成下拉選單；已完成 browser 驗證，確認 alumni 表內 `textarea` 數量為 0、固定選項欄位皆為 `select`（使用 skill: web-project-startup）。
- [16:52] 為 `系友收件` 補上勾選刪除流程：前端新增 checkbox 欄與 `刪除勾選列` 按鈕，後端新增 `/api/alumni-submissions/<object>` 的 `DELETE` 路由；同時將 `狀態`、`標籤`、`備註`、`姓名` 等欄位再收窄，並完成瀏覽器驗證確認刪除欄已渲染、常用欄位寬度已縮小（使用 skill: web-project-startup）。
- [17:12] 修正 `系友收件` 真實刪除鏈路：拆開本機 admin 的 alumni 寫入權限、修正 local alumni object path 與 `If-Match` 版本比對、補上 local server 對 percent-encoded alumni object path 的 decode；已完成 API 與 UI 實測，確認勾選一筆收件後可真正刪除成功（使用 skill: web-project-startup）。
- [17:18] 在 `系友收件` 後台新增 `下載 JSON 備份` 按鈕：下載前會先同步表格中的未儲存編輯，匯出檔內自動記錄 `exportedAt`、`sourceUpdatedAt` 與筆數，方便管理者留存備份快照，並以本機瀏覽器流程驗證可實際下載（使用 skill: frontend-testing-debugging）。
- [18:00] 將目前 `course_admin.html` / `cloudrun_admin.py` 版本重新部署到 Cloud Run `graduate-course-admin`，升級 revision `graduate-course-admin-00011-4hj`，並補上正式環境的 `ALUMNI_STORAGE_BUCKET=ntujour-graduate` 與 `ALUMNI_STORAGE_PREFIX=alumni/raw-submissions`；已確認 IAP 仍啟用且未登入請求會導向 Google OAuth。（使用 skill: frontend-testing-debugging）
- [18:30] 部署公開填表服務 `graduate-alumni-form` 至 Cloud Run，正式網址為 `https://graduate-alumni-form-sb2s54rpvq-de.a.run.app/`，使用 `cloudrun_alumni:app` 與 `ntujour-graduate/alumni/raw-submissions`；已完成公開頁載入、`OPTIONS /api/alumni-submissions`、真實提交與 bucket 落檔驗證，並刪除測試檔，維持暫時不掛首頁入口（使用 skill: frontend-testing-debugging）
- [23:59] 大幅重設 `alumni_form.html` 的前端介面：將原本仿社會系的表單改成 5 步驟的新視覺版型，保留核心題目但把「還在聯絡的所友」移入資源頁、刪除 `想串聯的人`、新增兩個「系辦分享方式」選項、移除 `授權：學術合作` 與取消訂閱文案，並同步更新 `course_admin.html` 與 `cloudrun_alumni.py` 的 alumni 欄位映射；已完成本機表單與後台 smoke test 驗證（使用 skill: web-project-startup、frontend-design、frontend-testing-debugging）
- [00:25] 再收斂 `alumni_form.html` 的版面：移除左側欄位、改回上方 header + 步驟列、將整體配色對齊新聞所首頁的淺底藍色系，並把 `所在行業`、`能提供的資源`、`希望獲得的資源` 等多選區塊改成直接勾選的 plain checkbox 清單，不再使用每項藥丸框；已完成本機 syntax 與 Playwright 渲染驗證（使用 skill: web-project-startup、frontend-design、frontend-testing-debugging）
- [00:35] 將 `alumni_form.html` 的步驟列改為直向方塊卡片，移除中間箭頭與多餘的第一頁說明文字，並將步驟 active 狀態改回磚紅色系；已完成本機 syntax 與 Playwright 驗證，確認 5 個步驟方塊可正常切頁（使用 skill: web-project-startup、frontend-design、frontend-testing-debugging）
- [00:41] 再把 `alumni_form.html` 的步驟列改成左至右的五格方塊，並把 major cards、表單欄位、按鈕與選項元件的圓角壓平；已完成本機 syntax 與 Playwright 驗證，確認步驟列仍可正常切頁且不再是縱向堆疊（使用 skill: web-project-startup、frontend-design、frontend-testing-debugging）
- [00:55] 收斂系友表單用字：將目前狀態的 `兼職／接案` 改為 `獨立記者／獨立接案`，並把所有「系辦」相關說明改成「所辦」，同步更新所辦與公開分享的授權文案（使用 skill: web-project-startup）
- [01:39] 再調整系友表單的聯絡與公開欄位：把聯絡設定移回基本資料、將公開姓名欄位改成按入學所級列出姓名、並把 `如步驟一有填寫` 的補充註記改成灰字樣式；已完成本機語法檢查與 headless browser 驗證（使用 skill: web-project-startup、frontend-testing-debugging）

## 2026-09-08

- [01:10] 將主站 30 位教師的中英文資料與長篇著作匯入教師雲端管理試作；採用輕量名單與逐人、逐語言完整 JSON，保留原始資料副本並完成內容完整性測試（使用 skill: web-project-startup、playwright）。
- [01:58] 把教師管理加入既有 `graduate-course-admin` 並部署 revision `graduate-course-admin-00012-trk`；新增獨立私有草稿 bucket 與 `faculty-pilot/v1` 公開試用資料，正式中英文網站尚未切換。已驗證舊管理功能、登入、長篇著作預覽及發布保護。
- [02:05] 驗證期間觀察到舊 revision `00011-4hj` 收到一筆指導學生資料 PUT 並自動備份；教師模組未呼叫該 API，因此保留該筆外部／既有後台變更，不進行回復。
- [07:15] 將教師管理首頁改為緊湊清單，顯示 30 位教師的主站列表資料、類別、中英文站狀態、專長與聯絡方式，點選後才進入完整雙語資料與長篇著作編輯；完成桌面／手機瀏覽器驗證後部署至既有 `graduate-course-admin` revision `00013-8qp`（使用 skill: frontend-design、webapp-testing）。
- [20:20] 在教師編輯頁新增照片上傳與取代功能，支援 JPG、PNG、WebP 與 8 MB 上限；上傳端會驗證、修正方向、縮圖並重新編碼，更新草稿照片網址且保留舊圖。API 與瀏覽器測試通過後部署至原服務 revision `00014-vhk`（使用 skill: frontend-design、webapp-testing）。
- [21:01] 把教師管理從工具列獨立入口移入共用五項資料選單，教師頁同步提供課程、指導學生、常態活動與系友收件入口，並移除「試用」顯示文字；補齊 Cloud Run 管理狀態 API，完成選單深連結及無前端錯誤驗證後部署 revision `00015-xfh`（使用 skill: frontend-design、webapp-testing）。
- [23:34] 在教師編輯頁新增教師類別與列表排序控制，支援「歷任實務教師」以區別單純不再授課與正式退休／名譽身分；類別保存、無效值拒絕、英文站顯示狀態與瀏覽器互動測試通過後部署 revision `00016-2sn`（使用 skill: frontend-design、webapp-testing）。

## 2026-09-08

- [23:41] 依需求在一般後台與教師管理加入系友問卷、主站首頁入口，保留學生服務公開首頁；連結可見性與目的網址已驗證（使用 skill: web-project-startup）。
- [23:42] 後台入口更新已部署至 Cloud Run，並在已登入的線上一般管理頁與教師管理頁確認兩個連結正常顯示。

## 2026-09-12

- [00:07] 診斷 Admin 的 Service Unavailable：Cloud Run 最新 revision 雖標示 Ready，但映像未包含新加入的 `news_portal` 模組，Gunicorn worker 載入失敗並回傳 503；待補齊部署檔案後重新發布與驗證（使用 skill: webapp-testing）。
- [00:14] 補齊 Cloud Run 映像與上傳清單中的 `news_portal`，部署 `graduate-course-admin-00019-xkn`；線上課程管理與最新消息後台均正常載入，沒有新增 5xx 錯誤（使用 skill: webapp-testing）。
- [00:21] 確認 19 張舊消息縮圖仍存在主站，修正 Cloud Run Admin 對 `/images/news/*` 相對路徑的預覽解析並部署 `graduate-course-admin-00020-pmn`；線上縮圖已恢復且未再產生相關 404（使用 skill: webapp-testing）。
- [00:30] 將教師與最新消息編輯頁的中英文切換改為「中文／English」分頁，保留切換時尚未儲存的內容並支援左右方向鍵；桌面、手機與線上 Cloud Run 驗證通過，部署 revision `graduate-course-admin-00021-25n`（使用 skill: frontend-design、webapp-testing）。
- [00:39] 建立「網站管理入口」，集中六個管理頁與主站、英文站、學生服務 Portal、系友問卷，並在課程、教師及最新消息管理頁加入返回入口；桌面、手機與正式網址驗證通過，部署 revision `graduate-course-admin-00022-d7r`（使用 skill: frontend-design、webapp-testing）。
- [01:05] 依使用者澄清關閉 Cloud Run `/links/` 與各管理頁的入口按鈕，部署 revision `graduate-course-admin-00023-zfq`；另建立並私人發布 ChatGPT Sites 網站入口，集中六個管理頁與四個公開網站（使用 skill: sites:sites-building、sites:sites-hosting）。

## 2026-09-13

- [15:28] 擴充消息後台為「消息與活動管理」，保留原有 25 筆消息並匯入 59 筆活動，發布含獨立活動索引的雲端版本；部署 Cloud Run revision `graduate-course-admin-00024-qxr`，線上確認 84 筆草稿、類型篩選與發布狀態正常（使用 skill: webapp-testing）。

## 2026-09-15

- [23:57] 在教師管理加入中文／英文教師頁獨立顯示勾選，保留隱藏教師的完整雙語資料與照片；舊資料自動沿用既有顯示結果，部署 Cloud Run revision `graduate-course-admin-00026-68v` 並完成正式登入介面驗證（使用 skill: webapp-testing、graduate-deploy-verify）。

## 2026-09-16

- [00:20] 教師資料新增主要分類之外的額外列表分類，管理介面加入「同時列入退休教師」勾選；谷玲玲與張錦華已保存並發布為退休教師成員，同時維持原兼任／名譽身分。部署 Cloud Run revision `graduate-course-admin-00028-zkz` 並驗證正式頁（使用 skill: webapp-testing、graduate-deploy-verify）。
- [13:12] 完成本機「新增教師」流程：清單加入新增入口，新紀錄預設合聘教師、排序接續 502 且中英文不公開；首次儲存後才開放照片與預覽，發布前會檢查公開語言的照片與職稱。17 項教師／消息測試與本機瀏覽器操作均通過；本次未部署 Cloud Run。
- [13:46] 將新增教師流程部署至 Cloud Run revision `graduate-course-admin-00029-2dt`，100% 流量切換後確認 IAP、管理員名單、service account 與資料物件設定均未變。部署前以正式草稿分別交由舊版及新版模型產生公開資料，release hash、62 個檔案內容及 `schemaVersion: 1` 完全相同；部署後正式草稿 generation 與公開 `current.json` 亦未改動。線上瀏覽器確認新增表單預設合聘教師且中英文不公開，未建立或發布任何資料。
- [14:16] 新增蘇慧婕合聘教師草稿（`hui-chieh-su`、排序 502），填入中英文姓名、中文職稱、Email、授課領域與研究專長，並上傳使用者提供的 400×400 照片。中英文公開狀態均維持關閉，草稿預覽與照片載入正常、瀏覽器無錯誤；公開 release `bcf174b…` 未切換，正式中文索引仍為 25 筆且不含本筆資料。
- [14:39] 主站 FTPS 後驗證公開教師 JSON 已指向 release `37cec6e…`：中文索引為 26 筆且包含蘇慧婕，英文索引仍為 7 筆且不含此教師；此回合未操作 Cloud Run 後台的發布功能，僅記錄驗證時觀察到的公開狀態。
## 2026-09-17

- [01:16] 在學生服務 Portal 的「相關表單」加入固定置頂的「兼任助理打卡」入口，連往正式 Cloud Run 打卡系統；維持 CSV 同步表單在後方顯示（使用 skill: graduate-page-editing、web-project-startup）。
- [01:17] 僅發布 `index.html` 至 `gs://ntujour-graduate`，確認公開 Portal 首張相關表單卡片可正常開啟正式打卡系統。
- [01:21] 將學生服務 Portal 的「相關表單」整區移到「相關鏈結」之前；公開頁確認區塊順序與置頂打卡入口皆正常（使用 skill: graduate-page-editing、web-project-startup）。

## 2026-09-18

- [23:45] 將消息與活動編輯頁的標籤欄升級為互動式標籤編輯器，支援 Enter 建立、歷史標籤自動建議、鍵盤選擇與 × 刪除；完成資料模型、本機瀏覽器及正式登入介面驗證，部署 Cloud Run revision `graduate-course-admin-00030-hz6`，原有 IAP、管理員、service account 與資料物件設定均維持不變（使用 skill: frontend-design、webapp-testing）。

## 2026-09-20

- [現在] 教師公開 release 改為只寫入已勾選公開語言的個人檔，並在發布時清除所有舊公開 release 的已隱藏個人檔；已發布 release `8bf837e…`。系友問卷 API 改為必填 origin allowlist、64KB 請求上限與每來源每小時 5 次限制，Cloud Run `graduate-course-admin-00032-z4g` 與 `graduate-alumni-form-00002-lf9` 均已 Ready。

- [00:19] 強化 `graduate-course-admin` 管理權限：空白 `ADMIN_EMAILS` 改為拒絕全部請求，改以 IAP 簽署 JWT 驗證身份及服務 audience，不再信任可偽造的 email header；維持既有 4 位管理員與 4 位 IAP 使用者。安全測試通過，部署 revision `graduate-course-admin-00031-2lq` 並確認 IAP 將偽造 header 導向登入（使用 skill: python-project-startup）。
- [02:31] 修正教師發布與系友問卷限流：教師公開指標會先以 generation precondition 切換，再清除舊 release 的隱藏個人檔，避免競爭失敗時舊索引出現失效連結；問卷限流改採 Cloud Run 追加在 `X-Forwarded-For` 最右端的客戶端 IP，忽略可偽造的前段值。24 項回歸測試通過，部署 `graduate-course-admin-00034-drh` 與 `graduate-alumni-form-00003-g8k`，公開教師指標未變更。

## 2026-09-21

- [20:51] 整理 Graduate Services 正式來源為 `stable-0921` Git 版本，納入目前 Cloud Run、Portal、教師、消息、活動與系友服務程式，排除虛擬環境、輸出備份、暫存與 QA 產物；修正工作區搬遷後的一次性匯入路徑，26 項回歸測試通過。
