"""Mover o card de etapa — Bloco D do pipeline da operação (29/10).

🔵 **As quatro decisões dele, nas palavras dele:**
  · *"O card pode ser por arrastar"* — o gesto;
  · *"deve ter o log de quem faz o que SEMPRE"* — e é a condição deste módulo;
  · *"que tal de caminho proibido é esse??"* — **não existe caminho proibido.**
    ⚠️ A pergunta era minha e foi descartada: **nada aqui valida transição**;
  · *"pode mover que tiver acesso a tela, por enquanto somente owner"* — quem
    cobra isso é a rota, e hoje a `PNL_1.1` é de permissão `owner`.

🚨 **O LOG É A CONDIÇÃO, NÃO UM EXTRA.** O Harmonit **não registra a situação na
linha do tempo** — só o `status`, conferido em 3 OS em 29/10. Então, movido o
card, não há como saber quem moveu, de onde e quando: nem aqui, nem lá. Sem a
`os_passagem` (migração 083), mover é escrita anônima e irreversível no ERP.

🚨 **A TENTATIVA RECUSADA TAMBÉM É GRAVADA**, e é metade do valor: escrita que o
ERP negou e não deixou rastro é a mesma família do `criada: null` da criação de
OS — ninguém descobre depois.

⚠️ **ESTE MÓDULO NÃO É O BLOCO C.** O C quer *"quanto tempo em cada etapa"*, com
os dois tempos no card. Aqui é o **registro da passagem** — e é ele que faz o C
sair barato depois, porque o dado passa a ser colhido desde já.
"""
import logging
import pathlib
import uuid

from . import banco, checklist, fpsl_ponte, paineis
from .operacao import DadoInvalido

log = logging.getLogger("movizap.passagem")


def _registrar(numero_os: int, de, para: int, atendente_id: int | None,
               ok: bool, erro: str | None, fora: dict | None,
               os_id: int | None = None) -> int:
    """Grava a passagem. 🔵 *"o log de quem faz o que SEMPRE"* — inclusive a
    recusada, e é por isso que esta função é chamada nos dois caminhos."""
    import json
    linha = banco.um(
        """INSERT INTO os_passagem
               (numero_os, os_id, de_situacao, para_situacao, atendente_id,
                ok, erro, fora_da_situacao)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id""",
        (numero_os, os_id, de, para, atendente_id, ok, erro,
         json.dumps(fora, ensure_ascii=False, default=str) if fora else None))
    return linha["id"]


def mover(numero_os: int, para_situacao: int, atendente_id: int | None,
          situacao_esperada: int | None = None) -> dict:
    """Move o card: escreve a situação no Harmonit e registra a passagem.

    🚨 **NÃO VALIDA TRANSIÇÃO**, por decisão dele — ver o cabeçalho. O que ela
    valida é que a situação de **destino** é uma das 17 do painel: um id
    inventado criaria um card sem coluna, e aí o card desapareceria da tela.

    🚨 **ESTOURA `DadoInvalido` SÓ ANTES DE TENTAR.** Depois de a escrita ser
    tentada, nada estoura: a resposta diz o que aconteceu e a passagem está
    gravada. Estourar depois perderia o registro de uma escrita que já pode ter
    chegado ao ERP.
    """
    conhecidas = {sid for sid, _ in paineis.SITUACOES}
    if para_situacao not in conhecidas:
        # ⚠️ A frase diz o que É: id fora das 17 não é "proibido", é
        # desconhecido para esta tela.
        raise DadoInvalido(
            f"A situação {para_situacao} não é uma das 17 do painel da "
            f"Operação — o card ficaria sem coluna.")

    resposta = fpsl_ponte.gravar_situacao_da_os(
        numero_os, para_situacao, situacao_esperada=situacao_esperada)

    # 🚨 O LOG SAI NOS DOIS CAMINHOS. ⚠️ Conflito de concorrência NÃO é gravado
    # como passagem: nada foi tentado no ERP, e registrar uma passagem que não
    # aconteceu encheria a linha do tempo da OS de ruído. A resposta diz o
    # conflito, e a tela recarrega.
    if resposta.get("conflito"):
        log.info("OS %s: conflito ao mover (ERP em %s, tela em %s)",
                 numero_os, resposta.get("de"), situacao_esperada)
        return resposta

    passagem = _registrar(
        numero_os=numero_os,
        de=resposta.get("de"),
        para=para_situacao,
        atendente_id=atendente_id,
        ok=bool(resposta.get("ok")),
        erro=None if resposta.get("ok") else (resposta.get("motivo")
                                             or "sem motivo informado"),
        fora=resposta.get("fora_da_situacao"),
    )

    # 🔵 04/11, decisão dele (O4): ao SAIR de uma etapa que tinha checklist, o
    # que foi feito vira **observação do card**. *"Só no MoviZap, como
    # observação"* -- gravar na `solucaoTecnica` exigiria reescrever a OS
    # inteira no Harmonit, e ele preferiu não tocar na OS.
    #
    # 🚨 SÓ QUANDO A MUDANÇA ACONTECEU DE VERDADE. Escrita recusada pelo ERP
    # não é saída de etapa: o card não saiu do lugar, e registrar o checklist
    # como encerrado afirmaria um fato que não houve.
    #
    # ⚠️ E A FALHA AQUI NÃO DERRUBA O MOVER. O card já mudou de situação no
    # ERP; perder o recado é ruim, devolver erro a quem moveu com sucesso é
    # pior -- e a passagem já está gravada de qualquer jeito.
    de_onde = resposta.get("de")
    if resposta.get("ok") and de_onde and de_onde != para_situacao:
        try:
            texto = checklist.como_texto(numero_os, de_onde)
            if texto:
                observar(numero_os, texto, atendente_id)
        except Exception:
            log.exception("OS %s: nao consegui guardar o checklist da etapa %s",
                          numero_os, de_onde)
    log.info("OS %s: %s -> %s por %s (ok=%s, passagem %s)", numero_os,
             resposta.get("de"), para_situacao, atendente_id,
             resposta.get("ok"), passagem)
    return {**resposta, "passagem_id": passagem}


