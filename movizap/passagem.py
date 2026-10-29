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

from . import banco, fpsl_ponte, paineis
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
