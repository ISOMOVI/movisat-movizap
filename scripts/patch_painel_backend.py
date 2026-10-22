"""Patch: a rota do painel e a tela PNL_1.1 no registro."""
import sys
from pathlib import Path

RAIZ = Path("/home/claude/movizap_painel")


def emendar(caminho: Path, ancora: str, novo: str, marca: str) -> None:
    t = caminho.read_text(encoding="utf-8")
    if marca in t:
        print(f"{caminho.name}: {marca!r} ja estava"); return
    if t.count(ancora) != 1:
        sys.exit(f"{caminho.name}: ancora de {marca!r} aparece {t.count(ancora)}x -- nada escrito")
    caminho.write_text(t.replace(ancora, novo, 1), encoding="utf-8")
    print(f"{caminho.name}: {marca!r} emendado")


# ================================================================= telas.py
TELAS = RAIZ / "movizap" / "telas.py"
emendar(
    TELAS,
    '''    {
        # 🔵 22/10: a tela que recebe o que chega pelos formularios proprios''',
    '''    {
        # 🔵 22/10, decisao dele depois de ver os tres mockups lado a lado:
        # *"vamos de A somente para a Operacao por enquanto, mas bem
        # documentado para as demais futuramente"*.
        #
        # 🚨 O PRIMEIRO HABITANTE DO GRUPO "Paineis", que nasceu declarado e
        # vazio em 19/10. As colunas sao as 11 situacoes da OS do Harmonit
        # mais "Sem OS" e "Sem situacao" -- e o painel existe para a situacao
        # PASSAR A SER USADA (*"hoje ainda nao usamos a situacao da OS"*).
        #
        # ⚠️ `owner` por ora, como o plano diz (Etapa 3). Nao e `equipe`: o
        # card mostra a OS do Harmonit ao lado da solicitacao, e mover o card
        # vai ESCREVER no ERP.
        #
        # ⚠️ MODULO PROPRIO `PNL`: painel nao e atendimento (nao se responde
        # ninguem por ele) nem relatorio (nao se le e fecha) -- e uma fila que
        # se movimenta. Os outros tres paineis entram como PNL_1.2, 1.3 e 1.4
        # quando ele decidir, cada um com modulo e rota propria.
        "codigo": "PNL_1.1",
        "titulo": "Operação",
        "rota": "/paineis/operacao",
        "icone": "bi-kanban",
        "descricao": "Solicitações da Operação pela situação da OS.",
        "grupo": "Painéis",
        "permissao": "owner",
        "fase": 1,
    },
    {
        # 🔵 22/10: a tela que recebe o que chega pelos formularios proprios''',
    "PNL_1.1")

# o grupo deixa de declarar o subgrupo que nunca teve tela
emendar(
    TELAS,
    '''    "Painéis": ["Operacional"],''',
    '''    # 🔵 22/10: o subgrupo "Operacional" SAIU, e isto fecha a pendencia 6 do
    # plano (*"alinhar o nome do subgrupo com o painel"*). Ele foi declarado em
    # 19/10 e nunca teve tela; o painel dele chama-se "Operação", e manter os
    # dois nomes faria o menu desenhar "Paineis › Operacional › Operação".
    # Os quatro paineis sao ITENS do grupo, sem subgrupo.
    "Painéis": [],''',
    '"Painéis": [],')

# ================================================================== main.py
MAIN = RAIZ / "movizap" / "main.py"
emendar(MAIN,
        "from . import formularios as formularios_mod",
        "from . import formularios as formularios_mod\nfrom . import paineis as paineis_mod",
        "paineis as paineis_mod")

emendar(
    MAIN,
    '''# ---------------------------------------------------- formulários próprios''',
    '''# --------------------------------------------------------------- painéis
#
# 🔵 Etapa 3, primeira volta (22/10): só o da Operação, opção A (kanban pelas
# situações da OS), por decisão dele depois dos mockups.
#
# ⚠️ UMA ROTA, NÃO QUATRO: o painel vem no caminho, e o módulo recusa os três
# que ainda não existem com a frase que DIZ isso -- não com 404, que faria
# parecer erro de digitação.

@app.get("/api/paineis/{painel}")
def ver_painel(painel: str, usuario: dict = Depends(auth.requer_tela("PNL_1.1"))):
    return paineis_mod.quadro(painel)


# ---------------------------------------------------- formulários próprios''',
    "/api/paineis/{painel}")

# A prova: reler o estado.
sys.path.insert(0, str(RAIZ))
from movizap.main import app  # noqa: E402
from movizap import telas  # noqa: E402

print()
print("rotas de painel:", sorted(r.path for r in app.routes if "painei" in r.path))
pnl = [t for t in telas.TELAS if t["codigo"] == "PNL_1.1"]
print("PNL_1.1:", bool(pnl), "| grupo:", pnl[0]["grupo"] if pnl else "-",
      "| permissao:", pnl[0]["permissao"] if pnl else "-")
print("GRUPOS['Painéis']:", telas.GRUPOS["Painéis"])
for perfil in ("owner", "admin", "atendimento"):
    u = {"owner": perfil == "owner",
         "permissoes": [] if perfil == "owner" else list(telas.PERFIS[perfil] or [])}
    print(perfil, "ve PNL_1.1?", telas.pode_acessar(u, "PNL_1.1"))
