FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY cloudrun_admin.py cloudrun_alumni.py course_admin.py course_admin.html courses-data.js advisees-data.js alumni_form.html ./
COPY faculty_portal/ ./faculty_portal/
COPY news_portal/ ./news_portal/

ENV APP_MODULE=cloudrun_admin:app

CMD exec gunicorn --bind :${PORT:-8080} --workers 1 --threads 8 --timeout 0 ${APP_MODULE}
