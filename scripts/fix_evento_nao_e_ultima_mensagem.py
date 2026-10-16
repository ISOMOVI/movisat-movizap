"""CORRECAO: o EVENTO nao e "a ultima mensagem" da conversa (15/10).

🚨 A REGRESSAO, achada pela suite inteira e nao por leitura: a regra de
**sem dono** (02/10, pedido dele) e "a ULTIMA mensagem tem de ser de
`entrada`". O evento do Bloco 11 e uma mensagem interna -- entao convidar
alguem numa conversa orfa a TIRAVA DA FILA. O teste
`test_convidar_nao_mexe_na_lista_de_sem_dono` pegou exatamente isso.

E a mesma coisa valia para a PREVIA da lista (`u.conteudo`): toda conversa
passaria a mostrar "assumiu a conversa" no lugar da ultima fala do cliente --
na tela mais usada do painel.

🚨 A CORRECAO EXCLUI O **EVENTO**, NAO A NOTA. Nota e coisa que uma pessoa
escreveu, e ve-la na previa informa ("fulano anotou X"). Evento e contabilidade
do sistema. Excluir toda `interna` mudaria comportamento que ele ja validou, e
isso nao e meu para decidir -- ver a pendencia que eu abri sobre nota interna
tirar conversa de "Sem dono", que e anterior a hoje.

⚠️ E O EVENTO DE TRANSFERENCIA PASSA A SER SO DO `motivo = 'manual'`. A
distribuicao automatica (`inatividade`, `ia_triagem`, `sem_time`) JA grava uma
nota do sistema explicando a regra dos 10 min; o evento ali seria uma segunda
linha dizendo quase o mesmo, em toda conversa distribuida.

Uso: ./venv/bin/python scripts/fix_evento_nao_e_ultima_mensagem.py [--conferir]
"""
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
SO_CONFERIR = "--conferir" in sys.argv

