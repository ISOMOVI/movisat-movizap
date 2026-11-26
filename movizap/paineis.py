"""Os painéis por setor — a Etapa 3, começando pelo da Operação.

🔵 Decisão dele em 22/10, depois de ver os mockups lado a lado: *"vamos de A
somente para a Operação por enquanto, mas bem documentado para as demais
futuramente"*. A opção A é o **kanban cujas colunas são as situações da OS do
Harmonit** (eram 11 em 22/10, e são **17** desde 29/10, quando ele deu a lista
inteira na ordem do fluxo) -- a única das três em que mover o card É a ação, e foi esse o
motivo que ele deu para o painel existir: *"hoje ainda não usamos a situação
da OS, por isso o painel e consulta para atualizar a situação no painel"*.

🚨 O QUE ESTE MÓDULO FAZ, E SÓ: lê o que vai nas colunas e as monta. Ele
**não escreve em nada** -- quem grava a situação no Harmonit é o
`passagem.mover`, e quem grava etapa nossa é o `pipeline.mover`.
⚠️ ISTO DIZIA *"mover o card ainda não existe"* ATÉ 05/11, e era verdade
quando foi escrito: mover passou a existir no Bloco D de 29/10 (*"O card pode
ser por arrastar"*). `M12` -- o texto era verdadeiro e a entrega seguinte não
voltou para matá-lo.

🚨 OS OUTROS TRÊS PAINÉIS NÃO SÃO ESTE COM OUTRO FILTRO **DE OS**, e é por
isso que só o da Operação nasceu em 22/10.

🔵 E ISTO SE INVERTEU PELA METADE EM 05/11, por pedido dele: *"a aba
'Operação' do Movizap é a mesma lógica para os demais"*, com as pipelines de
Pós-venda escritas por ele. Na **forma** passam a ser o mesmo kanban; o que
muda é **de quem é a coluna**:

  · as 17 colunas da Operação são **situações da OS no Harmonit**, e mover
    nelas **escreve no ERP**;
  · a coluna `Chamados` (05/11) e as colunas de Pós-venda são **etapas
    NOSSAS**, e mover nelas escreve **só no nosso banco**.

🚨 O MOTOR DAS ETAPAS NOSSAS É O `movizap/pipeline.py`, e ele **não importa
a ponte** -- há trava provando isso. A Operação é o caso misto de propósito: a
`Chamados` à esquerda das 17. O que separa as duas naturezas é **de onde vem a
coluna**, e não um `if` espalhado pelo módulo.

O que foi desenhado e medido para cada um está em
`docs/06_Conteudo_das_Telas.md` (22/10, quinta e sexta voltas) e nos mockups:

  · **Pós venda** NÃO É FILA, é MEDIÇÃO -- e isso saiu do formulário, não de
    gosto: a nota é lista de 1 a 10, e as regras do NPS já separam quem
    respondeu (8, 9 ou 10 pede INDICAÇÃO -- nome, telefone, e-mail --; 7 ou
    menos pede O QUE OCORREU, obrigatório). NPS e CES **não geram OS**: coluna
    por situação ali não mede nada. A tela quer três medidas, a distribuição
    das notas e duas filas de ação.
  · **Contratual**: o que trava não é a situação, é o **documento**. Três
    faixas (falta documento → a conferir → pronto), e a ficha dos 36 campos da
    ficha cadastral agrupada pelas quebras de página que o formulário já tem.
  · **Financeiro**: fila simples com três medidas, e o único com **elo
    externo** (pagamento de técnicos ↔ o fechamento do FPSL, que tem base
    própria). ⚠️ Risco nomeado: virar uma segunda contabilidade ao lado do
    `FIN_2.1`.

Quando um deles nascer, nasce com módulo e rota próprios -- não com um `if`
aqui dentro.
"""
import logging
from datetime import date, datetime

from . import (banco, chamado_os, checklist, fpsl_ponte, horas_uteis,
               passagem, pipeline)
from .operacao import DadoInvalido

log = logging.getLogger("movizap.paineis")

# ----------------------------------------------------------------------------
# As 17 situações da OS do Harmonit — e a ORDEM é a dele
# ----------------------------------------------------------------------------
# 🔵 Definidas por ele em 29/10: *"eis as situações que precisamos manter"*, e
# *"as situações já estão na Ordem"*. A ordem desta tupla É a ordem das colunas
# do painel, e é o fluxo da operação -- não alfabética, não por id.
#
# 🚨 O CATÁLOGO DO HARMONIT FOI AJUSTADO PARA ESTAS 17, em 29/10, pelo
# `fpsl_weso/ajustar_situacoes_os.py`: 11 renomeadas e 6 criadas. ⚠️ Nenhuma
# foi EXCLUÍDA -- excluir deixaria OS apontando para id inexistente --, e
# nenhuma sobrou fora: as 11 antigas todas mapearam.
#
# 🔵 As duas escolhas que ELE fez quando eu perguntei (não supus):
#   · a 677 "Envio dos Equipamentos" (4 OS reais) virou *"Enviar por
#     correio/transportadora"*, e *"Entrega de materiais prontos"* nasceu nova;
#   · a 15694 "Serviço Realizado" (19 OS) virou *"Atendimento finalizado"*.
#     🚨 ELA É A PORTA DO PAINEL FINANCEIRO DO FPSL (a rotina de conferência
#     dispara nesse id). O id não mudou, então o FPSL segue funcionando -- o
#     que mudou é o nome que a operação lê.
#
# ⚠️ Os nomes são como estão no ERP, inclusive "Novo Solicitação 1ª" e
# "Analise" sem acento: tela e ERP têm de chamar a mesma coisa pelo mesmo nome,
# e corrigir aqui criaria duas verdades. Quem muda o nome é o catálogo.
#
# ⚠️ A LISTA PODE CRESCER NO HARMONIT sem ninguém avisar. Situação que chegar
# fora desta lista não tem coluna -- e por isso o quadro conta essas em
# `fora_do_quadro`, para a tela dizer em vez de esconder.
SITUACOES = (
    (38,    "Novo Solicitação 1ª"),
    (16487, "Pendente de ação da Movisat"),
    (251,   "Configurar equipamentos e Sistemas"),
    (16488, "Entrega de materiais prontos"),
    (677,   "Enviar por correio/transportadora"),
    (15747, "Aguardando recebimento via correio/transportadora"),
    (15797, "Rescisão Aguardando Aviso Prévio"),
    (890,   "Agendar serviço"),
    (16489, "Confirmação agendamento"),
    (1316,  "Serviço Agendado"),
    (15696, "Aguardando devolução de equipamento"),
    (16490, "Analise de Equipamentos Retornados"),
    (15694, "Atendimento finalizado"),
    (16491, "Não atendido"),
)

# 🚨 AS TRES QUE SAIRAM EM 11/11, e para onde foram:
#
#   15746 Financeiro  -> painel Financeiro, etapa "Nova solicitação"
#   15695 Pós venda   -> painel Pós-venda,  etapa "Nova solicitação"
#   16492 Contratual  -> painel Contratual, primeira etapa
#
# 🔵 Decisao dele, 11/11, sobre uma OS de ressarcimento que nasceu na coluna
# `Financeiro` DESTE painel: *"não é nesse financeiro que deve nascer, essas
# etapas finais do OP devem ser excluídas e deveria ter nascido no painel
# Financeiro, na etapa correta 'Nova solicitação'"*.
#
# 🚨 ELAS NAO FORAM APAGADAS DA OPERACAO: foram REENDERECADAS. O destino vive
# em `pipeline_etapa.recebe_situacao` (migracao 106), porque e decisao dele e
# muda sem deploy -- ao contrario das 14 que ficam, que o ERP manda.
#
# ⚠️ E SE O DESTINO FOR APAGADO, a OS cai em `fora_do_quadro` e e CONTADA, nao
# escondida. Nenhuma OS pode sumir de todas as telas por causa de um cadastro.
SITUACOES_REENDERECADAS = (15746, 15695, 16492)

# 🔵 29/10: AS DUAS COLUNAS QUE NÃO ERAM SITUAÇÃO SAÍRAM -- *"qualquer aba
# fora dessas não deve estar no painel"*. E o motivo de cada uma deixou de
# valer no mesmo dia:
#
#   · "Sem OS" existia porque a OS nascia por BOTÃO (decisão de 23/10). Ele
#     mudou isso: *"todo chamado de suporte abrirá uma OS"*, automático no
#     envio -- então a coluna não recebe card nenhum;
#   · "Sem situação" existia por 164 OS com `situacao_id` 0 ou nulo no cache do
#     FPSL. ⚠️ Aquelas são OS de OUTRAS origens, não solicitações deste painel;
#     as daqui nascem em 38.
#
# 🚨 MAS NADA SOME DA TELA EM SILÊNCIO (`M12`). Solicitação sem OS (a escrita
# no Harmonit falhou) ou com situação fora das 17 não tem coluna -- e sumiria.
# Por isso o quadro conta essas em `fora_do_quadro`, e a tela escreve UMA linha
# quando houver o que dizer. Com zero, não escreve nada.

