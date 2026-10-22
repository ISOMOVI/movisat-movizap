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

from . import banco
from .operacao import DadoInvalido

log = logging.getLogger("movizap.paineis")

# ----------------------------------------------------------------------------
# As 11 situações da OS do Harmonit
# ----------------------------------------------------------------------------
# 🚨 CONSULTADAS AO VIVO EM 22/10 em `GET /SituacaoOrdemServico/ObterSituacoesOS`
# e copiadas AQUI porque são o vocabulário das colunas -- a tela não pode
# depender de uma chamada ao Harmonit para saber quais colunas desenhar.
#
# ⚠️ "Nova sollicitação" tem DOIS L, e é assim no Harmonit. Corrigir aqui faria
# a tela e o ERP chamarem a mesma coisa por nomes diferentes; quem lê os dois
# lado a lado é que decide, e ele ainda não pediu.
#
# ⚠️ A LISTA PODE CRESCER NO HARMONIT sem ninguém avisar. Situação que chegar
# fora desta lista cai em "Sem situação" com o número cru à vista -- é a régua
# do grid do FPSL: *"estado desconhecido mostra o valor cru"*, nunca um rótulo
# inventado.
SITUACOES = (
    (38, "Nova sollicitação"),
    (251, "Configuração"),
    (677, "Envio dos Equipamentos"),
    (890, "Agendamento"),
    (1316, "Serviço Agendado"),
    (15694, "Serviço Realizado"),
    (15695, "Pós Venda"),
    (15696, "Aguardando Devolução do Equipamento"),
    (15746, "Financeiro"),
    (15747, "Aguardando Chegada do Fornecedor"),
    (15797, "Aguardando aviso prévio"),
)

# As duas colunas que NÃO são situação do Harmonit, e por que existem:
#
# 🚨 `sem_os` é a primeira porque é de onde a OS nasce. Hoje TODAS as
# solicitações estão aqui -- nenhuma virou OS ainda --, e isso é o estado
# correto, não uma tela vazia.
#
# 🚨 `sem_situacao` existe por um número medido: das 574 OS no cache do FPSL em
# 22/10, **127 têm `situacao_id = 0` e 37 têm NULL** -- 164 que não estão em
# nenhuma das 11. Sem esta coluna elas desapareceriam da tela, e tela que
# esconde dado é o defeito que esta casa chama de `M12`.
COLUNA_SEM_OS = "sem_os"
COLUNA_SEM_SITUACAO = "sem_situacao"

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


def quadro(painel: str) -> dict:
    """O painel inteiro: as colunas, na ordem, com os cards de cada uma."""
    if painel not in PAINEIS:
        raise DadoInvalido("Painel desconhecido.")
    if painel not in COM_TELA:
        # ⚠️ A frase diz o que É, não "erro": as outras três estão desenhadas e
        # esperando decisão dele, e quem bater aqui tem de saber disso.
        raise DadoInvalido(
            f"O painel {PAINEIS[painel]} ainda não existe — só o da Operação "
            f"entrou nesta volta.")

    formularios = banco.varios(
        """SELECT codigo, slug, titulo, ativo,
                  (SELECT count(*) FROM formulario_campo c
                    WHERE c.formulario_id = f.id) AS campos
             FROM formulario f
            WHERE f.painel = %s
            ORDER BY f.ordem""", (painel,))

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

    conhecidas = {sid for sid, _ in SITUACOES}
    colunas = [
        {"chave": COLUNA_SEM_OS, "titulo": "Sem OS", "situacao_id": None,
         "nota": "a solicitação chegou e ainda não virou OS", "cards": []},
        {"chave": COLUNA_SEM_SITUACAO, "titulo": "Sem situação",
         "situacao_id": None,
         "nota": "tem OS, e a situação é 0, nula ou desconhecida", "cards": []},
    ]
    colunas += [{"chave": f"s{sid}", "titulo": nome, "situacao_id": sid,
                 "nota": None, "cards": []} for sid, nome in SITUACOES]
    por_chave = {c["chave"]: c for c in colunas}

    for linha in linhas:
        if not linha["os_id"]:
            chave = COLUNA_SEM_OS
        elif linha["situacao_id"] in conhecidas:
            chave = f"s{linha['situacao_id']}"
        else:
            # 🚨 Situação 0, nula ou que não está na lista. O número cru vai no
            # card, para o operador ver o que o Harmonit respondeu.
            chave = COLUNA_SEM_SITUACAO
        por_chave[chave]["cards"].append({
            "id": linha["id"],
            "formulario": linha["formulario"],
            "slug": linha["slug"],
            "criada_em": linha["criada_em"],
            "estado": linha["estado"],
            "cliente": linha["cliente_nome"],
            "resumo": _resumo(linha["valores"]),
            "anexos": linha["anexos"],
            "os_id": linha["os_id"],
            "numero_ordem": linha["numero_ordem"],
            "situacao_id": linha["situacao_id"],
            "situacao_em": linha["situacao_em"],
        })

    for coluna in colunas:
        coluna["total"] = len(coluna["cards"])
        coluna["cards"] = coluna["cards"][:TETO_CARDS_POR_COLUNA]

    return {
        "painel": painel,
        "titulo": PAINEIS[painel],
        "formularios": formularios,
        "colunas": colunas,
        "total": len(linhas),
        # 🚨 A TELA DIZ O QUE AINDA NÃO FAZ, em vez de oferecer o gesto que não
        # grava. É o precedente do `ModalAgendar`, que explica em vez de sumir.
        "pode_mover": False,
        "porque_nao_move": (
            "Mover o card vai escrever a situação na OS do Harmonit, e essa "
            "rota ainda não existe. Para ela nascer falta você confirmar qual "
            "problema cada formulário gera."),
    }
