"""A OS do chamado — Bloco A do pipeline da operação (29/10).

🔵 Duas decisões dele, no mesmo dia, que viraram este módulo:
  · **D4** — *"todo chamado de suporte abrirá uma OS"*: automático no envio,
    não por botão (o que inverteu a decisão 3.6 de 23/10);
  · **D3** — **uma OS por placa** informada (que inverteu a 3.5 de 23/10, "uma
    OS por envio").

🚨 A OS QUE NASCE DAQUI É DE ANÁLISE, NUNCA DE SERVIÇO, e isto é a decisão mais
estruturante da frente. Palavras dele, 23/10: *"somente 1 OS para analise do
problema mesmo, se for necessário manutenção, daí será gerada pelo painel de
'Operações' do FPSL. Não necessariamente todo chamado do cliente virá OS de
serviço. Daí a importancia da 'Situação da OS'"*.

🚨 ESTE MÓDULO NÃO FALA COM O HARMONIT. Ele decide **o quê** gravar e guarda o
resultado; quem grava é a ponte do FPSL (`fpsl_ponte.criar_os` ->
`/api/os/criar`), porque é lá que vive o cliente do ERP. O motivo é o mesmo de
21/10: o MoviZap não tem credencial do Harmonit, e dar uma a ele seria um
segundo lugar para rotacionar.

🚨 O CHAMADO É GRAVADO PRIMEIRO, E A OS DEPOIS — nesta ordem, e não é detalhe.
O pior caso desta frente é o cliente ler *"recebemos sua solicitação"* e
ninguém abrir OS. Então: a solicitação entra no banco, as linhas de
`solicitacao_os` nascem com `os_id` nulo, e cada falha fica **escrita na
linha** e contada no painel. A alternativa -- criar a OS antes e só então
gravar -- perderia o chamado inteiro quando o ERP estivesse fora do ar, que é
justamente quando o cliente mais precisa ser ouvido.

⚠️ O QUE ESTE MÓDULO AINDA NÃO FAZ, e é decisão dele: o sub-mapa de problema
por opção de lista (SUPORTE e ADMINISTRATIVO) e os dois "Backup" não têm
candidato nos 24 problemas do Harmonit. Enquanto não houver, todo chamado de
suporte abre com **12760 ANÁLISE OPERACIONAL**, que é exatamente o que a
decisão 3.5 pede -- a OS é de análise, e o problema fino é da operação, depois.
"""
import logging

from . import banco, formularios, fpsl_ponte

log = logging.getLogger("movizap.chamado_os")

# ----------------------------------------------------------------------------
# As constantes que ELE decidiu, e os ids conferidos contra o catálogo do ERP
# ----------------------------------------------------------------------------
# 🚨 OS CINCO FORAM LIDOS DO CATÁLOGO DO HARMONIT EM 29/10, não copiados de
# memória: `1782` Demanda Interna · `1783` Solicitação de Cliente · `12760`
# ANÁLISE OPERACIONAL · `38` Novo Solicitação 1ª · `382` Normal. Id de
# catálogo errado não dá erro de escrita -- dá OS torta e muda no ERP.
#
# ⚠️ `ABERTURA DE OS` (670990) NÃO FOI CONFERIDO POR LEITURA: está cadastrado
# como SERVIÇO, e `/Produto/ObterServicos` é a rota que o lista. O número vem
# da sessão de 23/10, quando ele o criou para este fim. Se a escrita o
# recusar, é aqui que se olha.

# 🔵 3.1 dele, 23/10: *"o `tipoId` vem da ORIGEM, não do formulário"*.
# ⚠️ E ele aceitou a consequência que eu apontei: pelo link livre quem preenche
# é o CLIENTE, e a OS nasce marcada "Demanda Interna" -- quem filtrar o ERP por
# origem para saber o que o cliente pediu não verá essas.
TIPO_POR_ORIGEM = {
    "link": 1782,      # Demanda Interna — `forms.movisat.com.br`
    "movizap": 1783,   # Solicitação de Cliente — botão na conversa (Etapa 2)
}

