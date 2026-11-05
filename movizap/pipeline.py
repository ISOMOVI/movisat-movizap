"""As etapas NOSSAS — o motor dos cards que não são OS (05/11).

🔵 **Dois pedidos dele que são a mesma coisa:**
  1. *"vamos criar uma coluna nova antes de 'Nova solicitação', chamada
     'Chamados' (…) nessa coluna não são OS ainda, somente o CARD mesmo"*;
  2. *"a aba 'Operação' do Movizap é a mesma lógica para os demais"*.

🚨 **POR QUE O MOTOR É UM SÓ, e é a descoberta que desenhou este módulo:** a
coluna do painel da Operação é uma **situação da OS no Harmonit**, e mover
escreve no ERP (`passagem.mover` → `fpsl_ponte.gravar_situacao_da_os`). Já
`Chamados`, `Treinamentos` e `Pós-venda` têm colunas que **não existem no
Harmonit** — são etapas **nossas**, e mover nelas escreve **só aqui**. Fazer a
coluna Chamados sozinha seria escrever este módulo duas vezes.

🚨 **ESTE MÓDULO NUNCA FALA COM O HARMONIT, e isso é a linha que o separa do
`passagem.py`.** Nem importa o `fpsl_ponte`. Se um dia alguém precisar criar OS
a partir de um chamado, o caminho é o `chamado_os.abrir`, que já existe e
continua testado — não um atalho daqui.

⚠️ **E ele não valida transição**, pela mesma decisão dele que vale no
`passagem.py`: *"que tal de caminho proibido é esse??"* — **não existe caminho
proibido**. O que se valida é que a etapa é da aba do card; para onde ela vai
dentro da aba é de quem opera.

⚠️ **O DESFECHO NÃO É O `estado` DA SOLICITAÇÃO.** `formulario_solicitacao`
tem um CHECK que aceita só `nova`/`em_andamento`/`concluida`, e dois contadores
leem `estado = 'nova'`. `estado` é ciclo de vida; desfecho é **como terminou**.
São duas perguntas, e vivem em dois lugares.
"""
import logging

from . import banco
from .operacao import DadoInvalido

log = logging.getLogger("movizap.pipeline")

# 🔵 Decisão dele: *"Resolvido encerra o card (…) com status de concluído"* e
# *"se não resolvido, o mesmo procedimento, mas o status de 'Virou OS'"*.
# 🚨 E "Virou OS" **só marca** — ele foi explícito: *"só marca; a OS é pelo
# Operação"*. Nada neste módulo escreve no ERP, e é isso que torna o botão
# reversível por quem tiver a tela.
DESFECHOS = {
    "resolvido": "Resolvido",
    "virou_os": "Virou OS",
}


# ----------------------------------------------------------------------------
# As abas e as etapas — o catálogo
# ----------------------------------------------------------------------------
# 🔵 A aba da Operacao reusa o codigo da tela que ja existe: a
# coluna `Chamados` e parte do quadro da Operacao, nao uma tela nova.
ABA_DA_OPERACAO = "PNL_1.1"
ETAPA_DOS_CHAMADOS = "Chamados"


def etapa_dos_chamados() -> dict | None:
    """A etapa `Chamados` da aba da Operacao, ou `None` se nao existir.

    ⚠️ DEVOLVE `None` EM VEZ DE ESTOURAR: a migracao 092 a semeia, mas
    um banco sem ela (ambiente novo, restore antigo) tem de montar o quadro
    com as 17 e seguir -- e nao derrubar a tela da operacao inteira, nem o
    envio do formulario, por falta de uma coluna.
    """
    aba = aba_por_codigo(ABA_DA_OPERACAO)
    if not aba:
        return None
    for e in etapas(aba['id']):
        if e['titulo'] == ETAPA_DOS_CHAMADOS:
            return {'id': e['id'], 'aba_id': aba['id']}
    return None


def abas(painel: str | None = None, incluir_inativas: bool = False) -> list[dict]:
    """As abas de um painel, na ordem dele.

    ⚠️ Sem `painel`, devolve todas — é o que a tela de configuração vai querer.
    """
    sql = ["""SELECT id, painel, codigo_tela, titulo, ordem, ativo
                FROM painel_aba WHERE 1 = 1"""]
    p: list = []
    if painel:
        sql.append("AND painel = %s")
        p.append(painel)
    if not incluir_inativas:
        sql.append("AND ativo")
    sql.append("ORDER BY painel, ordem, id")
    return banco.varios(" ".join(sql), tuple(p))


