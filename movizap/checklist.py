"""O checklist de cada etapa do painel da Operação — o mapa do operador.

🔵 Pedido dele em 04/11, com um print do Bitrix: *"são itens que vão ficar em um
botão dentro do card, como mapa para o operador saber o que fazer"*, e
**"Modelo fixo + o operador pode acrescentar"**.

🚨 NÃO É O CHECKLIST DO HARMONIT. O ERP tem o seu, que o app do técnico em campo
mostra; os itens daqui são de **escritório** (*"Verificar DataScope"*, *"Nota
Fiscal (emitir e enviar)"*) e lá só fariam ruído. Decisão dele: nem um nem
outro — é mapa do operador, no card.

🚨 NADA DAQUI VAI PARA A OS. Ao sair da etapa o checklist vira **observação do
card** (`os_observacao`). Decisão dele depois de eu medir que gravar
`solucaoTecnica` exigiria reescrever a OS inteira no Harmonit: *"Só no MoviZap,
como observação"*.

⚠️ O ITEM DO CARD É CÓPIA, NÃO REFERÊNCIA. O texto é gravado quando o card abre
a etapa pela primeira vez; editar o modelo depois **não** reescreve o que já
está marcado. O card é registro do que foi feito, não espelho da configuração —
o mesmo desenho do `tipo_nome` do agendamento e do `origem_endereco`.
"""
import logging

import psycopg

from . import banco
from .operacao import DadoInvalido

# 🚨 `paineis` É IMPORTADO TARDIAMENTE, dentro das funções que precisam da
# tupla `SITUACOES`. O motivo é um ciclo real: `paineis` passou a ler este
# módulo (para o selo "2 de 3" no card) e `passagem` também — importar
# `paineis` aqui no topo fecharia paineis → checklist → paineis, e o Python
# estoura no `import` com uma mensagem que não diz nada sobre checklist.

log = logging.getLogger("movizap.checklist")

TETO_TEXTO = 200

# 🚨 O MESMO handler do `operacao`: `main.py` tem UM
# `@app.exception_handler(operacao.DadoInvalido)`, e uma classe própria aqui
# escaparia dele e viraria 500.
__all__ = ["DadoInvalido"]


def _texto(valor) -> str:
    limpo = (valor or "").strip()
    if not limpo:
        raise DadoInvalido("O item não pode ser vazio.")
    if len(limpo) > TETO_TEXTO:
        raise DadoInvalido(f"O item passa de {TETO_TEXTO} caracteres.")
    return limpo


def _etapa_conhecida(situacao_id: int) -> None:
    """⚠️ A mesma guarda do `passagem.mover`: etapa fora das 17 não é
    'proibida', é desconhecida para esta tela — e um checklist pendurado nela
    nunca apareceria para ninguém."""
    from . import paineis
    if situacao_id not in {sid for sid, _ in paineis.SITUACOES}:
        raise DadoInvalido(
            f"A situação {situacao_id} não é uma das 17 do painel da Operação.")


# ===========================================================================
# O MODELO da etapa (configuração)
# ===========================================================================

def modelos(situacao_id: int | None = None,
            incluir_inativos: bool = False) -> list[dict]:
    onde = ["(%s OR ativo)"]
    params: list = [incluir_inativos]
    if situacao_id is not None:
        onde.append("situacao_id = %s")
        params.append(int(situacao_id))
    return banco.varios(
        f"""SELECT id, situacao_id, texto, ordem, ativo
              FROM checklist_modelo
             WHERE {' AND '.join(onde)}
             ORDER BY situacao_id, ordem, id""", tuple(params))


def etapas_com_modelo() -> set[int]:
    """As etapas que TÊM checklist — é o que decide se o botão aparece no card
    e se o aviso de entrada é dado."""
    return {r["situacao_id"] for r in banco.varios(
        "SELECT DISTINCT situacao_id FROM checklist_modelo WHERE ativo")}


def criar_modelo(situacao_id: int, texto: str, ordem: int | None = None) -> dict:
    _etapa_conhecida(int(situacao_id))
    texto = _texto(texto)
    if ordem is None:
        maior = banco.um("SELECT COALESCE(MAX(ordem), 0) AS m FROM checklist_modelo "
                         " WHERE situacao_id = %s", (int(situacao_id),))
        ordem = int(maior["m"]) + 1
    linha = banco.um(
        """INSERT INTO checklist_modelo (situacao_id, texto, ordem)
           VALUES (%s, %s, %s) RETURNING id""",
        (int(situacao_id), texto, int(ordem)))
    log.info("checklist: item de modelo %s criado na etapa %s",
             linha["id"], situacao_id)
    return banco.um("SELECT id, situacao_id, texto, ordem, ativo "
                    "FROM checklist_modelo WHERE id = %s", (linha["id"],))


