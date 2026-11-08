#!/usr/bin/env bash
# Backs up what a database reset loses, and rebuilds the database from such a backup.
#
#   scripts/db.sh backup    # DIR (default: external_data/backups/<timestamp>), EMAIL (default: .env)
#   scripts/db.sh rebuild   # DIR (default: the latest backup directory), HISTORY, EMAIL
#
# The backup holds the exports (ratings, blacklist, enrichment, every taste profile), the LLM usage reports, the
# account rows (user and provider token, so no new OAuth flow is needed) and a full SQL dump as a safety net.
# Called by `make db-backup` and `make db-rebuild`, which start the database first.
set -euo pipefail

BACKUPS_ROOT="external_data/backups"
LLM_USAGE_GROUPS=(operation model step month profile run)

# Rich wraps its tables to the terminal width; the reports are files, give them room.
export COLUMNS=200

EMAIL="${EMAIL:-$(grep -E '^MUSEFLOW_CLI_DEFAULT_EMAIL=' .env 2>/dev/null | cut -d= -f2- || true)}"
if [[ -z "$EMAIL" ]]; then
    echo "No email: set EMAIL=... or MUSEFLOW_CLI_DEFAULT_EMAIL in .env" >&2
    exit 1
fi

psql_db() {
    docker compose exec -T db sh -c 'psql -v ON_ERROR_STOP=1 -q -U "$POSTGRES_USER" -d "$POSTGRES_DB" "$@"' sh "$@"
}

psql_postgres() {
    docker compose exec -T db sh -c 'psql -v ON_ERROR_STOP=1 -q -U "$POSTGRES_USER" -d postgres'
}

pg_dump_db() {
    docker compose exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" --no-acl --no-owner "$@" "$POSTGRES_DB"' sh "$@"
}

museflow() {
    uv run museflow "$@"
}

step() {
    echo
    echo "=== $* ==="
}

backup() {
    local dir="${DIR:-$BACKUPS_ROOT/$(date +%Y%m%d-%H%M%S)}"
    # The dumps hold the password hash and the provider tokens.
    umask 077
    mkdir -p "$dir"

    step "SQL dump"
    pg_dump_db > "$dir/db.sql"
    pg_dump_db --data-only --column-inserts -t museflow_user -t museflow_auth_token > "$dir/accounts.sql"

    step "Ratings, blacklist, enrichment"
    museflow rate export --email "$EMAIL" --output "$dir/ratings.yaml"
    museflow blacklist export --email "$EMAIL" --output "$dir/blacklist.yaml"
    museflow enrich export --email "$EMAIL" --output "$dir/enrichment.yaml"

    step "Taste profiles"
    local name
    psql_db -tA -v email="$EMAIL" <<'SQL' | while IFS= read -r name; do
SELECT p.name FROM museflow_taste_profile p JOIN museflow_user u ON u.id = p.user_id WHERE u.email = :'email'
ORDER BY p.name;
SQL
        [[ -n "$name" ]] || continue
        # stdin is the list of names: keep the command from reading it.
        museflow taste export --email "$EMAIL" --name "$name" --output "$dir/taste-$name.yaml" < /dev/null
    done

    step "LLM usage reports"
    local group
    for group in "${LLM_USAGE_GROUPS[@]}"; do
        museflow llm usage --email "$EMAIL" --by "$group" > "$dir/llm-usage-by-$group.txt"
    done

    echo
    echo "Backup written to $dir"
}

rebuild() {
    # The backup directories are timestamps or plain names: ls sorts them by date safely.
    # shellcheck disable=SC2012
    local dir="${DIR:-$(ls -td "$BACKUPS_ROOT"/*/ 2>/dev/null | head -1)}"
    dir="${dir%/}"
    local history="${HISTORY:-external_data/spotify_history}"

    local file
    for file in ratings.yaml blacklist.yaml enrichment.yaml; do
        if [[ ! -f "$dir/$file" ]]; then
            echo "Missing $dir/$file: run \`make db-backup\` first, or pass DIR=path" >&2
            exit 1
        fi
    done
    if [[ ! -d "$history" ]]; then
        echo "Missing streaming history directory $history: pass HISTORY=path" >&2
        exit 1
    fi

    read -r -p "Drop the database and rebuild it from $dir (history: $history)? [y/N] " answer
    [[ "$answer" == "y" || "$answer" == "Y" ]] || { echo "Aborted."; exit 1; }

    step "Database reset and migrations"
    # FORCE closes the open connections (API server, a forgotten shell).
    psql_postgres <<'SQL'
\set db `echo "$POSTGRES_DB"`
DROP DATABASE IF EXISTS :"db" WITH (FORCE);
CREATE DATABASE :"db";
SQL
    uv run alembic upgrade head

    step "Account"
    # One transaction: a failure (e.g. the user table changed) leaves no half-restored account behind.
    if [[ -f "$dir/accounts.sql" ]] && psql_db --single-transaction < "$dir/accounts.sql"; then
        echo "User and provider token restored."
    else
        echo "Account not restored: creating the user, then run \`museflow provider connect\`." >&2
        museflow users create --email "$EMAIL"
    fi

    step "Streaming history"
    museflow tracks history --email "$EMAIL" --directory "$history"

    step "Ratings, blacklist, enrichment"
    museflow rate import --email "$EMAIL" --input "$dir/ratings.yaml"
    museflow blacklist import --email "$EMAIL" --input "$dir/blacklist.yaml"
    museflow enrich import --email "$EMAIL" --input "$dir/enrichment.yaml"

    step "Taste profiles"
    for file in "$dir"/taste-*.yaml; do
        [[ -f "$file" ]] || continue
        museflow taste import --email "$EMAIL" --input "$file"
    done

    echo
    echo "Database rebuilt from $dir"
}

case "${1:-}" in
    backup) backup ;;
    rebuild) rebuild ;;
    *)
        echo "Usage: $0 backup|rebuild" >&2
        exit 2
        ;;
esac
