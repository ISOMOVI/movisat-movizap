"""A chave POR INSTÂNCIA do Evolution tem escopo mesmo, ou é a mestra disfarçada?

Importa saber antes de entregar credencial a software de terceiro: se o token
da instância consegue listar/apagar as OUTRAS instâncias, entregar ele é o
mesmo que entregar a chave-mestra -- e a mestra comanda `atendimento` e
`informativos`, que são produção do MoviZap.

Não imprime token nenhum: só código de status.
"""
import sys

import httpx

sys.path.insert(0, "/home/claude/movizap_painel")
from movizap import evolution  # noqa: E402
from movizap.config import settings  # noqa: E402

base = settings.evolution_base_url.rstrip("/")

tokens = {}
for i in evolution.instancias():
    tokens[i.get("name")] = i.get("token")

alvo = "atendimento"
outra = "informativos"
token_alvo = tokens.get(alvo)

if not token_alvo:
    sys.exit("instancia sem token")


def bater(caminho: str, chave: str) -> int:
    try:
        r = httpx.get(f"{base}{caminho}", headers={"apikey": chave}, timeout=15)
        return r.status_code
    except Exception as e:
        return -1


print("Usando o token DA INSTANCIA 'atendimento':")
print(f"  estado da propria instancia   -> {bater('/instance/connectionState/' + alvo, token_alvo)}  (espero 200)")
print(f"  estado da OUTRA instancia     -> {bater('/instance/connectionState/' + outra, token_alvo)}  (200 = SEM escopo!)")
print(f"  listar TODAS as instancias    -> {bater('/instance/fetchInstances', token_alvo)}  (200 = SEM escopo!)")

print()
print("Usando a CHAVE MESTRA, para comparar:")
mestra = settings.evolution_api_key
print(f"  listar TODAS as instancias    -> {bater('/instance/fetchInstances', mestra)}  (espero 200)")