def aba_por_codigo(codigo_tela: str) -> dict | None:
    """A aba pelo código de tela — que é como a permissão a nomeia.

    🚨 O `codigo_tela` É O QUE TORNA A PERMISSÃO REAL, e ele tem de ter entrada
    no `movizap/telas.py`: é a lição dele de 03/11 (*"ESTÁ NO AR NÃO É 200"*),
    quando uma tela subiu sem registro e ficou **invisível no menu**, sem nem
    dar 403.
    """
    return banco.um(
        """SELECT id, painel, codigo_tela, titulo, ordem, ativo
             FROM painel_aba WHERE codigo_tela = %s""", (codigo_tela,))


def etapas(aba_id: int, incluir_inativas: bool = False) -> list[dict]:
    """As colunas de uma aba, na ordem dele."""
    sql = ["""SELECT id, aba_id, titulo, ordem, ativo, final
                FROM pipeline_etapa WHERE aba_id = %s"""]
    if not incluir_inativas:
        sql.append("AND ativo")
    sql.append("ORDER BY ordem, id")
    return banco.varios(" ".join(sql), (int(aba_id),))


def etapa(etapa_id: int) -> dict | None:
    return banco.um(
        """SELECT id, aba_id, titulo, ordem, ativo, final
             FROM pipeline_etapa WHERE id = %s""", (int(etapa_id),))


# ----------------------------------------------------------------------------
# O card
# ----------------------------------------------------------------------------
def criar(aba_id: int, etapa_id: int, *, solicitacao_id: int | None = None,
          cliente_id: int | None = None, atendente_id: int | None = None) -> dict:
    """Cria o card numa etapa, e registra a primeira passagem.

    🚨 **IDEMPOTENTE POR SOLICITAÇÃO**, e é o que impede o chamado de virar dois
    cards: `ux_pipeline_card_solicitacao` é único, e aqui a colisão devolve o
    card que já existe em vez de estourar. O envio do formulário é retentável
    (o cliente pode reenviar), e dois cards para o mesmo chamado seriam duas
    análises da mesma coisa.
    """
    if solicitacao_id is not None:
        achado = da_solicitacao(solicitacao_id)
        if achado:
            return achado

    e = etapa(etapa_id)
    if not e or e["aba_id"] != int(aba_id):
        raise DadoInvalido("Esta etapa não é da aba informada.")

    linha = banco.um(
        """INSERT INTO pipeline_card
               (aba_id, etapa_id, solicitacao_id, cliente_id, criado_por)
           VALUES (%s, %s, %s, %s, %s)
           RETURNING id, criado_em""",
        (int(aba_id), int(etapa_id), solicitacao_id, cliente_id, atendente_id))
    banco.executar(
        """INSERT INTO pipeline_passagem
               (card_id, de_etapa, para_etapa, para_titulo, quem)
           VALUES (%s, NULL, %s, %s, %s)""",
        (linha["id"], int(etapa_id), e["titulo"], atendente_id))
    log.info("pipeline: card %s criado na etapa %s (solicitacao %s)",
             linha["id"], etapa_id, solicitacao_id)
    return {"id": linha["id"], "criado_em": linha["criado_em"],
            "aba_id": int(aba_id), "etapa_id": int(etapa_id),
            "solicitacao_id": solicitacao_id}


def da_solicitacao(solicitacao_id: int) -> dict | None:
    """O card de um chamado, se existir."""
    return banco.um(
        """SELECT id, aba_id, etapa_id, solicitacao_id, cliente_id,
                  criado_em, desfecho, desfecho_em
             FROM pipeline_card WHERE solicitacao_id = %s""",
        (int(solicitacao_id),))


