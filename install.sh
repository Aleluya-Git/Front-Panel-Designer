#!/usr/bin/env bash
# Linux / macOS
set -e
cd "$(dirname "$0")"
PY=${PYTHON:-python3}
$PY -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
echo "Instalación completada. Use ./run.sh o ./autoprueba.sh"
