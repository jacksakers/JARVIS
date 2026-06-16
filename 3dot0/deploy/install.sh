#!/usr/bin/env bash
# install.sh — Install JARVIS systemd services on calculon (Ubuntu)
#
# Run once from the deploy/ directory:
#   cd /home/jack/src/JARVIS/3dot0/deploy
#   chmod +x install.sh
#   sudo ./install.sh
#
# To change the project location, edit JARVIS_ROOT below.

set -euo pipefail

# ── Configuration ─────────────────────────────────────────────────────────────
JARVIS_ROOT="/home/jack/src/JARVIS"
JARVIS_USER="jack"
SYSTEMD_DIR="/etc/systemd/system"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# ─────────────────────────────────────────────────────────────────────────────

if [[ $EUID -ne 0 ]]; then
  echo "ERROR: This script must be run as root (use sudo)." >&2
  exit 1
fi

echo "==> Patching project paths for JARVIS_ROOT=${JARVIS_ROOT} ..."

# If the user changed JARVIS_ROOT, rewrite the path in service files on the fly.
patch_file() {
  sed "s|/home/jack/src/JARVIS|${JARVIS_ROOT}|g; s|User=jack|User=${JARVIS_USER}|g" "$1"
}

# ── 1. Ollama drop-in: set OLLAMA_KEEP_ALIVE=-1 ───────────────────────────────
OLLAMA_DROPIN="${SYSTEMD_DIR}/ollama.service.d"
mkdir -p "${OLLAMA_DROPIN}"
patch_file "${SCRIPT_DIR}/ollama-keepalive.conf" > "${OLLAMA_DROPIN}/keepalive.conf"
echo "    Installed: ${OLLAMA_DROPIN}/keepalive.conf"

# ── 2. Copy service + target files ────────────────────────────────────────────
for unit in jarvis-preload.service jarvis-backend.service jarvis-frontend.service jarvis.target; do
  patch_file "${SCRIPT_DIR}/${unit}" > "${SYSTEMD_DIR}/${unit}"
  echo "    Installed: ${SYSTEMD_DIR}/${unit}"
done

# ── 3. Reload systemd daemon ──────────────────────────────────────────────────
echo "==> Reloading systemd daemon ..."
systemctl daemon-reload

# ── 4. Restart Ollama so the keepalive env var takes effect ───────────────────
echo "==> Restarting Ollama to apply KEEP_ALIVE=-1 ..."
systemctl restart ollama || echo "    WARNING: ollama.service not found — install Ollama first."

# ── 5. Enable jarvis.target to auto-start on boot ────────────────────────────
echo "==> Enabling jarvis.target (auto-start on boot) ..."
systemctl enable jarvis-preload.service jarvis-backend.service jarvis-frontend.service jarvis.target

# ── 6. Start everything now ───────────────────────────────────────────────────
echo "==> Starting JARVIS stack ..."
systemctl start jarvis.target

echo ""
echo "✓  Done!  JARVIS is running."
echo ""
echo "   Backend  →  http://calculon:8000"
echo "   API docs →  http://calculon:8000/docs"
echo "   Frontend →  http://calculon:5173"
echo ""
echo "   Useful commands:"
echo "     sudo systemctl status  jarvis-backend   jarvis-frontend   jarvis-preload"
echo "     sudo systemctl restart jarvis.target"
echo "     sudo systemctl stop    jarvis.target"
echo "     journalctl -u jarvis-backend  -f"
echo "     journalctl -u jarvis-frontend -f"
