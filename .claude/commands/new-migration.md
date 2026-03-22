# New Database Migration

You are creating an Alembic database migration for the MuseFlow project.

Migration description: **$ARGUMENTS**

## Steps

### 1. Verify model changes are in place
Before generating a migration, confirm the SQLAlchemy model changes have already been written. Read the relevant model files in `museflow/infrastructure/adapters/database/models/`.

### 2. Generate the migration
Run:
```bash
make db-revision
```
This runs `alembic revision --autogenerate -m "<description>"`. Review the generated file in `migrations/versions/`.

### 3. Review the generated migration
Read the generated migration file carefully. Check for:
- **Missing `nullable` defaults** — autogenerate may omit `nullable=False` on new columns with existing data; add a `server_default` or two-phase migration if needed
- **ARRAY/JSONB columns** — verify PostgreSQL dialect types are preserved
- **Index/constraint names** — confirm they match `__table_args__` in the model
- **`downgrade()`** — ensure it correctly reverses `upgrade()` (drop columns, drop tables, remove indexes)

### 4. Verify the migration runs cleanly
```bash
make db-upgrade
```
Then verify the DB state matches expectations.

### 5. Data migrations (if needed)
If this migration requires backfilling existing rows:
- Do it in a separate step inside `upgrade()` using `op.execute()`
- Never use ORM models inside migrations (import paths can break) — use raw SQL or `op.execute(text(...))`
- Add a corresponding cleanup or undo in `downgrade()` if relevant

### 6. Tests
If the migration introduces schema changes that affect integration tests (new columns, constraints), verify `make test-integration` still passes after the migration.

## Conventions reminders
- PostgreSQL only — use `postgresql` dialect for JSONB, ARRAY, UPSERT
- Migration file names follow: `<rev_id>_<description>.py`
- Never edit a migration that has already been applied to production
- Keep `upgrade()` and `downgrade()` in sync
- Run `make lint` after editing the migration file (mypy ignores migrations, but ruff checks them)
