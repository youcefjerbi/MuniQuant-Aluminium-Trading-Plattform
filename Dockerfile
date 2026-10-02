FROM python:3.12-slim AS builder
WORKDIR /build
RUN apt-get update && apt-get install -y --no-install-recommends g++ && rm -rf /var/lib/apt/lists/*
COPY requirements.lock pyproject.toml setup.py ./
COPY cpp ./cpp
COPY app ./app
RUN pip install --no-cache-dir -r requirements.lock && pip wheel --no-build-isolation --no-deps . -w /wheels

FROM python:3.12-slim
WORKDIR /app
COPY --from=builder /wheels /wheels
COPY requirements.lock ./
RUN pip install --no-cache-dir -r requirements.lock && pip install --no-deps /wheels/*.whl && rm -rf /wheels && useradd -m appuser
COPY app ./app
COPY migrations ./migrations
COPY alembic.ini ./
RUN mkdir -p /app/data && chown -R appuser:appuser /app
USER appuser
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
