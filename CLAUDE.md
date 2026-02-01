# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 專案概述

台大新聞所學生服務平台（NTU Journalism Services Portal），提供課程資訊、指導教師資源、活動時程等整合性服務。這是一個純前端靜態網站，資料來源為 Google Sheets 透過 CSV 匯出。

## 技術架構

- **前端框架**: 原生 HTML + Tailwind CSS (CDN) + D3.js (視覺化)
- **資料來源**: Google Sheets → CSV（存於 `data/` 目錄）
- **資料同步**: Python 腳本 (`update_forms.py`) 從 Google Sheets 下載 CSV

### 設計系統
- CSS 變數定義於各頁面 `:root`，統一使用 `--portal-*` 命名
- 共用樣式放在 `style.css`，部分頁面有內嵌樣式
- 圓角統一使用 `--portal-radius: 3px`，避免過度圓潤

## 主要頁面

| 檔案 | 功能 | 資料來源 |
|------|------|----------|
| `index.html` | 首頁/入口 | `data/office.csv` |
| `advisee.html` | 指導學生狀態 | `data/advisee.csv` |
| `courses.html` | 課程地圖（互動式拖拉規劃）| `data/courses.csv` |
| `courseplan.html` | 開課規劃（學期課程表）| `data/courses.csv` |
| `regular_event.html` | 常態活動時程 | `data/regular_event.csv` |

## 資料更新指令

```bash
# 從 Google Sheets 同步所有 CSV 資料
python update_forms.py
```

此腳本會下載以下資料：
- `office.csv` - 相關表單/公告
- `advisee.csv` - 指導學生資料
- `courses.csv` - 課程資訊
- `regular_event.csv` - 常態活動

## 目錄結構

```
graduate/
├── data/           # CSV 資料檔案
├── backup/         # 舊版檔案備份
├── knownews/       # 「媒聽說」子專案
└── *_old.html      # 舊版頁面
```

## 開發注意事項

1. **CSV 編碼**: 使用 UTF-8 with BOM (`utf-8-sig`)，確保中文正確顯示
2. **資料欄位**: 修改資料結構前，需同步更新對應的 HTML 中的 JavaScript 解析邏輯
3. **課程類別**: `courses.csv` 中的 `category` 欄位決定課程分類（必修、必選修-方法、必選修-實務等）
4. **D3.js 互動**: `courses.html` 使用 D3.js 實作課程拖拉功能，邏輯較複雜
