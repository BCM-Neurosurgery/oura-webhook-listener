#!/usr/bin/env bash
set -u

set -a
# shellcheck disable=SC1091
source /etc/oura-listener.env
set +a

if certbot renew --quiet --deploy-hook "systemctl reload nginx"; then
  exit 0
fi

logger -t oura-certbot "Certificate renewal failed for ouralisten.bcmelias.com"
cd /home/ec2-user/oura_webhook_listener || exit 1
/home/ec2-user/oura_env/bin/python -m utils.notify \
  "Oura listener certificate renewal failed on $(hostname)" || true
exit 1
