# 課程 JSON 雲端發布

本專案現在以 `data/courses.json` 作為課程資料的正式公開讀取格式。CSV 只作為匯入來源；轉成 JSON 並發布後，公開頁與管理介面都以 JSON 為準。

## 本機管理流程

```bash
# 由本機 CSV 重新產生 JSON，並保留額外補充欄位
python build_courses_json.py \
  --source data/courses.csv \
  --merge-missing data/courses.csv \
  --output data/courses.json

# 啟動管理介面，遠端 bucket 是唯一正式來源
DATA_BUCKET=ntujour-graduate python course_admin.py
```

管理介面會開在 `http://127.0.0.1:8765/`。啟動時會先同步遠端正式 JSON 到本機工作副本；若 `DATA_BUCKET` 未設定或遠端不可用，介面會自動進入唯讀模式。按下「儲存 JSON」前會先比對版本，通過後才更新資料並備份舊檔。

## Google Cloud Storage

以下指令假設已安裝並登入 Google Cloud CLI，且目前專案已設定：

```bash
gcloud auth login
gcloud config set project YOUR_PROJECT_ID
```

建立 bucket：

```bash
gcloud storage buckets create gs://YOUR_BUCKET_NAME \
  --location=asia-east1 \
  --uniform-bucket-level-access
```

允許公開讀取 JSON：

```bash
gcloud storage buckets add-iam-policy-binding gs://YOUR_BUCKET_NAME \
  --member=allUsers \
  --role=roles/storage.objectViewer
```

設定 CORS，讓網站可跨網域讀取 JSON：

```bash
gcloud storage buckets update gs://YOUR_BUCKET_NAME \
  --cors-file=data/courses-cors.json
```

上傳課程 JSON：

```bash
gcloud storage cp data/courses.json gs://YOUR_BUCKET_NAME/courses.json \
  --content-type=application/json \
  --cache-control=no-cache
```

公開網址會是：

```text
https://storage.googleapis.com/YOUR_BUCKET_NAME/courses.json
```

若要讓網站改讀雲端 JSON，可以在頁面載入 `courses-data.js` 之前設定：

```html
<script>
  window.COURSES_DATA_URL = "https://storage.googleapis.com/YOUR_BUCKET_NAME/courses.json";
</script>
```

目前 `courses.html` 和 `courseplan.html` 預設仍讀本機 `data/courses.json`，適合先用 GitHub Pages 或現有靜態主機部署；確認 GCS URL 後再切換即可。
