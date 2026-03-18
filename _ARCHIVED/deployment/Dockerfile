# =============================================================================
# Dagster User Code Server - Production Image
# =============================================================================
# Python 3.11 on slim Debian base
# Uses dbt-snowflake adapter for Snowflake warehouse

FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# dbt adapter for Snowflake
RUN pip install --no-cache-dir dbt-snowflake

# Copy project files
COPY dagster/ dagster/
COPY load_config.py .
COPY config.json .

# Pre-build dbt manifest (requires dbt deps + parse at build time)
WORKDIR /app/dagster/dbt
RUN dbt deps --profiles-dir .

WORKDIR /app

# Dagster user code server port
EXPOSE 3030

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python -c "import dagster; print('ok')" || exit 1

# Dagster gRPC server entry point
CMD ["python", "-m", "dagster", "api", "grpc", \
     "-h", "0.0.0.0", "-p", "3030", \
     "-f", "dagster/definitions.py"]
