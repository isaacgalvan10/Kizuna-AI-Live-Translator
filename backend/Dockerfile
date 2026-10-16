# 1. Base Image
FROM python:3.14-slim

# 2. Environment Variables
# POETRY_VIRTUALENVS_CREATE=false is vital for Docker
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    POETRY_VIRTUALENVS_CREATE=false

# 3. Work Directory
WORKDIR /app

# 4. Install Poetry Tool (CRITICAL MISSING STEP)
# You must install the 'poetry' executable before you can use it!
RUN pip install --no-cache-dir poetry

# 5. Dependency Layer (The Poetry Way)
# We copy pyproject.toml instead of requirements.txt
COPY pyproject.toml poetry.lock* ./

# 6. Install Dependencies
# --no-root means "Install libraries only, not the app code yet"
RUN poetry install --no-root --no-interaction --no-ansi

# 7. Copy Application Code
COPY . .

# 8. Security & Permissions
RUN useradd -m appuser && chown -R appuser /app
USER appuser

# 9. Start Command
CMD ["gunicorn", "app.main:app", "--workers", "4", "--worker-class", "uvicorn_worker.UvicornWorker", "--bind", "0.0.0.0:8000"]