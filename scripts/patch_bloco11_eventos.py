"""Bloco 11: o log de acoes como nota interna (15/10).

🔵 *"ao final proponha log dentro da conversa interno apenas sobre acoes de
transfernecia, inserir pessoas, etc, pode ser em Nota interna do Movizap"*,
aprovado em 15/10 (*"o 3 pode seguir"*).

🚨 OS PONTOS DE ENGATE SAO ACHADOS PELO AST, nao por ancora de texto. Sao 13
acoes, varias com mais de um caminho de sucesso (`sair` tem tres); ancora de
texto para cada uma seriam 13 chances de casar no lugar errado em silencio.
O script imprime cada insercao com o numero de linha, e valida o arquivo
inteiro com `compile()` antes de gravar.

Uso: ./venv/bin/python scripts/patch_bloco11_eventos.py [--conferir]
"""
import ast
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
CONVERSAS = RAIZ / "movizap" / "conversas.py"
MAIN = RAIZ / "movizap" / "main.py"
SO_CONFERIR = "--conferir" in sys.argv

# ===========================================================================
# 1. O HELPER
# ===========================================================================
HELPER_ANCORA = "def _minha_nota(conversa_id: int, mensagem_id: int, atendente_id: int | None):"
HELPER = '''# ── EVENTO: o log de ações DENTRO da conversa (Bloco 11, 15/10) ─────────────
#
# 🔵 Pedido dele: *"log dentro da conversa interno apenas sobre ações de
# transfernecia, inserir pessoas, etc, pode ser em Nota interna do Movizap"*.
#
# 🚨 O EVENTO É UMA NOTA INTERNA COM UMA MARCA (`mensagem.evento`, migração
# 064), e não um `tipo` novo: o CHECK `ck_nota_e_interna` amarra
# `tipo = 'nota'` a `direcao = 'interna'` nos dois sentidos, e afrouxá-lo
# abriria a porta para uma nota vazar como mensagem de saída. Como nota, o
# evento aparece na conversa, no ponto do tempo certo, e nunca vai ao cliente.
#
# 🚨 `autor = 'sistema'`, e NÃO 'atendente': a frase foi escrita pelo sistema,
# em nome de quem agiu. Quem agiu vai em `atendente_id`, que é o que a tela usa
# para dizer o nome.
#
# 🚨 EVENTO NÃO SE EDITA NEM SE APAGA -- log que se reescreve não é log. A
# recusa mora em `_minha_nota`, o único caminho de editar e apagar nota. Sem
# ela o próprio autor passaria no teste "só quem escreveu pode editar", porque
# `atendente_id` é dele.
#
# ⚠️ FALHAR AQUI NÃO PODE DERRUBAR A AÇÃO. A transferência já aconteceu e está
# comitada quando o evento é gravado; se a gravação do log estourar, o certo é
# perder a LINHA DO LOG e registrar o erro, nunca desfazer o trabalho de quem
# clicou. É a razão de o `except` ser largo e de o evento ficar FORA da
# transação da ação.
#
# ⚠️ NADA RETROATIVO, decisão declarada: transferência, encerramento e convite
# dariam para reconstituir, mas vínculo e tipo NÃO TÊM HISTÓRICO -- e log pela
# metade, com data inventada para o que falta, engana mais que log que começa
# hoje. A tela diz desde quando registra.
def registrar_evento(conversa_id: int, evento: str, texto: str,
                     atendente_id: int | None = None) -> int | None:
    """Uma linha no log da conversa. Devolve o id da nota, ou None se falhou.

    `evento` tem de estar na lista do CHECK `ck_evento_conhecido` (migração
    064): valor novo exige migração, e é isso que impede o log de ganhar dois
    verbos diferentes para a mesma ação em dois lugares do código.
    """
    try:
        linha = banco.um(
            """INSERT INTO mensagem
                   (conversa_id, direcao, autor, tipo, conteudo, evento,
                    atendente_id, criada_em)
               VALUES (%s, 'interna', 'sistema', 'nota', %s, %s, %s, now())
               RETURNING id""",
            (conversa_id, texto, evento, atendente_id))
        return linha["id"]
    except Exception:
        log.exception("evento %r não gravado na conversa %s", evento, conversa_id)
        return None


'''

