# ---- Stage 1: install dependencies ----
FROM python:3.12-slim AS builder
WORKDIR /build
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ---- Stage 2: runtime (small, non-root) ----
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    ACEEST_DB=/data/aceest_fitness.db
WORKDIR /app
COPY --from=builder /install /usr/local
COPY app.py .
RUN useradd --no-create-home --shell /usr/sbin/nologin appuser \
    && mkdir /data && chown appuser /data
USER appuser
VOLUME /data
EXPOSE 5000
HEALTHCHECK --interval=30s --timeout=3s CMD python -c "import urllib.request as u; u.urlopen('http://localhost:5000/health')" || exit 1
# One worker: SQLite + a single writer keeps things simple and safe.
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "1", "--threads", "4", "app:app"]