PAINEIS = {
    "operacao": "Operação",
    # Declarados porque o mapa do formulário já aponta para eles (migração
    # 075) e porque a rota recusa painel desconhecido. ⚠️ Ter nome aqui não
    # cria tela: as três ainda não existem, e o cabeçalho deste módulo diz o
    # que cada uma vai querer.
    "pos_venda": "Pós venda",
    "contratual": "Contratual",
    "financeiro": "Financeiro",
}

# Só este tem tela. É o que a rota confere, e é uma linha para mudar quando o
# próximo nascer.
COM_TELA = ("operacao",)

# ----------------------------------------------------------------------------
# A COLUNA `Chamados` -- a primeira do quadro, e a unica que NAO e do Harmonit
# ----------------------------------------------------------------------------
# 🔵 Pedido dele em 05/11: *"vamos criar uma coluna nova antes de 'Nova
# solicitacao', chamada 'Chamados' (...) nessa coluna nao sao OS ainda, somente
# o CARD mesmo"*. E a razao de negocio: *"O chamado e o cliente dizendo algo,
# como: 'rastreador parou de pegar'. O chamado e para analisar e decidir se
# realmente sera aberta OS."*
#
# 🚨 ELA NAO ENTRA NA TUPLA `SITUACOES`, e isso e deliberado: duas travas
# dependem de ela ter 17 (`teste_rotas_formularios` afirma `len == 17`, e
# `checklist._etapa_conhecida` recusa situacao fora das 17). A coluna Chamados e
# de OUTRA NATUREZA -- etapa NOSSA, com `situacao_id` nulo -- e nao uma 18a
# situacao do ERP.
#
# ⚠️ A `chave` nao segue o padrao `s<id>` das outras justamente para a tela
# nao poder confundi-la com situacao.
CHAVE_CHAMADOS = "chamados"
# A aba da Operacao reusa o codigo da tela que ja existe: a coluna Chamados e
# parte do quadro da Operacao, nao uma tela nova.
ABA_DA_OPERACAO = "PNL_1.1"

TETO_CARDS_POR_COLUNA = 50


def _resumo(valores: dict) -> str:
    """As duas primeiras respostas de texto -- o que faz a pessoa reconhecer o
    card. ⚠️ Nunca o conteúdo inteiro: card não é ficha."""
    textos = [str(v) for v in (valores or {}).values()
              if isinstance(v, str) and v.strip()]
    return " · ".join(textos[:2])


# ----------------------------------------------------------------------------
# O CARD É A OS — Bloco B do pipeline da operação (29/10)
# ----------------------------------------------------------------------------
# 🔵 Decisão D8 dele: *"seja pelo painel, seja pelo FPSL, seja pelo formulario,
# seja a mão"*. Até aqui este painel lia só `formulario_solicitacao` — e havia
# **uma** solicitação na base. A tela estava tecnicamente certa e praticamente
# vazia.
#
# 🔵 D9: a data matriz é **24/10/2026**, e *"a data inicial é somente do
# Owner"* · *"não vamos retroagir mais do que o dia que pedi"*.
#
# 🚨 A SOLICITAÇÃO NÃO DESAPARECEU DO QUADRO, e isso é escolha: ela é o que o
# cliente escreveu, e o card sem ela perderia as respostas e os anexos. O que
# mudou é quem manda: **a OS é a espinha do card**, e a solicitação entra como
# o que a originou, quando houver. Chamado sem OS continua contado em
# `fora_do_quadro` — nunca escondido.
#
# ⚠️ PONTE FORA DO AR NÃO ESVAZIA O PAINEL. A tela cai para o que o nosso banco
# sabe (as solicitações com `situacao_id` em cache, da migração 076) e **diz
# que caiu**. Quadro vazio por falha de rede faria o operador concluir que não
# há trabalho — e é exatamente nessa hora que há.

CHAVE_DATA_MATRIZ = "painel_operacao_desde"
# 🔵 *"não vamos retroagir mais do que o dia que pedi"*.
DATA_MATRIZ_PADRAO = "2026-10-24"


def data_matriz() -> str:
    """Desde quando o painel monta cards. 🔵 D9: 24/10/2026, e só o owner muda."""
    linha = banco.um("SELECT valor FROM config WHERE chave = %s",
                     (CHAVE_DATA_MATRIZ,))
    valor = (linha or {}).get("valor") or ""
    try:
        date.fromisoformat(valor)
    except ValueError:
        # ⚠️ Valor torto no banco NÃO derruba o painel e NÃO vira silêncio:
        # cai no padrão e registra. Um `desde` inválido faria a ponte recusar
        # com 422 e a tela abrir vazia.
        if valor:
            log.warning("data matriz do painel invalida no config (%r); "
                        "usando %s", valor, DATA_MATRIZ_PADRAO)
        return DATA_MATRIZ_PADRAO
    return valor


def definir_data_matriz(valor: str) -> dict:
    """🔵 *"a data inicial é somente do Owner"*. Quem cobra isso é a rota."""
    try:
        date.fromisoformat(valor)
    except ValueError:
        raise DadoInvalido("A data tem de estar no formato aaaa-mm-dd.")
    banco.executar(
        """INSERT INTO config (chave, valor, descricao, atualizado_em)
           VALUES (%s, %s, %s, now())
           ON CONFLICT (chave) DO UPDATE
              SET valor = EXCLUDED.valor, atualizado_em = now()""",
        (CHAVE_DATA_MATRIZ, valor,
         "Desde quando o painel da Operacao monta cards de OS (D9, 29/10). "
         "Somente o owner muda."))
    log.info("data matriz do painel da Operacao: %s", valor)
    return {"desde": valor}


def _solicitacoes_por_os() -> dict:
    """`numero_ordem` (inteiro) -> a solicitação que gerou aquela OS.

    🚨 LÊ AS DUAS FONTES, e precisa das duas:
      · a **tabela de ligação** (migração 082) é a fonte desde hoje -- com a D3
        um envio de 4 placas gera 4 OS, e a coluna da solicitação guarda só a
        primeira;
      · a **coluna `numero_ordem`** da solicitação é a única fonte para os
        chamados ANTERIORES ao Bloco A, que não têm linha de ligação nenhuma.

    Lendo só a tabela nova, o card daquelas OS antigas aparecia sem o chamado
    que o originou: sem respostas, sem anexos, sem o nome do formulário.
    ⚠️ Achado por teste, e só por teste: as duas solicitações que existem hoje
    (39 e 544) estão sem OS, então nenhum dado de hoje mostraria o buraco.

    🚨 A LIGAÇÃO GANHA DA COLUNA quando as duas falam da mesma OS: ela sabe
    **qual placa** gerou aquela OS, e a coluna não.

    ⚠️ A CHAVE SAI COMO INTEIRO dos dois lados: `numero_ordem` é `integer` na
    tabela de ligação e **TEXT** na solicitação (herança da migração 074), e
    sem a conversão `17099` nunca casaria com `"17099"`.
    """
    def _int(valor):
        try:
            return int(valor) if valor is not None else None
        except (TypeError, ValueError):
            return None

    campos = """s.id AS solicitacao_id, s.criada_em, s.estado, s.valores,
                  f.titulo AS formulario, f.slug,
                  c.nome AS cliente_nome,
                  (SELECT count(*) FROM formulario_arquivo a
                    WHERE a.solicitacao_id = s.id) AS anexos"""
    juncoes = """JOIN formulario f ON f.id = s.formulario_id
             LEFT JOIN cliente c ON c.id = s.cliente_id"""

    por_numero = {}
    # Primeiro a coluna antiga, para a ligação poder sobrescrever.
    for linha in banco.varios(
            f"""SELECT s.numero_ordem, NULL::varchar AS placa, {campos}
                  FROM formulario_solicitacao s
                  {juncoes}
                 WHERE s.numero_ordem IS NOT NULL"""):
        numero = _int(linha["numero_ordem"])
        if numero is not None:
            por_numero[numero] = linha

    for linha in banco.varios(
            f"""SELECT x.numero_ordem, x.placa, {campos}
                  FROM solicitacao_os x
                  JOIN formulario_solicitacao s ON s.id = x.solicitacao_id
                  {juncoes}
                 WHERE x.numero_ordem IS NOT NULL"""):
        numero = _int(linha["numero_ordem"])
        if numero is not None:
            por_numero[numero] = linha

    return por_numero


