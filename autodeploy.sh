#!/bin/bash
# Auto-deploy: poll origin/main and restart bot on new commits.
cd /root/task-bot || exit 1
git fetch --quiet origin main || exit 1

LOCAL=$(git rev-parse HEAD)
REMOTE=$(git rev-parse origin/main)
if [ "$LOCAL" = "$REMOTE" ]; then
    exit 0
fi

git pull --ff-only --quiet origin main || exit 1
/root/task-bot/.venv/bin/pip install -q -r requirements.txt
systemctl restart task-bot
logger -t autodeploy "Bot updated: $LOCAL -> $REMOTE"