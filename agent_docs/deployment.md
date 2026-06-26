# Deployment

# Deployment — FastAPI

## Build
- No build step. Run directly with `uvicorn app.main:app`.
- Pin dependencies with `pip-compile` or `uv pip compile`.

## Docker
```dockerfile
FROM python:3.12-slim
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app/ app/
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

## Production
- Run behind Gunicorn with Uvicorn workers: `gunicorn app.main:app -k uvicorn.workers.UvicornWorker -w 4`.
- Use `--proxy-headers` and `--forwarded-allow-ips` behind a reverse proxy.
- Health check endpoint: `GET /health` returning 200.

## Environment
- All config via environment variables loaded through `pydantic-settings`.
- Never commit `.env`. Provide `.env.example` with dummy values.
- Secrets (DB password, JWT key) injected via orchestrator or vault.