# ===========================================================================
# 2. OS ENGATES, por funcao e por linha do `return` de sucesso
#    (a linha e localizada pelo AST; aqui so se diz QUAL sucesso e o que gravar)
# ===========================================================================
# chave: (funcao, n-esimo sucesso contando de cima para baixo no arquivo)
ENGATES = {
    ("assumir", 0): '''# 🔵 15/10, Bloco 11: o log da ação.
registrar_evento(conversa_id, "assumiu", "assumiu a conversa", atendente_id)''',

    ("assumir", 1): '''registrar_evento(conversa_id, "assumiu",
                 "reabriu e assumiu a conversa", atendente_id)''',

    ("convidar", 0): '''# 🔵 15/10, Bloco 11. `convidado_por == atendente_id` é a pessoa entrando
# por conta própria -- `entrar()` reusa este caminho de propósito --, e não
# alguém sendo chamado. O log diz qual dos dois foi.
if convidado_por == atendente_id:
    registrar_evento(conversa_id, "entrou", "entrou na conversa", atendente_id)
else:
    registrar_evento(conversa_id, "convidou",
                     f"chamou {alvo['nome']} para acompanhar", convidado_por)''',

    ("sair", 0): '''registrar_evento(conversa_id, "saiu", "saiu da conversa", atendente_id)''',

    ("sair", 1): '''registrar_evento(conversa_id, "saiu",
                 "saiu da conversa, que voltou para a fila", atendente_id)''',

    ("sair", 2): '''registrar_evento(conversa_id, "saiu",
                 f"saiu da conversa; {herdeiro['nome']} herdou", atendente_id)''',

    ("remover", 0): '''# O nome de quem saiu vem por consulta: a função recebe só o id, e um log
# que diz "tirou o atendente 28684" não é legível por ninguém.
_fora = banco.um("SELECT nome FROM atendente WHERE id = %s", (atendente_id,))
registrar_evento(conversa_id, "removeu",
                 f"tirou {(_fora or {}).get('nome') or 'um atendente'} da conversa",
                 quem_pede)''',

    ("devolver_para_fila", 0): '''registrar_evento(conversa_id, "devolveu",
                 "devolveu a conversa para a fila", de_atendente_id)''',

    ("transferir", 0): '''# ⚠️ ESTE EVENTO NÃO SUBSTITUI A NOTA DE RESUMO de 23/09, e os dois não são
# a mesma coisa: a nota é o TEXTO que quem assume precisa ler, e só existe
# quando houve resumo; o evento é o LOG, e existe sempre. Transferência sem
# resumo não deixava rastro nenhum na conversa até hoje.
_destino = None
if para_atendente_id:
    _destino = (banco.um("SELECT nome FROM atendente WHERE id = %s",
                         (para_atendente_id,)) or {}).get("nome")
elif time_id:
    _time = (banco.um("SELECT nome FROM time WHERE id = %s", (time_id,)) or {}).get("nome")
    _destino = f"o time {_time}" if _time else None
registrar_evento(conversa_id, "transferiu",
                 f"transferiu para {_destino}" if _destino else "transferiu a conversa",
                 de_atendente_id)''',

    ("encerrar", 0): '''registrar_evento(
    conversa_id, "encerrou",
    "encerrou o atendimento"
    + (f" como {classificacao['nome']}" if classificacao else ""),
    autor)''',

    ("bloquear", 0): '''registrar_evento(conversa_id, "bloqueou", "bloqueou este número", atendente_id)''',

    ("desbloquear", 0): '''registrar_evento(conversa_id, "desbloqueou",
                 "desbloqueou este número", atendente_id)''',
}

# ===========================================================================
# 3. Dois ajustes de texto: a consulta que a tela lê, e a recusa de editar
# ===========================================================================
TEXTOS_CONVERSAS = [
    ("mensagens(): a tela precisa do campo que vai desenhar",
     """                      m.atendente_id,
                      -- Quem falou DENTRO do grupo. Nulo em conversa direta,""",
     """                      m.atendente_id,
                      -- 🔵 15/10, Bloco 11: a marca de EVENTO. Sem ela a tela
                      -- desenharia o log como nota comum, com balão e com
                      -- botão de editar -- e evento não se edita.
                      m.evento,
                      -- Quem falou DENTRO do grupo. Nulo em conversa direta,"""),

    ("_minha_nota(): evento não se edita nem se apaga",
     """        \"\"\"SELECT id, conversa_id, tipo, conteudo, atendente_id, apagada_em
             FROM mensagem WHERE id = %s\"\"\", (mensagem_id,))
    if not m or m["conversa_id"] != conversa_id:
        return None, "Nota não encontrada nesta conversa."
    if m["tipo"] != "nota":
        return None, "Só nota interna pode ser editada ou apagada por aqui.\"""",
     """        \"\"\"SELECT id, conversa_id, tipo, conteudo, evento, atendente_id, apagada_em
             FROM mensagem WHERE id = %s\"\"\", (mensagem_id,))
    if not m or m["conversa_id"] != conversa_id:
        return None, "Nota não encontrada nesta conversa."
    if m["tipo"] != "nota":
        return None, "Só nota interna pode ser editada ou apagada por aqui."
    # 🚨 LOG QUE SE REESCREVE NÃO É LOG (Bloco 11, 15/10). A recusa tem de
    # estar aqui porque o `atendente_id` do evento é de quem AGIU -- sem esta
    # linha, essa pessoa passaria no teste "só quem escreveu pode editar".
    if m["evento"]:
        return None, "Isto é um registro de ação, e não se edita nem se apaga.\""""),
]

