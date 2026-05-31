FROM python:3.11-slim

WORKDIR /app

# для Playwright
RUN apt-get update && apt-get install -y \
    wget gnupg curl \
    fonts-dejavu-core \
    libnss3 libatk-bridge2.0-0 libxkbcommon0 \
    libgtk-3-0 libasound2 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

RUN pip install psycopg2-binary

ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
RUN python -m playwright install --with-deps chromium

COPY . .
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "10000"]