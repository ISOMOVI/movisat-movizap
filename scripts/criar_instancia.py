"""Cria uma instancia no Evolution, SEM parear.

O pareamento e pelo painel, na CFG_1.1 -- ler o QR muda estado real no
WhatsApp e e decisao de gente, nao de script. Aqui so se cria o lugar onde o
QR vai aparecer.

🚨 A confirmacao e RELER a lista de instancias, nunca o codigo de retorno.

Uso:  ./venv/bin/python scripts/criar_instancia.py informativos
"""
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from movizap.config import settings, silenciar_clientes_http  # noqa: E402

silenciar_clientes_http()

if len(sys.argv) < 2:
    raise SystemExit("uso: criar_instancia.py <nome>")
nome = sys.argv[1]

with httpx.Client(base_url=settings.evolution_base_url, timeout=60) as c:
    cabecalhos = {"apikey": settings.evolution_api_key}

    ja = c.get("/instance/fetchInstances", headers=cabecalhos)
    existentes = {i.get("name") or (i.get("instance") or {}).get("instanceName")
                  for i in (ja.json() if ja.status_code == 200 else [])}
    if nome in existentes:
        print(f"{nome}: ja existe -- nada a fazer")
        raise SystemExit(0)

    r = c.post("/instance/create", headers=cabecalhos, json={
        "instanceName": nome,
        "integration": "WHATSAPP-BAILEYS",
        "qrcode": False,      # 🚨 nao gerar QR agora: quem pareia e o painel
    })
    print(f"criar {nome}: HTTP {r.status_code}")
    if r.status_code >= 300:
        print(r.text[:400])
        raise SystemExit(1)

    # 🚨 A prova: reler a lista.
    de_novo = c.get("/instance/fetchInstances", headers=cabecalhos)
    agora = {i.get("name") or (i.get("instance") or {}).get("instanceName")
             for i in (de_novo.json() if de_novo.status_code == 200 else [])}
    print(f"instancias agora: {sorted(x for x in agora if x)}")
    print(f"{nome} existe de verdade: {nome in agora}")
