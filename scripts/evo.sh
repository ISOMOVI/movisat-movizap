#!/bin/bash
# Helper da API do Evolution.
# A chave é lida do .env DENTRO do script -- nunca entra em linha de comando.
set -euo pipefail

ENV_FILE="/home/claude/movibot/.env"
KEY=$(grep -E '^EVOLUTION_API_KEY=' "$ENV_FILE" | cut -d= -f2- | tr -d '"'"'"'')
BASE=$(grep -E '^EVOLUTION_BASE_URL=' "$ENV_FILE" | cut -d= -f2- | tr -d '"'"'"'')

METODO="${1:-GET}"
ROTA="${2:-/}"
CORPO="${3:-}"

if [ -z "$KEY" ] || [ -z "$BASE" ]; then
    echo "ERRO: EVOLUTION_API_KEY ou EVOLUTION_BASE_URL ausente em $ENV_FILE" >&2
    exit 1
fi

if [ -n "$CORPO" ]; then
    curl -s --max-time 30 -X "$METODO" "$BASE$ROTA" \
        -H "apikey: $KEY" -H "Content-Type: application/json" -d "$CORPO"
else
    curl -s --max-time 30 -X "$METODO" "$BASE$ROTA" -H "apikey: $KEY"
fi
