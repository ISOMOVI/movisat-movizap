"""Operação: times, atendentes, jornada e classificações.

É o que alimenta a `CAD_2.1` (Atendentes), a `CAD_2.2` (Times) e a `CFG_4.1`
(Classificações) — o passo 3 do plano.

🚨 NADA AQUI APAGA LINHA. `conversa` e `transferencia` apontam para time,
atendente e classificação. Apagar um time faria a conversa antiga perder o
destino, e o histórico passaria a mentir sobre o que aconteceu. Tudo que a
tela chama de "excluir" é `ativo = false`: some do menu, continua explicando
o passado.

⚠️ A jornada NÃO bloqueia transferência, por decisão registrada no
`06_Conteudo_das_Telas.md`: bloquear faz o atendente fechar a conversa para se
livrar dela, e aí o cliente some do radar. `em_jornada()` existe para a tela
AVISAR, não para impedir.
"""
import logging
from datetime import datetime, timezone
from datetime import time as _hora
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import psycopg

from . import banco
from . import telas as registro_telas

log = logging.getLogger("movizap.operacao")

# 🚨 `offline` ENTROU EM 24/09. A Minha conta (17/09) oferece os quatro, e o
# CHECK da 044 aceita os quatro -- mas esta lista tinha três: quem se marcasse
# offline não podia mais ser editado na CAD_2.1 ("Estado inválido" ao salvar).
ESTADOS = ("disponivel", "ausente", "nao_perturbe", "offline")
PERFIS = tuple(registro_telas.PERFIS.keys())

# 0 = domingo, igual ao `extract(dow)` do Postgres. Fixado aqui porque a tela
# e o banco precisam concordar, e "segunda é 0 ou 1?" é erro que só aparece
# quando alguém não recebe conversa no dia errado.
DIAS = ("domingo", "segunda", "terça", "quarta", "quinta", "sexta", "sábado")


class DadoInvalido(ValueError):
    """O que veio da tela não serve. Vira 400, com a frase que o usuário lê."""


class EmUso(Exception):
    """A operação é válida, mas o estado atual não permite. Vira 409."""


def _texto(valor, campo: str, obrigatorio: bool = True, maximo: int = 200) -> str | None:
    limpo = (valor or "").strip()
    if not limpo:
        if obrigatorio:
            raise DadoInvalido(f"{campo} é obrigatório.")
        return None
    if len(limpo) > maximo:
        raise DadoInvalido(f"{campo} passa de {maximo} caracteres.")
    return limpo


# ============================================================================
# TIMES — CAD_2.2
# ============================================================================

def listar_times(incluir_inativos: bool = False, ocultar_owner: bool = False) -> list[dict]:
    """Os times com quem está dentro de cada um.

    🔵 25/09, `ocultar_owner`: *"owner não deve aparecer para admin"*. Quem
    não é owner não o vê entre os membros. Contar não muda: o owner não é
    `transferivel`, e `qtd_membros` já não o contava.

    🚨 `qtd_membros` vem junto de propósito: time sem membro aceita a
    transferência e a conversa não chega em ninguém. A tela mostra isso em
    vermelho sem fazer outra consulta.

    ⚠️ CORREÇÃO DE 25/08: este texto dizia que três times estavam vazios
    (Contratual, Pós Venda e agendamento). Isso é do CHATWOOT, não daqui --
    medido no banco do painel, os 7 times têm de 2 a 4 membros cada, nenhum
    vazio. O alerta continua existindo porque a situação pode voltar; o que
    saiu foi a afirmação errada sobre o presente.
    """
    return banco.varios(
        """
        SELECT t.id, t.nome, t.descricao, t.ativo, t.criado_em,
               t.time_transbordo_id,
               tr.nome AS transbordo_nome,
               COALESCE(m.qtd, 0) AS qtd_membros,
               COALESCE(m.membros, '[]'::json) AS membros,
               -- 🚨 QUANTAS ESPERAM NESTE TIME AGORA. É o número que diz se
               -- ele está dando conta -- e sem ele o cartão mostra quem está
               -- dentro sem dizer o que há para fazer.
               (SELECT count(*) FROM conversa c
                 WHERE c.time_id = t.id AND c.estado <> 'resolvida') AS na_fila,
               -- ⚠️ Quem ENXERGA a fila deste time é outro eixo que estar
               -- nele (`atendente_time_permissao` × `atendente_time`), e não
               -- aparecia em tela nenhuma. Lista vazia aqui quer dizer que
               -- TODO MUNDO vê -- padrão permissivo da migração 001.
               COALESCE((SELECT json_agg(a2.nome ORDER BY a2.nome)
                           FROM atendente_time_permissao p
                           JOIN atendente a2 ON a2.id = p.atendente_id
                          WHERE p.time_id = t.id AND a2.ativo),
                        '[]'::json) AS quem_ve
          FROM time t
          LEFT JOIN time tr ON tr.id = t.time_transbordo_id
          LEFT JOIN (
                SELECT at.time_id,
                       -- 🚨 CONTA SÓ QUEM PODE RECEBER. `qtd_membros` responde
                       -- "transferir para este time chega em alguém?", e o
                       -- owner não recebe transferência (decisão de 10/08).
                       -- Contá-lo faria um time onde só ele está parecer
                       -- atendido -- e a conversa sumiria.
                       COUNT(*) FILTER (WHERE a.transferivel) AS qtd,
                       json_agg(json_build_object('id', a.id, 'nome', a.nome,
                                                  'ativo', a.ativo,
                                                  'transferivel', a.transferivel)
                                ORDER BY a.nome) AS membros
                  FROM atendente_time at
                  JOIN atendente a ON a.id = at.atendente_id
                 WHERE a.ativo AND NOT (%s AND a.owner)
                 GROUP BY at.time_id
          ) m ON m.time_id = t.id
         WHERE (%s OR t.ativo)
         ORDER BY t.nome
        """,
        (ocultar_owner, incluir_inativos),
    )


