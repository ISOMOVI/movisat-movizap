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
from datetime import time as _hora

import psycopg

from . import banco
from . import telas as registro_telas

log = logging.getLogger("movizap.operacao")

ESTADOS = ("disponivel", "ausente", "nao_perturbe")
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

def listar_times(incluir_inativos: bool = False) -> list[dict]:
    """Os times com quem está dentro de cada um.

    🚨 `qtd_membros` vem junto de propósito: três dos sete times do Chatwoot
    (Contratual, Pós Venda e agendamento) estão SEM NENHUM MEMBRO, e uma
    conversa transferida para eles hoje não chega em ninguém. A tela precisa
    conseguir mostrar isso em vermelho sem fazer outra consulta.
    """
    return banco.varios(
        """
        SELECT t.id, t.nome, t.descricao, t.ativo, t.criado_em,
               t.time_transbordo_id,
               tr.nome AS transbordo_nome,
               COALESCE(m.qtd, 0) AS qtd_membros,
               COALESCE(m.membros, '[]'::json) AS membros
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
                 WHERE a.ativo
                 GROUP BY at.time_id
          ) m ON m.time_id = t.id
         WHERE (%s OR t.ativo)
         ORDER BY t.nome
        """,
        (incluir_inativos,),
    )


def time(time_id: int) -> dict | None:
    achados = [t for t in listar_times(incluir_inativos=True) if t["id"] == time_id]
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


def listar_atendentes(incluir_inativos: bool = False) -> list[dict]:
    linhas = banco.varios(
        """SELECT id, login, nome, email, ativo, owner, perfil, estado, fuso,
                  max_conversas, origem, criado_em,
                  (senha_hash IS NOT NULL) AS tem_senha
             FROM atendente
            WHERE (%s OR ativo)
            ORDER BY nome""",
        (incluir_inativos,),
    )
    for linha in linhas:
        linha["times"] = _times_do(linha["id"])
        linha["jornada"] = _jornada_do(linha["id"])
    return linhas


def atendente(atendente_id: int) -> dict | None:
    linha = banco.um(
        """SELECT id, login, nome, email, ativo, owner, perfil, estado, fuso,
                  max_conversas, origem, criado_em,
                  (senha_hash IS NOT NULL) AS tem_senha
             FROM atendente WHERE id = %s""",
        (atendente_id,),
    )
    if not linha:
        return None
    linha["times"] = _times_do(atendente_id)
    linha["jornada"] = _jornada_do(atendente_id)
    return linha


def _validar_campos(nome: str, login: str, email: str | None, perfil: str,
                    estado: str, max_conversas: int | None) -> tuple:
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
    if max_conversas is not None and max_conversas < 1:
        raise DadoInvalido("O teto de conversas, se preenchido, é pelo menos 1.")
    return nome, login, email


def criar_atendente(nome: str, login: str, email: str | None = None,
                    perfil: str = "atendimento", estado: str = "disponivel",
                    max_conversas: int | None = None,
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
    nome, login, email = _validar_campos(nome, login, email, perfil, estado,
                                         max_conversas)
    if perfil == "owner":
        raise DadoInvalido(
            "Não se cria owner. O owner é único e a conta passa de mão "
            "trocando o e-mail da linha existente.")
    try:
        linha = banco.um(
            """INSERT INTO atendente (login, nome, email, perfil, estado,
                                      max_conversas, fuso, origem)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING id""",
            (login, nome, email, perfil, estado, max_conversas, fuso, origem),
        )
    except psycopg.errors.UniqueViolation as e:
        raise DadoInvalido(f"Já existe um atendente com o login {login!r}.") from e
    log.info("atendente criado id=%s login=%s perfil=%s", linha["id"], login, perfil)
    return atendente(linha["id"])


def atualizar_atendente(atendente_id: int, nome: str, login: str,
                        email: str | None, perfil: str, estado: str,
                        max_conversas: int | None, ativo: bool,
                        fuso: str = "America/Sao_Paulo",
                        quem_edita: str | None = None) -> dict:
    atual = banco.um("SELECT login, owner, email FROM atendente WHERE id = %s",
                     (atendente_id,))
    if not atual:
        raise DadoInvalido("Atendente não encontrado.")
    nome, login, email = _validar_campos(nome, login, email, perfil, estado,
                                         max_conversas)

    # 🚨 O PERFIL `owner` NÃO ENTRA NEM SAI POR AQUI. Editar a linha do owner
    # (nome, e-mail, fuso) continua livre -- o que se barra é PROMOVER alguém
    # e REBAIXAR o dono.
    #
    # Depois da migração 025 os dois lados custam caro: `owner` virou coluna
    # DERIVADA de `perfil`, então promover concede owner pleno na hora, e
    # rebaixar tira o acesso do único administrador do sistema -- que é o
    # mesmo estrago de desativar a própria conta, e por um campo que parece
    # inofensivo num formulário.
    if perfil == "owner" and not atual["owner"]:
        raise DadoInvalido(
            "Não se promove ninguém a owner. O owner é único e a conta passa "
            "de mão trocando o e-mail da linha dele.")
    if atual["owner"] and perfil != "owner":
        raise EmUso(
            "O owner não pode deixar de ser owner: ele é o único administrador "
            "do sistema e ninguém poderia devolvê-lo ao lugar.")

    # ⚠️ Desativar a própria conta é o tipo de clique que só se percebe depois
    # de sair. Barrar aqui é barato; recuperar acesso não é.
    if not ativo and quem_edita and quem_edita.casefold() == atual["login"].casefold():
        raise EmUso("Você não pode desativar a sua própria conta.")

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
                      estado = %s, max_conversas = %s, ativo = %s, fuso = %s,
                      atualizado_em = now()
                WHERE id = %s""",
            (nome, login, email, perfil, estado, max_conversas, ativo, fuso,
             atendente_id),
        )
    except psycopg.errors.UniqueViolation as e:
        raise DadoInvalido(f"Já existe um atendente com o login {login!r}.") from e
    return atendente(atendente_id)


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


def definir_times(atendente_id: int, ids: list[int]) -> dict:
    if not banco.um("SELECT id FROM atendente WHERE id = %s", (atendente_id,)):
        raise DadoInvalido("Atendente não encontrado.")
    ids = sorted(set(int(i) for i in ids or []))
    if ids:
        achados = banco.varios("SELECT id FROM time WHERE id = ANY(%s)", (ids,))
        if len(achados) != len(ids):
            raise DadoInvalido("Algum time enviado não existe.")
    # Uma transação só: trocar o conjunto inteiro. Meio caminho aqui deixaria
    # o atendente fora de todos os times.
    with banco.cursor() as cur:
        cur.execute("DELETE FROM atendente_time WHERE atendente_id = %s", (atendente_id,))
        for time_id in ids:
            cur.execute(
                "INSERT INTO atendente_time (atendente_id, time_id) VALUES (%s, %s)",
                (atendente_id, time_id))
    return atendente(atendente_id)


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


def em_jornada(atendente_id: int, quando) -> bool:
    """Este atendente está dentro do horário dele neste instante?

    ⚠️ Serve para AVISAR, nunca para bloquear -- ver o cabeçalho do módulo.
    Quem não tem jornada cadastrada conta como fora: jornada vazia é
    "ninguém disse quando", e supor 24h é o jeito de criar a transferência
    fantasma que a regra existe para evitar.
    """
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
