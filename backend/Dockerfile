# ── Build stage ──────────────────────────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /app

RUN pip install uv

COPY pyproject.toml .
RUN uv pip install --system -e "."

COPY . .

# ── Runtime stage ────────────────────────────────────────────────────
FROM python:3.12-slim

WORKDIR /app

# Create non-root user
RUN adduser --system --no-create-home --group appuser

# Copy installed packages and app code from builder
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY --from=builder /app /app

# Create reports directory
RUN mkdir -p /app/reports && chown appuser:appuser /app/reports

USER appuser

EXPOSE 8000

ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