PASSOS = [
    ("movizap/conversas.py", "a prévia da lista ignora o evento",
     """          LEFT JOIN LATERAL (
                SELECT conteudo, direcao, tipo FROM mensagem m
                 WHERE m.conversa_id = c.id
                 ORDER BY m.criada_em DESC, m.id DESC LIMIT 1
          ) u ON true""",
     """          LEFT JOIN LATERAL (
                -- 🚨 15/10: `evento IS NULL` -- o log de ações (Bloco 11) NÃO
                -- é a última mensagem da conversa. Sem isto, toda conversa
                -- passaria a mostrar "assumiu a conversa" na prévia, no lugar
                -- da última fala do cliente, na tela mais usada do painel.
                -- ⚠️ NOTA DE GENTE CONTINUA VALENDO: ela é informação ("fulano
                -- anotou X"); evento é contabilidade do sistema.
                SELECT conteudo, direcao, tipo FROM mensagem m
                 WHERE m.conversa_id = c.id AND m.evento IS NULL
                 ORDER BY m.criada_em DESC, m.id DESC LIMIT 1
          ) u ON true"""),

    ("movizap/conversas.py", "sem dono: o evento não conta como resposta",
     """            \"\"\"c.atendente_id IS NULL
               AND c.estado <> 'resolvida'
               AND (SELECT m.direcao FROM mensagem m
                     WHERE m.conversa_id = c.id
                     ORDER BY m.criada_em DESC, m.id DESC
                     LIMIT 1) = 'entrada'\"\"\")""",
     """            \"\"\"c.atendente_id IS NULL
               AND c.estado <> 'resolvida'
               AND (SELECT m.direcao FROM mensagem m
                     WHERE m.conversa_id = c.id AND m.evento IS NULL
                     ORDER BY m.criada_em DESC, m.id DESC
                     LIMIT 1) = 'entrada'\"\"\")"""),

    ("movizap/conversas.py", "transferência: evento só no manual",
     """    _destino = None
    if para_atendente_id:""",
     """    # ⚠️ SÓ O MANUAL VIRA EVENTO. A distribuição automática
    # (`inatividade`, `ia_triagem`, `sem_time`) já grava uma nota do sistema
    # explicando a regra; o evento ali seria uma segunda linha dizendo quase o
    # mesmo, em toda conversa distribuída.
    _destino = None
    if motivo == "manual" and para_atendente_id:"""),

    ("movizap/conversas.py", "transferência: o elif acompanha a guarda",
     """    elif time_id:
        _time = (banco.um("SELECT nome FROM time WHERE id = %s", (time_id,)) or {}).get("nome")
        _destino = f"o time {_time}" if _time else None
    registrar_evento(conversa_id, "transferiu",
                     f"transferiu para {_destino}" if _destino else "transferiu a conversa",
                     de_atendente_id)""",
     """    elif motivo == "manual" and time_id:
        _time = (banco.um("SELECT nome FROM time WHERE id = %s", (time_id,)) or {}).get("nome")
        _destino = f"o time {_time}" if _time else None
    if motivo == "manual":
        registrar_evento(conversa_id, "transferiu",
                         f"transferiu para {_destino}" if _destino
                         else "transferiu a conversa",
                         de_atendente_id)"""),

    ("tests/teste_fila.py", "as guardas do RESUMO olham a nota, não o evento",
     """    @staticmethod
    def _notas(conversa_id):
        return banco.varios(
            "SELECT direcao, tipo, conteudo FROM mensagem "
            "WHERE conversa_id = %s AND tipo = 'nota'", (conversa_id,))""",
     """    @staticmethod
    def _notas(conversa_id):
        \"\"\"As notas de GENTE. 🔵 15/10: o log de ações (Bloco 11) também é
        nota interna, e sem o `evento IS NULL` estas guardas passariam a contar
        o evento de transferência junto do resumo -- e elas são sobre o resumo.
        \"\"\"
        return banco.varios(
            "SELECT direcao, tipo, conteudo FROM mensagem "
            "WHERE conversa_id = %s AND tipo = 'nota' AND evento IS NULL",
            (conversa_id,))

    @staticmethod
    def _eventos(conversa_id):
        return banco.varios(
            "SELECT evento, conteudo FROM mensagem "
            "WHERE conversa_id = %s AND evento IS NOT NULL ORDER BY id",
            (conversa_id,))"""),

    ("tests/teste_fila.py", "e uma guarda nova: transferir manual deixa evento",
     """    def test_transferencia_recusada_nao_deixa_nota(self, uma_conversa):""",
     """    def test_transferencia_manual_deixa_evento_mesmo_sem_resumo(self, uma_conversa):
        \"\"\"🔵 15/10, Bloco 11: até hoje, transferir sem escrever resumo não
        deixava rastro NENHUM na conversa -- a nota de 23/09 só nasce com
        resumo. O evento existe sempre.\"\"\"
        t = banco.um("SELECT id FROM time WHERE ativo ORDER BY id LIMIT 1")
        conversas.transferir(uma_conversa, t["id"], None)
        assert self._notas(uma_conversa) == [], "não havia resumo para anotar"
        assert [e["evento"] for e in self._eventos(uma_conversa)] == ["transferiu"]

    def test_transferencia_recusada_nao_deixa_nota(self, uma_conversa):"""),

    ("tests/teste_fila.py", "recusada também não deixa evento",
     """        r = conversas.transferir(uma_conversa, 999999, None, texto_resumo="x")
        assert r["ok"] is False
        assert self._notas(uma_conversa) == []""",
     """        r = conversas.transferir(uma_conversa, 999999, None, texto_resumo="x")
        assert r["ok"] is False
        assert self._notas(uma_conversa) == []
        # O log é de ação que ACONTECEU: transferência recusada não é ação.
        assert self._eventos(uma_conversa) == []"""),
]


def aplicar():
    por_arquivo: dict[str, str] = {}
    for rel, nome, velho, novo in PASSOS:
        caminho = RAIZ / rel
        if rel not in por_arquivo:
            por_arquivo[rel] = caminho.read_text(encoding="utf-8")
        texto = por_arquivo[rel]
        if novo in texto:
            print(f"  ja aplicado: {rel}: {nome}")
            continue
        n = texto.count(velho)
        if n != 1:
            raise SystemExit(f"ANCORA {n}x em {rel} '{nome}': {velho[:70]!r}")
        por_arquivo[rel] = texto.replace(velho, novo, 1)
        print(f"  {'conferido' if SO_CONFERIR else 'aplicado'}: {rel}: {nome}")
    for rel, texto in por_arquivo.items():
        compile(texto, str(RAIZ / rel), "exec")
    if not SO_CONFERIR:
        for rel, texto in por_arquivo.items():
            (RAIZ / rel).write_text(texto, encoding="utf-8")


aplicar()
