# ===== Stage 1: Build environment =====
FROM python:3.11 as builder

# Install system dependencies for ObsPy and scientific stack
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    gfortran \
    libxml2-dev \
    libxslt1-dev \
    libatlas-base-dev \
    liblapack-dev \
    libblas-dev \
    libgeos-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Poetry
ENV POETRY_VERSION=1.8.3
ENV POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_CREATE=false
RUN pip install --upgrade pip && pip install "poetry==$POETRY_VERSION"

# Copy project and install dependencies
WORKDIR /build
COPY pyproject.toml poetry.lock* ./
# Ensure dependencies are installed and poetry.lock is up-to-date before exporting
RUN poetry install --no-dev --no-interaction --no-ansi
RUN poetry export -f requirements.txt --output requirements.txt --without-hashes --with-credentials
RUN pip wheel --wheel-dir=/wheels -r requirements.txt

# Copy remaining app source
COPY . .

# Install app as wheel (optional)
# RUN poetry build -f wheel

# ===== Stage 2: Minimal runtime =====
FROM python:3.11-slim

# Install system libs needed at runtime (no compilers!)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libatlas-base-dev \
    liblapack3 \
    libblas3 \
    libglib2.0-0 \
    libgeos-dev \
    && rm -rf /var/lib/apt/lists/*

# Install app dependencies from wheels
COPY --from=builder /wheels /wheels
RUN pip install --no-cache-dir --no-index --find-links=/wheels /wheels/*

# Copy app source code
WORKDIR /app
COPY --from=builder /build .

# Allow logging to stdout
ENV PYTHONUNBUFFERED=1

CMD ["python", "producer.py", "--debug"]