def _iso_da_previsao(valor) -> str | None:
    """`dd/mm/aaaa HH:MM:SS` do Harmonit -> ISO, que é o que a tela sabe ler.

    🚨 O CONTRATO COM A TELA É UM FORMATO SÓ. Antes daqui o `quadro` devolvia
    ISO para o card de solicitação (`timestamptz` do Postgres) e brasileiro
    para o card de OS (texto do Harmonit) -- dois formatos no mesmo campo, e o
    navegador calado no segundo.

    ⚠️ Formato que eu não conheço devolve `None`, e `None` a tela já sabe
    tratar (não escreve a linha). O que não se pode é devolver o texto cru e
    deixar o `new Date` decidir.
    """
    if not valor:
        return None
    texto = str(valor).strip()
    for forma in ("%d/%m/%Y %H:%M:%S", "%d/%m/%Y %H:%M", "%d/%m/%Y"):
        try:
            return datetime.strptime(texto, forma).isoformat()
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(texto).isoformat()
    except ValueError:
        log.warning("data_previsao em formato desconhecido no card: %r", texto)
        return None


def _nomes_de_cliente(ids: set) -> dict:
    """`harmonit_id` (texto) -> nome, do nosso cadastro.

    ⚠️ O `harmonit_id` é TEXT neste banco e inteiro na OS. A conversão é aqui,
    uma vez — e não em toda junção.
    """
    if not ids:
        return {}
    linhas = banco.varios(
        "SELECT harmonit_id, nome FROM cliente WHERE harmonit_id = ANY(%s)",
        ([str(i) for i in ids],))
    return {linha["harmonit_id"]: linha["nome"] for linha in linhas}