def time(time_id: int, ocultar_owner: bool = False) -> dict | None:
    achados = [t for t in listar_times(incluir_inativos=True, ocultar_owner=ocultar_owner)
               if t["id"] == time_id]
    return achados[0] if achados else None


def _validar_transbordo(time_id: int | None, transbordo_id: int | None) -> None:
    """Impede que o transbordo aponte para si mesmo ou feche um ciclo.

    🚨 A→B→A não dá erro nenhum ao gravar, e só se manifesta quando uma
    conversa real entra no laço e nunca chega a um atendente. Custo de checar
    aqui: uma consulta. Custo de não checar: conversa perdida em produção.
    """
    if transbordo_id is None:
        return
    if time_id is not None and transbordo_id == time_id:
        raise DadoInvalido("Um time não pode transbordar para ele mesmo.")

    if not banco.um("SELECT id FROM time WHERE id = %s", (transbordo_id,)):
        raise DadoInvalido("O time de transbordo não existe.")

    visitados = {time_id} if time_id is not None else set()
    atual = transbordo_id
    while atual is not None:
        if atual in visitados:
            raise DadoInvalido(
                "Esse transbordo fecha um ciclo entre times -- a conversa "
                "ficaria rodando sem chegar em ninguém."
            )
        visitados.add(atual)
        linha = banco.um("SELECT time_transbordo_id FROM time WHERE id = %s", (atual,))
        atual = linha["time_transbordo_id"] if linha else None


def criar_time(nome: str, descricao: str | None = None,
               time_transbordo_id: int | None = None) -> dict:
    nome = _texto(nome, "O nome do time")
    descricao = _texto(descricao, "A descrição", obrigatorio=False, maximo=1000)
    _validar_transbordo(None, time_transbordo_id)
    try:
        linha = banco.um(
            """INSERT INTO time (nome, descricao, time_transbordo_id)
               VALUES (%s, %s, %s) RETURNING id""",
            (nome, descricao, time_transbordo_id),
        )
    except psycopg.errors.UniqueViolation:
        raise DadoInvalido(f"Já existe um time chamado {nome!r}.")
    log.info("time criado id=%s nome=%s", linha["id"], nome)
    return time(linha["id"])


def atualizar_time(time_id: int, nome: str, descricao: str | None,
                   time_transbordo_id: int | None, ativo: bool = True) -> dict:
    if not banco.um("SELECT id FROM time WHERE id = %s", (time_id,)):
        raise DadoInvalido("Time não encontrado.")
    nome = _texto(nome, "O nome do time")
    descricao = _texto(descricao, "A descrição", obrigatorio=False, maximo=1000)
    _validar_transbordo(time_id, time_transbordo_id)

    if not ativo:
        apontam = banco.varios(
            "SELECT nome FROM time WHERE time_transbordo_id = %s AND ativo AND id <> %s",
            (time_id, time_id))
        if apontam:
            raise EmUso(
                "Não dá para desativar: "
                + ", ".join(t["nome"] for t in apontam)
                + " transborda para este time. Troque o transbordo primeiro."
            )

    try:
        banco.executar(
            """UPDATE time SET nome = %s, descricao = %s,
                               time_transbordo_id = %s, ativo = %s
                WHERE id = %s""",
            (nome, descricao, time_transbordo_id, ativo, time_id),
        )
    except psycopg.errors.UniqueViolation:
        raise DadoInvalido(f"Já existe um time chamado {nome!r}.")
    return time(time_id)


