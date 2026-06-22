# Deploying HadithBot on Oracle Cloud (Always Free)

This guide hosts HadithBot 24/7 on an Oracle Cloud **Always Free** VM using Docker.
The database is Supabase (external), so the VM only runs one always-on container.

> **Note:** A Discord bot makes an *outbound* websocket connection — Discord never
> connects *to* you. So you do **not** need to open any inbound ports. The Flask
> health server on `:8080` ([server.py](server.py)) is optional on a dedicated VM;
> see [Optional: expose the health check](#optional-expose-the-health-check).

---

## 1. Create an Oracle Cloud account

1. Sign up at <https://www.oracle.com/cloud/free/>.
2. Pick a **home region** close to you — it **cannot** be changed later.
3. Verify your email and **credit card** (used for identity only; Always Free
   resources are not charged).

"Always Free" resources have no time limit and are separate from the 30-day
trial credits. As long as you only provision Always-Free-eligible shapes, you
won't be billed.

## 2. Launch a VM instance

Console → **Compute → Instances → Create Instance**:

| Setting | Value |
| --- | --- |
| **Image** | Canonical Ubuntu 22.04 (or Oracle Linux) |
| **Shape** | `VM.Standard.A1.Flex` (Arm, 1 OCPU / 6 GB) **or** `VM.Standard.E2.1.Micro` (AMD) — must show **"Always Free eligible"** |
| **SSH keys** | Generate or upload your public key; **save the private key** |

> **Arm "out of capacity"?** Common in busy regions. Retry later, switch
> availability domain, or use the AMD `E2.1.Micro` shape (more available, still
> enough for this bot).

## 3. SSH in

```bash
ssh ubuntu@<your-instance-public-ip>     # use opc@ for Oracle Linux
```

## 4. Install Docker & deploy

```bash
# Install Docker
sudo apt update && sudo apt install -y docker.io docker-compose git
sudo usermod -aG docker $USER && newgrp docker

# Clone the repo
git clone https://github.com/SaiyedRushan/HadithBot.git
cd HadithBot

# Create the production .env
nano .env        # fill in the three keys below

# Build and start (uses docker-compose.yml + .env)
docker compose up -d

# Watch logs — look for "Bot logged in as ..."
docker compose logs -f
```

Required `.env` contents (point these at **production**, not your test bot):

```env
DISCORD_TOKEN=your_production_discord_bot_token
SUPABASE_URL=https://your-project-id.supabase.co
SUPABASE_KEY=your_supabase_anon_key
```

`restart: unless-stopped` is already set in
[docker-compose.yml](docker-compose.yml), so the bot auto-restarts on crash or
VM reboot.

## 5. Update / restart / stop

```bash
cd HadithBot
git pull                 # get latest code
docker compose up -d --build   # rebuild & restart with new code

docker compose restart   # restart without rebuilding
docker compose down      # stop and remove the container
docker compose logs -f   # tail logs
```

---

## Optional: expose the health check

Only needed if you want to hit `http://<public-ip>:8080/health` from outside.

1. **Oracle ingress rule:** VCN → Security Lists → default list →
   **Add Ingress Rule**: Source `0.0.0.0/0`, IP Protocol TCP, Destination port `8080`.
2. **Ubuntu firewall:** Oracle Ubuntu images block ports by default —
   ```bash
   sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 8080 -j ACCEPT
   sudo netfilter-persistent save
   ```

Endpoints: `/` → `"Hello. I am alive!"`, `/health` → JSON bot status.

---

## Alternative: run without Docker (systemd)

For a single bot, systemd is lighter than Docker.

```bash
sudo apt update && sudo apt install -y git curl
git clone https://github.com/SaiyedRushan/HadithBot.git && cd HadithBot
curl -LsSf https://astral.sh/uv/install.sh | sh   # install uv
source $HOME/.local/bin/env                        # put uv on PATH
uv sync --frozen --no-dev                          # creates .venv with runtime deps
nano .env        # add the three keys
```

Create `/etc/systemd/system/hadithbot.service`:

```ini
[Unit]
Description=HadithBot Discord Bot
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/HadithBot
ExecStart=/home/ubuntu/HadithBot/.venv/bin/python server.py
Restart=always

[Install]
WantedBy=multi-user.target
```

> `server.py` reads `.env` via `load_dotenv()`, so no `EnvironmentFile` is
> needed. To run the bot **without** the Flask server, point `ExecStart` at
> `.../python bot.py` instead.

Enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now hadithbot
sudo systemctl status hadithbot      # check it's running
journalctl -u hadithbot -f           # tail logs
```