# 🔵 *"todas elas abre como Nova Solicitação por padrão do harmonit"*.
SITUACAO_INICIAL = 38
# 🔵 *"sempre padrão atual, normal"*.
PRIORIDADE_PADRAO = 382
# 🔵 O item de R$ 0,01 que ele criou para contar abertura de OS.
# 🚨 D12 (29/10): *"cada placa com OS de 0,01"* — é **por OS**, e isso MUDOU a
# nota de 23/10, que dizia "um por envio, nada de R$ 0,20". Com D3 (uma OS por
# placa) a nota antiga deixou de valer: 4 placas são 4 OS e R$ 0,04.
PRODUTO_ABERTURA_DE_OS = 670990

# O problema de cada formulário. 🚨 SÓ O SUPORTE ESTÁ AQUI, e é de propósito:
# é o único no formato novo e o único cuja ponte ele fechou. Formulário fora
# deste mapa **não abre OS** -- e não abrir é o comportamento certo, porque o
# mapa dos outros 14 ainda espera decisão dele (ver o cabeçalho).
#
# ⚠️ Os 6 que NÃO geram OS por decisão dele (NPS, CES, CONTATO,
# PAGAMENTO_TECNICOS) nunca entram aqui -- ausência é a regra, não esquecimento.
PROBLEMA_POR_FORMULARIO = {
    "suporte": 12760,   # ANÁLISE OPERACIONAL
}


def formulario_abre_os(slug: str) -> bool:
    """Se este formulário abre OS hoje. ⚠️ `False` não é defeito: 6 dos 15 não
    abrem por decisão dele, e os outros esperam o mapa de problema."""
    return slug in PROBLEMA_POR_FORMULARIO


def _descricao(d: dict, valores: dict, placa: str | None,
               solicitacao_id: int) -> str:
    """O que vai na `descricaoDetalhada` da OS.

    🚨 O ANEXO NÃO VAI AQUI, nem como link público. Decisão 3.8 de 23/10, que
    eu levantei e ele aceitou: seriam contrato social, CPF, RG e documento de
    veículo atrás de uma URL que, colada num grupo de WhatsApp, abre para
    qualquer um. O que vai é o número do card, que tem login.
    """
    linhas = [f"[MoviZap] Chamado {solicitacao_id} — {d.get('titulo') or d['slug']}"]
    if placa:
        linhas.append(f"Placa: {placa}")
    for campo in d["campos"]:
        if campo["tipo"] == "file":
            continue
        bruto = valores.get(campo["nome"])
        if bruto is None or bruto == "" or bruto == []:
            continue
        texto = ", ".join(str(p) for p in bruto) if isinstance(bruto, list) \
            else str(bruto)
        linhas.append(f"{campo.get('rotulo') or campo['nome']}: {texto}")
    # ⚠️ O teto é o da entrada da ponte (4000). Cortar aqui, dizendo que
    # cortou, é melhor que a ponte recusar a OS inteira por tamanho.
    texto = "\n".join(linhas)
    if len(texto) > 3900:
        texto = texto[:3900] + "\n[...] (texto cortado; o chamado inteiro está no card)"
    return texto


def preparar(solicitacao_id: int, d: dict, valores: dict) -> list[dict]:
    """Cria as linhas de `solicitacao_os` — uma por placa, antes de qualquer OS.

    🚨 NASCEM COM `os_id` NULO, e é o ponto: a partir daqui a falha tem onde
    ficar escrita. Devolve as linhas criadas.

    ⚠️ Sem placa informada, UMA linha com `placa` nula -- o caso "uma OS só"
    convive com o mesmo desenho, sem `if` em quem lê.
    """
    placas = formularios.placas_informadas(d, valores) or [None]
    # 🚨 Sem duplicata DENTRO do mesmo envio: a mesma placa duas vezes no mesmo
    # chamado não é pedido legítimo em dobro, e o índice único do banco
    # recusaria a segunda. Aqui a ordem é preservada, que é a que a pessoa
    # digitou.
    vistas, unicas = set(), []
    for p in placas:
        chave = (p or "").upper()
        if chave in vistas:
            continue
        vistas.add(chave)
        unicas.append(p)

    criadas = []
    for placa in unicas:
        linha = banco.um(
            """INSERT INTO solicitacao_os (solicitacao_id, placa)
               VALUES (%s, %s)
            ON CONFLICT (solicitacao_id, coalesce(placa, '')) DO NOTHING
            RETURNING id, placa""",
            (solicitacao_id, placa))
        if linha:
            criadas.append(linha)
    log.info("chamado %s: %s linha(s) de OS a abrir", solicitacao_id, len(criadas))
    return criadas


