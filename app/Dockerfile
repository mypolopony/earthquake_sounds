# Stage 1: Build environment
FROM python:3.11-slim as builder

# Install Poetry
RUN pip install poetry

# Set work directory
WORKDIR /app

# Copy Poetry files first to leverage Docker layer caching
COPY pyproject.toml poetry.lock /app/

# Install dependencies without dev dependencies
RUN poetry config virtualenvs.create false \
    && poetry install --only main --no-interaction --no-ansi

# Copy the rest of the application code
COPY . /app

# Stage 2: Runtime environment
FROM python:3.11-slim

# Set work directory
WORKDIR /app

# Copy dependencies from build stage
COPY --from=builder /app /app

# Expose the application port
EXPOSE 5001

# Start the app
CMD ["python", "app.py"]