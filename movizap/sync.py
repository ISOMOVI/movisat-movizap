"""Sync do Harmonit — a base cadastral do MoviZap nascendo.

Este cadastro **é** o cadastro do ERP começando, não middleware descartável.
Por isso as regras abaixo não são zelo: são o que impede a base de virar cópia
suja de outra base.

AS TRÊS REGRAS (metodologia §3):

  1. 🚨 **O sync nunca apaga o que não é dele.** `origem = 'movizap'` é
     intocável. Toda escrita filtra por `origem = 'harmonit'` -- não basta
     confiar que o `harmonit_id` está nulo do outro lado.
  2. 🚨 **Upsert por `harmonit_id`.** Nunca "apaga tudo e reinsere".
  3. 🚨 **Não se apaga cadastro.** Cliente que sumiu do Harmonit vira
     `ativo = false`, e continua lá.

E MAIS UMA, DESTE PROJETO:

  🚨 **O sync não encosta em `tem_whatsapp` nem em `verificado_em`.** Esses
  dois campos são do Evolution, e o Harmonit não sabe nada sobre WhatsApp.
  Deixá-los de fora do UPDATE é o que impede uma sincronização de apagar uma
  verificação real. Enquanto o chip não parear, `tem_whatsapp` fica NULL --
  que significa "não verificado" e é DIFERENTE de false.

O QUE CADA CONTADOR SIGNIFICA (a separação ok / vazio / erro):

  lidos        clientes recebidos do Harmonit
  criados      clientes que ainda não existiam aqui
  atualizados  clientes que já existiam
  inativados   clientes que **passaram** de ativo para inativo NESTA execução
  vazios       campos de telefone que vieram em branco -- **não é erro**
  erros        campos de telefone preenchidos que a normalização recusou

  🚨 `inativados` é FLUXO, não estoque. A primeira versão contava todo cliente
  que chegasse com `ativo = false`, e por isso as duas primeiras execuções
  completas devolveram 106 -- exatamente o total de inativos no banco. Um
  número que não muda entre execuções não responde "o que mudou desde ontem?",
  que é a única pergunta que ele existe para responder. Achado auditando em
  06/08, corrigido no mesmo dia.

  Sem essa separação o painel acusa "76% de falha" num sistema saudável. Em
  400 clientes medidos, 712 dos 1.200 campos de telefone vêm vazios: é o
  normal da base, não avaria.

FORMATO REAL, MEDIDO EM 2026-08-06:

  contatoPrincipal = {contatoPrincipalId, email,
                      telefone{ddd,ddi,phone}, telefone2{...}, celular{...}}

  🚨 **Não existe `nome` no contatoPrincipal.** O nome do contato vem do
  cliente -- `contato.nome` é NOT NULL e não há outra fonte.

  🚨 **`contatoPrincipalId` vem nulo em ~8% dos casos.** Quando falta, a chave
  do contato passa a ser `cli:{id_do_cliente}`, que é estável entre execuções.
  Sem isso o mesmo contato seria recriado a cada sync.

  ⚠️ `tipoPessoa` é 0 (sem descrição), 1 (Jurídica), 2 (Física) ou 3
  (Estrangeiro). O 0 existe em ~8% e não é erro.
"""
import logging
import threading
from datetime import datetime, timezone

from . import banco, harmonit, identidade, telefone

log = logging.getLogger("movizap.sync")

CAMPOS_TELEFONE = ("telefone", "telefone2", "celular")

# 🚨 Uma execução por vez. O botão da CFG_3.1 e o cron das 12h podem coincidir,
# e dois syncs simultâneos disputam as mesmas linhas: um lê o cliente enquanto
# o outro o atualiza, e o `inativar sumidos` do primeiro roda com a lista pela
# metade do segundo. A trava é de PROCESSO -- serve porque só existe um
# processo do MoviZap e o cron chama o mesmo código por script separado, que
# grava sua própria execução e falha cedo se colidir.
_trava = threading.Lock()


class SyncJaEmAndamento(RuntimeError):
    pass


def em_andamento() -> bool:
    return _trava.locked()


