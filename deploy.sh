#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"

: "${CLOUDBASE_ENV_ID:?Set CLOUDBASE_ENV_ID before deploying}"
echo "🚀 部署到 CloudBase 云托管..."
tcb -e "$CLOUDBASE_ENV_ID" cloudrun deploy \
  --serviceName api \
  --source . \
  --port 80 \
  --force
