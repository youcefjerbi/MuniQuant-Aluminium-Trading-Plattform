FROM python:3.12-slim
WORKDIR /app
COPY requirements.lock pyproject.toml ./
COPY app ./app
RUN pip install --no-cache-dir -r requirements.lock && pip install --no-cache-dir --no-deps . && useradd -m appuser
COPY migrations ./migrations
COPY alembic.ini ./
RUN mkdir -p /app/data && chown -R appuser:appuser /app
USER appuser
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