class Contadores:
    def __init__(self):
        self.lidos = 0
        self.criados = 0
        self.atualizados = 0
        self.inativados = 0
        self.vazios = 0
        self.erros = 0
        # Não vai para sync_execucao: é diagnóstico da regra de identidade,
        # não do sync. Aparece no log e no retorno.
        self.nao_atribuidos = 0
        self.em_revisao = 0
        self.removidos = 0

    def como_dict(self) -> dict:
        return {
            "lidos": self.lidos, "criados": self.criados,
            "atualizados": self.atualizados, "inativados": self.inativados,
            "vazios": self.vazios, "erros": self.erros,
            "nao_atribuidos": self.nao_atribuidos, "em_revisao": self.em_revisao,
            "removidos": self.removidos,
        }


def _texto(valor) -> str | None:
    if valor is None:
        return None
    t = str(valor).strip()
    return t or None


def _gravar_cliente(cur, bruto: dict) -> tuple[int, bool]:
    """Upsert do cliente. Devolve (id_local, criado)."""
    harmonit_id = str(bruto.get("id"))
    contato_principal = bruto.get("contatoPrincipal")
    if not isinstance(contato_principal, dict):
        contato_principal = {}

    motivo = identidade.motivo_de_revisao(bruto)

    cur.execute(
        """
        INSERT INTO cliente
            (nome, nome_fantasia, documento, tipo_pessoa, email,
             origem, harmonit_id, ativo, cadastrado_em, revisar,
             motivo_revisao, atualizado_em)
        VALUES (%s, %s, %s, %s, %s, 'harmonit', %s, %s, %s, %s, %s, now())
        ON CONFLICT (harmonit_id) WHERE harmonit_id IS NOT NULL
        DO UPDATE SET
            nome           = EXCLUDED.nome,
            nome_fantasia  = EXCLUDED.nome_fantasia,
            documento      = EXCLUDED.documento,
            tipo_pessoa    = EXCLUDED.tipo_pessoa,
            email          = EXCLUDED.email,
            ativo          = EXCLUDED.ativo,
            cadastrado_em  = EXCLUDED.cadastrado_em,
            revisar        = EXCLUDED.revisar,
            motivo_revisao = EXCLUDED.motivo_revisao,
            atualizado_em  = now()
        WHERE cliente.origem = 'harmonit'
        RETURNING id, (xmax = 0) AS criado
        """,
        (
            _texto(bruto.get("nome")) or f"(sem nome) {harmonit_id}",
            _texto(bruto.get("nomeFantasia")),
            _texto(bruto.get("cnpJ_CPF")),
            bruto.get("tipoPessoa"),
            _texto(contato_principal.get("email")),
            harmonit_id,
            bool(bruto.get("ativo")),
            # 🚨 O sentinela 0001-01-01 do .NET vira NULL aqui. Gravado como
            # data, ele venceria toda disputa de antiguidade.
            identidade.data_cadastro(bruto),
            motivo is not None,
            motivo,
        ),
    )
    linha = cur.fetchone()
    if linha is None:
        # Só acontece se a linha existir com origem = 'movizap'. O WHERE do
        # DO UPDATE barrou de propósito: é cadastro nosso, o sync não manda nele.
        log.warning("cliente harmonit_id=%s existe com origem movizap -- não tocado",
                    harmonit_id)
        return 0, False
    return linha["id"], linha["criado"]


def _gravar_contato(cur, cliente_id: int, bruto: dict) -> int:
    contato_principal = bruto.get("contatoPrincipal")
    if not isinstance(contato_principal, dict):
        contato_principal = {}

    id_harmonit_cliente = str(bruto.get("id"))
    id_contato = contato_principal.get("contatoPrincipalId")
    # ~8% vêm sem contatoPrincipalId. `cli:{id}` é estável entre execuções --
    # sem isso o contato seria recriado a cada sync.
    chave = str(id_contato) if id_contato else f"cli:{id_harmonit_cliente}"

    # Não existe nome no contatoPrincipal: o nome do contato é o do cliente.
    nome = (_texto(bruto.get("nomeFantasia"))
            or _texto(bruto.get("nome"))
            or f"(sem nome) {id_harmonit_cliente}")

    cur.execute(
        """
        INSERT INTO contato
            (cliente_id, nome, relacao, email, origem, harmonit_id, ativo, atualizado_em)
        VALUES (%s, %s, 'cliente', %s, 'harmonit', %s, %s, now())
        ON CONFLICT (harmonit_id) WHERE harmonit_id IS NOT NULL
        DO UPDATE SET
            cliente_id    = EXCLUDED.cliente_id,
            nome          = EXCLUDED.nome,
            email         = EXCLUDED.email,
            ativo         = EXCLUDED.ativo,
            atualizado_em = now()
        WHERE contato.origem = 'harmonit'
        RETURNING id
        """,
        (cliente_id, nome, _texto(contato_principal.get("email")),
         chave, bool(bruto.get("ativo"))),
    )
    linha = cur.fetchone()
    if linha is None:
        log.warning("contato harmonit_id=%s existe com origem movizap -- não tocado",
                    chave)
        return 0
    return linha["id"]


