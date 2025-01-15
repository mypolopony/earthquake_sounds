# Stage 1: Build environment
FROM python:3.11-slim as builder

# Install Poetry
RUN pip install --no-cache-dir poetry

# Set work directory
WORKDIR /app

# Copy Poetry files first to leverage Docker layer caching
COPY pyproject.toml poetry.lock /app/

# Install dependencies without dev dependencies
# Ensure that the virtual environment is created in the project directory
# (it will get obliterated if it goes to /root)
RUN poetry config virtualenvs.in-project true \
    && poetry install -vvv --no-interaction --no-ansi

# Copy the rest of the application code
COPY . /app

# Stage 2: Runtime environment
FROM python:3.11-slim

# Set work directory
WORKDIR /app

# Copy application files, including the .venv directory
COPY --from=builder /app /app

# Add virtual environment to PATH
ENV PATH="/app/.venv/bin:$PATH"

# Expose the application port
EXPOSE 5001

# Start the app
CMD ["python", "app.py"]