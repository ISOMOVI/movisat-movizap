"""Prova a delegacao em todo o dominio -- SO LEITURA neste teste.

Como funciona: a conta de servico assina um JWT dizendo "sou eu, e quero agir
como fulano@movisat.com.br" (campo `sub`). O Google devolve um token daquele
usuario. Nenhum consentimento individual, nenhum refresh token por pessoa.

🚨 Este teste NAO envia nada e NAO altera nada. So lista marcadores e conta
mensagens -- se a delegacao estiver errada, falha sem efeito colateral.
"""
import json
import pathlib
import sys
import time

import httpx
from jose import jwt

CHAVE = pathlib.Path("/home/claude/movizap_painel/.google_sa.json")
ESCOPOS = " ".join([
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/calendar.readonly",
])
QUEM = sys.argv[1] if len(sys.argv) > 1 else "iago@movisat.com.br"

sa = json.loads(CHAVE.read_text(encoding="utf-8"))
agora = int(time.time())

# O `sub` e o que faz a diferenca: sem ele o token seria da conta de servico,
# que nao tem caixa de e-mail nenhuma.
afirmacao = {
    "iss": sa["client_email"],
    "sub": QUEM,
    "scope": ESCOPOS,
    "aud": sa["token_uri"],
    "iat": agora,
    "exp": agora + 3600,
}
assinado = jwt.encode(afirmacao, sa["private_key"], algorithm="RS256",
                      headers={"kid": sa["private_key_id"]})

r = httpx.post(sa["token_uri"], timeout=30, data={
    "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
    "assertion": assinado,
})
print(f"troca do JWT -> HTTP {r.status_code}")
if r.status_code != 200:
    corpo = r.json()
    print("  erro:", corpo.get("error"), "-", corpo.get("error_description"))
    print("\n  unauthorized_client  -> escopos nao batem, ou ainda propagando")
    print("  invalid_grant        -> o `sub` nao existe no dominio")
    sys.exit(1)

token = r.json()["access_token"]
print(f"  token obtido para {QUEM}")

# 1) leitura do Gmail
g = httpx.get("https://gmail.googleapis.com/gmail/v1/users/me/labels",
              headers={"Authorization": f"Bearer {token}"}, timeout=30)
print(f"\nGmail /labels -> HTTP {g.status_code}")
if g.status_code == 200:
    marcadores = g.json().get("labels") or []
    print(f"  {len(marcadores)} marcadores lidos SEM consentimento individual")

p = httpx.get("https://gmail.googleapis.com/gmail/v1/users/me/profile",
              headers={"Authorization": f"Bearer {token}"}, timeout=30)
if p.status_code == 200:
    d = p.json()
    print(f"  caixa: {d.get('emailAddress')} · {d.get('messagesTotal')} mensagens")

# 2) leitura da agenda
c = httpx.get("https://www.googleapis.com/calendar/v3/calendars/primary",
              headers={"Authorization": f"Bearer {token}"}, timeout=30)
print(f"\nAgenda -> HTTP {c.status_code}"
      + (f" · {c.json().get('summary')}" if c.status_code == 200 else ""))

print("\nDELEGACAO FUNCIONANDO." if g.status_code == 200 else "\nFALHOU.")