# ============================================================================
# ATENDENTES — CAD_2.1
# ============================================================================

def _jornada_do(atendente_id: int) -> list[dict]:
    return banco.varios(
        """SELECT id, dia_semana, inicio::text AS inicio, fim::text AS fim
             FROM atendente_jornada
            WHERE atendente_id = %s
            ORDER BY dia_semana, inicio""",
        (atendente_id,),
    )


def _times_do(atendente_id: int) -> list[dict]:
    return banco.varios(
        """SELECT t.id, t.nome
             FROM atendente_time at JOIN time t ON t.id = at.time_id
            WHERE at.atendente_id = %s ORDER BY t.nome""",
        (atendente_id,),
    )


# As colunas que a CAD_2.1 lê, nas duas consultas (lista e uma pessoa).
# 🔵 25/09: `max_conversas` saiu (*"não deve haver máximo de conversas"*), e
# entraram as datas do afastamento marcado (`afasta_*`) e do em curso.
_COLUNAS_ATENDENTE = """
    id, login, nome, email, ativo, owner, perfil, estado, fuso,
    origem, criado_em,
    (senha_hash IS NOT NULL) AS tem_senha,
    -- A tela desenha a foto (Minha conta, 17/09) no avatar;
    -- sem isto ela pediria a foto de quem não tem.
    (foto IS NOT NULL) AS tem_foto,
    -- 🔵 24/09: quem pode receber (transferência, afastamento) e
    -- se o estado veio da regra de tempo.
    transferivel, estado_automatico, sempre_online,
    afastamento_motivo, afastado_de, afastado_ate,
    afasta_em, afasta_ate, afasta_motivo, afasta_substituto_id
"""


def listar_atendentes(incluir_inativos: bool = False, ver_owner: bool = True) -> list[dict]:
    """🔵 25/09, `ver_owner`: *"owner não deve aparecer para admin, então
    admin nunca inativará owner"*. Quem não é owner recebe a lista sem ele."""
    linhas = banco.varios(
        f"""SELECT {_COLUNAS_ATENDENTE}
             FROM atendente
            WHERE (%s OR ativo) AND (%s OR NOT owner)
            ORDER BY nome""",
        (incluir_inativos, ver_owner),
    )
    # 🚨 O NÚMERO QUE FAZ A TELA SER DE RH. Sem ele, "Atendentes" é uma lista
    # de logins: quem está no horário agora, quantas conversas carrega e
    # quantas concluiu na semana são as perguntas que se faz sobre uma equipe.
    situacao = {
        linha["atendente_id"]: linha
        for linha in banco.varios(
            """SELECT a.id AS atendente_id,
                      count(c.id) FILTER (
                          WHERE c.estado <> 'resolvida')            AS em_aberto,
                      count(d.id) FILTER (
                          WHERE d.resolvida_em >= now() - interval '7 days')
                                                                    AS concluidas_semana
                 FROM atendente a
                 LEFT JOIN conversa c ON c.atendente_id = a.id
                 LEFT JOIN conversa d ON d.resolvida_por = a.id
                GROUP BY a.id""")
    }

    agora = datetime.now(timezone.utc)
    for linha in linhas:
        linha["times"] = _times_do(linha["id"])
        linha["jornada"] = _jornada_do(linha["id"])
        atual = situacao.get(linha["id"], {})
        linha["em_aberto"] = atual.get("em_aberto", 0)
        linha["concluidas_semana"] = atual.get("concluidas_semana", 0)
        # ⚠️ `em_jornada` já existe e respeita o fuso da pessoa. Sem jornada
        # cadastrada ele devolve False -- e a tela precisa dizer POR QUÊ, senão
        # "fora do horário" parece defeito.
        linha["no_horario"] = em_jornada(linha["id"], agora)
        linha["tem_jornada"] = bool(linha["jornada"])
    return linhas


def atendente(atendente_id: int) -> dict | None:
    linha = banco.um(
        f"SELECT {_COLUNAS_ATENDENTE} FROM atendente WHERE id = %s",
        (atendente_id,),
    )
    if not linha:
        return None
    linha["times"] = _times_do(atendente_id)
    linha["jornada"] = _jornada_do(atendente_id)
    return linha


def _validar_campos(nome: str, login: str, email: str | None, perfil: str,
                    estado: str) -> tuple:
    nome = _texto(nome, "O nome")
    login = _texto(login, "O login", maximo=60)
    if " " in login:
        raise DadoInvalido("O login não pode ter espaço.")
    email = _texto(email, "O e-mail", obrigatorio=False)
    if email and "@" not in email:
        raise DadoInvalido("E-mail sem @.")
    if perfil not in PERFIS:
        raise DadoInvalido(f"Perfil inválido. Vale: {', '.join(PERFIS)}.")
    if estado not in ESTADOS:
        raise DadoInvalido(f"Estado inválido. Vale: {', '.join(ESTADOS)}.")
    return nome, login, email


