#!/usr/bin/env bash
# Déploiement de astro-engine sur le VPS. Lancé en SSH depuis /srv/astro/engine.
set -euo pipefail

git pull
sudo apt install -y build-essential python3-dev
.venv/bin/pip install -e .
.venv/bin/pytest -q
sudo systemctl restart astro-engine
