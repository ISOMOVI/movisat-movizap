"""Bloco 12: "visto por" na nota interna — backend (15/10).

🔵 *"confirmacao de leitura das notas dentro da conversa ... um icone que ao
clicar mostra que ja leu aquela nota, junto ao carimbo de data e hora, bem
pequeno mesmo"*.

Uso: ./venv/bin/python scripts/patch_bloco12_backend.py [--conferir]
"""
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
CONVERSAS = RAIZ / "movizap" / "conversas.py"
MAIN = RAIZ / "movizap" / "main.py"
SO_CONFERIR = "--conferir" in sys.argv

# ------------------------------------------------------------- conversas.py
FUNCAO_ANCORA = "def _minha_nota(conversa_id: int, mensagem_id: int, atendente_id: int | None):"
FUNCAO = '''# ── "VISTO POR": quem teve a nota interna na tela (Bloco 12, 15/10) ─────────
#
# 🔵 Pedido dele: *"um icone que ao clicar mostra que ja leu aquela nota, junto
# ao carimbo de data e hora, bem pequeno mesmo"*.
#
# 🚨 O RÓTULO É "VISTO POR", NUNCA "LEU", e isto não é preciosismo de palavra.
# O que o sistema sabe é que a nota ESTEVE NA TELA de alguém. Dizer "leu"
# transforma suposição em prova, e alguém vai cobrar com base nisso.
#
# 🚨 MARCA QUANDO A NOTA APARECE, não quando a conversa abre: abrir uma
# conversa de 200 mensagens e não rolar até o fim não é ver a nota de lá atrás.
# Quem decide que apareceu é a tela (ela é a única que sabe o que está visível);
# o backend só aceita ids de nota DESTA conversa.
#
# ⚠️ NOTA ANTERIOR A 15/10 NÃO TEM REGISTRO, e a tela diz isso em vez de
# "ninguém viu". O corte vai junto de cada nota, em `leitura_rastreada`, para a
# tela não precisar saber de data nenhuma.
LEITURA_DE_NOTA_DESDE = datetime(2026, 10, 15, tzinfo=timezone.utc)


def marcar_notas_vistas(conversa_id: int, mensagem_ids: list[int],
                        atendente_id: int | None) -> int:
    """Carimba "visto" nas notas que apareceram na tela desta pessoa.

    Devolve quantas linhas nasceram agora. Idempotente pela PK
    `(mensagem_id, atendente_id)`: a mesma nota reaparecendo na tela não muda
    a hora do primeiro "visto" -- e não deve, senão o carimbo passa a dizer
    "a última vez em que rolou por aqui".
    """
    if not atendente_id or not mensagem_ids:
        return 0
    ids = [int(i) for i in mensagem_ids][:200]
    linha = banco.um(
        """WITH alvo AS (
               SELECT id FROM mensagem
                WHERE id = ANY(%s) AND conversa_id = %s AND tipo = 'nota'
                  AND criada_em >= %s
           ), entrou AS (
               INSERT INTO nota_leitura (mensagem_id, atendente_id)
               SELECT id, %s FROM alvo
               ON CONFLICT DO NOTHING
               RETURNING 1
           )
           SELECT count(*) AS n FROM entrou""",
        (ids, conversa_id, LEITURA_DE_NOTA_DESDE, atendente_id))
    return linha["n"]


'''

VISTOS_ANCORA = """                      m.evento,
                      -- Quem falou DENTRO do grupo. Nulo em conversa direta,"""
VISTOS = """                      m.evento,
                      -- 🔵 15/10, Bloco 12: quem teve esta NOTA na tela, e
                      -- quando. Subconsulta, e não JOIN: com JOIN, uma nota
                      -- vista por três pessoas viraria três linhas no fio.
                      -- Só para nota: mensagem do cliente não tem isto.
                      CASE WHEN m.tipo = 'nota' THEN (
                          SELECT json_agg(json_build_object(
                                     'atendente_id', v.atendente_id,
                                     'nome', av.nome, 'visto_em', v.visto_em)
                                 ORDER BY v.visto_em)
                            FROM nota_leitura v
                            JOIN atendente av ON av.id = v.atendente_id
                           WHERE v.mensagem_id = m.id)
                      END AS vistos,
                      -- Quem falou DENTRO do grupo. Nulo em conversa direta,"""

