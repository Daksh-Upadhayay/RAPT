#!/bin/sh
# Runs inside the backup container: one pg_dump a night at 03:00, keep KEEP_DAYS days.
set -eu
while true; do
  now=$(date +%s)
  next=$(date -d "tomorrow 03:00" +%s 2>/dev/null || echo $((now + 86400)))
  if [ "$(date +%H)" -lt 3 ]; then next=$(date -d "today 03:00" +%s); fi
  sleep $((next - now))
  file="/backups/rapt-$(date +%Y-%m-%d-%H%M).dump"
  if pg_dump --format=custom --file="$file.partial" && mv "$file.partial" "$file"; then
    echo "backup written: $file"
  else
    echo "BACKUP FAILED at $(date)" >&2
    rm -f "$file.partial"
  fi
  find /backups -name 'rapt-*.dump' -mtime +"${KEEP_DAYS:-14}" -delete
done
