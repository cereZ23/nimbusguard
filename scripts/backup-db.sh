#!/bin/bash
# Database backup script — creates a compressed pg_dump and optionally uploads to S3/Azure Blob.
#
# Usage:
#   ./scripts/backup-db.sh                    # Backup to local ./backups/
#   BACKUP_S3_BUCKET=my-bucket ./scripts/backup-db.sh  # Upload to S3 after local backup
#
# Environment variables:
#   DB_HOST          — PostgreSQL host (default: localhost)
#   DB_PORT          — PostgreSQL port (default: 5432)
#   DB_USER          — PostgreSQL user (default: cspm)
#   DB_NAME          — Database name (default: cspm)
#   PGPASSWORD       — PostgreSQL password (must be set)
#   BACKUP_DIR       — Local backup directory (default: ./backups)
#   BACKUP_RETENTION — Days to keep local backups (default: 7)
#   BACKUP_S3_BUCKET — S3 bucket name (optional, skips upload if empty)

set -euo pipefail

DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-5432}"
DB_USER="${DB_USER:-cspm}"
DB_NAME="${DB_NAME:-cspm}"
BACKUP_DIR="${BACKUP_DIR:-./backups}"
BACKUP_RETENTION="${BACKUP_RETENTION:-7}"
BACKUP_S3_BUCKET="${BACKUP_S3_BUCKET:-}"

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
FILENAME="${DB_NAME}_${TIMESTAMP}.sql.gz"
FILEPATH="${BACKUP_DIR}/${FILENAME}"

# Create backup directory
mkdir -p "${BACKUP_DIR}"

echo "[$(date)] Starting backup of ${DB_NAME}..."

# Create compressed backup
pg_dump \
  -h "${DB_HOST}" \
  -p "${DB_PORT}" \
  -U "${DB_USER}" \
  -d "${DB_NAME}" \
  --no-owner \
  --no-acl \
  --format=plain \
  | gzip > "${FILEPATH}"

FILESIZE=$(du -sh "${FILEPATH}" | cut -f1)
echo "[$(date)] Backup created: ${FILEPATH} (${FILESIZE})"

# Upload to S3 if bucket is configured
if [ -n "${BACKUP_S3_BUCKET}" ]; then
  S3_PATH="s3://${BACKUP_S3_BUCKET}/db-backups/${FILENAME}"
  echo "[$(date)] Uploading to ${S3_PATH}..."
  aws s3 cp "${FILEPATH}" "${S3_PATH}" --quiet
  echo "[$(date)] Upload complete."
fi

# Clean up old local backups
if [ "${BACKUP_RETENTION}" -gt 0 ]; then
  DELETED=$(find "${BACKUP_DIR}" -name "${DB_NAME}_*.sql.gz" -mtime +${BACKUP_RETENTION} -delete -print | wc -l)
  if [ "${DELETED}" -gt 0 ]; then
    echo "[$(date)] Cleaned up ${DELETED} old backup(s) (>${BACKUP_RETENTION} days)."
  fi
fi

echo "[$(date)] Backup complete."
