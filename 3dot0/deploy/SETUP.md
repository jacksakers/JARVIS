# JARVIS Auto-Start — Setup & Operations Guide

This guide covers deploying the JARVIS stack on **calculon** (Ubuntu) as a
set of systemd services that start automatically on boot and can be managed
with a single command.

---

## What Gets Installed

| Unit | What it does |
|---|---|
| `ollama.service.d/keepalive.conf` | Drop-in that sets `OLLAMA_KEEP_ALIVE=-1` on the existing Ollama service so loaded models are never evicted from VRAM |
| `jarvis-preload.service` | One-shot: hits the Ollama API after boot to load `gemma4:e4b` into memory immediately |
| `jarvis-backend.service` | Runs `run.py` via the virtualenv Python — FastAPI on port **8000** |
| `jarvis-frontend.service` | Runs `vite --host` in the frontend directory — React PWA on port **5173** |
| `jarvis.target` | Groups all three services so you can start/stop/restart the whole stack in one command |

---

## Prerequisites

Before running the installer, make sure the following are already set up on
calculon:

1. **Ollama is installed** and the `ollama.service` systemd unit exists.
   ```bash
   systemctl status ollama
   ```
   If not installed: https://ollama.com/download/linux

2. **gemma4:e4b is pulled.**
   ```bash
   ollama pull gemma4:e4b
   ```

3. **The Python virtualenv exists** at `3dot0/.venv`.
   ```bash
   cd /home/jack/src/JARVIS/3dot0
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

4. **Node modules are installed** in `3dot0/frontend/`.
   ```bash
   cd /home/jack/src/JARVIS/3dot0/frontend
   npm install
   ```

---

## One-Time Installation

Copy the repo to calculon (e.g. via `git clone` or `scp`), then:

```bash
cd /home/jack/src/JARVIS/3dot0/deploy
chmod +x install.sh
sudo ./install.sh
```

The script will:
- Install the systemd drop-in and service files
- Restart Ollama with the new keepalive setting
- Enable all units to auto-start on boot
- Start the stack immediately

> **Non-standard install path?**  Edit the `JARVIS_ROOT` variable at the top
> of `install.sh` before running it.

---

## Day-to-Day Operations

All commands use `sudo` because systemd services run as system units.

### Check overall status
```bash
sudo systemctl status jarvis-backend jarvis-frontend jarvis-preload
```

### Restart the entire stack
```bash
sudo systemctl restart jarvis.target
```

### Stop the entire stack
```bash
sudo systemctl stop jarvis.target
```

### Start the entire stack
```bash
sudo systemctl start jarvis.target
```

### Restart only the backend (e.g. after a code change)
```bash
sudo systemctl restart jarvis-backend
```

### Restart only the frontend
```bash
sudo systemctl restart jarvis-frontend
```

---

## Viewing Logs

Logs stream to the system journal.

```bash
# Backend logs (live tail)
journalctl -u jarvis-backend -f

# Frontend logs (live tail)
journalctl -u jarvis-frontend -f

# Model preload log
journalctl -u jarvis-preload

# All JARVIS units together
journalctl -u 'jarvis-*' -f

# Last 100 lines of backend log
journalctl -u jarvis-backend -n 100 --no-pager
```

---

## Enabling / Disabling Auto-Start on Boot

Auto-start is **enabled by default** after running `install.sh`.

```bash
# Disable auto-start (still runs until you stop it manually)
sudo systemctl disable jarvis.target

# Re-enable auto-start
sudo systemctl enable jarvis.target
```

---

## Accessing JARVIS

| Service | URL |
|---|---|
| **API (local)** | http://localhost:8000 |
| **API (network)** | http://calculon:8000 |
| **Swagger UI** | http://calculon:8000/docs |
| **Frontend (local)** | http://localhost:5173 |
| **Frontend (network / PWA)** | http://calculon:5173 |
| **WebSocket** | ws://calculon:8000/ws |

For remote access over Tailscale, replace `calculon` with your Tailscale
hostname (e.g. `calculon.tailnet-name.ts.net`).

---

## Updating JARVIS

After pulling new code:

```bash
cd /home/jack/src/JARVIS/3dot0

# If Python dependencies changed:
source .venv/bin/activate
pip install -r requirements.txt

# If frontend dependencies changed:
cd frontend && npm install && cd ..

# Restart the affected service(s):
sudo systemctl restart jarvis-backend
sudo systemctl restart jarvis-frontend
```

No need to re-run `install.sh` unless the service files themselves change.

---

## Uninstalling

```bash
sudo systemctl stop    jarvis.target
sudo systemctl disable jarvis-preload.service jarvis-backend.service \
                       jarvis-frontend.service jarvis.target

sudo rm /etc/systemd/system/jarvis.target
sudo rm /etc/systemd/system/jarvis-backend.service
sudo rm /etc/systemd/system/jarvis-frontend.service
sudo rm /etc/systemd/system/jarvis-preload.service
sudo rm /etc/systemd/system/ollama.service.d/keepalive.conf

sudo systemctl daemon-reload
sudo systemctl restart ollama   # restart Ollama without the keepalive override
```

---

## Troubleshooting

### Backend won't start — "No module named …"
The venv may be missing dependencies. Run:
```bash
source /home/jack/src/JARVIS/3dot0/.venv/bin/activate
pip install -r /home/jack/src/JARVIS/3dot0/requirements.txt
sudo systemctl restart jarvis-backend
```

### Frontend won't start — "Cannot find module vite"
Node modules aren't installed. Run:
```bash
cd /home/jack/src/JARVIS/3dot0/frontend
npm install
sudo systemctl restart jarvis-frontend
```

### Model preload fails — "curl: connection refused"
Ollama isn't ready yet. The preload service will retry automatically. You
can also trigger it manually after Ollama is up:
```bash
sudo systemctl restart jarvis-preload
```

### Check if Ollama has the model loaded in memory
```bash
curl http://localhost:11434/api/ps | python3 -m json.tool
```
You should see `gemma4:e4b` with `"expires_at": "0001-01-01T00:00:00Z"` (the
sentinel value Ollama uses for "never expire").
