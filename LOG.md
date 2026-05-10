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