def quadro(painel: str, so_abertas: bool = True,
           busca: str | None = None,
           ordem: str = "prazo") -> dict:
    """O painel inteiro: as colunas, na ordem, com os cards de cada uma.

    🔵 **D8 dele (29/10):** o card é a OS, **de qualquer origem** — *"seja pelo
    painel, seja pelo FPSL, seja pelo formulario, seja a mão"*.

    🚨 O QUADRO É A UNIÃO DE DUAS FONTES, e a ordem importa:
      1. **as OS do ERP** desde a data matriz (D9), lidas pela ponte do FPSL;
      2. **as nossas solicitações** que já têm OS, que entram para quem a OS
         não veio na lista da ponte — OS anterior à data matriz, finalizada com
         o interruptor ligado, ou a ponte fora do ar.
    A deduplicação é pelo `numero_ordem`: a mesma OS não vira dois cards.

    ⚠️ PONTE FORA DO AR NÃO ESVAZIA O PAINEL: a tela cai para a fonte 2 e
    `ponte_respondeu` vem falso, para a tela DIZER que está vendo menos.
    Quadro vazio por falha de rede faria o operador concluir que não há
    trabalho — e é justo nessa hora que há.
    """
    if painel not in PAINEIS:
        raise DadoInvalido("Painel desconhecido.")
    if painel not in COM_TELA:
        # ⚠️ A frase diz o que É, não "erro": as outras três estão desenhadas e
        # esperando decisão dele, e quem bater aqui tem de saber disso.
        raise DadoInvalido(
            f"O painel {PAINEIS[painel]} ainda não existe — só o da Operação "
            f"entrou nesta volta.")

    desde = data_matriz()

    # ---- fonte 1: as OS do ERP, pela ponte -------------------------------
    ponte_respondeu, ponte_motivo, os_do_erp = True, None, []
    try:
        resposta = fpsl_ponte.os_por_situacao(desde, so_abertas=so_abertas)
        os_do_erp = resposta.get("os") or []
    except Exception as e:  # noqa: BLE001 -- qualquer falha da ponte
        # 🚨 NÃO ESTOURA: ver o docstring. A tela mostra menos e diz isso.
        log.warning("painel %s: a ponte do FPSL nao respondeu: %s", painel, e)
        ponte_respondeu, ponte_motivo = False, str(e)

    # ---- fonte 2: as nossas solicitações ---------------------------------
    linhas = banco.varios(
        """SELECT s.id, s.criada_em, s.estado, s.valores, s.os_id,
                  s.numero_ordem, s.situacao_id, s.situacao_em,
                  f.titulo AS formulario, f.slug,
                  c.nome AS cliente_nome,
                  (SELECT count(*) FROM formulario_arquivo x
                    WHERE x.solicitacao_id = s.id) AS anexos
             FROM formulario_solicitacao s
             JOIN formulario f ON f.id = s.formulario_id
             LEFT JOIN cliente c ON c.id = s.cliente_id
            WHERE f.painel = %s
            ORDER BY s.id DESC""", (painel,))

    por_os = _solicitacoes_por_os()
    # Lido a cada montagem, de propósito -- ver `_mapa_de_painel`.
    mapa_de_painel = _mapa_de_painel()
    # 🔵 Bloco C: de quando é a etapa atual de cada OS. 🚨 UMA consulta para
    # todos os cards -- ver `passagem.etapa_desde`.
    numeros_do_erp = [o.get("numero_os") for o in os_do_erp
                      if o.get("numero_os")]
    desde_a_etapa = passagem.etapa_desde(numeros_do_erp)
    # 🔵 Bloco F: quantos recados cada OS tem. ⚠️ O card fechado mostra so o
    # NUMERO -- recado e para ler no card aberto, e um trecho no card fechado
    # faria a coluna crescer sem limite.
    quantos_recados = passagem.quantas_observacoes(numeros_do_erp)
    nomes = _nomes_de_cliente({o.get("cliente_id") for o in os_do_erp
                               if o.get("cliente_id")})

    # 🚨 ANTES DE DISTRIBUIR: a OS cuja situacao tem etapa noutro painel ganha
    # o card dela LA. Aqui porque este e o unico lugar que ja leu a ponte --
    # e dentro de `try` porque semear e efeito colateral: falhar nao pode
    # tirar o quadro do ar.
    try:
        pipeline.semear_os(os_do_erp)
    except Exception:  # noqa: BLE001
        log.exception("painel %s: nao deu para semear os cards dos outros "
                      "paineis", painel)

    conhecidas = {sid for sid, _ in SITUACOES}
    colunas = [{"chave": f"s{sid}", "titulo": nome, "situacao_id": sid,
                "nota": None, "cards": []} for sid, nome in SITUACOES]
    # 🔵 A COLUNA `Chamados` VEM NA FRENTE DAS 17, e so no painel da Operacao
    # -- *"antes de 'Nova solicitacao'"*. ⚠️ `situacao_id` NULO e o que a marca
    # como etapa nossa: a tela ja nao desenha a linha *"situacao N no Harmonit"*
    # quando ele e nulo, e o arrasto ja esta desligado para card sem OS.
    # 🔵 11/11: AS ETAPAS NOSSAS ENTRAM ONDE ELAS DIZEM QUE ENTRAM. A
    # `Chamados` vem na frente de todas (`depois_da_situacao` nulo) e a
    # `Serviço Realizado` **entre a 1316 e a 15694** -- que é a ordem que ele
    # descreveu: *"moverão para la e depois auditarão o card e por fim,
    # atendimento finalizado"*.
    #
    # 🚨 "ENTRE" NÃO SE DIZ COM UM NÚMERO SOLTO: a etapa carrega a situação
    # DEPOIS da qual ela aparece (migração 105). Renumerar as 17 no banco seria
    # copiar para cá uma lista que vive no código e que o ERP manda.
    #
    # ⚠️ `situacao_id` NULO é o que marca a coluna como nossa: a tela usa isso
    # para saber que mover ali não escreve no ERP.
    etapas_nossas = (pipeline.etapas_nossas_da_operacao()
                     if painel == "operacao" else [])
    for etapa in etapas_nossas:
        coluna = {"chave": f"e{etapa['id']}", "titulo": etapa["titulo"],
                  "situacao_id": None, "etapa_id": etapa["id"],
                  "nota": None, "cards": []}
        # A `Chamados` mantém a chave histórica: 22 travas e o arrasto a usam.
        if etapa["titulo"] == "Chamados":
            coluna["chave"] = CHAVE_CHAMADOS
        depois = etapa.get("depois_da_situacao")
        if depois is None:
            colunas.insert(0, coluna)
            continue
        onde = next((i for i, c in enumerate(colunas)
                     if c["situacao_id"] == depois), None)
        # ⚠️ Âncora que não existe mais (situação renomeada ou fora das 17) põe
        # a coluna no FIM, e não a esconde: coluna sumida leva card com ela.
        colunas.insert(onde + 1 if onde is not None else len(colunas), coluna)

    por_chave = {c["chave"]: c for c in colunas}

    # 🚨 AS OS QUE ESTÃO NUMA ETAPA NOSSA NÃO VÃO PARA A COLUNA DA SITUAÇÃO
    # DELAS. É o card com duas posições: a OS segue em 1316 no Harmonit e o
    # card mora aqui até alguém movê-lo para `Atendimento finalizado`.
    os_em_etapa_nossa = {}
    if painel == "operacao" and etapas_nossas:
        aba = pipeline.aba_por_codigo(ABA_DA_OPERACAO)
        if aba:
            os_em_etapa_nossa = pipeline.cards_por_os(aba["id"])

    # 🚨 O que não tem coluna é CONTADO, não escondido (ver o cabeçalho).
    falhas = chamado_os.falhas_em_aberto(painel)
    # 🚨 E O OUTRO CASO, que ele achou na tela: solicitação sem OS e **sem
    # tentativa**. Até 29/10 isso era o normal (a OS nascia por botão), e
    # chamá-lo de "a escrita falhou" é a tela mentindo -- ninguém escreveu.
    nunca_tentadas = chamado_os.sem_tentativa(painel)
    # 🔵 Ele, 29/10: o NÚMERO do chamado vale mais que a contagem.
    quais_nunca = chamado_os.quais_sem_tentativa(painel)
    fora = {"sem_os": 0, "situacao_fora": 0, "situacoes": [],
            # 🔵 11/11: quantas OS desta leitura moram agora em OUTRO painel.
            # ⚠️ Nao e defeito nem pendencia: e informacao, e a tela a escreve
            # como informacao -- "2 OS estao no painel Financeiro", nao "2 OS
            # fora do quadro".
            "noutro_painel": 0,
            "os_falhou": falhas["quantas"],
            "os_falhou_chamados": falhas["chamados"],
            "os_falhou_em": falhas["ultima"],
            # ⚠️ "Nunca se tentou" é outra coisa de "falhou", e a tela escreve
            # frases diferentes.
            "sem_tentativa": nunca_tentadas,
            # Os números, até 5. Ver `quais_sem_tentativa`.
            "sem_tentativa_quais": quais_nunca[:5],
            # 🚨 E as OS que não têm coluna saem com NÚMERO e situação, não só
            # contadas: "OS 17050 está em situação 0 no Harmonit" é uma frase
            # que leva a algum lugar; "1 com situação fora das 17" não é.
            "fora_quais": []}

    vistos = set()

    def _colocar(card: dict, situacao) -> None:
        """Põe o card na coluna da situação dele, ou conta como fora.

        🔵 11/11: ou na ETAPA NOSSA, quando a OS está pousada numa.
        """
        etapa_nossa = os_em_etapa_nossa.get(card.get("numero_ordem"))
        if etapa_nossa:
            alvo = por_chave.get(f"e{etapa_nossa}")
            if alvo is not None:
                # ⚠️ O card leva a situação REAL do ERP junto: é ela que a
                # trava de concorrência compara quando alguém o mover de volta.
                alvo["cards"].append(card)
                return
        # 🚨 REENDERECADA NAO E "FORA DO QUADRO". A linha do `fora_do_quadro`
        # avisa *"ha OS que nenhuma coluna mostra"*; estas estao noutro
        # painel, por decisao dele. Conta-las ali seria a tela mentindo (M12)
        # -- e foi o primeiro efeito que a medicao mostrou depois de tirar as
        # tres colunas.
        if situacao in SITUACOES_REENDERECADAS:
            fora["noutro_painel"] += 1
            return
        if situacao not in conhecidas:
            fora["situacao_fora"] += 1
            # ⚠️ O número cru entra na lista, nunca um rótulo inventado -- é a
            # régua do grid do FPSL: *"estado desconhecido mostra o valor
            # cru"*. 🚨 `0` e `NULL` entram SEPARADOS: `0` é "o ERP gravou
            # zero" e `NULL` é "a varredura não leu", e são 129 OS com `0` no
            # cache. O que fazer com elas é decisão dele.
            if situacao not in fora["situacoes"]:
                fora["situacoes"].append(situacao)
            if len(fora["fora_quais"]) < 5:
                fora["fora_quais"].append(
                    {"numero_os": card.get("numero_ordem"),
                     "situacao_id": situacao})
            return
        por_chave[f"s{situacao}"]["cards"].append(card)

    # 🔵 A FILA DAS PASSAGENS — migração 115, decisão dele de 18/11:
    # *"assim op não para de trabalhar e seguimos no background com a OS"*.
    #
    # 🚨 É AQUI QUE O CARD ANDA ANTES DO ERP. O quadro lê o `situacao_id` do
    # cache do FPSL, varrido a cada 5 min; a fila guarda o que o operador já
    # decidiu. ⚠️ Sem esta linha o card voltaria para a coluna antiga na
    # próxima abertura do painel -- e a pessoa concluiria que não gravou e
    # moveria de novo, que é exatamente o laço de 7 cliques da OS 17133.
    pendentes = passagem.pendentes_por_os()

    # ---- os cards das OS do ERP ------------------------------------------
    for o in os_do_erp:
        numero = o.get("numero_os")
        if numero in vistos:
            continue
        vistos.add(numero)
        s = por_os.get(numero)
        # ⚠️ OS de outro painel não entra: a solicitação que a gerou diz de
        # quem ela é. OS sem solicitação (origem FPSL ou à mão) é da Operação
        # por decisão D8 -- e é a maioria hoje.
        if s and s["slug"] and mapa_de_painel.get(s["slug"]) != painel:
            continue
        _colocar({
            "id": (s or {}).get("solicitacao_id"),
            "origem": "formulario" if s else "erp",
            "formulario": (s or {}).get("formulario"),
            "slug": (s or {}).get("slug"),
            # 🚨 ISO, SEMPRE. A OS do ERP traz `dd/mm/aaaa HH:MM:SS`, que o
            # JavaScript NÃO sabe ler (`new Date(...)` = Invalid Date) -- e por
            # causa disso o "há 2 dias" do card não aparecia em NENHUM dos 10
            # cards reais. Era o efeito que ele aprovou no mockup.
            # ⚠️ Eu conhecia a armadilha do lado da ponte (o corte por data usa
            # `_PREVISAO_ISO` justamente por isso) e mandei o texto cru para o
            # navegador.
            "criada_em": ((s or {}).get("criada_em")
                          or _iso_da_previsao(o.get("data_previsao"))),
            "estado": (s or {}).get("estado"),
            "cliente": ((s or {}).get("cliente_nome")
                        or nomes.get(str(o.get("cliente_id")))),
            "cliente_id": o.get("cliente_id"),
            "resumo": _resumo((s or {}).get("valores")) or None,
            "anexos": (s or {}).get("anexos") or 0,
            "os_id": o.get("os_id"),
            "numero_ordem": numero,
            "situacao_id": o.get("situacao_id"),
            "situacao_em": None,
            # 🚨 O que só a OS sabe, e que o card de solicitação não tinha:
            "tipo_nome": o.get("tipo_nome"),
            "status_str": o.get("status_str"),
            "finalizada": o.get("finalizada"),
            "placas": o.get("placas") or [],
            "tecnicos": o.get("tecnicos") or [],
            # ⚠️ QUANDO ESTE DADO FOI LIDO DO ERP. A varredura roda a cada
            # 5 min, e a tela tem de poder dizer isso em vez de deixar o
            # operador supor que é agora.
            #
            # 🚨 E O CAMPO E `atualizado_em`, NAO `visto_em` -- eu li o nome e
            # supus o significado. Medido no `storage.salvar_os_historico`:
            # `visto_em` e **a primeira vez** que a OS foi vista e e
            # PRESERVADO em toda atualizacao; quem guarda a ultima leitura e
            # `atualizado_em`. Achado na prova do Bloco D: movi a OS, o cache
            # atualizou a situacao na hora, e o card seguiu dizendo "lido do
            # Harmonit 01/10". Rotulo que mente sobre frescor e pior que
            # rotulo nenhum, porque ele existe exatamente para isso.
            "visto_em": o.get("atualizado_em") or o.get("visto_em"),
            # 🔵 BLOCO C — os dois tempos. ⚠️ `etapa_desde` NULO quer dizer
            # "não medido", e a tela DIZ isso: a `os_passagem` começou em
            # 29/10, então OS nunca movida por aqui não tem de onde tirar o
            # tempo da etapa. Mostrar "0h" seria afirmar o que ninguém mediu.
            "etapa_desde": (desde_a_etapa.get(numero) or {}).get("em"),
            # 🔵 Bloco F -- ver o comentario em `quantos_recados`.
            "observacoes": quantos_recados.get(numero) or 0,
            # 🔵 *"a prioridade vem escrita porque ela nasce Normal e mudar e
            # excecao, e excecao precisa estar visivel sem abrir"*.
            "prioridade": o.get("prioridade"),
            "prioridade_nome": passagem.PRIORIDADES.get(o.get("prioridade")),
            # 🔵 ÁREA E (05/11) — O TERMO NO CARD. *"termo no card e busca por
            # termo"*. 🚨 Ele NÃO é campo da OS no Harmonit: vive dentro do
            # texto da `descricao`, e a ponte o extrai e o guarda no cache
            # (`fpsl_weso/termo_da_os.py`). Sem isso, procurar uma OS pelo
            # termo custaria uma leitura do ERP por card.
            # ⚠️ NULO É O CASO NORMAL em 1 de cada 7: venda, cartão RFID e
            # manutenção não nascem de termo (medido: 27 de 200 OS em 05/11).
            # A tela escreve só o número da OS -- não existe "sem termo"
            # escrito no card, que seria ruído em 85 cards.
            "termo": o.get("termo"),
            # 🚨 O SELO, e ele é obrigatório junto com o card andar. Card que
            # anda sem garantia e sem dizer é tela que mente (`M12`) -- pior
            # que o erro honesto de antes, porque ninguém desconfia.
            "passagem_pendente": numero in pendentes,
            "pendente_desde": (pendentes.get(numero) or {}).get("pendente_desde"),
            "pendente_tentativas": (pendentes.get(numero) or {}).get("tentativas"),
            "pendente_erro": (pendentes.get(numero) or {}).get("pendente_erro"),
            # ⚠️ Onde o ERP ainda está, quando diferem. A tela pode dizer as
            # duas coisas: onde o card está e o que a OS ainda diz.
            "situacao_do_erp": (o.get("situacao_id")
                                if numero in pendentes else None),
        # 🚨 A COLUNA SAI DA FILA quando há pendência, e do cache quando não há.
        }, ((pendentes[numero]["para_situacao"]) if numero in pendentes
            else o.get("situacao_id")))

    # ---- os cards de CHAMADO, que nao sao OS ----------------------------
    # 🚨 ESTES VEM DO MOTOR DE ETAPAS NOSSAS (`movizap/pipeline.py`), e nao da
    # ponte: chamado nao tem OS, entao nao ha o que pedir ao Harmonit.
    # ⚠️ UMA LEITURA PARA TODAS AS ETAPAS NOSSAS, e nao uma por etapa: sao duas
    # hoje (`Chamados` e `Servico Realizado`) e serao mais.
    # 🚨 E O CARD DE CHAMADO SO ENTRA NA COLUNA DELE: card com `numero_os` ja
    # foi colocado pelo `_colocar`, junto da OS -- aqui entram so os que nao
    # tem OS, que e o que faz deles um chamado.
    if etapas_nossas:
        aba_nossa = pipeline.aba_por_codigo(ABA_DA_OPERACAO)
        por_etapa = {e["id"]: e for e in etapas_nossas}
        if aba_nossa:
            for c in pipeline.cards_da_aba(aba_nossa["id"],
                                           teto=TETO_CARDS_POR_COLUNA):
                if c.get("numero_os"):
                    continue
                # 🚨 O FILTRO "SO AS ABERTAS" ALCANCA O CHAMADO desde 12/11.
                # 🔵 Dele: *"por estarem inativos, o filtro na tela nao deveria
                # exibi-los, pois so exibe abertos"*.
                # 📏 Medido antes: ligado ou desligado, a coluna devolvia os
                # MESMOS 5 cards, com 2 concluidos no meio -- o `so_abertas`
                # ia so na leitura da ponte e filtrava as OS do ERP; o card de
                # chamado vem do nosso banco por outro caminho e ninguem olhava
                # o desfecho dele.
                # ⚠️ FILTRA, NAO APAGA: com o interruptor desligado o card
                # volta, esmaecido e no fim da fila. Sumir de vez tiraria o
                # caminho de reabrir.
                if so_abertas and c.get("desfecho"):
                    continue
                etapa = por_etapa.get(c["etapa_id"])
                if not etapa:
                    continue
                chave = (CHAVE_CHAMADOS if etapa["titulo"] == "Chamados"
                         else f"e{etapa['id']}")
                alvo = por_chave.get(chave)
                if alvo is not None:
                    alvo["cards"].append(_card_do_chamado(c, nomes))

    # ---- os cards das nossas solicitações que a ponte não trouxe ---------
    for linha in linhas:
        if not linha["os_id"]:
            fora["sem_os"] += 1
            continue
        numero = linha["numero_ordem"]
        try:
            numero_int = int(numero) if numero is not None else None
        except (TypeError, ValueError):
            # ⚠️ `numero_ordem` é TEXT na solicitação e INTEGER na OS. Valor
            # que não é número não casa com nada -- e não derruba o quadro.
            numero_int = None
        if numero_int is not None and numero_int in vistos:
            continue
        if numero_int is not None:
            vistos.add(numero_int)
        _colocar({
            "id": linha["id"],
            "origem": "formulario",
            "formulario": linha["formulario"],
            "slug": linha["slug"],
            "criada_em": linha["criada_em"],
            "estado": linha["estado"],
            "cliente": linha["cliente_nome"],
            "cliente_id": None,
            "resumo": _resumo(linha["valores"]),
            "anexos": linha["anexos"],
            "os_id": linha["os_id"],
            "numero_ordem": linha["numero_ordem"],
            "situacao_id": linha["situacao_id"],
            "situacao_em": linha["situacao_em"],
            # 🚨 NULOS DE PROPÓSITO: estes campos vêm da OS, e esta OS não veio
            # na lista da ponte. Preencher com o que o nosso banco "acha" seria
            # inventar estado do ERP.
            "tipo_nome": None,
            "status_str": None,
            "finalizada": None,
            "placas": [],
            "tecnicos": [],
            "visto_em": None,
            # ⚠️ Nulo pelo mesmo motivo dos campos acima: esta OS não veio na
            # lista da ponte, então não se mediu a etapa dela.
            "etapa_desde": None,
            "observacoes": 0,
            "prioridade": None,
            "prioridade_nome": None,
            # ⚠️ Nulo pelo mesmo motivo dos vizinhos: o termo mora na OS, e
            # esta OS não veio na lista da ponte.
            "termo": None,
        }, linha["situacao_id"])

    # ----------------------------------------------------------------------
    # 🔵 O FILTRO E A ORDEM — *"filtros para os cards, por cliente, OS, placa
    # // ordenadores tbm"*.
    # ----------------------------------------------------------------------
    # 🚨 FILTRA NO SERVIDOR, não na tela, e a razão é medida: o teto por coluna
    # é 50 e o do quadro é 600. Filtrar no navegador esconderia o que o teto já
    # cortou, e a pessoa procuraria uma OS que o servidor nem mandou.
    #
    # ⚠️ UMA CAIXA SÓ para os QUATRO campos, e não quatro caixas (o termo
    # entrou em 05/11, área E): quem procura tem
    # um número ou um nome na mão e não quer decidir em qual caixa ele vai. O
    # que casa é dito em `filtro_casou_por`, para a tela poder mostrar.
    casou_por = set()
    if busca:
        alvo = _normalizar(busca)
        for coluna in colunas:
            ficam = []
            for card in coluna["cards"]:
                onde = _onde_casa(card, alvo)
                if onde:
                    casou_por.update(onde)
                    ficam.append(card)
            coluna["cards"] = ficam

    for coluna in colunas:
        coluna["cards"] = _ordenar(coluna["cards"], ordem)

    total = 0
    for coluna in colunas:
        coluna["total"] = len(coluna["cards"])
        total += coluna["total"]
        coluna["cards"] = coluna["cards"][:TETO_CARDS_POR_COLUNA]

    # 🔵 04/11: o selo do checklist no card fechado ("2 de 3"), para o operador
    # ver sem precisar abrir. ⚠️ UMA consulta para todos os cards -- o quadro
    # desenha até 50 por coluna, e uma por card seriam 850 (o molde é
    # `passagem.quantas_observacoes`).
    #
    # ⚠️ Conta o checklist da etapa em que o card ESTÁ: o das anteriores já
    # virou observação e não é mais tarefa.
    # ⚠️ `numero_ordem` NÃO É SEMPRE INTEIRO: o card do ERP traz número e o da
    # solicitação pode trazer o texto do legado. Misturar os dois no `= ANY`
    # faz o Postgres recusar a consulta inteira (`cannot dump lists of mixed
    # types`) -- achado pelo teste do painel, não por leitura.
    numeros_de_card = []
    for col in colunas:
        for c in col["cards"]:
            try:
                numeros_de_card.append(int(c["numero_ordem"]))
            except (TypeError, ValueError):
                continue    # sem número de OS não há checklist a contar
    marcas = checklist.resumo(numeros_de_card) if numeros_de_card else {}
    etapas_com_lista = checklist.etapas_com_modelo()
    for col in colunas:
        for card in col["cards"]:
            try:
                chave = (int(card["numero_ordem"]), card.get("situacao_id"))
            except (TypeError, ValueError):
                chave = None
            card["checklist"] = marcas.get(chave) if chave else None
            # 🚨 "tem lista e ninguém abriu ainda" é diferente de "não tem
            # lista nenhuma": o primeiro mostra "0 de N", o segundo não mostra
            # nada. Sem este campo a tela não conseguiria dizer a diferença.
            # ⚠️ Card de chamado nao tem checklist: `situacao_id` e nulo, e
            # `_etapa_conhecida` do checklist exige uma das 17. Nao foi pedido,
            # e forcar faria o checklist tratar a coluna nova como etapa do ERP.
            card["tem_checklist"] = card.get("situacao_id") in etapas_com_lista

    return {
        "painel": painel,
        "titulo": PAINEIS[painel],
        "colunas": colunas,
        "total": total,
        # 🔵 D9: desde quando o quadro monta, e a tela DIZ isso.
        "desde": desde,
        "so_abertas": so_abertas,
        # 🔵 O filtro e a ordem, devolvidos para a tela DIZER o que está
        # aplicado -- quadro filtrado que não diz que está filtrado é a mesma
        # família do `M12`.
        "busca": busca or None,
        "ordem": ordem,
        "filtro_casou_por": sorted(casou_por) or None,
        "ordens": list(ORDENS),
        # 🚨 A tela tem de dizer quando está vendo menos. Ver o docstring.
        "ponte_respondeu": ponte_respondeu,
        "ponte_motivo": ponte_motivo,
        # 🚨 O que não tem coluna. A tela só escreve se algum for maior que
        # zero -- `M12` sem encher a tela de aviso.
        "fora_do_quadro": fora,
        # 🔵 MOVER EXISTE DESDE 29/10 (Bloco D), por decisão dele: *"O card
        # pode ser por arrastar"*. ⚠️ Quem move é quem alcança a tela, e hoje a
        # `PNL_1.1` é de permissão `owner` — *"pode mover que tiver acesso a
        # tela, por enquanto somente owner"*. Então este campo é `True` para
        # quem chegou até aqui: a permissão foi cobrada na rota.
        #
        # 🚨 E A ORDEM É LIVRE: *"que tal de caminho proibido é esse??"*. Não há
        # mapa de transições, nem aqui nem na ponte — o Harmonit também não tem.
        "pode_mover": True,
    }


