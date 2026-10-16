"""CORRECAO do Bloco 11: o evento tem de entrar na MESMA transacao da acao
quando o chamador esta dentro de um `with banco.cursor()` (15/10).

🚨 O DEFEITO, medido com `faulthandler` e nao deduzido: dentro de `sair()`, o
`registrar_evento` pedia uma conexao NOVA ao pool e fazia `INSERT INTO mensagem`.
Essa INSERT tem FK para `conversa(id)` e por isso precisa de trava na linha da
conversa -- que a transacao AINDA ABERTA do `sair()` ja segurava. Uma sessao
esperando a outra, que espera a primeira. O Postgres nao enxerga isso como
deadlock (so ha um esperando), entao nao aborta ninguem: **espera para sempre**.
A suite ficou pendurada e o `timeout` teve de derrubar.

🚨 E NAO FOI O POOL. O pool tem `max_size=8` e `timeout=10`: faltar conexao
teria dado erro em 10 segundos. Quem travou foi a TRAVA DE LINHA, e e por isso
que aumentar o pool nao consertaria nada -- a licao e outra: **nunca pedir
conexao nova dentro de um `with banco.cursor()`**.

A correcao: `registrar_evento` aceita `cur`. Com ele, grava na mesma transacao
(sem trava nova) e protege a transacao do chamador com SAVEPOINT -- se a
gravacao do log falhar, o rollback e so do savepoint, e a ACAO continua valendo.
Sem ele, segue como estava, com conexao propria.

Uso: ./venv/bin/python scripts/fix_evento_na_transacao.py [--conferir]
"""
import ast
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
ALVO = RAIZ / "movizap" / "conversas.py"
SO_CONFERIR = "--conferir" in sys.argv

HELPER_VELHO = '''def registrar_evento(conversa_id: int, evento: str, texto: str,
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
        return None'''

HELPER_NOVO = '''_INSERT_EVENTO = """INSERT INTO mensagem
       (conversa_id, direcao, autor, tipo, conteudo, evento,
        atendente_id, criada_em)
   VALUES (%s, 'interna', 'sistema', 'nota', %s, %s, %s, now())
   RETURNING id"""


def registrar_evento(conversa_id: int, evento: str, texto: str,
                     atendente_id: int | None = None, cur=None) -> int | None:
    """Uma linha no log da conversa. Devolve o id da nota, ou None se falhou.

    `evento` tem de estar na lista do CHECK `ck_evento_conhecido` (migração
    064): valor novo exige migração, e é isso que impede o log de ganhar dois
    verbos diferentes para a mesma ação em dois lugares do código.

    🚨 **QUEM CHAMA DE DENTRO DE UM `with banco.cursor()` TEM DE PASSAR O
    `cur`.** Sem ele, esta função pede uma conexão NOVA e faz `INSERT INTO
    mensagem`, que precisa de trava na linha de `conversa` por causa da FK --
    trava que a transação ainda aberta do chamador já segura. Uma sessão espera
    a outra, que espera a primeira; o Postgres não vê deadlock (só há um
    esperando) e **espera para sempre**. Medido em 15/10 dentro de `sair()`,
    com `faulthandler`, depois de a suíte ficar pendurada.

    ⚠️ Não foi o pool: ele tem `max_size=8` e `timeout=10`, e falta de conexão
    daria erro em 10 s. Aumentar o pool não consertaria nada.

    ⚠️ COM `cur`, O LOG ENTRA NA TRANSAÇÃO DA AÇÃO, e um erro aqui abortaria
    essa transação inteira -- o `except` não desfaz o estado abortado no
    Postgres. Daí o SAVEPOINT: falha de log desfaz só o log, e a ação, que é o
    trabalho de quem clicou, continua valendo.
    """
    dados = (conversa_id, texto, evento, atendente_id)
    if cur is not None:
        try:
            cur.execute("SAVEPOINT evento_log")
            cur.execute(_INSERT_EVENTO, dados)
            return cur.fetchone()["id"]
        except Exception:
            log.exception("evento %r não gravado na conversa %s (na transação)",
                          evento, conversa_id)
            try:
                cur.execute("ROLLBACK TO SAVEPOINT evento_log")
            except Exception:
                log.exception("savepoint do evento não desfeito")
            return None
    try:
        return banco.um(_INSERT_EVENTO, dados)["id"]
    except Exception:
        log.exception("evento %r não gravado na conversa %s", evento, conversa_id)
        return None'''


def dentro_de_cursor(fonte: str) -> set[int]:
    """As linhas de chamada de `registrar_evento` que estão DENTRO de um
    `with banco.cursor()`. Pelo AST: indentação não distingue `with` de `if`."""
    arvore = ast.parse(fonte)
    dentro: set[int] = set()

    def e_cursor(no: ast.With) -> bool:
        for item in no.items:
            ctx = item.context_expr
            if (isinstance(ctx, ast.Call) and isinstance(ctx.func, ast.Attribute)
                    and ctx.func.attr == "cursor"):
                return True
        return False

    for no in ast.walk(arvore):
        if not isinstance(no, ast.With) or not e_cursor(no):
            continue
        for sub in ast.walk(no):
            if (isinstance(sub, ast.Call) and isinstance(sub.func, ast.Name)
                    and sub.func.id == "registrar_evento"):
                dentro.add(sub.lineno)
    return dentro


def aplicar():
    fonte = ALVO.read_text(encoding="utf-8")

    if "cur=None) -> int | None:" in fonte:
        print("  ja aplicado: o helper")
    else:
        if fonte.count(HELPER_VELHO) != 1:
            raise SystemExit(f"ancora do helper {fonte.count(HELPER_VELHO)}x")
        fonte = fonte.replace(HELPER_VELHO, HELPER_NOVO, 1)
        print("  helper: aceita `cur` e protege com SAVEPOINT")

    alvos = sorted(dentro_de_cursor(fonte), reverse=True)
    linhas = fonte.splitlines(keepends=True)
    mexidas = 0
    for n in alvos:
        # A chamada pode ocupar mais de uma linha: fecha-se no primeiro ')'
        # em nivel zero a partir do inicio da chamada.
        inicio = n - 1
        nivel, fim = 0, None
        for i in range(inicio, min(inicio + 8, len(linhas))):
            for ch in linhas[i]:
                if ch == "(":
                    nivel += 1
                elif ch == ")":
                    nivel -= 1
                    if nivel == 0:
                        fim = i
                        break
            if fim is not None:
                break
        if fim is None:
            raise SystemExit(f"nao achei o fim da chamada na linha {n}")
        if "cur=cur" in "".join(linhas[inicio:fim + 1]):
            continue
        # Insere `, cur=cur` antes do ')' que fecha.
        pos = linhas[fim].rfind(")")
        linhas[fim] = linhas[fim][:pos] + ", cur=cur" + linhas[fim][pos:]
        mexidas += 1
        print(f"  cur=cur na chamada da linha {n} (fecha em {fim + 1})")

    fonte = "".join(linhas)
    compile(fonte, str(ALVO), "exec")
    if not SO_CONFERIR:
        ALVO.write_text(fonte, encoding="utf-8")
    print(f"{mexidas} chamada(s) dentro de transação; "
          f"{'nada gravado' if SO_CONFERIR else 'GRAVADO'}")


aplicar()
