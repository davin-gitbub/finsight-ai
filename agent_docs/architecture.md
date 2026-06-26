# Architecture

# Architecture — FastAPI

## Directory Layout
```
app/
  main.py             # FastAPI app factory, middleware, lifespan
  api/
    v1/
      router.py       # Includes all v1 route modules
      users.py        # /users endpoints
      items.py        # /items endpoints
    deps.py           # Shared dependencies (get_db, get_current_user)
  models/
    user.py           # SQLAlchemy / SQLModel ORM models
    item.py
  schemas/
    user.py           # Pydantic request/response schemas
    item.py
  services/
    user_service.py   # Business logic layer
  core/
    config.py         # Settings via pydantic-settings
    security.py       # JWT / OAuth2 utilities
  db/
    session.py        # Engine, SessionLocal, get_db dependency
    migrations/       # Alembic migrations
```

## Key Patterns
- **Router → Dependency → Service → Repository**: routes are thin; business logic lives in services; DB access in repository functions.
- **Pydantic Settings**: `BaseSettings` with `.env` loading for all config. No raw `os.getenv`.
- **Lifespan context manager**: startup/shutdown logic (DB pool, cache connections) in `@asynccontextmanager` passed to `FastAPI(lifespan=...)`.
- **Middleware stack**: CORS, trusted-host, request-ID, timing — registered in `main.py`.
- **Exception handlers**: register global handlers for `HTTPException`, `RequestValidationError`, and domain-specific errors.