def atualizar_modelo(modelo_id: int, texto: str, ordem: int, ativo: bool) -> dict:
    if not banco.um("SELECT id FROM checklist_modelo WHERE id = %s", (modelo_id,)):
        raise DadoInvalido("Item de modelo não encontrado.")
    texto = _texto(texto)
    # ⚠️ Mexer aqui NÃO mexe em card nenhum: os itens já copiados seguem com o
    # texto que tinham. É o ponto do desenho, e há teste prendendo.
    banco.executar(
        "UPDATE checklist_modelo SET texto = %s, ordem = %s, ativo = %s "
        " WHERE id = %s", (texto, int(ordem), bool(ativo), modelo_id))
    return banco.um("SELECT id, situacao_id, texto, ordem, ativo "
                    "FROM checklist_modelo WHERE id = %s", (modelo_id,))


# ===========================================================================
# O CHECKLIST do card
# ===========================================================================

def do_card(numero_os: int, situacao_id: int,
            atendente_id: int | None = None) -> list[dict]:
    """A lista daquele card naquela etapa, criando-a do modelo na primeira vez.

    🚨 A CÓPIA É IDEMPOTENTE. O `UNIQUE (numero_os, situacao_id, de_modelo_id)`
    com `ON CONFLICT DO NOTHING` garante que abrir o card dez vezes não duplica
    nada — e que dois atendentes abrindo ao mesmo tempo também não.

    ⚠️ Item de modelo **desativado depois** não é copiado para card novo, mas
    continua no card de quem já o tinha. Registro não se reescreve.
    """
    numero_os, situacao_id = int(numero_os), int(situacao_id)

    pendentes = banco.varios(
        """SELECT m.id, m.texto, m.ordem FROM checklist_modelo m
            WHERE m.situacao_id = %s AND m.ativo
              AND NOT EXISTS (SELECT 1 FROM checklist_item i
                               WHERE i.numero_os = %s AND i.situacao_id = %s
                                 AND i.de_modelo_id = m.id)
            ORDER BY m.ordem, m.id""",
        (situacao_id, numero_os, situacao_id))

    if pendentes:
        with banco.cursor() as cur:
            for m in pendentes:
                cur.execute(
                    """INSERT INTO checklist_item
                           (numero_os, situacao_id, texto, ordem, de_modelo_id,
                            criado_por)
                       VALUES (%s, %s, %s, %s, %s, %s)
                       ON CONFLICT (numero_os, situacao_id, de_modelo_id)
                       DO NOTHING""",
                    (numero_os, situacao_id, m["texto"], m["ordem"], m["id"],
                     atendente_id))
        log.info("checklist: OS %s etapa %s recebeu %s item(ns) do modelo",
                 numero_os, situacao_id, len(pendentes))

    return itens(numero_os, situacao_id)


def itens(numero_os: int, situacao_id: int) -> list[dict]:
    """Só lê — não cria nada. É o que a listagem e os testes usam."""
    return banco.varios(
        """SELECT i.id, i.texto, i.ordem, i.feito, i.feito_em,
                  i.de_modelo_id, (i.de_modelo_id IS NULL) AS avulso,
                  a.nome AS feito_por
             FROM checklist_item i
             LEFT JOIN atendente a ON a.id = i.feito_por
            WHERE i.numero_os = %s AND i.situacao_id = %s
            ORDER BY i.ordem, i.id""",
        (int(numero_os), int(situacao_id)))


def marcar(item_id: int, feito: bool, atendente_id: int | None) -> dict:
    """🚨 DESMARCAR NÃO APAGA: vira `feito = false` com `feito_em` novo. Quem
    marcou e depois desmarcou fez duas coisas, e as duas são informação."""
    linha = banco.um("SELECT id, numero_os, situacao_id FROM checklist_item "
                     " WHERE id = %s", (item_id,))
    if not linha:
        raise DadoInvalido("Item não encontrado.")
    banco.executar(
        """UPDATE checklist_item
              SET feito = %s, feito_em = now(), feito_por = %s
            WHERE id = %s""", (bool(feito), atendente_id, item_id))
    return {"numero_os": linha["numero_os"], "situacao_id": linha["situacao_id"],
            "itens": itens(linha["numero_os"], linha["situacao_id"])}


