#!/bin/bash
# macOS: doble clic abre Atril (necesita Python 3: https://www.python.org/downloads/)
cd "$(dirname "$0")" && exec python3 atril.pyw "$@"
