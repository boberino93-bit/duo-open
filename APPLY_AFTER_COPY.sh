#!/usr/bin/env sh
set -eu
python3 ./APPLY_AFTER_COPY.py --check
python3 ./APPLY_AFTER_COPY.py