def _etapa_dos_chamados() -> dict | None:
    """A etapa `Chamados`, pelo motor.

    ⚠️ SUBIU PARA O `pipeline.py` em 05/11 porque o ENVIO do formulario
    tambem precisa dela, e o `main` nao ia chamar um `_privado` do painel.
    Fica aqui o nome curto, que o resto deste modulo ja usa.
    """
    return pipeline.etapa_dos_chamados()


def _card_do_chamado(c: dict, nomes: dict, da_os: dict | None = None) -> dict:
    """O card de um chamado, no MESMO contrato de chaves do card de OS.

    🚨 O CONTRATO E UNICO DE PROPOSITO: a tela desenha um card so, e um
    segundo formato faria dois caminhos de desenho para a mesma caixa. O que
    muda sao os NULOS -- e eles sao a mesma regua do card de solicitacao sem
    OS, que ja existia.

    ⚠️ `numero_ordem` NULO e o que mantem o card nao-arrastavel e sem
    `<select>` de mover: as duas guardas da tela olham esse campo, e o chamado
    nao tem situacao para gravar no ERP.
    """
    valores = c.get("valores") or {}
    return {
        # """ + S + """ O `id` aqui e o do CARD DE PIPELINE, nao o da solicitacao: e por
        # ele que a tela move, finaliza e reabre.
        "id": c["id"],
        # 🚨 O RÓTULO DA ORIGEM DEIXOU DE MENTIR em 18/11, e isto veio de uma
        # pergunta dele: *"Então pq os cards informam que não vem de OS no
        # painel?"*
        #
        # 📏 Os 8 cards do Financeiro naquele dia eram TODOS OS (17120, 17119,
        # 17122, 17127, 17125, 17129, 17134, 17136), e nenhum veio de
        # formulário -- a `formulario_solicitacao` não tinha uma linha dos 4
        # formulários que apontam a etapa 875. Quem os trouxe foi
        # `recebe_situacao = 15746`. E ainda assim este campo dizia "chamado",
        # e a tela usava isso para pintar a borda cujo próprio comentário
        # afirmava *"ele não é uma OS"*.
        #
        # ⚠️ O NOME NOVO DIZ AS DUAS COISAS porque as duas são verdade: é uma
        # OS do ERP **e** está numa etapa nossa. Nenhum dos dois lados some.
        "origem": "erp_em_etapa_nossa" if c.get("numero_os") else "chamado",
        # ⚠️ A ETAPA VEM NO CARD desde 05/11: a tela das abas compara
        # `card.etapa_id` com `coluna.etapa_id` para nao chamar a rota quando o
        # card e solto na propria coluna. Sem ela a comparacao era
        # `undefined === 1`, e todo solto ia a rota.
        "etapa_id": c["etapa_id"],
        "solicitacao_id": c["solicitacao_id"],
        "formulario": c.get("formulario"),
        "slug": c.get("slug"),
        "criada_em": c.get("solicitada_em") or c["criado_em"],
        "estado": None,
        "cliente": (_nome_do_chamado(valores)
                    or nomes.get(str(c.get("cliente_id")))),
        "cliente_id": c.get("cliente_id"),
        "resumo": _resumo(valores) or None,
        "anexos": 0,
        # 🚨 A CHAVE DE EXIBICAO DA OS, e ela e SEPARADA do `numero_ordem`
        # de proposito (11/11): desde a migracao 106 ha card COM OS em etapa
        # nossa -- as OS reenderecadas para os paineis Financeiro, Pos-venda e
        # Contratual. O operador precisa ver QUAL OS e.
        #
        # ⚠️ E `numero_ordem` CONTINUA NULO: e esse nulo que as duas guardas da
        # tela leem para manter o card nao-arrastavel e sem `<select>` de
        # mover. Reusar o `numero_ordem` para exibir ligaria o arrasto para o
        # ERP numa aba cujo mover escreve so no nosso banco.
        "numero_os": c.get("numero_os"),
        # ⚠️ OS DOIS NULOS QUE FAZEM O CARD SER DA ABA, e eles ficam:
        # `numero_ordem` e `situacao_id` sao o que as guardas da tela leem
        # para manter o card nao-arrastavel e sem `<select>` de mover. A aba
        # move no NOSSO banco; encher qualquer um dos dois ligaria o arrasto
        # ao Harmonit.
        "os_id": None,
        "numero_ordem": None,
        "situacao_id": None,
        "situacao_em": None,
        # 🔵 12/11, dele: *"nos cards do financeiro, faltam informacoes sobre
        # o tipo do termo, numero do termo"* e *"igual da OP"*.
        #
        # 🚨 ESTES VINHAM NULOS SEM MOTIVO. O card da Operacao (`origem: erp`)
        # ja mostrava todos, e a leitura da ponte que os traz JA ERA FEITA
        # pelo `quadro_da_aba` para semear -- e jogada fora depois. Nenhuma
        # chamada nova: so parei de descartar o que ja estava na mao.
        #
        # ⚠️ `da_os` e None quando o card nao tem OS (o chamado de verdade) ou
        # quando a ponte nao respondeu. Nos dois casos volta a ser nulo, que e
        # o que a tela ja sabe desenhar.
        "tipo_nome": (da_os or {}).get("tipo_nome"),
        "status_str": (da_os or {}).get("status_str"),
        "finalizada": (da_os or {}).get("finalizada"),
        "placas": (da_os or {}).get("placas") or [],
        "tecnicos": (da_os or {}).get("tecnicos") or [],
        "visto_em": (da_os or {}).get("visto_em"),
        # 🔵 11/11: *"controle de atraso o contador de tempo de etapa"*.
        # 🚨 ERA `None` FIXO, E A TELA DIZIA "não medido" EM TODO CARD DE
        # CHAMADO -- o contador existia no `PainelOperacao.vue` desde o Bloco C
        # e nunca teve o que mostrar aqui. Agora vem da `pipeline_passagem`,
        # pelo `cards_da_aba`.
        "etapa_desde": c.get("etapa_desde"),
        # 🔵 *"Abrirá com prazo de 24hrs uteis (08:00 - 18:00) para conclusão,
        # apenas informativo do card e controle de atraso"*, com a janela que
        # ele fixou depois: 08:30-17:00.
        # ⚠️ INFORMATIVO: nada no card depende disto para funcionar.
        "prazo": horas_uteis.prazo_do_chamado(c.get("criado_em")),
        "observacoes": c.get("observacoes") or 0,
        "prioridade": (da_os or {}).get("prioridade"),
        "prioridade_nome": passagem.PRIORIDADES.get(
            (da_os or {}).get("prioridade")),
        # 🔵 ÁREA E (05/11): *"termo no card e busca por termo"*. 🚨 O termo
        # NAO e campo da OS no Harmonit -- ele vive dentro do texto da
        # descricao e quem o extrai e o FPSL. Chega pronto na ponte.
        # ⚠️ E NORMAL vir nulo: 📏 medido em 12/11 nas 19 OS do Financeiro,
        # 17 tem termo e 2 nao -- e as duas sem termo sao exatamente as de
        # RESSARCIMENTO (`problema 7524`). Card sem termo mostra so a OS.
        # 🚨 O TERMO DA OS GANHA DO POSTO A MAO, e a tela diz QUAL E A
        # ORIGEM (`termo_a_mao`). Quando a OS existe, o numero dela e o
        # oficial; o digitado preenche so a janela entre assinar e gerar a OS.
        # Tela que mostra digitado com cara de oficial e tela mentindo (`M12`).
        "termo": (da_os or {}).get("termo") or c.get("termo"),
        "termo_a_mao": bool(not (da_os or {}).get("termo") and c.get("termo")),
        "termo_por_nome": c.get("termo_por_nome"),
        "termo_em": c.get("termo_em"),
        # 🔵 O DESFECHO, que e o que faz o card esmaecer e ir para o fim:
        # *"Resolvido encerra o card e ele esmaece e fica no fim da fila
        # arquivado com status de concluido"*.
        "desfecho": c.get("desfecho"),
        "desfecho_em": c.get("desfecho_em"),
        "desfecho_rotulo": pipeline.DESFECHOS.get(c.get("desfecho")),
        "desfecho_por": c.get("desfecho_por_nome"),
        # 🔵 *"no card do chamado, tbm tem um botao de 'abrir conversa'"*. O
        # formulario de suporte coleta `CONTACT_PHONE` como OBRIGATORIO, com
        # validacao de telefone -- entao ele sai normalizado dos `valores`.
        "telefone": _telefone_do_chamado(valores),
    }


