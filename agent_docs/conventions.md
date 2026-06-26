# Conventions

# Conventions — FastAPI

## Naming
- Files: snake_case. Routers: plural nouns (`users.py`, `items.py`).
- Pydantic schemas: `<Entity>Create`, `<Entity>Read`, `<Entity>Update`.
- Service functions: verb-first (`create_user`, `get_user_by_id`).
- Dependencies: `get_*` naming (`get_db`, `get_current_user`).

## Endpoint Guidelines
- Group endpoints in `APIRouter` with a common `prefix` and `tags`.
- Use path parameters for resource identity (`/users/{user_id}`), query parameters for filtering/pagination.
- Return explicit `response_model` — never leak ORM objects to the client.
- Use status codes: 201 for creation, 204 for deletes, 422 auto-handled by FastAPI for validation.

## Async Best Practices
- Use `httpx.AsyncClient` for outbound HTTP, not `requests`.
- Database: use async drivers (asyncpg, aiosqlite) with async session.
- File I/O: use `aiofiles` or run in threadpool via `run_in_executor`.

## Error Handling
- Domain errors: custom exception classes inheriting `HTTPException`.
- Validation: let Pydantic handle it — do not manually validate request bodies.
- Logging: structured JSON logs via `structlog` or stdlib `logging` with JSON formatter.
