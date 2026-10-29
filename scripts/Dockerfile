FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY sync_mysql_to_postgres.py .

CMD ["python", "sync_mysql_to_postgres.py", "--interval", "15"]