def mover(card_id: int, para_etapa: int, atendente_id: int | None) -> dict:
    """Move o card de etapa, dentro da MESMA aba.

    🚨 **NADA AQUI CHEGA AO HARMONIT**, e é a diferença inteira em relação ao
    `passagem.mover`. Card de pipeline não tem OS: não há `situacaoId` para
    gravar, e inventar um seria escrever no ERP sobre uma OS que não existe.

    ⚠️ **A etapa tem de ser da aba do card.** Não é validação de caminho (não
    existe caminho proibido, decisão dele) — é a garantia de que o card não
    atravessa para a pipeline de outro setor, onde ele ficaria invisível.
    """
    card = banco.um(
        """SELECT id, aba_id, etapa_id, desfecho
             FROM pipeline_card WHERE id = %s""", (int(card_id),))
    if not card:
        raise DadoInvalido("Este card não existe.")
    # ⚠️ Card arquivado não se move: o desfecho é o fim da linha, e mover um
    # arquivado faria o histórico mentir sobre quando ele terminou.
    if card["desfecho"]:
        raise DadoInvalido(
            f"Este card já foi finalizado como "
            f"'{DESFECHOS.get(card['desfecho'], card['desfecho'])}'.")

    e = etapa(para_etapa)
    if not e:
        raise DadoInvalido("Esta etapa não existe.")
    if e["aba_id"] != card["aba_id"]:
        raise DadoInvalido("Esta etapa é de outra aba.")
    if e["id"] == card["etapa_id"]:
        return {"ok": True, "etapa_id": e["id"], "mudou": False}

    banco.executar(
        "UPDATE pipeline_card SET etapa_id = %s WHERE id = %s",
        (e["id"], card["id"]))
    de = etapa(card["etapa_id"])
    banco.executar(
        """INSERT INTO pipeline_passagem
               (card_id, de_etapa, para_etapa, de_titulo, para_titulo, quem)
           VALUES (%s, %s, %s, %s, %s, %s)""",
        (card["id"], card["etapa_id"], e["id"],
         (de or {}).get("titulo"), e["titulo"], atendente_id))
    log.info("pipeline: card %s de %s para %s por %s",
             card["id"], card["etapa_id"], e["id"], atendente_id)
    return {"ok": True, "etapa_id": e["id"], "mudou": True}


def finalizar(card_id: int, desfecho: str, atendente_id: int | None) -> dict:
    """Arquiva o card com um desfecho.

    🔵 *"ter o botão de 'Finalizar Chamado' e daí vai perguntar 'Resolvido' ou
    'Não resolvido'"*.

    🚨 **NÃO ESCREVE NO ERP**, nos dois desfechos — nem no *"Virou OS"*. Ele foi
    explícito: *"só marca; a OS é pelo Operação"*. O card diz que **vai** virar
    OS; abrir a OS é passo separado, e é o que torna este botão reversível.
    """
    if desfecho not in DESFECHOS:
        raise DadoInvalido("Desfecho desconhecido.")
    card = banco.um(
        "SELECT id, desfecho FROM pipeline_card WHERE id = %s", (int(card_id),))
    if not card:
        raise DadoInvalido("Este card não existe.")
    if card["desfecho"]:
        # ⚠️ Já finalizado não refinaliza: a segunda chamada reescreveria o
        # "quando" e apagaria o desfecho que alguém registrou.
        raise DadoInvalido(
            f"Este card já foi finalizado como "
            f"'{DESFECHOS.get(card['desfecho'], card['desfecho'])}'.")

    linha = banco.um(
        """UPDATE pipeline_card
              SET desfecho = %s, desfecho_em = now(), desfecho_por = %s
            WHERE id = %s
        RETURNING desfecho, desfecho_em""",
        (desfecho, atendente_id, int(card_id)))
    log.info("pipeline: card %s finalizado como %s por %s",
             card_id, desfecho, atendente_id)
    return {"ok": True, "desfecho": linha["desfecho"],
            "desfecho_em": linha["desfecho_em"],
            "rotulo": DESFECHOS[desfecho]}


def reabrir(card_id: int, atendente_id: int | None) -> dict:
    """Desfaz o arquivamento.

    🔵 Ele decidiu que finalizar **só marca** — e marca que não se desmarca é
    uma porta de mão única numa tela que a operação usa o dia todo. Nada foi
    escrito fora, então desfazer é seguro.
    ⚠️ A passagem NÃO é apagada: o histórico de etapas continua sendo o que
    aconteceu.
    """
    card = banco.um(
        "SELECT id, desfecho FROM pipeline_card WHERE id = %s", (int(card_id),))
    if not card:
        raise DadoInvalido("Este card não existe.")
    if not card["desfecho"]:
        return {"ok": True, "mudou": False}
    banco.executar(
        """UPDATE pipeline_card
              SET desfecho = NULL, desfecho_em = NULL, desfecho_por = NULL
            WHERE id = %s""", (int(card_id),))
    log.info("pipeline: card %s reaberto por %s", card_id, atendente_id)
    return {"ok": True, "mudou": True}


