"""Canais: o que o banco sabe + o que o Evolution responde agora.

🚨 As duas fontes não são a mesma coisa e não podem ser confundidas:

    banco       o que a Movisat DECIDIU que existe (canal cadastrado)
    Evolution   o que está acontecendo AGORA (conectado, caiu, aguardando QR)

O banco é a verdade sobre configuração; o Evolution é a verdade sobre estado.
Guardar estado no banco e confiar nele é como se descobre, três dias depois,
que parou de chegar mensagem.
"""
import logging

from . import banco, evolution

log = logging.getLogger("movizap.canais")

# Vocabulário do Evolution -> o nosso. O `canal_evento.estado` é CHECK no
# banco: mapear aqui evita gravar um valor que a constraint recusa.
DE_EVOLUTION = {
    "open": "conectado",
    "connecting": "pareando",
    "close": "desconectado",
    "refused": "caiu",
}


def traduzir(estado_evolution: str) -> str:
    return DE_EVOLUTION.get(estado_evolution, "desconectado")


def registrar_evento(canal_id: int, estado: str, motivo: str | None = None) -> bool:
    """Grava mudança de estado — e SÓ quando muda.

    Gravar a cada consulta encheria a tabela de linhas iguais e afogaria a
    pergunta que ela existe para responder: *quando* mudou.
    """
    ultimo = banco.um(
        "SELECT estado FROM canal_evento WHERE canal_id=%s ORDER BY em DESC LIMIT 1",
        (canal_id,),
    )
    if ultimo and ultimo["estado"] == estado:
        return False
    banco.executar(
        "INSERT INTO canal_evento (canal_id, estado, motivo) VALUES (%s,%s,%s)",
        (canal_id, estado, motivo),
    )
    log.info("canal %s: %s%s", canal_id, estado, f" ({motivo})" if motivo else "")
    return True


def listar() -> list[dict]:
    """Os canais do banco, cada um com o estado ao vivo do Evolution."""
    canais = banco.varios(
        "SELECT id, nome, tipo, gateway, instancia, modo, ativo, criado_em "
        "FROM canal ORDER BY id"
    )
    for c in canais:
        c["estado"] = "desconhecido"
        c["numero"] = None
        c["erro"] = None
        if c["gateway"] != "evolution" or not c["instancia"]:
            continue
        try:
            bruto = evolution.estado(c["instancia"])
            c["estado"] = traduzir(bruto)
            if c["estado"] == "conectado":
                c["numero"] = evolution.numero(c["instancia"])
            registrar_evento(c["id"], c["estado"])
        except evolution.ErroEvolution as e:
            # 🚨 Falar "desconectado" quando o Evolution está fora do ar é
            # mentira: manda o atendente ler um QR que não vai aparecer.
            c["erro"] = str(e)
            c["estado"] = "indisponivel"
        c.update(_marcos(c["id"]))
    return canais


def _marcos(canal_id: int) -> dict:
    """Os números da tela: quando pareou, há quanto tempo, quantas quedas."""
    pareado = banco.um(
        "SELECT em FROM canal_evento WHERE canal_id=%s AND estado='conectado' "
        "ORDER BY em ASC LIMIT 1", (canal_id,))
    desde = banco.um(
        "SELECT em FROM canal_evento WHERE canal_id=%s AND estado='conectado' "
        "ORDER BY em DESC LIMIT 1", (canal_id,))
    quedas = banco.um(
        "SELECT COUNT(*) AS n FROM canal_evento WHERE canal_id=%s "
        "AND estado IN ('caiu','desconectado') AND em > now() - interval '24 hours'",
        (canal_id,))
    return {
        "pareado_em": pareado["em"] if pareado else None,
        "conectado_desde": desde["em"] if desde else None,
        "quedas_24h": quedas["n"] if quedas else 0,
    }


def por_id(canal_id: int) -> dict | None:
    return banco.um("SELECT * FROM canal WHERE id=%s", (canal_id,))


def eventos(canal_id: int, limite: int = 50) -> list[dict]:
    return banco.varios(
        "SELECT estado, motivo, em FROM canal_evento WHERE canal_id=%s "
        "ORDER BY em DESC LIMIT %s", (canal_id, limite))


def conectar(canal_id: int, quem: str) -> dict:
    """Pede o QR e registra a intenção.

    ⚠️ O QR expira em ~60 s. A tela chama de novo e recebe outro — não há
    estado a guardar entre chamadas.
    """
    canal = por_id(canal_id)
    if not canal:
        raise ValueError("canal não existe")
    if not canal["instancia"]:
        raise ValueError("canal sem instância configurada")

    qr = evolution.conectar(canal["instancia"])
    registrar_evento(canal_id, "aguardando_qr", f"QR pedido por {quem}")
    return qr


def confirmar_pareamento(canal_id: int, quem: str) -> dict:
    """Chamado quando a tela vê que conectou.

    🚨 É AQUI que as settings entram, não no arranque: settings aplicadas
    antes de a instância conectar não pegam, e o silêncio faz parecer que
    pegaram.
    """
    canal = por_id(canal_id)
    if not canal or not canal["instancia"]:
        raise ValueError("canal sem instância configurada")

    aplicadas = evolution.aplicar_settings(canal["instancia"])
    registrar_evento(canal_id, "conectado", f"pareado por {quem}")
    log.info("canal %s pareado; settings aplicadas: %s", canal_id, aplicadas)
    return aplicadas


def desconectar(canal_id: int, quem: str) -> None:
    canal = por_id(canal_id)
    if not canal or not canal["instancia"]:
        raise ValueError("canal sem instância configurada")
    evolution.desconectar(canal["instancia"])
    registrar_evento(canal_id, "desconectado", f"desconectado por {quem}")