def criar_atendente(nome: str, login: str, email: str | None = None,
                    perfil: str = "atendimento", estado: str = "disponivel",
                    fuso: str = "America/Sao_Paulo",
                    origem: str | None = None) -> dict:
    """Cria a conta SEM SENHA, de propósito.

    🚨 Conta nasce sem poder entrar. `auth.validar_login` recusa
    `senha_hash IS NULL` antes de chegar no bcrypt, então uma conta criada e
    esquecida não é porta aberta -- é porta que não existe ainda. A senha se
    define depois, na própria tela.

    🚨 E NÃO NASCE OWNER. Decisão do usuário em 12/08: o owner é único, e a
    conta passa de mão trocando o e-mail DELA, não criando outra.
    """
    nome, login, email = _validar_campos(nome, login, email, perfil, estado)
    if perfil == "owner":
        raise DadoInvalido("Este perfil não pode ser criado.")
    try:
        linha = banco.um(
            """INSERT INTO atendente (login, nome, email, perfil, estado,
                                      fuso, origem)
               VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id""",
            (login, nome, email, perfil, estado, fuso, origem),
        )
    except psycopg.errors.UniqueViolation as e:
        # 🚨 E-MAIL É ÚNICO DESDE 24/09 (053): a entrada pelo Google casa pelo
        # e-mail, e dois cadastros com o mesmo deixavam a conta ambígua.
        if "email" in (getattr(e.diag, "constraint_name", "") or ""):
            raise DadoInvalido(f"Já existe um atendente com o e-mail {email!r}.") from e
        raise DadoInvalido(f"Já existe um atendente com o login {login!r}.") from e
    log.info("atendente criado id=%s login=%s perfil=%s", linha["id"], login, perfil)
    return atendente(linha["id"])


def atualizar_atendente(atendente_id: int, nome: str, login: str,
                        email: str | None, perfil: str, estado: str,
                        fuso: str = "America/Sao_Paulo") -> dict:
    """Os dados da pessoa. 🚨 `ativo` NÃO ENTRA AQUI desde 25/09: gravado por
    esta rota, ele pulava tudo o que inativar precisa fazer (conversas presas
    com dono que não entra -- o defeito de 07/08). É `definir_ativo`."""
    atual = banco.um("SELECT login, owner, email FROM atendente WHERE id = %s",
                     (atendente_id,))
    if not atual:
        raise DadoInvalido("Atendente não encontrado.")
    nome, login, email = _validar_campos(nome, login, email, perfil, estado)

    # 🚨 O PERFIL `owner` NÃO ENTRA NEM SAI POR AQUI. Editar a linha do owner
    # (nome, e-mail, fuso) continua livre -- o que se barra é PROMOVER alguém
    # e REBAIXAR o dono.
    #
    # Depois da migração 025 os dois lados custam caro: `owner` virou coluna
    # DERIVADA de `perfil`, então promover concede owner pleno na hora, e
    # rebaixar tira o acesso do único administrador do sistema -- que é o
    # mesmo estrago de desativar a própria conta, e por um campo que parece
    # inofensivo num formulário.
    #
    # ⚠️ 25/09: as duas recusas dizem o que acontece, não quem decide
    # (*"owner é invisível para operação do Movizap"*).
    if perfil == "owner" and not atual["owner"]:
        raise DadoInvalido("Este perfil não pode ser atribuído.")
    if atual["owner"] and perfil != "owner":
        raise EmUso("Este perfil não pode ser alterado.")

    # 🚨 TROCAR O E-MAIL É PASSAR A CONTA — e o `google_sub` tem de ir junto.
    # A entrada pelo Google casa por `google_sub OR email`, e o `sub` fica
    # gravado na primeira entrada. Trocar só o e-mail deixaria o dono anterior
    # entrando normalmente, porque o `sub` dele continua casando -- em
    # silêncio, sem erro e sem recusa no log. O novo dono só o expulsaria ao
    # entrar pela primeira vez, quando o UPDATE sobrescreve o `sub`; até lá,
    # os dois teriam acesso. Zerar aqui fecha essa janela.
    trocou_email = (email or "").casefold() != (atual["email"] or "").casefold()
    if trocou_email:
        banco.executar(
            "UPDATE atendente SET google_sub = NULL WHERE id = %s", (atendente_id,))
        log.info("atendente %s trocou de e-mail: google_sub zerado", atendente_id)

    try:
        banco.executar(
            """UPDATE atendente
                  SET nome = %s, login = %s, email = %s, perfil = %s,
                      estado = %s, fuso = %s,
                      atualizado_em = now()
                WHERE id = %s""",
            (nome, login, email, perfil, estado, fuso, atendente_id),
        )
    except psycopg.errors.UniqueViolation as e:
        # 🚨 E-MAIL É ÚNICO DESDE 24/09 (053): a entrada pelo Google casa pelo
        # e-mail, e dois cadastros com o mesmo deixavam a conta ambígua.
        if "email" in (getattr(e.diag, "constraint_name", "") or ""):
            raise DadoInvalido(f"Já existe um atendente com o e-mail {email!r}.") from e
        raise DadoInvalido(f"Já existe um atendente com o login {login!r}.") from e
    return atendente(atendente_id)