def _registrar_resultado(linha_id: int, resposta: dict) -> bool:
    """Grava na linha o que a ponte respondeu. Devolve se a OS nasceu.

    🚨 `criada: None` É O CASO FEIO e tem tratamento próprio: o Harmonit
    aceitou a escrita e não disse o número. Pode haver OS no ERP que ninguém
    sabe que existe -- então a linha guarda o aviso **e não é marcada como
    livre para nova tentativa**. Tentar de novo criaria a segunda.
    """
    numero = resposta.get("numero_os")
    if numero:
        banco.executar(
            """UPDATE solicitacao_os
                  SET os_id = %s, numero_ordem = %s, erro = %s,
                      tentativas = tentativas + 1, tentada_em = now()
                WHERE id = %s""",
            (resposta.get("os_id"), numero,
             # ⚠️ OS criada COM divergência não é sucesso limpo: o número é
             # guardado (senão fica órfã no ERP) e a divergência fica dita.
             None if resposta.get("ok") else
             f"OS criada com divergencia: {resposta.get('divergencias')}",
             linha_id))
        return True

    motivo = resposta.get("motivo") or "a ponte do FPSL nao disse o motivo"
    if resposta.get("criada") is None:
        motivo = "🚨 " + motivo
    banco.executar(
        """UPDATE solicitacao_os
              SET erro = %s, tentativas = tentativas + 1, tentada_em = now()
            WHERE id = %s""",
        (motivo, linha_id))
    return False


def abrir(solicitacao_id: int, d: dict, valores: dict, cliente_id: int | None,
          origem: str = "link") -> dict:
    """Abre a OS de análise de cada placa do chamado. 🚨 NUNCA ESTOURA.

    Devolve `{"abertas", "falhas", "motivo"}`. Quem chama é a rota de envio, e
    ela já respondeu "recebemos" ao cliente -- derrubar o envio porque o ERP
    recusou faria o cliente perder o chamado por um problema nosso.

    `cliente_id` é o **`harmonit_id`** do cliente, já resolvido por quem chama.
    🔴 SEM ELE NÃO HÁ OS, e isto é uma pendência dele, não uma escolha minha: o
    `SalvarOrdemServico` exige `clienteId`, o formulário é público, e o modal
    *"Sem empresa vinculada"* deixa enviar sem empresa. Então o chamado de
    quem não é cliente fica gravado, **marcado**, e aparece na linha de aviso
    do painel -- em vez de virar OS de um cliente inventado.
    """
    if not formulario_abre_os(d["slug"]):
        return {"abertas": 0, "falhas": 0,
                "motivo": f"o formulario {d['slug']} nao abre OS hoje"}

    linhas = preparar(solicitacao_id, d, valores)
    if not linhas:
        return {"abertas": 0, "falhas": 0,
                "motivo": "nenhuma linha a abrir (o chamado ja as tinha)"}

    if not cliente_id:
        motivo = ("sem empresa vinculada: o chamado nao casou com cliente do "
                  "cadastro, e a OS do Harmonit exige cliente")
        for linha in linhas:
            banco.executar(
                """UPDATE solicitacao_os
                      SET erro = %s, tentativas = tentativas + 1,
                          tentada_em = now()
                    WHERE id = %s""", (motivo, linha["id"]))
        log.warning("chamado %s: %s", solicitacao_id, motivo)
        return {"abertas": 0, "falhas": len(linhas), "motivo": motivo}

    tipo_id = TIPO_POR_ORIGEM.get(origem) or TIPO_POR_ORIGEM["link"]
    abertas, falhas, primeira = 0, 0, None
    for linha in linhas:
        resposta = fpsl_ponte.criar_os(
            cliente_id=int(cliente_id),
            tipo_id=tipo_id,
            problema_id=PROBLEMA_POR_FORMULARIO[d["slug"]],
            situacao_id=SITUACAO_INICIAL,
            prioridade_id=PRIORIDADE_PADRAO,
            produto_servico_id=PRODUTO_ABERTURA_DE_OS,
            descricao=_descricao(d, valores, linha["placa"], solicitacao_id),
        )
        if _registrar_resultado(linha["id"], resposta):
            abertas += 1
            primeira = primeira or resposta
        else:
            falhas += 1

    # ⚠️ `formulario_solicitacao.os_id` passa a ser **a primeira OS** desta
    # solicitação, não "a OS" -- ver o cabeçalho da migração 082. O painel de
    # hoje a lê, e deixá-la nula faria o card desaparecer da tela.
    if primeira:
        banco.executar(
            """UPDATE formulario_solicitacao
                  SET os_id = %s, numero_ordem = %s, situacao_id = %s,
                      situacao_em = now()
                WHERE id = %s AND os_id IS NULL""",
            (primeira.get("os_id"), str(primeira.get("numero_os")),
             primeira.get("situacao_id") or SITUACAO_INICIAL, solicitacao_id))

    log.info("chamado %s: %s OS abertas, %s falhas", solicitacao_id, abertas, falhas)
    return {"abertas": abertas, "falhas": falhas, "motivo": None}


