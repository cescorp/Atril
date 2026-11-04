#!/bin/sh
# Linux: ./desklens.sh abre DeskLens (necesita python3; para la ventana, Chrome, Chromium, Edge o Brave)
cd "$(dirname "$0")" && exec python3 desklens.pyw "$@"