def definir_ativo(atendente_id: int, ativo: bool, quem_edita: str | None = None,
                  transferir_para: int | None = None) -> dict:
    """O interruptor Ativo/Inativo do perfil (25/09), no lugar do "desligar".

    🔵 *"vamos ligar isso a um status de inativo e ativo no perfil do
    atendente, um interruptor, inativo não loga a conta permanece lá. sem
    acesso, apenas admin e owner podem mexer ... sistema nunca pode ficar com
    menos de 1 owner ativo."*

    · INATIVO NÃO ENTRA: `auth.validar_login` e `auth.get_usuario` recusam
      `ativo = false` a cada chamada, então a sessão aberta cai na seguinte.
    · A CONTA FICA: senha, `google_sub`, e-mail e times continuam. O antigo
      desligar apagava os três primeiros e os times, e não tinha volta -- nem
      recadastrar dava, porque o e-mail é único (053). Reativar devolve tudo.
    · 🟡 AS CONVERSAS ABERTAS PASSAM PARA ALGUÉM, obrigatório, pelo mesmo
      caminho do afastamento. O defeito de 07/08 foi exatamente esse: inativo
      segurando conversa que ninguém vê.

    🚨 NÃO EXISTE APAGAR, E NÃO DEVE EXISTIR. `conversa`, `transferencia`,
    `mensagem` e `chat_mensagem` apontam para o atendente.
    """
    from . import presenca  # tardio: presenca importa este módulo

    atual = banco.um(
        "SELECT id, login, nome, ativo, owner FROM atendente WHERE id = %s",
        (atendente_id,))
    if not atual:
        raise DadoInvalido("Atendente não encontrado.")
    ativo = bool(ativo)
    if ativo == atual["ativo"]:
        return {"ok": True, "nome": atual["nome"], "ativo": ativo, "transferidas": 0}

    if ativo:
        # Volta sem estado de trabalho: offline até a pessoa entrar e escolher.
        banco.executar(
            """UPDATE atendente
                  SET ativo = true, estado = 'offline', estado_automatico = false,
                      atualizado_em = now()
                WHERE id = %s""", (atendente_id,))
        log.info("atendente %s reativado", atendente_id)
        return {"ok": True, "nome": atual["nome"], "ativo": True, "transferidas": 0}

    # ⚠️ Inativar a própria conta é o tipo de clique que só se percebe depois
    # de sair. Barrar aqui é barato; recuperar acesso não é.
    if quem_edita and quem_edita.casefold() == atual["login"].casefold():
        raise EmUso("Você não pode inativar a sua própria conta.")
    if atual["owner"]:
        outros = banco.um(
            "SELECT count(*) AS n FROM atendente WHERE owner AND ativo AND id <> %s",
            (atendente_id,))
        if not outros["n"]:
            raise EmUso("Esta conta não pode ser inativada: o sistema ficaria "
                        "sem administração.")

    abertas = presenca.conversas_abertas(atendente_id)
    if abertas:
        if not transferir_para:
            raise DadoInvalido(
                f"{atual['nome']} tem {len(abertas)} conversa(s) em aberto: "
                "escolha quem vai recebê-las.")
        if int(transferir_para) == int(atendente_id):
            raise DadoInvalido("Escolha outra pessoa para receber as conversas.")
        ok, motivo = presenca.pode_receber(int(transferir_para))
        if not ok:
            raise DadoInvalido(motivo)

    # 🚨 AS CONVERSAS PRIMEIRO. Se inativar falhasse depois de transferir, o
    # pior caso é a pessoa ativa sem conversa -- visível e corrigível. Na
    # ordem inversa, é conversa presa com dono que não entra.
    r = presenca.transferir_abertas(atendente_id, transferir_para,
                                    f"{atual['nome']} ficou inativo.",
                                    fila_se_falhar=False)
    if r["falhas"]:
        return {"ok": False, "nome": atual["nome"],
                "transferidas": r["abertas"] - len(r["falhas"]), "falhas": r["falhas"]}
    banco.executar(
        """UPDATE atendente
              SET ativo = false, estado = 'offline', estado_automatico = false,
                  atualizado_em = now()
            WHERE id = %s""", (atendente_id,))
    log.info("atendente %s inativado; %d conversa(s) transferida(s)",
             atendente_id, r["abertas"])
    return {"ok": True, "nome": atual["nome"], "ativo": False,
            "transferidas": r["abertas"]}