def falhas_em_aberto(painel: str | None = None) -> dict:
    """Quantos chamados ficaram sem OS, para o painel DIZER (`M12`).

    🚨 É O CONTRÁRIO DE ESCONDER: solicitação gravada cuja OS não nasceu não
    tem coluna no painel e sumiria da tela. Esta conta é o que faz a linha de
    aviso existir.

    🚨 FILTRA POR PAINEL, e não filtrava — defeito meu, achado na auditoria do
    mesmo dia: o `sem_tentativa()` ao lado filtrava e este não, então a linha
    de aviso da Operação somava falha de chamado do Financeiro e do
    Contratual. Hoje não há falha nenhuma na base, então nada se via: era
    latente, e o primeiro chamado recusado de outro setor o mostraria.

    ⚠️ `painel = None` conta TODOS, de propósito: serve a quem quer o número da
    casa inteira (uma varredura, um relatório), e nunca a uma tela de painel.
    """
    onde, params = "", ()
    if painel is not None:
        onde = """AND EXISTS (SELECT 1 FROM formulario_solicitacao s
                               JOIN formulario f ON f.id = s.formulario_id
                              WHERE s.id = solicitacao_id
                                AND f.painel = %s)"""
        params = (painel,)
    linha = banco.um(
        f"""SELECT count(*) AS quantas,
                  count(DISTINCT solicitacao_id) AS chamados,
                  max(tentada_em) AS ultima
             FROM solicitacao_os
            WHERE os_id IS NULL AND erro IS NOT NULL
              {onde}""", params)
    return {"quantas": (linha or {}).get("quantas") or 0,
            "chamados": (linha or {}).get("chamados") or 0,
            "ultima": (linha or {}).get("ultima")}


def sem_tentativa(painel: str) -> int:
    """Quantos chamados deste painel nunca tiveram tentativa de abrir OS.

    🚨 ISTO NÃO É FALHA, e confundir os dois foi um defeito meu que ele achou
    na tela em 29/10: a frase dizia *"a escrita no Harmonit falhou"* para uma
    solicitação que **nunca teve escrita tentada**. São dois casos legítimos:
      · o chamado é anterior ao Bloco A (a OS nascia por botão até 29/10);
      · o formulário não abre OS por decisão dele (6 dos 15).

    A marca de "nunca se tentou" é **não haver linha** em `solicitacao_os` --
    e é por isso que aquelas linhas nascem antes da OS existir.
    """
    linha = banco.um(
        """SELECT count(*) AS quantas
             FROM formulario_solicitacao s
             JOIN formulario f ON f.id = s.formulario_id
            WHERE f.painel = %s
              AND s.os_id IS NULL
              AND NOT EXISTS (SELECT 1 FROM solicitacao_os x
                               WHERE x.solicitacao_id = s.id)""", (painel,))
    return (linha or {}).get("quantas") or 0


