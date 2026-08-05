"""Verificação ao vivo do painel — contra o serviço que está no ar na 8008.

Não usa senha: o token é criado pelo próprio `movizap.auth`, lendo o segredo
do .env pelo módulo de config. Nenhum valor sensível vai para a linha de
comando nem é impresso.

Descartável: roda, mostra e sai.
"""
import json
import sys
import urllib.error
import urllib.request

sys.path.insert(0, "/home/claude/movizap_painel")

from movizap import auth  # noqa: E402
from movizap.config import settings  # noqa: E402

BASE = "http://127.0.0.1:8008"
falhas = []


def pedir(caminho, token=None):
    req = urllib.request.Request(BASE + caminho)
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, r.headers.get("Content-Type", ""), r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.headers.get("Content-Type", ""), e.read().decode("utf-8", "replace")


def conferir(rotulo, condicao, detalhe=""):
    marca = "OK  " if condicao else "FALHA"
    print(f"  [{marca}] {rotulo}" + (f"  -- {detalhe}" if detalhe else ""))
    if not condicao:
        falhas.append(rotulo)


print("== 1. API viva ==")
st, ct, corpo = pedir("/api/saude")
dados = json.loads(corpo) if "json" in ct else {}
conferir("GET /api/saude responde 200", st == 200)
conferir("devolve req_id", bool(dados.get("req_id")), f"req_id={dados.get('req_id')}")
conferir("12 telas ativas", dados.get("telas_ativas") == 12, f"telas_ativas={dados.get('telas_ativas')}")

print("== 2. SPA servida pelo FastAPI ==")
st, ct, corpo = pedir("/")
conferir("GET / responde 200", st == 200)
conferir("é o index do Vue", '<div id="app">' in corpo)
conferir("tema aplicado antes da pintura", "movizap.tema" in corpo)
conferir("carrega o bundle", "/assets/index-" in corpo)

st, ct, corpo = pedir("/config/telas")
conferir("rota do Vue cai no index", st == 200 and '<div id="app">' in corpo)

print("== 3. /api inexistente NÃO devolve HTML ==")
st, ct, corpo = pedir("/api/isto-nao-existe")
conferir("responde 404", st == 404, f"status={st}")
conferir("não é HTML", "text/html" not in ct, f"content-type={ct}")

print("== 4. barreira de permissão ==")
st, ct, corpo = pedir("/api/telas")
conferir("sem token: 401", st == 401, f"status={st}")

token = auth.criar_token(settings.admin_login)
st, ct, corpo = pedir("/api/telas", token)
telas = json.loads(corpo) if st == 200 else []
conferir("com token: 200", st == 200)
conferir("menu com 12 telas", len(telas) == 12, f"{len(telas)} telas")
conferir(
    "toda tela do menu tem código, título, rota e ícone",
    all(all(t.get(c) for c in ("codigo", "titulo", "rota", "icone")) for t in telas),
)

st, ct, corpo = pedir("/api/telas/registro", token)
reg = json.loads(corpo) if st == 200 else {}
conferir("CFG_9.1 lê o registro completo", st == 200)
conferir("16 telas registradas (12 ativas + 4 reservadas)", len(reg.get("telas", [])) == 16,
         f"{len(reg.get('telas', []))} telas")
conferir("fase atual = 1", reg.get("fase_atual") == 1)

print("== 5. nada de segredo vazando pelo estático ==")
for caminho in ("/.env", "/../.env", "/%2e%2e/.env"):
    st, ct, corpo = pedir(caminho)
    conferir(f"{caminho} não entrega o .env",
             "MOVIZAP_JWT_SECRET" not in corpo and "MOVIZAP_ADMIN_SENHA_HASH" not in corpo,
             f"status={st}")

print()
if falhas:
    print(f"!! {len(falhas)} FALHA(S): " + "; ".join(falhas))
    sys.exit(1)
print("Tudo verificado contra o estado, não contra o código de retorno.")