def definir_senha(atendente_id: int, senha: str) -> dict:
    from . import auth  # tardio: auth importa telas, e telas não importa isto

    if not senha or len(senha) < 10:
        raise DadoInvalido("A senha precisa de pelo menos 10 caracteres.")
    if not banco.um("SELECT id FROM atendente WHERE id = %s", (atendente_id,)):
        raise DadoInvalido("Atendente não encontrado.")
    banco.executar(
        "UPDATE atendente SET senha_hash = %s, atualizado_em = now() WHERE id = %s",
        (auth.hash_senha(senha), atendente_id),
    )
    log.info("senha definida para atendente id=%s", atendente_id)
    return atendente(atendente_id)


def definir_membros(time_id: int, ids: list[int], preservar_owner: bool = False) -> dict:
    """Troca quem está no time.

    🔵 Decisão dele em 24/09: *"vamos deixar a tela de times vincular os
    atendentes e no cadastro do atendentes pode ter os times dos quais são
    vinculados, mas só visualizar"*. Só a CAD_2.2 grava este vínculo.

    ⚠️ SÓ TROCA OS ATIVOS. A tela lista quem está ativo; apagar o vínculo de
    um inativo porque ele não apareceu na lista seria perder dado por não
    mostrá-lo -- e desde 25/09 reativar devolve os times.

    🚨 `preservar_owner` (25/09): para o admin o owner não aparece, então ele
    nunca vem na lista enviada. Sem preservar, salvar o time Geral o tiraria
    de lá em silêncio.
    """
    if not banco.um("SELECT id FROM time WHERE id = %s", (time_id,)):
        raise DadoInvalido("Time não encontrado.")
    ids = sorted(set(int(i) for i in ids or []))
    if ids:
        achados = banco.varios(
            "SELECT id, owner FROM atendente WHERE id = ANY(%s) AND ativo", (ids,))
        if len(achados) != len(ids):
            raise DadoInvalido("Algum atendente enviado não existe ou está inativo.")
        if preservar_owner:
            ids = [a["id"] for a in achados if not a["owner"]]
    # Uma transação só: meio caminho deixaria o time vazio, e time vazio
    # aceita transferência que não chega a ninguém.
    with banco.cursor() as cur:
        cur.execute(
            """DELETE FROM atendente_time at
                USING atendente a
                WHERE a.id = at.atendente_id AND a.ativo AND at.time_id = %s
                  AND NOT (%s AND a.owner)""",
            (time_id, preservar_owner))
        for atendente_id in ids:
            cur.execute(
                """INSERT INTO atendente_time (atendente_id, time_id) VALUES (%s, %s)
                   ON CONFLICT DO NOTHING""",
                (atendente_id, time_id))
    return time(time_id, ocultar_owner=preservar_owner)


def _hhmm(valor: str, campo: str) -> _hora:
    try:
        horas, minutos = str(valor).strip().split(":")[:2]
        return _hora(int(horas), int(minutos))
    except (ValueError, AttributeError):
        raise DadoInvalido(f"{campo} precisa estar no formato HH:MM.")


