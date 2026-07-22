#!/usr/bin/env bash
set -u

if [[ $# -lt 2 ]]; then
  echo "Usage: $0 JOB_NAME COMMAND [ARG ...]" >&2
  exit 2
fi

job_name="$1"
shift
log_dir="/home/ec2-user/oura_webhook_listener/logs"
mkdir -p "$log_dir"
cd /home/ec2-user/oura_webhook_listener || exit 1
set -a
# shellcheck disable=SC1091
source /etc/oura-listener.env
set +a

exec 9>"/tmp/oura-${job_name}.lock"
if ! flock -n 9; then
  printf '%s skipped overlapping job=%s\n' "$(date --iso-8601=seconds)" "$job_name" >> "$log_dir/jobs.log"
  exit 0
fi

"$@" >> "$log_dir/${job_name}.log" 2>&1
status=$?
if [[ $status -ne 0 ]]; then
  printf '%s failed job=%s status=%s\n' "$(date --iso-8601=seconds)" "$job_name" "$status" >> "$log_dir/jobs.log"
  /home/ec2-user/oura_env/bin/python -m utils.notify "Oura job failed: ${job_name} (status ${status})" || true
fi
exit "$status"