def _nome_do_chamado(valores: dict) -> str | None:
    """Quem abriu o chamado -- a empresa, e o nome da pessoa como reserva."""
    for chave in ("COMPANY_TITLE", "CONTACT_NAME"):
        v = (valores or {}).get(chave)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return None


def _telefone_do_chamado(valores: dict) -> str | None:
    """O telefone de quem abriu, para o botao de abrir conversa.

    ⚠️ Pode ser nulo: o campo e obrigatorio no formulario de suporte, mas
    um card criado a mao (quando ele decidir a origem) nao tera. A tela nao
    mostra o botao sem numero, em vez de oferecer um gesto que falha.
    """
    v = (valores or {}).get("CONTACT_PHONE")
    return v.strip() if isinstance(v, str) and v.strip() else None


def quadro_da_aba(codigo_tela: str,
                  so_abertas: bool = True) -> dict | None:
    """O quadro de uma aba de pipeline -- as colunas sao as etapas DELA.

    🔵 05/11: *"a aba 'Operacao' do Movizap e a mesma logica para os
    demais"*, com as colunas que ele escreveu para Treinamentos e Pos-venda.

    🚨 NENHUMA IDA AO HARMONIT AQUI, e e a diferenca inteira em relacao ao
    `quadro()`: as colunas sao nossas, entao nao ha situacao de OS para
    pedir a ponte. Este quadro nao pode ficar vazio porque um terceiro caiu.

    ⚠️ O CONTRATO E O MESMO do quadro da Operacao, de proposito: a tela
    desenha um card so. O que muda e que `situacao_id` e nulo em TODAS as
    colunas -- aqui nao existe coluna do ERP.
    """
    aba = pipeline.aba_por_codigo(codigo_tela)
    if not aba:
        return None
    etapas = pipeline.etapas(aba['id'])

    # 🚨 ESTA ABA SEMEIA O QUE E DESTA ABA, se alguma etapa dela recebe
    # situacao do ERP (migracao 106). ⚠️ Sem isto, o card da OS financeira so
    # nasceria quando alguem abrisse a OPERACAO -- um acoplamento invisivel
    # entre duas telas, e o tipo de coisa que funciona por meses e um dia para
    # sem ninguem entender por que.
    #
    # 🚨 A PROMESSA DO CABECALHO CONTINUA VALENDO: o card e materializado, e a
    # leitura da ponte esta dentro de `try`. Ponte caida = nenhum card NOVO, e
    # nunca quadro vazio -- os cards que ja existem sao linhas no nosso banco.
    # 🚨 O QUE A PONTE DEVOLVE E GUARDADO, nao so usado para semear. 🔵 12/11,
    # dele: *"nos cards do financeiro, faltam informacoes sobre o tipo do
    # termo, numero do termo"*. Esses campos sempre vieram nesta mesma
    # resposta e eram descartados -- o card ficava nulo de graca.
    # ⚠️ Fica VAZIO quando a ponte nao responde, e o card volta a ser o de
    # antes. Nunca quadro vazio: essa promessa e do cabecalho.
    por_os: dict = {}
    if any(e.get('recebe_situacao') for e in etapas):
        try:
            resposta = fpsl_ponte.os_por_situacao(data_matriz(),
                                                  so_abertas=True)
            do_erp = resposta.get('os') or []
            pipeline.semear_os(do_erp)
            por_os = {o.get('numero_os'): o for o in do_erp
                      if o.get('numero_os')}
        except Exception as e:  # noqa: BLE001
            log.warning('aba %s: a ponte nao respondeu ao semear: %s',
                        codigo_tela, e)
    colunas = [{'chave': f"e{e['id']}", 'titulo': e['titulo'],
                'situacao_id': None, 'etapa_id': e['id'],
                'final': e['final'], 'nota': None, 'cards': []}
               for e in etapas]
    por_etapa = {c['etapa_id']: c for c in colunas}

    cards = pipeline.cards_da_aba(aba['id'], teto=TETO_CARDS_POR_COLUNA * 4)
    # 🚨 O MESMO FILTRO DA OPERACAO, e pelo mesmo motivo: card concluido numa
    # aba tambem e card inativo. Hoje ha 1 so em producao, entao nao doi --
    # mas o Financeiro tem 10 etapas e duas finais, e sem isto a fila
    # encheria de concluido com o tempo.
    # ⚠️ Filtra, nao apaga: `so_abertas=False` devolve todos.
    if so_abertas:
        cards = [c for c in cards if not c.get('desfecho')]
    nomes = _nomes_de_cliente({c.get('cliente_id') for c in cards
                              if c.get('cliente_id')})
    for c in cards:
        destino = por_etapa.get(c['etapa_id'])
        # ⚠️ CARD EM ETAPA DESLIGADA NAO SOME EM SILENCIO: ele fica fora do
        # quadro e CONTADO, que e a regua do `fora_do_quadro` (M12).
        if destino is not None:
            destino['cards'].append(
                _card_do_chamado(c, nomes, por_os.get(c.get('numero_os'))))
    for col in colunas:
        # 🚨 O concluido no FIM tambem aqui, pela mesma regua de 11/11.
        col['cards'] = _ordenar(col['cards'], 'prazo')
        col['total'] = len(col['cards'])

    desenhados = sum(c['total'] for c in colunas)
    return {
        'painel': aba['painel'],
        'aba': aba['codigo_tela'],
        'titulo': aba['titulo'],
        # 🚨 06/11: AS ABAS IRMAS, as deste painel e so dele. Achado por ele:
        # *"os itens do pos venda estao aparecendo dentro do financeiro e
        # contratual"*. A tela declarava a lista em CODIGO e filtrava so por
        # permissao -- reusada nos paineis novos, levava a tira do Pos-venda
        # para dentro deles.
        #
        # 🔵 Decisao dele no mesmo minuto: *"o financeiro tera suas proprias
        # abas, mas por agora so 1, o mesmo para o contratual, so o pos venda
        # ja temos as duas pipelines em abas"*. Por isso sai do BANCO: no dia
        # em que o Financeiro ganhar a segunda aba, ela aparece sozinha.
        #
        # ⚠️ O `titulo` daqui e o da ABA (`painel_aba.titulo`), que e onde
        # moram "Treinamentos" e "Pos-venda" -- no registro as duas telas se
        # chamam as duas "Pos-venda". A ROTA nao vem aqui: o frontend a resolve
        # pelo `sessao.telas`, e assim aba que a pessoa nao alcanca cai fora
        # sozinha, sem segunda regua de permissao.
        'abas': [{'codigo_tela': a['codigo_tela'], 'titulo': a['titulo']}
                 for a in pipeline.abas(aba['painel'])],
        'colunas': colunas,
        'total': desenhados,
        'pode_mover': True,
        'fora_do_quadro': len(cards) - desenhados,
        'etapas': etapas,
        'desfechos': pipeline.DESFECHOS,
    }


