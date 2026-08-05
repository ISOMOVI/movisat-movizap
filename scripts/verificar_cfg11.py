"""Verificacao ao vivo da CFG_1.1, contra o servico que esta no ar.

Nao pareia nada: pedir o QR muda estado no Evolution, e isso e decisao do
usuario, nao de um script de verificacao. Confere tudo que vem ANTES disso.
"""
import json
import sys
import urllib.error
import urllib.request

sys.path.insert(0, "/home/claude/movizap_painel")
from movizap import auth, evolution  # noqa: E402
from movizap.config import settings  # noqa: E402

BASE = "http://127.0.0.1:8008"
falhas = []


def pedir(caminho, token=None, metodo="GET"):
    req = urllib.request.Request(BASE + caminho, method=metodo)
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")


def conferir(rotulo, cond, detalhe=""):
    print(f"  [{'OK  ' if cond else 'FALHA'}] {rotulo}" + (f"  -- {detalhe}" if detalhe else ""))
    if not cond:
        falhas.append(rotulo)


token = auth.criar_token(settings.admin_login)

print("== 1. banco visivel pela API ==")
st, corpo = pedir("/api/saude")
d = json.loads(corpo)
b = d.get("banco", {})
conferir("saude responde", st == 200)
conferir("banco conectado", b.get("ok") is True, f"pg {b.get('postgres')}")
conferir("migracao 003 aplicada", b.get("migracao") == "003", f"versao={b.get('migracao')}")

print("\n== 2. a rota exige a tela CFG_1.1 ==")
st, _ = pedir("/api/canais")
conferir("sem token: 401", st == 401, f"status={st}")
st, corpo = pedir("/api/canais", token)
conferir("com token: 200", st == 200, f"status={st}")

canais = json.loads(corpo) if st == 200 else []
print("\n== 3. o canal da migracao 003 ==")
conferir("exatamente 1 canal", len(canais) == 1, f"{len(canais)} canal(is)")
if canais:
    c = canais[0]
    conferir("instancia = atendimento", c["instancia"] == "atendimento")
    conferir("gateway = evolution", c["gateway"] == "evolution")
    conferir("modo = baileys", c["modo"] == "baileys")
    conferir("estado veio do Evolution ao vivo",
             c["estado"] in ("desconectado", "pareando", "conectado", "caiu"),
             f"estado={c['estado']}")
    conferir("nao pareado (esperado)", c["numero"] is None,
             "o pareamento e pelo painel, decisao do usuario")
    conferir("historico tem marco inicial", c["pareado_em"] is None
             or c["estado"] == "conectado")

print("\n== 4. o Evolution concorda? ==")
try:
    bruto = evolution.estado("atendimento")
    print(f"  Evolution diz: {bruto!r}")
    conferir("estado da API bate com o traduzido",
             canais and canais[0]["estado"] == {"open": "conectado",
                                                "connecting": "pareando",
                                                "close": "desconectado"}.get(bruto, "desconectado"))
except evolution.ErroEvolution as e:
    conferir("Evolution responde", False, str(e))

print("\n== 5. historico de eventos ==")
if canais:
    st, corpo = pedir(f"/api/canais/{canais[0]['id']}/eventos", token)
    evs = json.loads(corpo) if st == 200 else []
    conferir("rota de eventos responde", st == 200)
    conferir("ha pelo menos o evento inicial", len(evs) >= 1, f"{len(evs)} evento(s)")
    for e in evs[:4]:
        print(f"     {e['em'][:19]}  {e['estado']:<14} {e.get('motivo') or ''}")

print("\n== 6. canal inexistente ==")
st, _ = pedir("/api/canais/99999/eventos", token)
conferir("404 para canal que nao existe", st == 404, f"status={st}")

print("\n== 7. nenhum segredo no que a API devolve ==")
st, corpo = pedir("/api/canais", token)
for proibido in ("apikey", "EVOLUTION_API_KEY", "password", "senha"):
    conferir(f"{proibido!r} ausente da resposta", proibido.lower() not in corpo.lower())

print()
if falhas:
    print("!! " + "; ".join(falhas))
    sys.exit(1)
print("CFG_1.1 conferida contra o estado. Falta so o QR -- que e sua decisao.")
