#!/bin/sh
# Runs once, as the postgres superuser, when the data directory is empty (C3).
# Passwords reach psql as variables, never inline in the SQL text.
set -eu

psql -v ON_ERROR_STOP=1 \
  -v migrator_pw="$POSTGRES_MIGRATOR_PASSWORD" \
  -v app_pw="$POSTGRES_APP_PASSWORD" \
  --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<'SQL'
CREATE ROLE migrator LOGIN PASSWORD :'migrator_pw';
CREATE ROLE app_rw  LOGIN PASSWORD :'app_pw';
GRANT CONNECT ON DATABASE saveclock TO migrator, app_rw;
GRANT USAGE ON SCHEMA public TO app_rw;
GRANT USAGE, CREATE ON SCHEMA public TO migrator;
ALTER DEFAULT PRIVILEGES FOR ROLE migrator IN SCHEMA public
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO app_rw;
ALTER DEFAULT PRIVILEGES FOR ROLE migrator IN SCHEMA public
  GRANT USAGE, SELECT ON SEQUENCES TO app_rw;
SQL