def _mapa_de_painel() -> dict:
    """`slug` -> painel, lido do banco a cada montagem do quadro.

    🚨 ISTO ERA UM CACHE DE PROCESSO E O CACHE MENTIA. Eu o escrevi com um
    comentário dizendo que ficar velho era "aceitável porque mover formulário
    de painel é cadastro, não operação". **O preço medido é outro:** com o mapa
    velho, `_e_do_painel` devolve `False` para um formulário criado depois do
    primeiro acesso — e o `quadro` então **DESCARTA o card** daquela OS, não o
    rotula errado. Card que desaparece da tela é `M12`, e nenhuma suíte
    reclamaria.

    ⚠️ E na suíte isso fazia o resultado depender da ORDEM dos testes: o
    fixture cria um formulário, e se o cache já tivesse sido povoado antes o
    card do teste simplesmente não aparecia.

    A consulta é 15 linhas, uma por abertura de painel. Eu otimizei o que não
    precisava de otimização e paguei com um caminho de silêncio.
    """
    return {linha["slug"]: linha["painel"]
            for linha in banco.varios("SELECT slug, painel FROM formulario")}


# ----------------------------------------------------------------------------
# O FILTRO E OS ORDENADORES (29/10)
# ----------------------------------------------------------------------------
# 🔵 *"filtros para os cards, por cliente, OS, placa // ordenadores tbm"*.