def definir_jornada(atendente_id: int, faixas: list[dict]) -> dict:
    """Troca a jornada inteira do atendente.

    🚨 A PAUSA É O INTERVALO ENTRE DUAS FAIXAS DO MESMO DIA. 08:00-12:00 e
    13:00-18:00 são duas linhas, e o almoço é o buraco entre elas. Não existe
    campo "pausa" -- e é por isso que a tabela aceita várias linhas por dia.

    ⚠️ Faixas sobrepostas são recusadas: com 08:00-12:00 e 10:00-14:00 no mesmo
    dia, "quantas horas ele trabalha?" passa a ter duas respostas certas.
    """
    if not banco.um("SELECT id FROM atendente WHERE id = %s", (atendente_id,)):
        raise DadoInvalido("Atendente não encontrado.")

    limpas = []
    for faixa in faixas or []:
        dia = int(faixa.get("dia_semana", -1))
        if not 0 <= dia <= 6:
            raise DadoInvalido("Dia da semana fora de 0 (domingo) a 6 (sábado).")
        inicio = _hhmm(faixa.get("inicio"), "O início")
        fim = _hhmm(faixa.get("fim"), "O fim")
        if fim <= inicio:
            raise DadoInvalido(
                f"Em {DIAS[dia]}, o fim ({fim:%H:%M}) não é depois do início "
                f"({inicio:%H:%M}). Turno que vira a meia-noite precisa de duas "
                f"faixas, uma em cada dia."
            )
        limpas.append((dia, inicio, fim))

    for dia in range(7):
        do_dia = sorted([f for f in limpas if f[0] == dia], key=lambda f: f[1])
        for anterior, seguinte in zip(do_dia, do_dia[1:]):
            if seguinte[1] < anterior[2]:
                raise DadoInvalido(
                    f"Em {DIAS[dia]} há faixas sobrepostas "
                    f"({anterior[1]:%H:%M}-{anterior[2]:%H:%M} e "
                    f"{seguinte[1]:%H:%M}-{seguinte[2]:%H:%M})."
                )

    with banco.cursor() as cur:
        cur.execute("DELETE FROM atendente_jornada WHERE atendente_id = %s",
                    (atendente_id,))
        for dia, inicio, fim in limpas:
            cur.execute(
                """INSERT INTO atendente_jornada (atendente_id, dia_semana, inicio, fim)
                   VALUES (%s, %s, %s, %s)""",
                (atendente_id, dia, inicio, fim))
    return atendente(atendente_id)


# ⚠️ A JORNADA NASCE DESLIGADA (decisão do usuário em 25/08): *"pode colocar
# interruptor na configuração do owner de usar jornada ou não, daí pode montar
# ela mas deixando desligado"*. Monta-se a escala com calma, e só quando o
# owner ligar ela passa a significar alguma coisa na fila.
#
# 🚨 Vive em `config`, não em coluna nova: é UM valor para o sistema inteiro,
# e a tabela existe exatamente para isso desde a migração 001.
CHAVE_JORNADA = "jornada_ativa"


def jornada_ativa() -> bool:
    linha = banco.um("SELECT valor FROM config WHERE chave = %s",
                     (CHAVE_JORNADA,))
    return bool(linha) and linha["valor"] == "true"


def definir_jornada_ativa(ligada: bool) -> dict:
    banco.executar(
        """INSERT INTO config (chave, valor, descricao, atualizado_em)
           VALUES (%s, %s, %s, now())
           ON CONFLICT (chave) DO UPDATE
              SET valor = EXCLUDED.valor, atualizado_em = now()""",
        (CHAVE_JORNADA, "true" if ligada else "false",
         "A fila considera a jornada dos atendentes. Nasce desligada."))
    log.info("jornada %s", "ligada" if ligada else "desligada")
    return {"ok": True, "jornada_ativa": ligada}


def em_jornada(atendente_id: int, quando) -> bool:
    """Este atendente está dentro do horário dele neste instante?

    ⚠️ Serve para AVISAR, nunca para bloquear -- ver o cabeçalho do módulo.
    Quem não tem jornada cadastrada conta como fora: jornada vazia é
    "ninguém disse quando", e supor 24h é o jeito de criar a transferência
    fantasma que a regra existe para evitar.
    """
    # 🚨 O FUSO NÃO ERA APLICADO ATÉ 24/09. Quem chama passa `now(utc)`, e a
    # jornada é gravada na hora LOCAL da pessoa: comparar direto deixava o
    # "fora do horário" 3 h adiantado (08:00-12:00 virava fora às 09:00 de
    # Brasília). O comentário da chamada dizia que respeitava o fuso; não
    # respeitava. Ninguém tinha jornada ainda, então nada foi afetado.
    pessoa = banco.um("SELECT fuso FROM atendente WHERE id = %s", (atendente_id,))
    try:
        fuso = ZoneInfo((pessoa or {}).get("fuso") or "America/Sao_Paulo")
    except (ZoneInfoNotFoundError, ValueError):
        fuso = ZoneInfo("America/Sao_Paulo")
    if quando.tzinfo is not None:
        quando = quando.astimezone(fuso)
    dia = (quando.weekday() + 1) % 7  # weekday(): 0=segunda; aqui 0=domingo
    linha = banco.um(
        """SELECT 1 AS dentro FROM atendente_jornada
            WHERE atendente_id = %s AND dia_semana = %s
              AND inicio <= %s AND fim > %s LIMIT 1""",
        (atendente_id, dia, quando.time(), quando.time()),
    )
    return bool(linha)


# ============================================================================
# CLASSIFICAÇÕES — CFG_4.1
# ============================================================================

