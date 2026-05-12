#!/bin/sh
set -e

if [ ! -f "data/references/arbitration_courts_ru.json" ]; then
    mkdir -p data/references
    cp -r /app/references.bundled/* data/references/
fi

exec "$@"
