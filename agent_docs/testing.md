# Testing

# Testing — FastAPI

## Stack
- **Framework**: pytest + pytest-asyncio.
- **Client**: `httpx.AsyncClient` with `ASGITransport` (not deprecated `TestClient` for async tests).
- **Database**: test-scoped database with rollback per test, or SQLite in-memory.

## Principles
- Test through the HTTP layer using the ASGI test client. This validates routing, serialization, and dependency injection together.
- Override dependencies with `app.dependency_overrides[get_db] = ...` for isolation.
- Fixtures: define `client`, `db_session`, `auth_headers` as session/function-scoped pytest fixtures.
- Use `factory_boy` or simple factory functions for test data creation.

## File Layout
```
tests/
  conftest.py         # Shared fixtures (client, db, auth)
  api/
    test_users.py     # Endpoint tests grouped by router
    test_items.py
  services/
    test_user_service.py  # Unit tests for business logic
```

## Commands
- `pytest` — run all tests.
- `pytest -x --tb=short` — stop on first failure, short traceback.
- `pytest --cov=app --cov-report=term-missing` — with coverage.
