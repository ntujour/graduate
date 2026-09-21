# Cloud Run 課程管理介面

公開頁面放在 Google Cloud Storage；Cloud Run 只放管理介面與 API，負責讀寫同一個 bucket 裡的 `data/courses.json` 與 `data/advisees.json`。

## 資料來源規則

- 正式資料來源是 bucket 內的 JSON：
  - `gs://YOUR_BUCKET/data/courses.json`
  - `gs://YOUR_BUCKET/data/advisees.json`
- 公開頁與管理介面都只讀這兩個 JSON。
- Word、CSV 只作為匯入來源；匯入後需轉成 JSON，並由管理介面或部署流程發布。
- JSON 內的 `source` 固定標示 canonical JSON；原始匯入來源保留在 `importSource`。

## 架構

- 公開網站：Cloud Storage bucket，允許 `allUsers` 讀取
- 管理介面：Cloud Run，建議用 IAP 或 Cloud Run authentication 限制使用者
- 資料檔：`gs://YOUR_BUCKET/data/courses.json`、`gs://YOUR_BUCKET/data/advisees.json`

## 部署

```bash
PROJECT_ID="你的-gcp-project-id"
REGION="asia-east1"
BUCKET="你的-public-bucket-name"
SERVICE="graduate-course-admin"
ADMIN_EMAIL="you@example.com"

gcloud config set project "$PROJECT_ID"
gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com storage.googleapis.com

gcloud run deploy "$SERVICE" \
  --source . \
  --region "$REGION" \
  --no-allow-unauthenticated \
  --set-env-vars "DATA_BUCKET=$BUCKET,COURSES_OBJECT=data/courses.json,ADVISEES_OBJECT=data/advisees.json"
```

讓指定使用者可以叫用 Cloud Run：

```bash
gcloud run services add-iam-policy-binding "$SERVICE" \
  --region "$REGION" \
  --member="user:$ADMIN_EMAIL" \
  --role="roles/run.invoker"
```

讓 Cloud Run 的 service account 可以更新課程 JSON。先查服務身分：

```bash
SERVICE_ACCOUNT="$(gcloud run services describe "$SERVICE" \
  --region "$REGION" \
  --format='value(spec.template.spec.serviceAccountName)')"

echo "$SERVICE_ACCOUNT"
```

如果輸出是空值，Cloud Run 使用預設 Compute Engine service account；可在 Cloud Run console 的 Security / Service identity 查看完整帳號。給它 bucket 物件管理權：

```bash
gcloud storage buckets add-iam-policy-binding "gs://$BUCKET" \
  --member="serviceAccount:$SERVICE_ACCOUNT" \
  --role="roles/storage.objectAdmin"
```

## 關於瀏覽器登入

Cloud Run 的 `--no-allow-unauthenticated` 使用 IAM 驗證；適合用 Google Cloud 帳號與 `roles/run.invoker` 控制。這種模式下，管理頁不會在一般瀏覽器直接跳 Google 登入頁，未帶 token 的請求會回 403；若要一般瀏覽器直接出現 Google 登入頁，請在 Cloud Run 前面啟用 IAP，並把可管理的人加入 IAP allowlist。

`cloudrun_admin.py` 會驗證 IAP 的 `X-Goog-IAP-JWT-Assertion` 簽章、issuer 與 audience，並以簽署 token 內的 email 比對 `ADMIN_EMAILS`。`X-Goog-Authenticated-User-Email` 是未簽署的相容 header，不可作為權限判斷依據。

管理服務必須設定兩個環境變數：

```text
ADMIN_EMAILS=owner@example.com,student-admin@example.com
IAP_JWT_AUDIENCE=/projects/PROJECT_NUMBER/locations/REGION/services/SERVICE_NAME
```

任一設定缺失時後台會拒絕所有請求。新增或移除管理員時，同步更新 `ADMIN_EMAILS` 和 IAP 的 `roles/iap.httpsResourceAccessor` allowlist。

## 更新公開頁面

管理介面儲存後會直接覆寫：

```text
gs://YOUR_BUCKET/data/courses.json
gs://YOUR_BUCKET/data/advisees.json
```

覆寫前 Cloud Run 會自動備份舊檔：

```text
gs://YOUR_BUCKET/backup/courses-YYYYMMDD-HHMMSS.json
gs://YOUR_BUCKET/backup/advisees-YYYYMMDD-HHMMSS.json
```

公開頁面只要從同一個 bucket 讀 `data/courses.json` 與 `data/advisees.json`，就會使用最新資料。

## 目前部署值

2026-05-13 已搬移至 `ntujour` project，使用以下設定部署：

```text
PROJECT_ID=ntujour
REGION=asia-east1
BUCKET=ntujour-graduate
SERVICE=graduate-course-admin
SERVICE_ACCOUNT=graduate-course-admin-sa@ntujour.iam.gserviceaccount.com
ADMIN_EMAIL=jirlong@gmail.com
COURSES_OBJECT=data/courses.json
ADVISEES_OBJECT=data/advisees.json
```

公開頁面：

```text
https://storage.googleapis.com/ntujour-graduate/index.html
https://storage.googleapis.com/ntujour-graduate/courseplan.html
```

Cloud Run 管理服務：

```text
https://graduate-course-admin-sb2s54rpvq-de.a.run.app
https://graduate-course-admin-623280269212.asia-east1.run.app
```

目前管理服務已啟用 IAP，並已將 `jirlong@gmail.com` 加入 `roles/iap.httpsResourceAccessor`。如果直接開管理 URL 回 `Empty Google Account OAuth client ID(s)/secret(s)`，表示 `ntujour` project 尚未完成第一次 IAP OAuth client 設定；需到 Cloud Console 的 Cloud Run 服務 Security / IAP 設定中完成 OAuth consent，並使用 Auto generate credentials。

若要在本機以瀏覽器使用受保護服務，可先開 proxy：

```bash
gcloud run services proxy graduate-course-admin \
  --project ntujour \
  --region asia-east1 \
  --port 8080
```

然後開：

```text
http://127.0.0.1:8080/
```

舊 project `pacific-chalice-390913` 的 `ntujour-graduate` bucket 已移除，並在 `ntujour` project 重建同名 bucket，因此正式公開連結維持不變。舊 bucket `ntu-journalism-graduate-services` 曾作為初次部署目標，目前未作為正式公開連結。