def _escolher_principal(validos: list[tuple[str, str, str]]) -> str | None:
    """Qual dos telefones responde "o número do cliente".

    🚨 A primeira versão marcava principal só o campo `celular`, e deixou
    **659 dos 1.050 contatos sem nenhum principal** -- justamente os que têm
    fixo e não têm celular. Quando o atendimento perguntar "qual é o número
    deste cliente", 63% da base não tinha resposta. Achado auditando em 06/08.

    A ordem é a que o atendimento usaria na mão:
      1. o que veio no campo `celular`;
      2. qualquer móvel (o Harmonit guarda celular no campo `telefone` também);
      3. o primeiro que houver -- fixo responde melhor que nada.
    """
    if not validos:
        return None
    for campo, e164, _ in validos:
        if campo == "celular":
            return e164
    for _campo, e164, tipo in validos:
        if tipo == telefone.MOVEL:
            return e164
    return validos[0][1]


def extrair_telefones(bruto: dict, cont: Contadores) -> list[tuple[str, str, str, str]]:
    """Os telefones aproveitáveis de um cliente: (campo, e164, tipo, grafia).

    Separado da gravação porque a decisão de QUEM fica com um número
    compartilhado precisa ver a base inteira antes de qualquer escrita.
    """
    contato_principal = bruto.get("contatoPrincipal")
    if not isinstance(contato_principal, dict):
        return []

    validos: list[tuple[str, str, str, str]] = []
    for campo in CAMPOS_TELEFONE:
        parte = contato_principal.get(campo)
        if not isinstance(parte, dict):
            cont.vazios += 1
            continue

        crua = str(parte.get("phone") or "").strip()
        if not crua:
            # Vazio NÃO é erro. É o normal da base.
            cont.vazios += 1
            continue

        analise = telefone.de_partes(
            ddi=parte.get("ddi"), ddd=parte.get("ddd"), numero=parte.get("phone"))
        if not analise:
            # Preenchido mas irrecuperável (DDD 00 aparece de verdade na base).
            cont.erros += 1
            log.debug("telefone recusado (%s) em %s: %s",
                      campo, bruto.get("id"), analise.motivo)
            continue

        grafia = "+{} {} {}".format(
            str(parte.get("ddi") or "").strip(),
            str(parte.get("ddd") or "").strip(),
            crua,
        ).replace("+  ", "+").strip()
        validos.append((campo, analise.e164, analise.tipo, grafia))

    return validos


def _gravar_telefones(cur, contato_id: int, harmonit_id: str,
                      telefones: list[tuple[str, str, str, str]],
                      donos: dict[str, str], cont: Contadores) -> None:
    """Grava só os números cujo dono é ESTE cliente.

    🚨 Número em revisão não entra em ninguém. Decisão do usuário em 06/08:
    "não cadastre os duvidosos ainda, pode sujar a base nova". Nada é perdido
    -- o vínculo continua no Harmonit e entra assim que a regra mudar.
    """
    validos = [(campo, e164, tipo, grafia)
               for campo, e164, tipo, grafia in telefones
               if donos.get(e164) == harmonit_id]

    cont.nao_atribuidos += len(telefones) - len(validos)

    principal = _escolher_principal([(c, e, t) for c, e, t, _g in validos])

    for campo, e164, _tipo, grafia in validos:
        cur.execute(
            """
            INSERT INTO contato_telefone
                (contato_id, e164, bruto, origem_campo, principal)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (contato_id, e164) DO UPDATE SET
                bruto        = EXCLUDED.bruto,
                origem_campo = EXCLUDED.origem_campo,
                principal    = EXCLUDED.principal
            """,
            # 🚨 tem_whatsapp e verificado_em FICAM DE FORA do UPDATE de
            # propósito: são do Evolution. Incluí-los apagaria verificação real.
            #
            # ⚠️ `principal` ENTRA no UPDATE, e isso tem um custo conhecido:
            # quando a CAD_1.2.2 (aba telefones) deixar alguém escolher o
            # principal na mão, o sync das 12h vai desfazer a escolha. Cai
            # quando existir uma marca de "escolhido por gente" para o sync
            # respeitar -- hoje não existe tela nenhuma, então não há escolha
            # manual para preservar.
            (contato_id, e164, grafia, campo, e164 == principal),
        )


