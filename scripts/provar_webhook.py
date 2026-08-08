"""Prova de ponta a ponta do webhook publico, antes do pareamento.

Manda 1 evento sintetico pela URL publica (nginx -> uvicorn), confirma RELENDO
a linha no banco, e apaga a linha em seguida -- webhook_evento e' tabela de
producao e a primeira mensagem real tem que ser o id 1.

Nao imprime o segredo em lugar nenhum.
"""
import json
import sys

import httpx

from movizap import banco, config

s = config.settings
base = "https://movizap.movisat.com.br/api/webhook/evolution/"
MARCA = "PROVA-PRE-PAREAMENTO-NAO-E-MENSAGEM-REAL"

corpo = {
    "event": "messages.upsert",
    "instance": "atendimento",
    "data": {
        "key": {"id": MARCA, "remoteJid": "5518998116168@s.whatsapp.net",
                "fromMe": False},
        "message": {"conversation": "prova sintetica"},
    },
}

# 1. segredo errado tem que ser recusado
r_err = httpx.post(base + ("z" * len(s.webhook_segredo)), json=corpo, timeout=20)
print("segredo errado ->", r_err.status_code, "(esperado 404)")

# 2. segredo certo
r_ok = httpx.post(base + s.webhook_segredo, json=corpo, timeout=20)
print("segredo certo  ->", r_ok.status_code, json.dumps(r_ok.json())[:200])

# 3. a unica prova: reler o banco
banco.abrir()
linha = banco.um(
    "SELECT id, instancia, evento, id_externo, telefone, canal_id, processado "
    "FROM webhook_evento WHERE id_externo = %s", (MARCA,))
print("linha no banco ->", linha)

if not linha:
    print("FALHOU: nao gravou")
    sys.exit(1)

bruto = banco.um("SELECT payload FROM webhook_evento WHERE id = %s",
                 (linha["id"],))
print("payload cru veio inteiro:",
      bruto["payload"]["data"]["message"]["conversation"] == "prova sintetica")

# 4. limpar e conferir que limpou
banco.executar("DELETE FROM webhook_evento WHERE id_externo = %s", (MARCA,))
sobrou = banco.um("SELECT id FROM webhook_evento WHERE id_externo = %s", (MARCA,))
print("apagada:", sobrou is None)

resto = banco.um("SELECT count(*) AS n FROM webhook_evento")
print("eventos restantes na tabela:", resto["n"])