def da_solicitacao(solicitacao_id: int) -> list[dict]:
    """As OS desta solicitação, com a placa de cada uma e a falha, se houve."""
    return banco.varios(
        """SELECT id, placa, os_id, numero_ordem, erro, tentativas, tentada_em,
                  criada_em
             FROM solicitacao_os
            WHERE solicitacao_id = %s
            ORDER BY id""", (solicitacao_id,))


# ----------------------------------------------------------------------------
# DE QUEM É O CHAMADO — o `clienteId` que a OS exige
# ----------------------------------------------------------------------------
# 🚨 POR QUE NÃO SE REUSA O `formularios.cliente_por_documento`: aquele serve a
# tela pública e **de propósito não devolve o `harmonit_id`** -- o comentário
# dele diz *"é id interno; o que sai são as placas"*. Aqui é o servidor falando
# com o ERP, e o id é justamente o que se precisa. Então a consulta é a mesma,
# o que sai é outro.
#
# ⚠️ O CAMPO DO DOCUMENTO É ACHADO PELA VALIDAÇÃO, não pelo nome: as chaves dos
# campos são as do Bitrix (`COMPANY_UF_CRM_1646332310941`), e escrever uma
# dessas aqui amarraria este módulo ao formulário de hoje. `validacao in
# ('cnpj', 'cpf')` vale para os 15.


def _documentos_do_chamado(d: dict, valores: dict) -> list[str]:
    """Os documentos que o chamado informou, na forma canônica.

    ⚠️ Mais de um é possível e é o desenho: o SUPORTE tem `cnpj` E `cpf`, e as
    três regras condicionais mostram um ou outro conforme PF/PJ. Campo
    escondido por regra nem chega aqui -- o `validar` o tira do registro.
    """
    import re
    saida = []
    for campo in d["campos"]:
        if campo.get("validacao") not in ("cnpj", "cpf"):
            continue
        bruto = valores.get(campo["nome"])
        partes = bruto if isinstance(bruto, list) else [bruto]
        for p in partes:
            so = re.sub(r"[^A-Za-z0-9]", "", str(p or "")).upper()
            if len(so) in (11, 14):
                saida.append(so)
    return saida


def cliente_do_chamado(d: dict, valores: dict) -> int | None:
    """O `harmonit_id` do cliente deste chamado, ou `None`.

    🔴 `None` NÃO É DEFEITO E NÃO É SILÊNCIO: o formulário é público, e o modal
    *"Sem empresa vinculada"* (29/10) existe justamente para deixar enviar quem
    ainda não é cliente. Quem chama trata isso marcando a linha -- ver o
    docstring do `abrir`.

    🚨 MAIS DE UM CLIENTE COM O MESMO DOCUMENTO EXISTE (10 pares na base, medido
    em 29/10). Aqui se escolhe o **ativo mais antigo**, que é a mesma ordem que
    a busca da tela pública usa -- duas ordens diferentes para a mesma pergunta
    fariam a tela dizer um nome e a OS nascer no outro cadastro.
    """
    for documento in _documentos_do_chamado(d, valores):
        linha = banco.um(
            """SELECT harmonit_id FROM cliente
                WHERE upper(regexp_replace(coalesce(documento, ''),
                                           '[^A-Za-z0-9]', '', 'g')) = %s
                  AND harmonit_id IS NOT NULL
                ORDER BY ativo DESC, id
                LIMIT 1""", (documento,))
        if linha and linha["harmonit_id"]:
            try:
                return int(linha["harmonit_id"])
            except (TypeError, ValueError):
                # ⚠️ `harmonit_id` é TEXT neste banco. Valor que não é número
                # é cadastro sujo, e virar OS no cliente errado seria pior que
                # não abrir.
                log.warning("harmonit_id nao numerico no cliente do documento "
                            "%s: %r", documento, linha["harmonit_id"])
                return None
    return None