def _decidir_donos(todos: dict, telefones_de: dict,
                   apenas_id: str | None) -> tuple[dict, dict]:
    """De quem é cada número. Ver `identidade.decidir_donos`.

    ⚠️ Com `apenas_id` não há contexto: um cliente só não revela se o número
    dele é compartilhado. Aí a pergunta vai para o BANCO -- se o número já
    pertence a outro contato, este não o recebe. É menos completo que a
    varredura inteira, e é o melhor que 1 registro permite saber.
    """
    numeros_de = {hid: {e164 for _c, e164, _t, _g in tels}
                  for hid, tels in telefones_de.items()}

    if not apenas_id:
        return identidade.decidir_donos(todos, numeros_de)

    donos, em_revisao = {}, {}
    for harmonit_id, numeros in numeros_de.items():
        for e164 in numeros:
            outro = banco.um(
                """SELECT c.harmonit_id FROM contato_telefone t
                     JOIN contato c ON c.id = t.contato_id
                    WHERE t.e164 = %s AND c.harmonit_id IS DISTINCT FROM %s
                    LIMIT 1""",
                (e164, f"cli:{harmonit_id}"))
            if outro:
                em_revisao[e164] = "já pertence a outro contato no banco"
            else:
                donos[e164] = harmonit_id
    return donos, em_revisao


def _limpar_em_revisao(cur, em_revisao: dict) -> tuple[int, int]:
    """Tira do banco os números que a regra nova diz que não deviam estar lá.

    🚨 Por que isto existe: o sync só INSERE. Quando a regra de identidade
    mudou, em 06/08, os 96 vínculos duvidosos gravados pelas execuções
    anteriores continuaram no banco -- a regra nova valia para o que entrava,
    e a base já estava suja. Sem esta limpeza, "não cadastre os duvidosos"
    valeria só para uma base virgem.

    🚨 NUNCA apaga telefone com WhatsApp verificado. Verificação é do
    Evolution, custa uma chamada e não se reconstrói relendo o Harmonit --
    diferente do vínculo, que volta na próxima sincronização. Se houver algum
    verificado, ele fica e é registrado no log para alguém olhar.

    Devolve (apagados, preservados_por_verificacao).
    """
    if not em_revisao:
        return 0, 0

    numeros = list(em_revisao)

    cur.execute(
        """SELECT count(*) AS n FROM contato_telefone t
             JOIN contato c ON c.id = t.contato_id
            WHERE t.e164 = ANY(%s) AND c.origem = 'harmonit'
              AND t.tem_whatsapp IS NOT NULL""",
        (numeros,))
    preservados = cur.fetchone()["n"]
    if preservados:
        log.warning(
            "%s telefones em revisão têm WhatsApp verificado e NÃO foram "
            "removidos -- verificação do Evolution não se reconstrói", preservados)

    cur.execute(
        """DELETE FROM contato_telefone t
            USING contato c
            WHERE c.id = t.contato_id
              AND c.origem = 'harmonit'
              AND t.e164 = ANY(%s)
              AND t.tem_whatsapp IS NULL""",
        (numeros,))
    return cur.rowcount, preservados


