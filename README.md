# Oura webhook listener

A small Flask service that manages Oura OAuth, webhook subscriptions, and webhook storage for TRBD, AA, Percept, EMU, and Utah.

One Gunicorn process serves every project. Each project keeps separate token, participant-map, and webhook directories defined in `config.json`.

## Setup

```bash
python3 -m venv /home/ec2-user/oura_env
/home/ec2-user/oura_env/bin/pip install -r requirements.txt
cp config.example.json config.json
```

Edit `config.json` to point to the existing project data directories. Keep credentials in `/etc/oura-listener.env`, using `deploy/oura-listener.env.example` as the template.

```bash
sudo cp deploy/oura-listener.env.example /etc/oura-listener.env
sudo chown root:ec2-user /etc/oura-listener.env
sudo chmod 640 /etc/oura-listener.env
sudoedit /etc/oura-listener.env

sudo cp deploy/oura-global-listener.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now oura-global-listener.service

sudo mkdir -p /etc/nginx/conf.d/ouralisten
sudo cp deploy/nginx.conf /etc/nginx/conf.d/ouralisten/oura.conf
sudo nginx -t && sudo systemctl reload nginx
```

Register these callbacks in the Oura application:

```text
https://ouralisten.bcmelias.com/trbd/callback
https://ouralisten.bcmelias.com/aa/callback
https://ouralisten.bcmelias.com/percept/callback
https://ouralisten.bcmelias.com/emu/callback
https://ouralisten.bcmelias.com/utah/callback
```

Install the schedules from `deploy/ec2-user.crontab` and `deploy/root.crontab`, preserving any unrelated cron entries already on the server.

## Check the service

```bash
cd /home/ec2-user/oura_webhook_listener
set -a; source /etc/oura-listener.env; set +a

python -m utils.preflight
python -m utils.subscriptions ensure
python -m utils.subscriptions list
python -m utils.health_check
```

Participant enrollment starts at:

```text
https://ouralisten.bcmelias.com/<project>/authorize?participant_id=PARTICIPANT_ID
```

## Safety

- Secrets, tokens, participant maps, logs, and webhook data are excluded from Git.
- Webhook writes are locked and atomic; unmatched events are preserved.
- Cron jobs use `flock` to prevent overlap.
- Disabled participant tokens are retained but skipped during refresh.
- No automatic data-deletion job is included.

Run tests with:

```bash
python -m pytest -q
python -m ruff check .
```
