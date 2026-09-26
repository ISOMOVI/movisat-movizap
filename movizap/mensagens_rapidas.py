"""Mensagens rápidas — Plano 3 (25/09).

🔵 Decisões dele:
  · três tipos, cada um uma aba em Configurações (CFG_12.1): **Padrões** (owner
    e admin criam), **Minhas notas** (cada um as suas), **Formulários**
    (*"serão links"*; owner e admin criam);
  · *"apelido curto como 'Mensagem de encerramento'"* -- é o que aparece na
    lista da conversa;
  · só o botão redondo no compositor; o texto vai para o campo de escrever e
    ainda pode ser editado;
  · três variáveis: `{cliente}` (a empresa), `{contato}` (a pessoa) e
    `{saudacao}` (Bom dia / Boa tarde / Boa noite) -- preenchidas NA TELA,
    com os dados da conversa aberta (`frontend/src/util/variaveis.js`);
  · no Chat interno aparecem **Minhas notas e Formulários**.

⚠️ QUEM PODE O QUÊ mora aqui e não só na tela: a rota é pública para quem
atende (todos usam), e a nota de um nunca aparece para outro.
"""
import logging

import psycopg

from . import banco
from .operacao import DadoInvalido

log = logging.getLogger("movizap.mensagens_rapidas")

TIPOS = ("padrao", "nota", "formulario")
# 🔵 No Chat interno, *"Minhas notas e Formulários"*.
TIPOS_POR_LUGAR = {"cliente": TIPOS, "interno": ("nota", "formulario")}
TETO_APELIDO = 60
TETO_CONTEUDO = 4000


def pode_gerir_equipe(usuario: dict) -> bool:
    """Padrões e Formulários: owner e admin (a permissão `equipe`)."""
    return bool(usuario.get("owner")) or "equipe" in (usuario.get("permissoes") or [])


def _validar(tipo: str, apelido: str, conteudo: str) -> tuple[str, str]:
    if tipo not in TIPOS:
        raise DadoInvalido("Tipo de mensagem rápida desconhecido.")
    apelido = (apelido or "").strip()
    conteudo = (conteudo or "").strip()
    if not apelido:
        raise DadoInvalido("Dê um apelido curto: é ele que aparece na conversa.")
    if len(apelido) > TETO_APELIDO:
        raise DadoInvalido(f"O apelido passa de {TETO_APELIDO} caracteres.")
    if not conteudo:
        raise DadoInvalido("Escreva o texto." if tipo != "formulario" else "Cole o link.")
    if len(conteudo) > TETO_CONTEUDO:
        raise DadoInvalido(f"O texto passa de {TETO_CONTEUDO} caracteres.")
    if tipo == "formulario":
        # 🔵 *"serão links"*. Um só, começando por http(s): o que se cola aqui
        # vai direto para o cliente clicar.
        if not conteudo.lower().startswith(("http://", "https://")) or " " in conteudo:
            raise DadoInvalido("O formulário é um link: comece com https://.")
    return apelido, conteudo


def _checar_quem(tipo: str, usuario: dict, eu: int | None) -> None:
    if tipo == "nota":
        if not eu:
            raise DadoInvalido("Sua conta não está vinculada a um atendente.")
        return
    if not pode_gerir_equipe(usuario):
        from fastapi import HTTPException  # tardio: o módulo não depende da web
        raise HTTPException(status_code=403,
                            detail="Você não tem permissão para esta alteração.")


def para_usar(eu: int | None, onde: str = "cliente") -> dict:
    """O que o botão da conversa oferece: só ativas, agrupadas por tipo."""
    tipos = TIPOS_POR_LUGAR.get(onde, TIPOS)
    linhas = banco.varios(
        """SELECT id, tipo, apelido, conteudo FROM mensagem_rapida
            WHERE ativo AND tipo = ANY(%s)
              AND (tipo <> 'nota' OR atendente_id = %s)
            ORDER BY ordem, lower(apelido)""", (list(tipos), eu or 0))
    grupos = {t: [] for t in tipos}
    for linha in linhas:
        grupos[linha["tipo"]].append(linha)
    return grupos


def para_gerir(eu: int | None) -> dict:
    """A CFG_12.1: tudo de Padrões e Formulários (ativas ou não) e as MINHAS
    notas. A tela decide o que é só leitura; a escrita é conferida aqui."""
    linhas = banco.varios(
        """SELECT id, tipo, apelido, conteudo, ativo, ordem, atualizada_em
             FROM mensagem_rapida
            WHERE tipo <> 'nota' OR atendente_id = %s
            ORDER BY ordem, lower(apelido)""", (eu or 0,))
    grupos = {t: [] for t in TIPOS}
    for linha in linhas:
        grupos[linha["tipo"]].append(linha)
    return grupos


def _gravar(sql: str, params: tuple, apelido: str) -> dict:
    try:
        return banco.um(sql, params)
    except psycopg.errors.UniqueViolation as e:
        raise DadoInvalido(f"Já existe uma com o apelido {apelido!r}.") from e


def criar(usuario: dict, eu: int | None, tipo: str, apelido: str, conteudo: str,
          ativo: bool = True) -> dict:
    apelido, conteudo = _validar(tipo, apelido, conteudo)
    _checar_quem(tipo, usuario, eu)
    linha = _gravar(
        """INSERT INTO mensagem_rapida (tipo, apelido, conteudo, atendente_id, ativo)
           VALUES (%s, %s, %s, %s, %s)
           RETURNING id, tipo, apelido, conteudo, ativo, ordem""",
        (tipo, apelido, conteudo, eu if tipo == "nota" else None, bool(ativo)), apelido)
    log.info("mensagem rápida %s criada (%s)", linha["id"], tipo)
    return linha


def _minha_ou_da_equipe(mensagem_id: int, usuario: dict, eu: int | None) -> dict:
    atual = banco.um("SELECT id, tipo, atendente_id FROM mensagem_rapida WHERE id = %s",
                     (mensagem_id,))
    # A nota de outra pessoa é tratada como inexistente: nem confirma que existe.
    if not atual or (atual["tipo"] == "nota" and atual["atendente_id"] != eu):
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Mensagem não encontrada.")
    _checar_quem(atual["tipo"], usuario, eu)
    return atual


def atualizar(mensagem_id: int, usuario: dict, eu: int | None, apelido: str,
              conteudo: str, ativo: bool = True) -> dict:
    atual = _minha_ou_da_equipe(mensagem_id, usuario, eu)
    apelido, conteudo = _validar(atual["tipo"], apelido, conteudo)
    return _gravar(
        """UPDATE mensagem_rapida
              SET apelido = %s, conteudo = %s, ativo = %s, atualizada_em = now()
            WHERE id = %s
        RETURNING id, tipo, apelido, conteudo, ativo, ordem""",
        (apelido, conteudo, bool(ativo), mensagem_id), apelido)


def apagar(mensagem_id: int, usuario: dict, eu: int | None) -> dict:
    """Apagar é seguro: o que já foi enviado é texto na conversa."""
    _minha_ou_da_equipe(mensagem_id, usuario, eu)
    banco.executar("DELETE FROM mensagem_rapida WHERE id = %s", (mensagem_id,))
    return {"ok": True}