def _inativar_sumidos(cur, vistos: set[str]) -> int:
    """Quem sumiu do Harmonit vira inativo. NUNCA é apagado.

    🚨 O filtro `origem = 'harmonit'` é o que protege o cadastro feito aqui.
    Sem ele, um sync que lesse a base pela metade inativaria cliente nosso.
    """
    if not vistos:
        # Guarda-corpo: lista vazia inativaria a base inteira. Se a leitura
        # falhou, o certo é não mexer em nada.
        log.warning("nenhum cliente lido -- inativação pulada por segurança")
        return 0

    cur.execute(
        """
        UPDATE cliente
           SET ativo = false, atualizado_em = now()
         WHERE origem = 'harmonit'
           AND ativo = true
           AND harmonit_id IS NOT NULL
           AND harmonit_id <> ALL(%s)
        """,
        (list(vistos),),
    )
    return cur.rowcount


def executar(origem: str = "manual", atendente_id: int | None = None,
             limite: int | None = None, apenas_id: str | None = None) -> dict:
    """Roda o sync. Bloqueante -- a rota joga numa thread.

    `apenas_id` faz um cliente só, e existe porque **todo lote começa com 1**.
    Com ele, `_inativar_sumidos` não roda: um cliente não é a base.
    """
    if origem not in ("cron", "manual"):
        raise ValueError(f"origem inválida: {origem!r}")

    if not _trava.acquire(blocking=False):
        raise SyncJaEmAndamento("já existe uma sincronização em andamento")
    try:
        return _executar(origem, atendente_id, limite, apenas_id)
    finally:
        _trava.release()


def _executar(origem: str, atendente_id: int | None,
              limite: int | None, apenas_id: str | None) -> dict:
    cont = Contadores()
    inicio = datetime.now(timezone.utc)
    erro_fatal: str | None = None
    vistos: set[str] = set()

    with banco.cursor() as cur:
        cur.execute(
            "INSERT INTO sync_execucao (origem, atendente_id) VALUES (%s, %s) "
            "RETURNING id",
            (origem, atendente_id),
        )
        execucao_id = cur.fetchone()["id"]

    log.info("sync %s iniciado (origem=%s, apenas_id=%s, limite=%s)",
             execucao_id, origem, apenas_id, limite)

    # 🚨 Quem estava ativo ANTES. É o que torna `inativados` um fluxo:
    # sem essa foto, o contador vira estoque e devolve o mesmo número toda
    # execução, sem responder "o que mudou desde ontem?".
    ativos_antes = {
        linha["harmonit_id"] for linha in banco.varios(
            "SELECT harmonit_id FROM cliente "
            " WHERE origem = 'harmonit' AND ativo AND harmonit_id IS NOT NULL")
    }

    try:
        if apenas_id:
            bruto = harmonit.obter_cliente(apenas_id)
            paginas = [] if bruto is None else [(0, [bruto])]
        else:
            # 🚨 SÓ OS ATIVOS. Decisão do usuário em 10/08: empresa
            # inativa não faz parte desta base -- ela não escreve, e se
            # escrever entra como não identificada, que é o caso normal.
            # Sem este filtro as 106 inativas apagadas voltariam às 17:45.
            paginas = harmonit.paginar_clientes(somente_ativos=True,
                                                limite=limite)

        # ── PASSAGEM 1: cliente e contato, e a coleta dos telefones ─────────
        #
        # 🚨 Nenhum telefone é gravado aqui. Decidir de quem é um número
        # compartilhado exige ver TODOS os clientes -- gravar durante a leitura
        # faria a decisão depender da ordem das páginas.
        todos: dict[str, dict] = {}
        contato_de: dict[str, int] = {}
        telefones_de: dict[str, list] = {}

        for _pagina, lista in paginas:
            with banco.cursor() as cur:
                for bruto in lista:
                    if not isinstance(bruto, dict) or bruto.get("id") is None:
                        cont.erros += 1
                        continue
                    harmonit_id = str(bruto["id"])
                    cont.lidos += 1
                    vistos.add(harmonit_id)
                    todos[harmonit_id] = bruto

                    cliente_id, criado = _gravar_cliente(cur, bruto)
                    if not cliente_id:
                        continue
                    if criado:
                        cont.criados += 1
                    else:
                        cont.atualizados += 1

                    # Só conta quem VIROU inativo agora, não quem já estava.
                    if not bruto.get("ativo") and harmonit_id in ativos_antes:
                        cont.inativados += 1

                    contato_id = _gravar_contato(cur, cliente_id, bruto)
                    if contato_id:
                        contato_de[harmonit_id] = contato_id
                        telefones_de[harmonit_id] = extrair_telefones(bruto, cont)

        # ── PASSAGEM 2: de quem é cada número, e só então gravar ────────────
        donos, em_revisao = _decidir_donos(todos, telefones_de, apenas_id)
        cont.em_revisao = len(em_revisao)
        if em_revisao:
            log.warning(
                "%s números ficaram SEM dono e não foram gravados -- ver "
                "revisao/ e docs/08_Identidade.md", len(em_revisao))

        with banco.cursor() as cur:
            for harmonit_id, contato_id in contato_de.items():
                _gravar_telefones(cur, contato_id, harmonit_id,
                                  telefones_de.get(harmonit_id, []), donos, cont)

            # O sync só insere: sem isto, vínculo gravado antes da regra de
            # 06/08 ficaria no banco para sempre.
            apagados, preservados = _limpar_em_revisao(cur, em_revisao)
            cont.removidos = apagados
            if apagados or preservados:
                log.info("limpeza da revisão: %s removidos, %s preservados por "
                         "terem WhatsApp verificado", apagados, preservados)

        if not apenas_id and limite is None:
            with banco.cursor() as cur:
                cont.inativados += _inativar_sumidos(cur, vistos)

    except harmonit.HarmonitIndisponivel as exc:
        erro_fatal = str(exc)
        log.error("sync %s interrompido: %s", execucao_id, erro_fatal)
    except Exception as exc:  # noqa: BLE001 -- o registro tem que sobreviver a tudo
        erro_fatal = f"{type(exc).__name__}: {exc}"
        log.exception("sync %s falhou", execucao_id)

    with banco.cursor() as cur:
        cur.execute(
            """
            UPDATE sync_execucao
               SET terminado_em = now(), lidos = %s, criados = %s,
                   atualizados = %s, inativados = %s, vazios = %s, erros = %s,
                   mensagem_erro = %s
             WHERE id = %s
            """,
            (cont.lidos, cont.criados, cont.atualizados, cont.inativados,
             cont.vazios, cont.erros, erro_fatal, execucao_id),
        )

    duracao = (datetime.now(timezone.utc) - inicio).total_seconds()
    log.info("sync %s terminado em %.1fs: %s%s", execucao_id, duracao,
             cont.como_dict(), f" ERRO: {erro_fatal}" if erro_fatal else "")

    return {"execucao_id": execucao_id, "duracao_seg": round(duracao, 1),
            "erro": erro_fatal, **cont.como_dict()}