# ------------------------------------------------------------------ main.py
ROTA_ANCORA = '''@app.get("/api/conversas/{conversa_id}/contatos-da-empresa")'''
ROTA = '''class NotasVistas(BaseModel):
    # Teto de 200: isto vem do navegador, e a tela manda o que está visível.
    ids: list[int] = Field(default_factory=list, max_length=200)


@app.post("/api/conversas/{conversa_id}/notas/vistas")
def marcar_notas_vistas(conversa_id: int, corpo: NotasVistas,
                        usuario: dict = Depends(auth.requer_tela("ATD_1.2"))):
    """🔵 15/10, Bloco 12: carimba "visto por" nas notas que apareceram na tela.

    🚨 QUEM SABE O QUE ESTÁ VISÍVEL É A TELA, e por isso ela é que manda os
    ids. O backend não confia neles para nada além disto: só carimba nota
    DESTA conversa, e só a partir do dia em que o registro passou a existir.

    ⚠️ Sem vínculo de atendimento não há quem carimbar, e isso não é erro: a
    rota responde 0 e segue. Levantar 400 faria a tela mostrar erro para quem
    só estava lendo.
    """
    quantas = conversas.marcar_notas_vistas(
        conversa_id, corpo.ids, _atendente_do_usuario(usuario))
    return {"ok": True, "novas": quantas}


'''


def trocar(caminho: Path, pares, texto=None):
    texto = caminho.read_text(encoding="utf-8") if texto is None else texto
    for nome, velho, novo in pares:
        if novo in texto:
            print(f"  ja aplicado: {nome}")
            continue
        n = texto.count(velho)
        if n != 1:
            raise SystemExit(f"ANCORA {n}x em '{nome}': {velho[:70]!r}")
        texto = texto.replace(velho, novo, 1)
        print(f"  {'conferido' if SO_CONFERIR else 'aplicado'}: {nome}")
    compile(texto, str(caminho), "exec")
    if not SO_CONFERIR:
        caminho.write_text(texto, encoding="utf-8")


# `leitura_rastreada` sai em PYTHON, e não no SQL: a consulta de `mensagens()`
# usa parâmetros POSICIONAIS, e um `%(nome)s` no meio dela quebraria a chamada
# inteira (psycopg não mistura os dois estilos). Assim a data do corte continua
# existindo num lugar só, que é a constante.
POS_ANCORA = """           ) recentes
           ORDER BY criada_em, id\"\"\",
        (_ids_do_historico(conversa_id), antes_de, antes_de, limite))"""
POS_NOVO = """           ) recentes
           ORDER BY criada_em, id\"\"\",
        (_ids_do_historico(conversa_id), antes_de, antes_de, limite))

    for linha in linhas:
        # Lista no lugar de NULL: a tela não precisa saber que `json_agg` sem
        # acerto devolve `None`.
        linha["vistos"] = linha.get("vistos") or []
        # ⚠️ O QUE DISTINGUE "NINGUÉM VIU" DE "NÃO HAVIA REGISTRO" (Bloco 12).
        # Sem isto, toda nota anterior a 15/10 apareceria como não vista por
        # ninguém -- afirmação falsa sobre o passado, dita com cara de dado.
        linha["leitura_rastreada"] = bool(
            linha["tipo"] == "nota"
            and linha["criada_em"] >= LEITURA_DE_NOTA_DESDE)
    return linhas"""

RETORNO_ANCORA = """    # Pega-se as n mais RECENTES e reordena para exibir.
    return banco.varios("""
RETORNO_NOVO = """    # Pega-se as n mais RECENTES e reordena para exibir.
    linhas = banco.varios("""

trocar(CONVERSAS, [
    ("conversas: marcar_notas_vistas()", FUNCAO_ANCORA, FUNCAO + FUNCAO_ANCORA),
    ("conversas: `vistos` na consulta da tela", VISTOS_ANCORA, VISTOS),
    ("conversas: a consulta vira variável", RETORNO_ANCORA, RETORNO_NOVO),
    ("conversas: `leitura_rastreada` calculado em Python", POS_ANCORA, POS_NOVO),
])
trocar(MAIN, [("main: a rota de marcar visto", ROTA_ANCORA, ROTA + ROTA_ANCORA)])