# ⚠️ As ordens que existem, e cada uma responde a uma pergunta de verdade:
ORDENS = {
    # 🔵 O PADRÃO, por decisão dele: *"o ordenador padrão deve ser por 'Prazo de
    # entrega'"*. ⚠️ CRESCENTE -- prazo mais PRÓXIMO primeiro, que é o que a
    # operação precisa ver.
    #
    # 🚨 ELE SUBSTITUI a antiga "aberta há mais tempo": as duas ordenavam pelo
    # MESMO campo, porque hoje a previsão de entrega **é** a data de criação
    # (medido em 12 de 12 OS). Duas opções com nomes diferentes para a mesma
    # ordem fariam quem escolhe achar que são coisas distintas.
    # ⚠️ Quando a frente do aviso prévio entrar (ela move a previsão em +90
    # dias) as duas deixam de coincidir, e aí faz sentido ter as duas.
    "prazo": "prazo de entrega (mais próximo)",
    "os_desc": "OS, da mais nova",
    "os_asc": "OS, da mais antiga",
    # 🔵 "o que está parado há mais tempo" -- usa o Bloco C
    "parado": "parado há mais tempo nesta etapa",
    "cliente": "cliente (A-Z)",
}


def _normalizar(texto: str) -> str:
    """Minúsculas, sem acento e sem pontuação — para a busca casar de verdade.

    🚨 SEM ACENTO DOS DOIS LADOS: quem procura "veiculo" tem de achar
    "veículo", e quem procura uma placa escreve "ABC-1D23" tanto quanto
    "abc1d23". ⚠️ E insensível a caixa, que é o defeito que a memória desta
    casa chama de varredura-de-rótulo-ignora-caixa.
    """
    import unicodedata
    sem = unicodedata.normalize("NFKD", str(texto or ""))
    sem = "".join(c for c in sem if not unicodedata.combining(c))
    return "".join(c for c in sem.lower() if c.isalnum())


def _onde_casa(card: dict, alvo: str) -> set:
    """Em quais dos quatro campos a busca casou. Vazio = o card sai.

    ⚠️ Devolve ONDE casou, e não só sim/não, porque a tela diz *"casou por
    placa"* -- sem isso, quem procura um número e acha um card não sabe se
    achou a OS ou o cliente.

    🔵 ÁREA E (05/11): o **termo** é o quarto campo. 🚨 E ele é o que mais
    precisa do `casou_por`: termo e número de OS são os dois números de 4-5
    dígitos do card, e sem dizer qual casou quem procura `8937` não sabe se
    achou a OS 8937 ou as 6 OS do termo 8937.
    """
    onde = set()
    if not alvo:
        return onde
    numero = str(card.get("numero_ordem") or "")
    if alvo in _normalizar(numero):
        onde.add("OS")
    if card.get("cliente") and alvo in _normalizar(card["cliente"]):
        onde.add("cliente")
    # ⚠️ O id do cliente também: a operação às vezes tem o código, não o nome.
    if card.get("cliente_id") and alvo in _normalizar(card["cliente_id"]):
        onde.add("cliente")
    for p in (card.get("placas") or []):
        if alvo in _normalizar(p.get("placa")):
            onde.add("placa")
            break
    # 🔵 ÁREA E — o termo. ⚠️ Card sem termo simplesmente não casa por aqui:
    # é 1 de cada 7, e nulo não é "casa com tudo".
    if card.get("termo") and alvo in _normalizar(card["termo"]):
        onde.add("termo")
    return onde


def _ordenar(cards: list, ordem: str) -> list:
    """Ordena os cards de uma coluna. ⚠️ Ordem desconhecida cai no padrão.

    🚨 O CONCLUIDO VAI SEMPRE PARA O FIM, qualquer que seja a ordem escolhida.
    🔵 Regua dele de 11/11: *"Resolvido encerra o card e ele esmaece e fica no
    fim da fila arquivado com status de concluido"*.

    📏 Ela NAO estava valendo, e foi ele quem viu: o `cards_da_aba` ja devolvia
    os arquivados por ultimo, mas esta funcao reordenava tudo e perdia isso --
    os dois concluidos, por serem os mais antigos, iam parar no COMECO da
    coluna.

    ⚠️ E por isso o desfecho entra como PRIMEIRA chave de toda ordem, e nao
    como uma ordem a parte: "mais proximo do vencimento" e "concluido no fim"
    sao duas perguntas diferentes, e a segunda vale sempre.
    """
    def arquivado(c):
        """🚨 `bool`, e nao o texto: `False` ordena antes de `True`, entao o
        aberto vem primeiro sem depender de qual desfecho foi dado."""
        return bool(c.get("desfecho"))

    def numero(c):
        try:
            return int(c.get("numero_ordem") or 0)
        except (TypeError, ValueError):
            return 0

    # 🚨 NULO VAI PARA O FIM em toda ordem por data: card sem a medida não é
    # "o mais antigo do mundo", é card sem a medida.
    def por_data(chave):
        """🚨 NORMALIZA O TIPO, e faltava: o card de solicitação traz a data
        como `datetime` (do `timestamptz` do Postgres) e o card do ERP como
        **texto ISO**. `sorted` não compara os dois -- `TypeError`. Com o prazo
        como ordem PADRÃO isso derrubaria o painel em toda abertura que tivesse
        os dois tipos de card.

        ⚠️ `isoformat()` ordena como texto porque o ISO é lexicograficamente
        ordenado -- é o que permite comparar os dois mundos sem converter o
        texto em data.
        """
        def f(c):
            v = c.get(chave)
            if v is None:
                # 🚨 Nulo vai para o FIM: card sem a medida não é "o mais
                # antigo do mundo", é card SEM a medida.
                return (True, "")
            return (False, v.isoformat() if hasattr(v, "isoformat") else str(v))
        return f

    if ordem == "os_asc":
        return sorted(cards, key=lambda c: (arquivado(c), numero(c)))
    if ordem == "cliente":
        return sorted(cards, key=lambda c: (arquivado(c),
                                            not c.get("cliente"),
                                            _normalizar(c.get("cliente") or "")))
    if ordem in ("prazo", "antiga"):
        # 🔵 O padrão. ⚠️ "antiga" segue aceito para não quebrar link salvo --
        # é o mesmo campo, e o rótulo antigo sumiu da tela.
        return sorted(cards, key=lambda c: (arquivado(c),
                                            por_data("criada_em")(c)))
    if ordem == "parado":
        # 🔵 Usa o Bloco C: quanto mais antiga a última passagem, mais parado.
        # ⚠️ Card SEM passagem vai para o fim, porque "não medido" não é "parado
        # há mais tempo" -- afirmar isso seria inventar.
        return sorted(cards, key=lambda c: (arquivado(c),
                                            por_data("etapa_desde")(c)))
    # ⚠️ Ordem desconhecida cai no PADRAO dele, que e o prazo -- nao no
    # numero da OS. O padrao e um so, em um lugar so.
    return sorted(cards, key=lambda c: (arquivado(c),
                                        por_data("criada_em")(c)))
