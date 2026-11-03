#!/bin/sh
# Linux: ./atril.sh abre Atril (necesita python3; para la ventana, Chrome, Chromium, Edge o Brave)
cd "$(dirname "$0")" && exec python3 atril.pyw "$@"
