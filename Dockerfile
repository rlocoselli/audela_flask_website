FROM python:3.10-slim

# --- System deps ---
# - libpq-dev: PostgreSQL driver build support
# - unixodbc-dev + msodbcsql18: optional pyodbc (SQL Server)
# - poppler-utils + tesseract-ocr: optional PDF/OCR features (pdf2image/pytesseract)
RUN set -eux; \
    apt-get update; \
    apt-get install -y --no-install-recommends \
      build-essential gcc g++ \
      curl ca-certificates gnupg apt-transport-https \
      libpq-dev \
      unixodbc unixodbc-dev \
      poppler-utils tesseract-ocr; \
    # Microsoft ODBC Driver 18 for SQL Server (Debian)
    mkdir -p /etc/apt/keyrings; \
    curl -fsSL https://packages.microsoft.com/keys/microsoft.asc | gpg --dearmor -o /etc/apt/keyrings/microsoft.gpg; \
    chmod 0644 /etc/apt/keyrings/microsoft.gpg; \
    . /etc/os-release; \
    echo "deb [arch=amd64,arm64 signed-by=/etc/apt/keyrings/microsoft.gpg] https://packages.microsoft.com/debian/${VERSION_ID}/prod ${VERSION_CODENAME} main" > /etc/apt/sources.list.d/microsoft-prod.list; \
    apt-get update; \
    ACCEPT_EULA=Y apt-get install -y --no-install-recommends msodbcsql18; \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps first (better layer caching)
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Create an unprivileged user
RUN useradd -m -u 10001 appuser \
  && chown -R appuser:appuser /app
USER appuser

# Instance folder (SQLite fallback, uploads, tenant files)
RUN mkdir -p /app/instance /app/instance/tenant_files

EXPOSE 8000

# Default command (overridden by docker-compose if needed)
CMD ["gunicorn", "-b", "0.0.0.0:8000", "--workers", "3", "--threads", "4", "--timeout", "120", "app:app"]
