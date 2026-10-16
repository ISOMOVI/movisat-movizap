"""Bloco 3: a rota das ligações de uma conversa (o modal de 7 dias da ficha).

Idempotente, com âncora conferida. Não reinicia serviço.
Uso: ./venv/bin/python scripts/patch_rota_ficha.py [--conferir]
"""
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
SO_CONFERIR = "--conferir" in sys.argv

IMPORT_ANCORA = "from . import ligacoes_alistar\n"
IMPORT_NOVO = "from . import ligacoes_consulta\n"

ROTA_ANCORA = '''@app.get("/api/conversas/buscar-empresa")
'''
ROTA_NOVA = '''@app.get("/api/conversas/{conversa_id}/ligacoes")
def ligacoes_da_conversa(conversa_id: int, dias: int = ligacoes_consulta.DIAS_PADRAO_FICHA,
                         usuario: dict = Depends(auth.requer_tela("ATD_1.2"))):
    """As ligações do telefone desta conversa, para o modal do botão Ligações.

    🔵 *"aqui na conversa, o modal só trará ultimos 7 dias, para mais dias um
    botão vai levar para a aba Ligações"*.

    🚨 É `ATD_1.2`, a permissão da própria conversa — não a da aba Ligações.
    Quem atende vê as ligações do número que está atendendo; a aba (com o
    histórico de todos) é outra permissão, e nasce só do owner.

    ⚠️ Devolve `cobertura` junto: a tela precisa poder dizer que só aparecem
    ligações de ramais com agente instalado. Sem isso ela afirmaria "nenhuma
    ligação" onde a verdade é "aquele PC não manda".
    """
    conversa = banco.um("SELECT telefone_e164 FROM conversa WHERE id = %s", (conversa_id,))
    if not conversa:
        raise HTTPException(status_code=404, detail="Conversa não encontrada.")
    if not conversa["telefone_e164"]:
        # Grupo não tem ficha, e sem número não há o que consultar.
        return {"dias": dias, "telefone_e164": None, "total": 0,
                "por_sentido": {s: [] for s in ligacoes.SENTIDOS},
                "cobertura": {"com_agente": 0, "atendentes": 0}}
    return ligacoes_consulta.do_telefone(conversa["telefone_e164"], dias)


'''

PASSOS = [
    ("import do ligacoes_consulta", IMPORT_ANCORA, IMPORT_ANCORA + IMPORT_NOVO,
     "from . import ligacoes_consulta"),
    ("rota /api/conversas/{id}/ligacoes", ROTA_ANCORA, ROTA_NOVA + ROTA_ANCORA,
     '/api/conversas/{conversa_id}/ligacoes'),
]

alvo = RAIZ / "movizap/main.py"
texto = alvo.read_text(encoding="utf-8")
for nome, ancora, novo, marca in PASSOS:
    if marca in texto:
        print(f"já estava: {nome}")
        continue
    if ancora not in texto:
        raise SystemExit(f"ÂNCORA NÃO ACHADA ({nome}): {ancora[:60]!r}")
    if texto.count(ancora) != 1:
        raise SystemExit(f"ÂNCORA AMBÍGUA ({nome}): {texto.count(ancora)}×")
    texto = texto.replace(ancora, novo)
    print(f"{'conferido' if SO_CONFERIR else 'aplicado'}: {nome}")

if not SO_CONFERIR:
    alvo.write_text(texto, encoding="utf-8")
    print(f"gravado: {alvo}")
