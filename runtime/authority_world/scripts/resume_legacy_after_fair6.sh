#!/usr/bin/env bash
set -euo pipefail

while systemctl is-active --quiet authority-fair6-deepseek.service \
   || systemctl is-active --quiet authority-fair6-gpt55.service; do
  sleep 30
done

systemctl start authority-world-strict72-deepseekv4pro-worker0.service
systemctl start authority-world-strict72-deepseekv4pro-worker1.service
systemctl restart authority-start-gpt55-after-deepseek.service