def ultima_execucao() -> dict | None:
    return banco.um(
        "SELECT * FROM sync_execucao ORDER BY iniciado_em DESC LIMIT 1")


def execucoes(limite: int = 20) -> list[dict]:
    return banco.varios(
        "SELECT * FROM sync_execucao ORDER BY iniciado_em DESC LIMIT %s",
        (limite,))


def resumo() -> dict:
    """O que a CFG_3.1 mostra. Estado do banco + estado da API, separados.

    🚨 Os dois não são a mesma pergunta: "quantos clientes eu tenho" é do
    banco, "o Harmonit está de pé" é do disjuntor. Misturar os dois é como se
    descobre tarde que a base parou de atualizar.
    """
    totais = banco.um("""
        SELECT (SELECT count(*) FROM cliente)                        AS clientes,
               (SELECT count(*) FROM cliente WHERE ativo)            AS clientes_ativos,
               (SELECT count(*) FROM cliente WHERE origem='movizap') AS clientes_nossos,
               (SELECT count(*) FROM contato)                        AS contatos,
               (SELECT count(*) FROM contato_telefone)               AS telefones,
               (SELECT count(*) FROM contato_telefone
                 WHERE tem_whatsapp IS TRUE)                         AS com_whatsapp,
               (SELECT count(*) FROM contato_telefone
                 WHERE tem_whatsapp IS NULL)                         AS nao_verificados
    """)
    return {
        "em_andamento": em_andamento(),
        "totais": totais,
        "harmonit": harmonit.estado(),
        "ultima": ultima_execucao(),
        "historico": execucoes(10),
    }
