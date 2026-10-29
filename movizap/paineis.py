"""Os painéis por setor — a Etapa 3, começando pelo da Operação.

🔵 Decisão dele em 22/10, depois de ver os mockups lado a lado: *"vamos de A
somente para a Operação por enquanto, mas bem documentado para as demais
futuramente"*. A opção A é o **kanban cujas colunas são as 11 situações da OS
do Harmonit** -- a única das três em que mover o card É a ação, e foi esse o
motivo que ele deu para o painel existir: *"hoje ainda não usamos a situação
da OS, por isso o painel e consulta para atualizar a situação no painel"*.

🚨 O QUE ESTE MÓDULO FAZ, E SÓ: lê solicitações e as distribui em colunas.
**Não cria OS e não escreve no Harmonit** -- as duas rotas da ponte (criar OS
e gravar `situacaoId`) são da volta seguinte e dependem de duas decisões dele
(o mapa formulário → `problemaId` e a prioridade). Mover o card, por isso,
ainda não existe: a tela DIZ isso, em vez de oferecer um gesto que não grava.

🚨 OS OUTROS TRÊS PAINÉIS NÃO SÃO ESTE COM OUTRO FILTRO, e é por isso que só
o da Operação nasce agora. O que foi desenhado e medido para cada um está em
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
from datetime import date

from . import banco, chamado_os, fpsl_ponte
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
    (15746, "Financeiro"),
    (15695, "Pós venda"),
    (16492, "Contratual"),
)

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


def quadro(painel: str, so_abertas: bool = True) -> dict:
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
    nomes = _nomes_de_cliente({o.get("cliente_id") for o in os_do_erp
                               if o.get("cliente_id")})

    conhecidas = {sid for sid, _ in SITUACOES}
    colunas = [{"chave": f"s{sid}", "titulo": nome, "situacao_id": sid,
                "nota": None, "cards": []} for sid, nome in SITUACOES]
    por_chave = {c["chave"]: c for c in colunas}

    # 🚨 O que não tem coluna é CONTADO, não escondido (ver o cabeçalho).
    falhas = chamado_os.falhas_em_aberto()
    # 🚨 E O OUTRO CASO, que ele achou na tela: solicitação sem OS e **sem
    # tentativa**. Até 29/10 isso era o normal (a OS nascia por botão), e
    # chamá-lo de "a escrita falhou" é a tela mentindo -- ninguém escreveu.
    nunca_tentadas = chamado_os.sem_tentativa(painel)
    fora = {"sem_os": 0, "situacao_fora": 0, "situacoes": [],
            "os_falhou": falhas["quantas"],
            "os_falhou_chamados": falhas["chamados"],
            "os_falhou_em": falhas["ultima"],
            # ⚠️ "Nunca se tentou" é outra coisa de "falhou", e a tela escreve
            # frases diferentes.
            "sem_tentativa": nunca_tentadas}

    vistos = set()

    def _colocar(card: dict, situacao) -> None:
        """Põe o card na coluna da situação dele, ou conta como fora."""
        if situacao not in conhecidas:
            fora["situacao_fora"] += 1
            # ⚠️ O número cru entra na lista, nunca um rótulo inventado -- é a
            # régua do grid do FPSL: *"estado desconhecido mostra o valor
            # cru"*. 🚨 `0` e `NULL` entram SEPARADOS: `0` é "o ERP gravou
            # zero" e `NULL` é "a varredura não leu", e são 129 OS com `0` no
            # cache. O que fazer com elas é decisão dele.
            if situacao not in fora["situacoes"]:
                fora["situacoes"].append(situacao)
            return
        por_chave[f"s{situacao}"]["cards"].append(card)

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
        if s and s["slug"] and not _e_do_painel(s["slug"], painel):
            continue
        _colocar({
            "id": (s or {}).get("solicitacao_id"),
            "origem": "formulario" if s else "erp",
            "formulario": (s or {}).get("formulario"),
            "slug": (s or {}).get("slug"),
            "criada_em": (s or {}).get("criada_em") or o.get("data_previsao"),
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
            # ⚠️ QUANDO ESTE DADO FOI VISTO no ERP. A varredura roda a cada
            # 5 min, e a tela tem de poder dizer isso em vez de deixar o
            # operador supor que é agora.
            "visto_em": o.get("visto_em"),
        }, o.get("situacao_id"))

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
        }, linha["situacao_id"])

    total = 0
    for coluna in colunas:
        coluna["total"] = len(coluna["cards"])
        total += coluna["total"]
        coluna["cards"] = coluna["cards"][:TETO_CARDS_POR_COLUNA]

    return {
        "painel": painel,
        "titulo": PAINEIS[painel],
        "colunas": colunas,
        "total": total,
        # 🔵 D9: desde quando o quadro monta, e a tela DIZ isso.
        "desde": desde,
        "so_abertas": so_abertas,
        # 🚨 A tela tem de dizer quando está vendo menos. Ver o docstring.
        "ponte_respondeu": ponte_respondeu,
        "ponte_motivo": ponte_motivo,
        # 🚨 O que não tem coluna. A tela só escreve se algum for maior que
        # zero -- `M12` sem encher a tela de aviso.
        "fora_do_quadro": fora,
        # ⚠️ MOVER AINDA NÃO EXISTE, e `pode_mover` continua sendo a verdade
        # disso -- o que saiu em 29/10, a pedido dele, foi a FRASE que a tela
        # desenhava ao lado das colunas (*"os comentários tbm devem sumir
        # dali"*). O gesto não passou a existir por isso: quem o ligar muda
        # este campo, e aí a tela ganha o `draggable`. É o Bloco D.
        "pode_mover": False,
    }


def _e_do_painel(slug: str, painel: str) -> bool:
    """Se o formulário daquele slug pertence a este painel.

    ⚠️ Uma consulta por slug e não um `JOIN`: a lista de OS vem do ERP, e a
    maioria não tem solicitação nenhuma. O mapa é pequeno (15 formulários) e
    fica em memória do processo por chamada.
    """
    global _MAPA_PAINEL
    if _MAPA_PAINEL is None:
        _MAPA_PAINEL = {
            linha["slug"]: linha["painel"]
            for linha in banco.varios("SELECT slug, painel FROM formulario")}
    return _MAPA_PAINEL.get(slug) == painel


# 🚨 CACHE DE PROCESSO, E ELE PODE FICAR VELHO: mover um formulário de painel é
# `UPDATE formulario SET painel` (migração 075, decisão dele de que o mapa é
# DADO), e esta cópia não vê o `UPDATE` até o serviço reiniciar. É aceitável
# porque mover formulário de painel é cadastro, não operação -- e está dito
# aqui para quem mover não passar uma tarde procurando.
_MAPA_PAINEL = None
