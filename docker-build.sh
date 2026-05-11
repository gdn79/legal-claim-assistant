#!/bin/sh
set -e
cd "$(dirname "$0")"

if [ "$(id -u)" -ne 0 ]; then
    if groups | grep -q docker; then
        docker build --no-cache -t legal-claim-assistant:latest .
    else
        echo "Нет прав на Docker. Попробуйте: sudo bash docker-build.sh"
        exit 1
    fi
else
    docker build --no-cache -t legal-claim-assistant:latest .
fi

echo "Build complete. Use 'docker compose up -d' to start."
