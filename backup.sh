#!/data/data/com.termux/files/usr/bin/bash
BACKUP_DIR="$HOME/storage/shared/Haedrstorebot_backup"
PROJECT_DIR="$HOME/Haedrstorebot"
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_PATH="$BACKUP_DIR/backup_$DATE"
mkdir -p "$BACKUP_DIR"
mkdir -p "$BACKUP_PATH"
cp "$PROJECT_DIR"/*.py "$BACKUP_PATH/" 2>/dev/null
cp "$PROJECT_DIR"/.env "$BACKUP_PATH/" 2>/dev/null
mkdir -p "$BACKUP_PATH/data"
cp "$PROJECT_DIR"/data/bot.db "$BACKUP_PATH/data/" 2>/dev/null
cd "$BACKUP_DIR"
ls -t | tail -n +11 | xargs -r rm -rf
echo "BACKUP_OK: $BACKUP_PATH"