def acrescentar(numero_os: int, situacao_id: int, texto: str,
                atendente_id: int | None) -> dict:
    """O item avulso do operador — *"Modelo fixo + o operador pode acrescentar"*.

    ⚠️ Nasce com `de_modelo_id` nulo, e é isso que o torna removível.
    """
    _etapa_conhecida(int(situacao_id))
    texto = _texto(texto)
    maior = banco.um(
        "SELECT COALESCE(MAX(ordem), 0) AS m FROM checklist_item "
        " WHERE numero_os = %s AND situacao_id = %s",
        (int(numero_os), int(situacao_id)))
    try:
        banco.executar(
            """INSERT INTO checklist_item
                   (numero_os, situacao_id, texto, ordem, de_modelo_id, criado_por)
               VALUES (%s, %s, %s, %s, NULL, %s)""",
            (int(numero_os), int(situacao_id), texto, int(maior["m"]) + 1,
             atendente_id))
    except psycopg.errors.UniqueViolation as e:
        raise DadoInvalido("Este item já existe neste card.") from e
    log.info("checklist: OS %s etapa %s ganhou item avulso", numero_os, situacao_id)
    return {"numero_os": int(numero_os), "situacao_id": int(situacao_id),
            "itens": itens(numero_os, situacao_id)}


def remover(item_id: int) -> dict:
    """Só item AVULSO sai.

    🚨 Item que veio do modelo **não se remove do card**: ele é a lista da
    etapa, e deixar apagar transformaria o "mapa do operador" numa lista que
    cada um edita — e aí duas OS na mesma etapa deixariam de ser comparáveis.
    Quem não quer o item tira do MODELO, e isso vale para os cards seguintes.
    """
    linha = banco.um(
        "SELECT id, numero_os, situacao_id, de_modelo_id FROM checklist_item "
        " WHERE id = %s", (item_id,))
    if not linha:
        raise DadoInvalido("Item não encontrado.")
    if linha["de_modelo_id"] is not None:
        raise DadoInvalido(
            "Este item é da lista da etapa e não sai do card. Para tirá-lo de "
            "todos os cards, mexa no modelo da etapa.")
    banco.executar("DELETE FROM checklist_item WHERE id = %s", (item_id,))
    return {"numero_os": linha["numero_os"], "situacao_id": linha["situacao_id"],
            "itens": itens(linha["numero_os"], linha["situacao_id"])}


def resumo(numeros: list[int]) -> dict:
    """`{numero_os: {"feitos": n, "total": n}}` — o selo "2 de 3" do card.

    ⚠️ UMA consulta para todos os cards, como `passagem.quantas_observacoes`:
    o quadro desenha até 50 por coluna, e uma consulta por card seria 850.

    ⚠️ Conta o checklist da etapa **em que o card está agora** — o de etapas
    anteriores já virou observação e não é mais tarefa.
    """
    if not numeros:
        return {}
    linhas = banco.varios(
        """SELECT numero_os, situacao_id,
                  count(*) AS total,
                  count(*) FILTER (WHERE feito) AS feitos
             FROM checklist_item
            WHERE numero_os = ANY(%s)
            GROUP BY numero_os, situacao_id""",
        (list(numeros),))
    return {(r["numero_os"], r["situacao_id"]):
            {"feitos": r["feitos"], "total": r["total"]} for r in linhas}


def como_texto(numero_os: int, situacao_id: int) -> str | None:
    """O checklist escrito, para virar observação ao sair da etapa (decisão O4).

    🚨 Devolve `None` quando não há item nenhum — etapa sem checklist não gera
    linha, para não encher a linha do tempo de ruído. É a mesma régua do
    conflito de concorrência, que não vira passagem.
    """
    lista = itens(numero_os, situacao_id)
    if not lista:
        return None

    from . import paineis
    nome = dict(paineis.SITUACOES).get(int(situacao_id), str(situacao_id))
    feitos = sum(1 for i in lista if i["feito"])
    linhas = [f"[checklist] {nome} — {feitos} de {len(lista)}"]
    for i in lista:
        if not i["feito"]:
            linhas.append(f"✗ {i['texto']}")
            continue
        # ⚠️ Autor e hora podem faltar (atendente apagado é `ON DELETE SET
        # NULL`), e aí a assinatura some em vez de virar "(None, )".
        assinatura = [p for p in (
            i["feito_por"],
            i["feito_em"].strftime("%d/%m %H:%M") if i["feito_em"] else None,
        ) if p]
        marca = f" ({', '.join(assinatura)})" if assinatura else ""
        linhas.append(f"✓ {i['texto']}{marca}")

    texto = "\n".join(linhas)
    # ⚠️ `os_observacao.texto` não tem teto no banco, mas `passagem.observar`
    # recusa acima de 4000 — cortar aqui é melhor que perder a observação
    # inteira por causa de uma lista longa.
    if len(texto) > 3900:
        texto = texto[:3900].rstrip() + "\n… (lista cortada no limite do recado)"
    return texto
