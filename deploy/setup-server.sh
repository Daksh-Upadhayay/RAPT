#!/usr/bin/env bash
# One-time server setup for Ubuntu 24.04 (run as the admin user with sudo):
# Docker, a firewall allowing only SSH/HTTP/HTTPS, automatic security updates, key-only
# SSH, and a swap file (the models briefly need more memory while loading).
set -euo pipefail

echo "== Packages and Docker"
sudo apt-get update
sudo apt-get install -y ca-certificates curl git ufw unattended-upgrades docker.io docker-compose-v2
sudo systemctl enable --now docker
sudo usermod -aG docker "$USER"

echo "== Firewall: SSH, HTTP, HTTPS only"
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow OpenSSH
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw allow 443/udp
sudo ufw --force enable

echo "== Automatic security updates"
sudo dpkg-reconfigure -f noninteractive unattended-upgrades

echo "== SSH: keys only"
sudo sed -i -E 's/^#?PasswordAuthentication .*/PasswordAuthentication no/' /etc/ssh/sshd_config
sudo systemctl reload ssh || sudo systemctl reload sshd || true

if ! swapon --show | grep -q /swapfile; then
  echo "== 2 GB swap file"
  sudo fallocate -l 2G /swapfile
  sudo chmod 600 /swapfile
  sudo mkswap /swapfile
  sudo swapon /swapfile
  echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab >/dev/null
fi

echo "Done. Log out and back in (so your user can run docker), then run deploy/deploy.sh."
