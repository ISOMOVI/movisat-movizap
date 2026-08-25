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

from movizap import auth, telas  # noqa: E402
from movizap.config import settings  # noqa: E402

# 🚨 O NÚMERO DE TELAS SE LÊ DO REGISTRO, NUNCA SE ESCREVE AQUI.
# Até 25/08 este arquivo comparava com 12 e 16, escritos à mão em 05/08. O
# painel cresceu para 17 ativas e 19 registradas, e o portão passou a acusar
# três falhas por motivo errado -- e portão que grita à toa é portão que todo
# mundo aprende a ignorar. Nenhuma entrega foi verificada por ele desde então.
# O que se prova aqui é que os dois lados CONCORDAM, não que sejam um número.
ATIVAS = len(telas.ativas())
REGISTRADAS = len(telas.TELAS)

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
conferir(f"{ATIVAS} telas ativas", dados.get("telas_ativas") == ATIVAS,
         f"telas_ativas={dados.get('telas_ativas')}")

print("== 2. SPA servida pelo FastAPI ==")
st, ct, corpo = pedir("/")
conferir("GET / responde 200", st == 200)
conferir("é o index do Vue", '<div id="app">' in corpo)
# ⚠️ SAIU O CHECK DE TEMA. Ele provava que o cálculo claro/escuro rodava inline
# no <head> antes da primeira pintura. O tema escuro foi REMOVIDO em 10/08 a
# pedido do usuário -- `tokens.css` tem um tema só -- então não há o que
# aplicar antes de pintar. Continuava aqui acusando falha por uma coisa que
# deixou de existir de propósito.
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
conferir("com token: 200", st == 200)
# ⚠️ `menu`, não `telas`: a variável antiga se chamava `telas` e passaria a
# sombrear o MÓDULO `telas` importado no topo -- que é de onde saem ATIVAS e
# REGISTRADAS. Sombreamento assim não dá erro, dá resultado errado depois.
menu = json.loads(corpo) if st == 200 else []
# O owner enxerga tudo que está ativo: menu menor que o registro ativo é
# permissão vazando para menos, e maior é tela sem registro.
conferir(f"menu do owner com {ATIVAS} telas", len(menu) == ATIVAS, f"{len(menu)} telas")
conferir(
    "toda tela do menu tem código, título, rota e ícone",
    all(all(t.get(c) for c in ("codigo", "titulo", "rota", "icone")) for t in menu),
)

st, ct, corpo = pedir("/api/telas/registro", token)
reg = json.loads(corpo) if st == 200 else {}
conferir("CFG_9.1 lê o registro completo", st == 200)
conferir(f"{REGISTRADAS} telas registradas ({ATIVAS} ativas + "
         f"{REGISTRADAS - ATIVAS} reservadas)",
         len(reg.get("telas", [])) == REGISTRADAS,
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
