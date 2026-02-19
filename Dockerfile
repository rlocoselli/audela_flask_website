FROM python:3.10-slim

# Microsoft ODBC Driver 18 for SQL Server (Debian 9-13)
RUN set -eux; \
    apt-get update; \
    apt-get install -y --no-install-recommends \
      curl ca-certificates \
      unixodbc unixodbc-dev \
      libgssapi-krb5-2; \
    . /etc/os-release; \
    curl -sSL -o /tmp/packages-microsoft-prod.deb \
      "https://packages.microsoft.com/config/debian/${VERSION_ID}/packages-microsoft-prod.deb"; \
    dpkg -i /tmp/packages-microsoft-prod.deb; \
    rm -f /tmp/packages-microsoft-prod.deb; \
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
