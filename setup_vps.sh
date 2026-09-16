#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"
PROJECT_DIR="$(pwd)"

if [ "$(id -u)" -ne 0 ]; then
  echo "Запусти от root: sudo bash setup_vps.sh" >&2
  exit 1
fi

echo "==> Установка системных пакетов (python3, git)"
if command -v apt-get >/dev/null 2>&1; then
  apt-get update -qq
  apt-get install -y -qq python3 python3-venv python3-pip git
elif command -v dnf >/dev/null 2>&1; then
  dnf install -y python3 git
else
  echo "Не нашёл apt-get/dnf. Установи python3, python3-venv и git вручную." >&2
  exit 1
fi

if [ ! -f .env ]; then
  echo "ОШИБКА: нет .env с BOT_TOKEN. Скопируй .env со своего Mac или создай заново." >&2
  exit 1
fi

echo "==> Создание чистого venv (не переноси .venv с Mac!)"
rm -rf .venv
python3 -m venv .venv
.venv/bin/pip install -q --upgrade pip
.venv/bin/pip install -q -r requirements.txt

echo "==> Установка systemd-службы"
sed "s|__PROJECT_DIR__|$PROJECT_DIR|g" task-bot.service > /etc/systemd/system/task-bot.service

systemctl daemon-reload
systemctl enable task-bot
systemctl restart task-bot

echo ""
echo "==> ГОТОВО. Состояние службы:"
systemctl status task-bot --no-pager

echo ""
echo "Полезные команды:"
echo "  systemctl status task-bot   # статус"
echo "  journalctl -u task-bot -f   # логи в реальном времени"