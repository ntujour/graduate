# 系友表單 Cloud Run 部署

`alumni_form.html` 是公開表單頁；`cloudrun_alumni.py` 是公開提交 API。這條路徑的目的，是保留前端問卷體驗，但把系友資料寫到 Google Cloud 的私有儲存空間，而不是放在 Airtable 或前端 JavaScript。

## 架構

- 公開表單頁：`alumni_form.html`
- 公開提交 API：`POST /api/alumni-submissions`
- 儲存位置：私有 Google Cloud Storage bucket
- 每筆提交會存成一個獨立 JSON 檔，方便之後由管理後台列出、整理、匯出或轉成正式系友主檔

## 為什麼不直接用既有管理服務

既有 `graduate-course-admin` 服務目前是課程與指導學生管理介面，正式資料也已經綁在 `data/courses.json` 與 `data/advisees.json`。  
系友資料是另一條新線，應該獨立儲存，避免動到現有主資料結構。

## 建議的資料落點

建議使用另一個私有 bucket，例如：

```text
gs://YOUR_PRIVATE_BUCKET/alumni/raw-submissions/YYYY/MM/DD/<submission-id>.json
```

每筆提交內容會包含：

- `submissionId`
- `submittedAt`
- `schemaVersion`
- `status`
- `fields`

這樣管理者日後可以：

- 列出所有 raw submissions
- 建立正式的 alumni records
- 加上標籤、狀態、備註
- 匯出 CSV 或搬到另一個管理系統

## 需要的環境變數

```text
APP_MODULE=cloudrun_alumni:app
ALUMNI_STORAGE_BACKEND=gcs
ALUMNI_STORAGE_BUCKET=YOUR_PRIVATE_BUCKET
ALUMNI_STORAGE_PREFIX=alumni/raw-submissions
```

選填：

```text
ALUMNI_ALLOWED_ORIGINS=https://graduate-alumni-form-xxxxx.a.run.app,https://storage.googleapis.com
```

`ALUMNI_ALLOWED_ORIGINS` 為必要設定；未設定時 API 會拒絕所有瀏覽器送件。表單頁與 API 同一個 Cloud Run service 時，填入該 service 的 HTTPS 網址。

這個設定是 CORS 的瀏覽器邊界，不能作為防濫用或身分驗證機制，因為程式呼叫可自行偽造 `Origin`。提交頻率改由 Cloud Run 在代理鏈最後加入的客戶端 IP 限制；若日後需要抵擋大量分散來源的濫用，應在 Cloud Armor 或 CAPTCHA 層處理。

## 部署指令

```bash
PROJECT_ID="ntujour"
REGION="asia-east1"
SERVICE="graduate-alumni-form"
BUCKET="your-private-alumni-bucket"

gcloud config set project "$PROJECT_ID"
gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com storage.googleapis.com

gcloud run deploy "$SERVICE" \
  --source . \
  --region "$REGION" \
  --allow-unauthenticated \
  --set-env-vars "APP_MODULE=cloudrun_alumni:app,ALUMNI_STORAGE_BACKEND=gcs,ALUMNI_STORAGE_BUCKET=$BUCKET,ALUMNI_STORAGE_PREFIX=alumni/raw-submissions,ALUMNI_ALLOWED_ORIGINS=https://graduate-alumni-form-sb2s54rpvq-de.a.run.app,ALUMNI_MAX_REQUEST_BYTES=65536,ALUMNI_RATE_LIMIT_PER_HOUR=5"
```

讓 Cloud Run 的 service account 可以寫入私有 bucket：

```bash
SERVICE_ACCOUNT="$(gcloud run services describe "$SERVICE" \
  --region "$REGION" \
  --format='value(spec.template.spec.serviceAccountName)')"

gcloud storage buckets add-iam-policy-binding "gs://$BUCKET" \
  --member="serviceAccount:$SERVICE_ACCOUNT" \
  --role="roles/storage.objectAdmin"
```

## 本機驗證

本機測試時可以改用檔案模式，不需要 GCP 權限：

```bash
export APP_MODULE=cloudrun_alumni:app
export ALUMNI_STORAGE_BACKEND=local

python -m flask --app cloudrun_alumni run --debug
```

然後開：

```text
http://127.0.0.1:5000/
```

## 管理後台的分工

- 公開提交服務只負責收件與落檔
- 管理後台之後再獨立做成另一個 private admin service
- 管理後台讀同一個私有 bucket，但不會改到 `data/advisees.json`
- 如果日後要跟指導教授或論文資料做關聯，也應該在 alumni 這條線上建立新關聯欄位，不要回寫現有主檔

## 公開站整合原則

- 可以先不把這個表單連到 `index.html`
- 不要把儲存金鑰、bucket 名稱以外的敏感資訊寫回 `alumni_form.html`
- 這條線先獨立運作，之後再決定是否和首頁或其他頁面串接