def historico(numero_os: int) -> list[dict]:
    """A linha do tempo das passagens desta OS — a nossa, porque o ERP não tem.

    🔵 É o que o card aberto (Bloco E) vai ler, e já existe desde agora.
    """
    return banco.varios(
        """SELECT p.id, p.de_situacao, p.para_situacao, p.em, p.ok, p.erro,
                  p.fora_da_situacao, a.nome AS quem
             FROM os_passagem p
             LEFT JOIN atendente a ON a.id = p.atendente_id
            WHERE p.numero_os = %s
            ORDER BY p.em DESC, p.id DESC""", (numero_os,))


def ultima_passagem(numero_os: int) -> dict | None:
    """A última passagem **confirmada** desta OS — o que faz o "Voltar" existir.

    🟡 Proposta minha que ele não precisou decidir, porque é consequência do
    log: sabendo de onde o card veio, voltar é **uma nova passagem**, nunca um
    "desfazer". ⚠️ A palavra importa: o ERP não desfaz nada, e dizer "desfazer"
    afirmaria que a primeira escrita não aconteceu — e ela aconteceu.
    """
    return banco.um(
        """SELECT de_situacao, para_situacao, em
             FROM os_passagem
            WHERE numero_os = %s AND ok AND de_situacao IS NOT NULL
            ORDER BY em DESC, id DESC
            LIMIT 1""", (numero_os,))


# ===========================================================================
# O ANEXO DA OBSERVAÇÃO (migração 091, 04/11)
#
# 🔵 *"Card OBS anexos, texto, format conve -- exibir em modal"*.
#
# 🚨 NÃO USA A TABELA `midia`, e não é escolha de estilo: o banco proíbe. O
# `CHECK midia_tem_um_dono` exige conversa **ou** sala, e observação de card não
# é nenhuma das duas. Afrouxar o CHECK abriria caminho para mídia órfã -- que é
# mídia que ninguém acha para apagar.
#
# ⚠️ O molde é o `formularios.py`: pasta própria fora do repositório, lista
# BRANCA de extensão, nome original preservado só para exibir, e o arquivo
# gravado com nome sorteado.
# ===========================================================================

PASTA_ANEXOS_OBS = pathlib.Path("/home/claude/movizap_observacao_anexos")
TETO_ANEXO_OBS = 10 * 1024 * 1024        # o mesmo do formulário

# 🚨 LISTA BRANCA, nunca lista negra: o que não está aqui não entra. Lista
# negra é aposta de que alguém lembrou de todas as extensões perigosas.
EXTENSOES_DA_OBS = {
    ".pdf", ".jpg", ".jpeg", ".png", ".webp", ".heic",
    ".doc", ".docx", ".xls", ".xlsx", ".csv", ".txt",
}


