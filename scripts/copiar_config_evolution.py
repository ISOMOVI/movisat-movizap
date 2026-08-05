"""Leva a configuracao do Evolution para o .env do MoviZap.

A chave e LIDA do .env do MoviBot e ESCRITA no do MoviZap, sem nunca passar
por argumento, variavel de ambiente exportada nem saida padrao.

Valida antes de gravar. Idempotente.
"""
import sys
from pathlib import Path

ORIGEM = Path("/home/claude/movibot/.env")
DESTINO = Path("/home/claude/movizap_painel/.env")

CHAVES = ["EVOLUTION_BASE_URL", "EVOLUTION_API_KEY"]


def ler(caminho):
    d = {}
    for l in caminho.read_text(encoding="utf-8").splitlines():
        if "=" in l and not l.strip().startswith("#"):
            k, _, v = l.partition("=")
            d[k.strip()] = v.strip()
    return d

origem = ler(ORIGEM)
texto = DESTINO.read_text(encoding="utf-8")

if "EVOLUTION_API_KEY=" in texto:
    sys.exit("o .env do MoviZap ja tem EVOLUTION_API_KEY -- nada a fazer")

faltando = [k for k in CHAVES if not origem.get(k)]
if faltando:
    sys.exit(f"nao encontrei no MoviBot: {', '.join(faltando)}")

bloco = "\n# ---- Evolution (CFG_1.1, 2026-08-05) ----\n"
for k in CHAVES:
    bloco += f"{k}={origem[k]}\n"
# A instancia NAO e segredo: e so um nome.
bloco += "EVOLUTION_INSTANCIA_ATENDIMENTO=atendimento\n"

novo = texto.rstrip("\n") + "\n" + bloco

falhas = []
for guarda in ("MOVIZAP_JWT_SECRET=", "MOVIZAP_DB_SENHA=", "MOVIZAP_ADMIN_SENHA_HASH="):
    if guarda not in novo:
        falhas.append(f"{guarda} sumiu")
if novo.count("EVOLUTION_API_KEY=") != 1:
    falhas.append("a chave entrou zero ou mais de uma vez")
if len(novo) <= len(texto):
    falhas.append("o .env encolheu")

if falhas:
    print("NAO GRAVEI:")
    for f in falhas:
        print(f"  - {f}")
    sys.exit(1)

DESTINO.write_text(novo, encoding="utf-8")
DESTINO.chmod(0o600)

print(f"{len(CHAVES) + 1} chaves acrescentadas ao .env do MoviZap")
print(f"modo: {oct(DESTINO.stat().st_mode)[-3:]}  (nenhum valor impresso)")
