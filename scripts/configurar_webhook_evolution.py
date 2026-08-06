"""Aponta o webhook das instancias do Evolution para o MoviZap.

🚨 O segredo sai do .env e NUNCA passa por linha de comando. A URL montada
contem o segredo, entao ela tambem nao e impressa -- so o host e o comprimento.

⚠️ POR QUE A URL PUBLICA E NAO O 127.0.0.1

  O Evolution roda em container e o MoviZap escuta so em 127.0.0.1:8008 do
  host. O `localhost` do container e o container. Ele alcancaria 172.17.0.1,
  mas ai seria preciso abrir o uvicorn para fora -- e um listener a mais e
  exposicao a mais.

  Pelo dominio, a chamada entra pelo nginx que ja existe, com TLS que ja
  existe. O que protege o endpoint e o segredo de 43 caracteres no caminho.

Uso:  ./venv/bin/python scripts/configurar_webhook_evolution.py
"""
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from movizap.config import settings, silenciar_clientes_http  # noqa: E402

silenciar_clientes_http()

INSTANCIAS = ["atendimento", "informativos"]

# O que interessa na Fase 1. `MESSAGES_UPSERT` e a mensagem chegando;
# `CONNECTION_UPDATE` e o canal caindo ou voltando.
EVENTOS = [
    "MESSAGES_UPSERT",
    "MESSAGES_UPDATE",
    "SEND_MESSAGE",
    "CONNECTION_UPDATE",
    "QRCODE_UPDATED",
]

if not settings.webhook_segredo:
    raise SystemExit("MOVIZAP_WEBHOOK_SEGREDO nao esta no .env")

url = f"https://{settings.dominio}/api/webhook/evolution/{settings.webhook_segredo}"
print(f"destino: https://{settings.dominio}/api/webhook/evolution/<segredo>")
print(f"segredo: {len(settings.webhook_segredo)} caracteres (nao impresso)")

with httpx.Client(base_url=settings.evolution_base_url, timeout=30) as c:
    cabecalhos = {"apikey": settings.evolution_api_key}
    for instancia in INSTANCIAS:
        corpo = {
            "webhook": {
                "enabled": True,
                "url": url,
                "byEvents": False,   # tudo no mesmo caminho, sem sufixo por evento
                "base64": True,      # midia chega embutida -- Fase 1 so RECEBE
                "events": EVENTOS,
            }
        }
        r = c.post(f"/webhook/set/{instancia}", json=corpo, headers=cabecalhos)
        print(f"\n{instancia}: HTTP {r.status_code}")
        if r.status_code >= 300:
            print(f"  {r.text[:300]}")
            continue

        # 🚨 A confirmacao e RELER, nunca o codigo de retorno.
        v = c.get(f"/webhook/find/{instancia}", headers=cabecalhos)
        if v.status_code != 200:
            print(f"  nao consegui reler: HTTP {v.status_code}")
            continue
        lido = v.json() or {}
        gravado = lido.get("url") or ""
        print(f"  relido: enabled={lido.get('enabled')} "
              f"eventos={len(lido.get('events') or [])}")
        print(f"  url bate com a que enviamos: {gravado == url}")
        if gravado and gravado != url:
            print(f"  🔴 gravou outra coisa: {gravado[:60]}...")
