# -*- coding: utf-8 -*-
"""Acrescenta ao main.py o import e as duas rotas da aba CFG_15.1 (06/11).

Idempotente: se ja estiver aplicado, nao faz nada e avisa.
"""
import pathlib
import sys

ALVO = pathlib.Path("/home/claude/movizap_painel/movizap/main.py")
texto = ALVO.read_text(encoding="utf-8")

if "permissao_paineis" in texto:
    sys.exit("ja aplicado -- nada a fazer")

ANCORA_IMPORT = "from . import pipeline\n"
NOVO_IMPORT = "from . import pipeline\nfrom . import permissao_paineis\n"
if texto.count(ANCORA_IMPORT) != 1:
    sys.exit(f"ancora de import apareceu {texto.count(ANCORA_IMPORT)}x")
texto = texto.replace(ANCORA_IMPORT, NOVO_IMPORT)

ANCORA_ROTA = '''class OrdemDoAgendamento(BaseModel):'''
if texto.count(ANCORA_ROTA) != 1:
    sys.exit(f"ancora de rota apareceu {texto.count(ANCORA_ROTA)}x")

ROTAS = '''# ===========================================================================
# CFG_15.1 — A PERMISSÃO DOS PAINÉIS, por pessoa e por aba (06/11)
# ===========================================================================
# 🔵 Pedido dele: *"em configuração, crie uma aba de permissão para os paineis,
# ali vou definir quem pode ver o que e por aba tbm, como notará que o pós venda
# ja possui abas"*.
#
# 🚨 AS DUAS ROTAS SÃO `CFG_15.1`, QUE É `owner` — e `CFG_15.1` NÃO é do grupo
# "Painéis", então ela não pode ser concedida por ela mesma. Escrito de
# propósito: ninguém se concede a própria chave.
class PermissaoDePainel(BaseModel):
    """A linha inteira de UMA pessoa, e não um clique.

    🚨 `codigos` É O ESTADO COMPLETO dela, porque é isso que faz desmarcar
    revogar. ⚠️ Lista vazia é válida e significa *"nenhum painel"* — não é
    campo faltando.
    """
    atendente_id: int = Field(ge=1)
    codigos: list[str] = Field(default_factory=list, max_length=50)


@app.get("/api/config/permissao-paineis")
def ler_permissao_paineis(
        usuario: dict = Depends(auth.requer_tela("CFG_15.1"))):
    """A grade pronta: as telas de painel, as pessoas ativas e as marcas."""
    return permissao_paineis.grade()


@app.put("/api/config/permissao-paineis")
def gravar_permissao_paineis(
        entrada: PermissaoDePainel,
        usuario: dict = Depends(auth.requer_tela("CFG_15.1"))):
    """Grava a linha de uma pessoa e DEVOLVE A GRADE RELIDA.

    ⚠️ Devolve a grade inteira, e não um `ok`: a tela redesenha do que o banco
    respondeu, e não do que ela achava que tinha mandado. Tela que confia no
    próprio palpite é como `M12` começa.

    🚨 CÓDIGO FORA DOS PAINÉIS É 422, e não 500 nem 200 calado: a recusa é de
    REGRA (só o grupo "Painéis" é concedível), e quem a lê precisa saber o que
    foi recusado.
    """
    try:
        permissao_paineis.definir(entrada.atendente_id, entrada.codigos,
                                  concedida_por=usuario.get("id"))
    except permissao_paineis.TelaNaoConcedivel as e:
        raise HTTPException(status_code=422, detail=str(e))
    return permissao_paineis.grade()


class OrdemDoAgendamento(BaseModel):'''

texto = texto.replace(ANCORA_ROTA, ROTAS)
ALVO.write_text(texto, encoding="utf-8")
print("main.py: import + 2 rotas da CFG_15.1 aplicados")