def guardar_anexo(observacao_id: int, nome: str, dados: bytes,
                  mime: str | None = None) -> dict:
    """Guarda um arquivo na observação, e devolve a linha gravada.

    ⚠️ RECUSA ANTES DE ESCREVER NO DISCO: extensão e tamanho são conferidos
    primeiro, para não deixar arquivo solto quando a linha não vai existir.
    """
    if not banco.um("SELECT id FROM os_observacao WHERE id = %s", (observacao_id,)):
        raise DadoInvalido("Observação não encontrada.")

    limpo = pathlib.Path(nome or "").name.strip() or "arquivo"
    extensao = pathlib.Path(limpo).suffix.lower()
    if extensao not in EXTENSOES_DA_OBS:
        raise DadoInvalido(
            f"{extensao or 'arquivo sem extensão'} não é um tipo aceito aqui. "
            f"Aceito: {', '.join(sorted(EXTENSOES_DA_OBS))}.")
    if len(dados) > TETO_ANEXO_OBS:
        raise DadoInvalido(
            f"O arquivo tem {len(dados) // 1024} KB e o limite é "
            f"{TETO_ANEXO_OBS // 1024 // 1024} MB.")
    if not dados:
        raise DadoInvalido("O arquivo veio vazio.")

    pasta = PASTA_ANEXOS_OBS / uuid.uuid4().hex
    pasta.mkdir(parents=True, exist_ok=True)
    destino = pasta / limpo
    destino.write_bytes(dados)

    linha = banco.um(
        """INSERT INTO os_observacao_arquivo
               (observacao_id, nome_original, caminho, bytes, mime)
           VALUES (%s, %s, %s, %s, %s) RETURNING id""",
        (observacao_id, limpo, str(destino), len(dados), mime))
    log.info("observacao %s: anexo %s guardado (%s bytes)",
             observacao_id, linha["id"], len(dados))
    return anexo(linha["id"])


def anexo(anexo_id: int) -> dict | None:
    return banco.um(
        """SELECT id, observacao_id, nome_original, caminho, bytes, mime,
                  criado_em
             FROM os_observacao_arquivo WHERE id = %s""", (anexo_id,))


def anexos_de(observacao_ids: list[int]) -> dict:
    """`{observacao_id: [anexos]}` — UMA consulta para a lista toda.

    ⚠️ O `caminho` NÃO sai daqui para a tela: é caminho de disco, e a tela não
    tem o que fazer com ele. Quem baixa usa o id.
    """
    if not observacao_ids:
        return {}
    por_obs: dict = {}
    for r in banco.varios(
            """SELECT id, observacao_id, nome_original, bytes, mime
                 FROM os_observacao_arquivo
                WHERE observacao_id = ANY(%s)
                ORDER BY id""", (list(observacao_ids),)):
        por_obs.setdefault(r["observacao_id"], []).append(r)
    return por_obs


def quem_mexeu(desde_dias: int = 7, teto: int = 200) -> list[dict]:
    """O log por pessoa. 🔵 *"o log de quem faz o que SEMPRE"* — e um log que
    ninguém consegue ler não cumpre o pedido."""
    return banco.varios(
        """SELECT p.numero_os, p.de_situacao, p.para_situacao, p.em, p.ok,
                  p.erro, a.nome AS quem
             FROM os_passagem p
             LEFT JOIN atendente a ON a.id = p.atendente_id
            WHERE p.em > now() - (%s || ' days')::interval
            ORDER BY p.em DESC
            LIMIT %s""", (desde_dias, teto))


# ----------------------------------------------------------------------------
# BLOCO C — de quando é a etapa atual de cada OS
# ----------------------------------------------------------------------------
# 🔵 *"o card mostra dois tempos: nesta etapa e total da OS"*.
#
# 🚨 UMA CONSULTA PARA TODOS OS CARDS. O quadro tem 11 cards e uma consulta por
# card seriam 11 idas ao banco por abertura de tela.