def listar_classificacoes(incluir_inativas: bool = False) -> list[dict]:
    return banco.varios(
        """SELECT id, nome, exige_comentario, ativo, ordem
             FROM classificacao WHERE (%s OR ativo)
            ORDER BY ordem, nome""",
        (incluir_inativas,),
    )


def criar_classificacao(nome: str, exige_comentario: bool = False,
                        ordem: int | None = None) -> dict:
    nome = _texto(nome, "O nome da classificação", maximo=80)
    if ordem is None:
        maior = banco.um("SELECT COALESCE(MAX(ordem), 0) AS m FROM classificacao "
                         "WHERE ordem < 99")
        ordem = int(maior["m"]) + 1
    try:
        linha = banco.um(
            """INSERT INTO classificacao (nome, exige_comentario, ordem)
               VALUES (%s, %s, %s) RETURNING id""",
            (nome, bool(exige_comentario), int(ordem)),
        )
    except psycopg.errors.UniqueViolation as e:
        raise DadoInvalido(f"Já existe a classificação {nome!r}.") from e
    return banco.um("SELECT id, nome, exige_comentario, ativo, ordem "
                    "FROM classificacao WHERE id = %s", (linha["id"],))


def atualizar_classificacao(classificacao_id: int, nome: str,
                            exige_comentario: bool, ativo: bool,
                            ordem: int) -> dict:
    if not banco.um("SELECT id FROM classificacao WHERE id = %s", (classificacao_id,)):
        raise DadoInvalido("Classificação não encontrada.")
    nome = _texto(nome, "O nome da classificação", maximo=80)

    # ⚠️ Havia aqui uma regra impedindo desativar a ÚLTIMA classificação: sem
    # nenhuma, ninguém encerrava conversa. Ela saiu em 11/08, junto com a
    # obrigatoriedade de classificar -- guardar o sistema contra um problema
    # que não existe mais só impede o usuário de limpar a própria base.
    try:
        banco.executar(
            """UPDATE classificacao SET nome = %s, exige_comentario = %s,
                                        ativo = %s, ordem = %s
                WHERE id = %s""",
            (nome, bool(exige_comentario), bool(ativo), int(ordem), classificacao_id),
        )
    except psycopg.errors.UniqueViolation as e:
        raise DadoInvalido(f"Já existe a classificação {nome!r}.") from e
    return banco.um("SELECT id, nome, exige_comentario, ativo, ordem "
                    "FROM classificacao WHERE id = %s", (classificacao_id,))


# ============================================================================
# O RESUMO QUE A TELA ABRE MOSTRANDO
# ============================================================================

def alertas() -> list[dict]:
    """O que está montado de um jeito que só dá problema depois.

    Existe porque as três coisas abaixo são silenciosas: nada falha, nada
    aparece no log, e a conta só chega quando um cliente real está do outro
    lado esperando resposta.
    """
    achados = []

    sem_membro = banco.varios(
        """SELECT t.nome FROM time t
            WHERE t.ativo AND NOT EXISTS (
                  SELECT 1 FROM atendente_time at JOIN atendente a ON a.id = at.atendente_id
                   WHERE at.time_id = t.id AND a.ativo)
            ORDER BY t.nome""")
    if sem_membro:
        achados.append({
            "grave": True,
            "titulo": "Time sem nenhum atendente",
            "detalhe": ", ".join(t["nome"] for t in sem_membro),
            "porque": "conversa transferida para esses times não chega em ninguém.",
        })

    sem_descricao = banco.varios(
        "SELECT nome FROM time WHERE ativo AND (descricao IS NULL OR descricao = '') "
        "ORDER BY nome")
    if sem_descricao:
        achados.append({
            "grave": False,
            "titulo": "Time sem descrição",
            "detalhe": ", ".join(t["nome"] for t in sem_descricao),
            "porque": "a descrição é o que a IA lê para escolher o destino.",
        })

    sem_jornada = banco.varios(
        """SELECT a.nome FROM atendente a
            WHERE a.ativo AND NOT EXISTS (
                  SELECT 1 FROM atendente_jornada j WHERE j.atendente_id = a.id)
            ORDER BY a.nome""")
    if sem_jornada:
        achados.append({
            "grave": False,
            "titulo": "Atendente sem jornada",
            "detalhe": ", ".join(a["nome"] for a in sem_jornada),
            "porque": "sem horário, o painel conta como fora do expediente sempre.",
        })

    sem_senha = banco.varios(
        "SELECT nome FROM atendente WHERE ativo AND senha_hash IS NULL ORDER BY nome")
    if sem_senha:
        achados.append({
            "grave": False,
            "titulo": "Atendente sem senha definida",
            "detalhe": ", ".join(a["nome"] for a in sem_senha),
            "porque": "a conta existe mas ainda não entra no painel.",
        })

    return achados
