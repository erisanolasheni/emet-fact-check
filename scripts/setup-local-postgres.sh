#!/usr/bin/env bash
# Create local PostgreSQL role + database for Emet (matches default .env.example).
# Usage: ./scripts/setup-local-postgres.sh
# Env overrides: DB_USER, DB_PASS, DB_NAME, PGHOST, PGPORT

set -euo pipefail

DB_NAME="${DB_NAME:-emet}"
DB_USER="${DB_USER:-emet}"
DB_PASS="${DB_PASS:-emet}"
ADMIN_DB="${ADMIN_DB:-postgres}"

if ! command -v psql &>/dev/null; then
  echo "ERROR: psql not found. Install PostgreSQL (e.g. brew install postgresql@16) and ensure psql is on PATH."
  exit 1
fi

echo "Using psql: $(command -v psql)"
echo "Target database: ${DB_NAME}, role: ${DB_USER}"

exists_role() {
  psql -d "${ADMIN_DB}" -tAc "SELECT 1 FROM pg_roles WHERE rolname='${DB_USER}'" 2>/dev/null | grep -q 1
}

exists_db() {
  psql -d "${ADMIN_DB}" -tAc "SELECT 1 FROM pg_database WHERE datname='${DB_NAME}'" 2>/dev/null | grep -q 1
}

if exists_role; then
  echo "Role '${DB_USER}' already exists — skipping CREATE USER."
else
  echo "Creating role '${DB_USER}'..."
  psql -d "${ADMIN_DB}" -v ON_ERROR_STOP=1 -c "CREATE USER ${DB_USER} WITH PASSWORD '${DB_PASS}';"
fi

if exists_db; then
  echo "Database '${DB_NAME}' already exists — skipping CREATE DATABASE."
else
  echo "Creating database '${DB_NAME}'..."
  psql -d "${ADMIN_DB}" -v ON_ERROR_STOP=1 -c "CREATE DATABASE ${DB_NAME} OWNER ${DB_USER};"
fi

echo ""
echo "OK. Set in emet/backend/.env (or repo root .env):"
echo "  DATABASE_URL=postgresql+asyncpg://${DB_USER}:${DB_PASS}@localhost:5432/${DB_NAME}"
echo ""
echo "Then: cd backend && uvicorn app.main:app --reload"
