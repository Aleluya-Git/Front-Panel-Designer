#!/usr/bin/env bash
cd "$(dirname "$0")"
.venv/bin/python tools/autoprueba.py "$@"