# ===========================================================================
# 4. As tres acoes de CADASTRO: o evento sai da ROTA, nao da funcao
#    (`vincular`, `desvincular` e `definir_tipo` nao recebem quem agiu --
#     mudar as assinaturas mexeria em quem as chama, e o log precisa do autor)
# ===========================================================================
TEXTOS_MAIN = []


def achar_sucessos(fonte: str) -> dict:
    """{(funcao, n): linha do return} para todo `return {"ok": True, ...}`."""
    arvore = ast.parse(fonte)
    achados: dict = {}
    for no in arvore.body:
        if not isinstance(no, ast.FunctionDef):
            continue
        rets = []
        for sub in ast.walk(no):
            if not isinstance(sub, ast.Return):
                continue
            v = sub.value
            if not isinstance(v, ast.Dict):
                continue
            for k, val in zip(v.keys, v.values):
                if (isinstance(k, ast.Constant) and k.value == "ok"
                        and isinstance(val, ast.Constant) and val.value is True):
                    rets.append(sub.lineno)
                    break
        for i, linha in enumerate(sorted(rets)):
            achados[(no.name, i)] = linha
    return achados


def aplicar_conversas() -> list[str]:
    fonte = CONVERSAS.read_text(encoding="utf-8")
    relato = []

    if "def registrar_evento(" in fonte:
        relato.append("  ja aplicado: conversas.py")
        return relato

    # ---- os dois ajustes de texto, antes (nao mexem em numero de linha de
    #      forma que atrapalhe: sao feitos depois dos engates, por isso ficam
    #      guardados e aplicados no fim)
    for nome, velho, novo in TEXTOS_CONVERSAS:
        if fonte.count(velho) != 1:
            raise SystemExit(f"ANCORA {fonte.count(velho)}x em '{nome}'")

    # ---- os engates, de BAIXO PARA CIMA: inserir embaixo nao desloca o que
    #      esta em cima, e assim as linhas achadas pelo AST continuam valendo
    sucessos = achar_sucessos(fonte)
    faltando = [k for k in ENGATES if k not in sucessos]
    if faltando:
        raise SystemExit(f"nao achei o sucesso de: {faltando}")

    linhas = fonte.splitlines(keepends=True)
    for chave in sorted(ENGATES, key=lambda k: sucessos[k], reverse=True):
        n = sucessos[chave]
        alvo = linhas[n - 1]
        recuo = " " * (len(alvo) - len(alvo.lstrip()))
        bloco = "".join(f"{recuo}{l}\n" if l.strip() else "\n"
                        for l in ENGATES[chave].split("\n"))
        linhas.insert(n - 1, bloco)
        relato.append(f"  engatado: {chave[0]}#{chave[1]} antes da linha {n}")

    fonte = "".join(linhas)

    # ---- o helper e os dois ajustes
    fonte = fonte.replace(HELPER_ANCORA, HELPER + HELPER_ANCORA, 1)
    relato.append("  helper: registrar_evento()")
    for nome, velho, novo in TEXTOS_CONVERSAS:
        fonte = fonte.replace(velho, novo, 1)
        relato.append(f"  ajustado: {nome}")

    compile(fonte, str(CONVERSAS), "exec")
    if not SO_CONFERIR:
        CONVERSAS.write_text(fonte, encoding="utf-8")
    return relato


for linha in aplicar_conversas():
    print(linha)
print("conferido (nada gravado)" if SO_CONFERIR else "GRAVADO")
