#!/usr/bin/env bash
#
# One-time setup for HadithBot on a fresh Linux VM.
# Works on Oracle Cloud Always Free (Ubuntu or Oracle Linux) and most other
# Debian/Ubuntu or RHEL/Oracle Linux boxes.
#
# Idempotent — safe to re-run. It will:
#   1. install Docker (engine + compose v2 plugin) if missing
#   2. clone the repo (or pull latest if already cloned)
#   3. create a .env template if none exists, and stop so you can fill it in
#   4. build and start the bot with docker compose
#
# Usage (on the VM):
#   curl -fsSL https://raw.githubusercontent.com/SaiyedRushan/HadithBot/main/setup-vm.sh | bash
# then edit ~/HadithBot/.env and re-run:
#   ~/HadithBot/setup-vm.sh

set -euo pipefail

REPO_URL="https://github.com/SaiyedRushan/HadithBot.git"
APP_DIR="${APP_DIR:-$HOME/HadithBot}"

log()  { printf '\n\033[1;32m==>\033[0m %s\n' "$*"; }
warn() { printf '\n\033[1;33m!!\033[0m %s\n' "$*"; }

# Install a package using whichever package manager is present.
pkg_install() {
  if   command -v apt-get >/dev/null 2>&1; then sudo apt-get update -y && sudo apt-get install -y "$@"
  elif command -v dnf     >/dev/null 2>&1; then sudo dnf install -y "$@"
  elif command -v yum     >/dev/null 2>&1; then sudo yum install -y "$@"
  else warn "No supported package manager found; install these manually: $*"; exit 1
  fi
}

# --- 1. Docker -------------------------------------------------------------
if ! command -v docker >/dev/null 2>&1; then
  log "Installing Docker via the official convenience script..."
  curl -fsSL https://get.docker.com | sudo sh
else
  log "Docker already installed: $(docker --version)"
fi

sudo systemctl enable --now docker

if ! id -nG "$USER" | grep -qw docker; then
  log "Adding $USER to the 'docker' group..."
  sudo usermod -aG docker "$USER"
  warn "Added to 'docker' group — this run uses sudo for docker; log out/in for password-less docker."
fi

# Use docker directly if the current shell can; otherwise fall back to sudo.
if docker info >/dev/null 2>&1; then DOCKER="docker"; else DOCKER="sudo docker"; fi

# --- 2. Repo ---------------------------------------------------------------
command -v git >/dev/null 2>&1 || pkg_install git

if [ -d "$APP_DIR/.git" ]; then
  log "Repo found at $APP_DIR — pulling latest..."
  git -C "$APP_DIR" pull --ff-only
else
  log "Cloning repo into $APP_DIR..."
  git clone "$REPO_URL" "$APP_DIR"
fi
cd "$APP_DIR"

# --- 3. .env ---------------------------------------------------------------
if [ ! -f .env ]; then
  log "No .env found — writing a template."
  cat > .env <<'EOF'
DISCORD_TOKEN=your_production_discord_bot_token
SUPABASE_URL=https://your-project-id.supabase.co
SUPABASE_KEY=your_supabase_anon_key
EOF
  warn "Edit .env with your PRODUCTION credentials, then re-run this script:"
  warn "    nano $APP_DIR/.env && $APP_DIR/setup-vm.sh"
  exit 0
fi

if grep -q "your_production_discord_bot_token" .env; then
  warn ".env still has placeholder values. Edit it, then re-run this script:"
  warn "    nano $APP_DIR/.env && $APP_DIR/setup-vm.sh"
  exit 1
fi

# --- 4. Build & start ------------------------------------------------------
log "Building and starting HadithBot..."
$DOCKER compose up -d --build

log "Started. Recent logs (look for 'Bot logged in as ...'):"
$DOCKER compose logs --tail 30

cat <<EOF

Done. Useful commands (from $APP_DIR):
  $DOCKER compose logs -f        # follow logs
  $DOCKER compose restart        # restart
  $DOCKER compose down           # stop
  ./setup-vm.sh                  # pull latest + rebuild + restart
EOF
