#!/usr/bin/env bash
# Déploiement de astro-engine sur le VPS. Lancé en SSH depuis /srv/astro/engine.
set -euo pipefail

git pull
# `update` d'abord : sur un index périmé l'install échoue et `set -e` avorte
# le déploiement avant même les tests.
sudo apt-get update
sudo apt-get install -y build-essential python3-dev
# L'extra dev, sinon pytest est absent et le garde-fou de la ligne suivante
# s'évapore en « command not found » au lieu de tester quoi que ce soit.
.venv/bin/pip install -e ".[dev]"
.venv/bin/pytest -q
sudo systemctl restart astro-engine
