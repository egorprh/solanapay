#!/bin/sh

# Fail fast on errors, unset vars, and pipeline failures
set -euo pipefail

# -------- Configuration (hardcoded) --------
# Update these to your server credentials and target directory
SERVER_USER="root"
SERVER_HOST="79.137.192.124"
SERVER_PATH="/var/www/payka"  # Target directory on the server

# Optional: SSH port (default 22)
SSH_PORT="22"

# -------- Derived paths --------
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$SCRIPT_DIR"
DEPLOY_DIR="$PROJECT_ROOT/deploy"

# -------- Helpers --------
cleanup() {
  if [ -d "$DEPLOY_DIR" ]; then
    rm -rf "$DEPLOY_DIR"
  fi
}

trap cleanup EXIT INT TERM

echo "Preparing deploy directory at: $DEPLOY_DIR"
rm -rf "$DEPLOY_DIR"
mkdir -p "$DEPLOY_DIR"

echo "Copying project files excluding virtualenv, git, caches, and onchain_payments..."
# Use rsync to stage files into the deploy directory with exclusions
rsync -a --delete \
  --exclude '.git' \
  --exclude '.gitignore' \
  --exclude '.gitattributes' \
  --exclude '.gitmodules' \
  --exclude '.git*' \
  --exclude 'venv' \
  --exclude '__pycache__' \
  --exclude '**/__pycache__' \
  --exclude '*.pyc' \
  --exclude '*.pyo' \
  --exclude 'onchain_payments' \
  --exclude 'deploy' \
  "$PROJECT_ROOT/" "$DEPLOY_DIR/"

echo "Uploading deploy contents to $SERVER_USER@$SERVER_HOST:$SERVER_PATH via scp..."
# Upload recursively using scp
scp -P "$SSH_PORT" -r "$DEPLOY_DIR/" "$SERVER_USER@$SERVER_HOST:$SERVER_PATH/"

echo "Deployment completed successfully to $SERVER_USER@$SERVER_HOST:$SERVER_PATH"


