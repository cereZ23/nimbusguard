#!/bin/bash
# Database restore script — restores from a pg_dump backup.
#
# Usage:
#   ./scripts/restore-db.sh /path/to/cspm_20260319_020000.sql.gz
#
# WARNING: This will DROP and RECREATE the target database!

set -euo pipefail

if [ $# -eq 0 ]; then
  echo "Usage: $0 <backup_file.sql.gz>"
  echo "Example: $0 ./backups/cspm_20260319_020000.sql.gz"
  exit 1
fi

BACKUP_FILE="$1"
DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-5432}"
DB_USER="${DB_USER:-cspm}"
DB_NAME="${DB_NAME:-cspm}"

if [ ! -f "$BACKUP_FILE" ]; then
  echo "ERROR: Backup file not found: $BACKUP_FILE"
  exit 1
fi

echo "[$(date)] Starting restore of ${DB_NAME} from ${BACKUP_FILE}..."
echo "WARNING: This will DROP and RECREATE the database ${DB_NAME}!"
read -p "Continue? (yes/no): " CONFIRM
if [ "$CONFIRM" != "yes" ]; then
  echo "Aborted."
  exit 0
fi

# Drop and recreate
echo "[$(date)] Dropping and recreating database..."
psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d postgres -c "DROP DATABASE IF EXISTS ${DB_NAME};"
psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d postgres -c "CREATE DATABASE ${DB_NAME};"

# Restore
echo "[$(date)] Restoring from backup..."
gunzip -c "$BACKUP_FILE" | psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" --quiet

echo "[$(date)] Restore complete. Verify with: psql -h $DB_HOST -U $DB_USER -d $DB_NAME -c 'SELECT count(*) FROM users;'"