def etapa_desde(numeros: list[int]) -> dict:
    """`numero_os` -> quando a etapa atual começou, da última passagem CONFIRMADA.

    ⚠️ OS QUE NÃO ESTÁ NO RESULTADO NÃO TEM PASSAGEM, e isso é informação: a
    `os_passagem` começou em 29/10, então OS movida antes disso (ou nunca
    movida) não tem de onde tirar o tempo da etapa. Quem monta o card **diz
    "não medido"** em vez de inventar um zero -- a OS pode estar na etapa desde
    setembro e ninguém sabe.

    🚨 SÓ PASSAGEM CONFIRMADA (`ok`): uma tentativa recusada não moveu a OS, e
    contar o tempo a partir dela seria medir desde um evento que não aconteceu.
    """
    if not numeros:
        return {}
    linhas = banco.varios(
        """SELECT DISTINCT ON (numero_os) numero_os, em, de_situacao,
                  para_situacao
             FROM os_passagem
            WHERE ok AND numero_os = ANY(%s)
            ORDER BY numero_os, em DESC, id DESC""",
        ([int(n) for n in numeros],))
    return {linha["numero_os"]: linha for linha in linhas}


# ----------------------------------------------------------------------------
# A OBSERVAÇÃO DO PAINEL — Bloco F, fase 1 (migração 084)
# ----------------------------------------------------------------------------
# 🔵 *"observação do painel, com autor e hora, **no MoviZap**. Não vai para a
# `solucaoTecnica`"*.
#
# 🚨 NÃO SE APAGA E NÃO SE EDITA, e não há coluna para isso: reescrever recado é
# reescrever a história que a operação leu. É a mesma régua do *"log de quem faz
# o que SEMPRE"*.

PRIORIDADES = {381: "Baixa", 382: "Normal", 383: "Alta", 384: "Urgente"}


def observar(numero_os: int, texto: str, atendente_id: int | None) -> dict:
    """Grava uma observação do painel sobre a OS."""
    texto = (texto or "").strip()
    if not texto:
        raise DadoInvalido("Escreva a observação antes de salvar.")
    if len(texto) > 4000:
        raise DadoInvalido("A observação passa de 4000 caracteres.")
    linha = banco.um(
        """INSERT INTO os_observacao (numero_os, texto, atendente_id)
           VALUES (%s, %s, %s) RETURNING id, em""",
        (int(numero_os), texto, atendente_id))
    log.info("OS %s: observacao %s por %s", numero_os, linha["id"], atendente_id)
    return {"id": linha["id"], "em": linha["em"]}


def observacoes(numero_os: int) -> list[dict]:
    """As observações desta OS, da mais nova para a mais velha."""
    return banco.varios(
        """SELECT o.id, o.texto, o.em, a.nome AS quem
             FROM os_observacao o
             LEFT JOIN atendente a ON a.id = o.atendente_id
            WHERE o.numero_os = %s
            ORDER BY o.em DESC, o.id DESC""", (int(numero_os),))


def quantas_observacoes(numeros: list[int]) -> dict:
    """`numero_os` -> quantas observações. 🚨 UMA consulta para todos os cards.

    ⚠️ O card fechado mostra só o NÚMERO: recado é para ler no card aberto, e
    um trecho no card fechado faria a coluna crescer sem limite.
    """
    if not numeros:
        return {}
    linhas = banco.varios(
        """SELECT numero_os, count(*) AS quantas
             FROM os_observacao
            WHERE numero_os = ANY(%s)
            GROUP BY numero_os""", ([int(n) for n in numeros],))
    return {linha["numero_os"]: linha["quantas"] for linha in linhas}


def mudar_prioridade(numero_os: int, prioridade_id: int,
                     atendente_id: int | None,
                     prioridade_esperada: int | None = None) -> dict:
    """Muda a prioridade da OS no Harmonit, e REGISTRA quem mudou.

    🔵 *"deve ter o log de quem faz o que SEMPRE"* — vale para a prioridade
    como vale para a etapa. ⚠️ O registro vai na `os_observacao`, como uma
    linha escrita pelo sistema: criar uma segunda tabela de log para uma
    escrita de um campo seria tabela por campo.
    """
    if prioridade_id not in PRIORIDADES:
        raise DadoInvalido(
            f"A prioridade {prioridade_id} não existe. "
            f"As quatro são: {', '.join(PRIORIDADES.values())}.")

    resposta = fpsl_ponte.gravar_prioridade_da_os(
        numero_os, prioridade_id, prioridade_esperada=prioridade_esperada)

    if resposta.get("ok") and resposta.get("gravou"):
        de = PRIORIDADES.get(resposta.get("de"), resposta.get("de"))
        para = PRIORIDADES[prioridade_id]
        banco.executar(
            """INSERT INTO os_observacao (numero_os, texto, atendente_id)
               VALUES (%s, %s, %s)""",
            (int(numero_os), f"[sistema] prioridade: {de} → {para}",
             atendente_id))
    return resposta