def aba_do_card(card_id: int) -> dict | None:
    """A aba a que o card pertence -- e, com ela, o `codigo_tela`.

    🚨 E ISTO QUE TORNA A PERMISSAO DO CARD CORRETA quando ha mais de uma
    aba: ate 05/11 as rotas de card exigiam `PNL_1.1` fixo, e um card do
    Pos-venda cairia em 403 pedido pela tela certa. A permissao sai do
    CARD, nao da rota.
    """
    return banco.um(
        """SELECT a.id, a.painel, a.codigo_tela, a.titulo, a.ordem, a.ativo
             FROM pipeline_card c
             JOIN painel_aba a ON a.id = c.aba_id
            WHERE c.id = %s""", (int(card_id),))


def aba_da_solicitacao(solicitacao_id: int) -> dict | None:
    """A aba do card daquela solicitacao, para a rota de observacao."""
    return banco.um(
        """SELECT a.id, a.painel, a.codigo_tela, a.titulo, a.ordem, a.ativo
             FROM pipeline_card c
             JOIN painel_aba a ON a.id = c.aba_id
            WHERE c.solicitacao_id = %s
            ORDER BY c.id LIMIT 1""", (int(solicitacao_id),))


def historico(card_id: int) -> list[dict]:
    """As passagens deste card, da mais nova para a mais velha.

    🔵 *"deve ter o log de quem faz o que SEMPRE"*.

    🚨 LE O RETRATO, e nao faz JOIN com a etapa: o titulo guardado e o
    de ENTAO. Renomear a etapa amanha nao pode reescrever o que a passagem
    dizia -- e apagar a aba nao pode levar o historico (migracao 093, pelo
    molde do `orcamento_item.servico`).
    """
    return banco.varios(
        """SELECT p.id, p.em, p.de_etapa, p.para_etapa,
                  p.de_titulo, p.para_titulo,
                  a.nome AS quem
             FROM pipeline_passagem p
             LEFT JOIN atendente a ON a.id = p.quem
            WHERE p.card_id = %s
            ORDER BY p.em DESC, p.id DESC""", (int(card_id),))


def cards_da_aba(aba_id: int, teto: int = 200) -> list[dict]:
    """Os cards de uma aba, com o que o card fechado precisa mostrar.

    🚨 **O ARQUIVADO VEM NO FIM, e é decisão dele:** *"ele esmaece e fica no fim
    da fila arquivado com status de concluído"*. A ordem é `desfecho IS NOT
    NULL` primeiro (falso antes de verdadeiro), e dentro disso o mais novo
    primeiro — a mesma régua de nulo-vai-para-o-fim que o `_ordenar` do painel
    já usa.

    ⚠️ **UMA consulta para a aba toda**, como o `quantas_observacoes` faz: uma
    por card seriam N idas ao banco por abertura de tela.
    """
    return banco.varios(
        """SELECT c.id, c.aba_id, c.etapa_id, c.solicitacao_id, c.cliente_id,
                  c.criado_em, c.desfecho, c.desfecho_em,
                  qa.nome AS desfecho_por_nome,
                  s.valores, s.criada_em AS solicitada_em,
                  f.titulo AS formulario, f.slug,
                  (SELECT count(*) FROM os_observacao o
                    WHERE o.solicitacao_id = c.solicitacao_id) AS observacoes
             FROM pipeline_card c
             LEFT JOIN atendente qa ON qa.id = c.desfecho_por
             LEFT JOIN formulario_solicitacao s ON s.id = c.solicitacao_id
             LEFT JOIN formulario f ON f.id = s.formulario_id
            WHERE c.aba_id = %s
            ORDER BY (c.desfecho IS NOT NULL), c.criado_em DESC, c.id DESC
            LIMIT %s""", (int(aba_id), int(teto)))
