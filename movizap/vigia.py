"""Vigia dos canais — observa o estado mesmo com ninguém olhando.

🚨 POR QUE ISTO EXISTE

A auditoria de 2026-08-05 achou o defeito: `canal_evento` só era escrito
quando alguém ABRIA a CFG_1.1. E essa tabela existe exatamente para responder
*"desde quando parou de chegar mensagem?"*.

Se ninguém abrisse a tela por três dias e o canal caísse no primeiro,
o histórico registraria a queda no terceiro — no momento em que alguém olhou,
não no momento em que aconteceu. A resposta estaria errada por 48 horas, e
com toda a cara de estar certa.

Uma tabela de histórico que só avança quando observada não é histórico: é
uma foto tirada na hora errada.

⚠️ Roda dentro do processo do painel, não por cron. Com 1 worker isso é
suficiente e não precisa de agendador. Se um dia o serviço rodar com mais de
um worker, cada um vai vigiar por conta própria e a mesma mudança pode ser
gravada em duplicidade -- aí o vigia sai daqui para um processo só.
"""
import asyncio
import logging

from . import banco, canais, evolution

log = logging.getLogger("movizap.vigia")

INTERVALO_SEG = 60

# O Evolution acabou de reiniciar / a rede piscou: não vale acordar o painel
# inteiro. Só interessa quando o estado MUDA e permanece.
_falhas_seguidas = 0
LIMITE_AVISO = 5


def _uma_ronda(apenas_canal_id: int | None = None) -> None:
    """🚨 SÍNCRONA de propósito, e isso não é detalhe.

    `apenas_canal_id` existe para o teste: sem ele, a ronda varre TODOS os
    canais ativos, e um teste que finge "conectado" gravaria essa transição
    no histórico do canal de produção — mentindo sobre quando ele caiu, que é
    exatamente o que esta tabela existe para não fazer. Em produção o
    parâmetro é sempre `None`.

    `psycopg` e `httpx.Client` aqui são bloqueantes. Quem chama usa
    `asyncio.to_thread(_uma_ronda)`, que roda função COMUM numa thread e não
    trava o laço de eventos.

    Na primeira versão isto era `async def`. O efeito: `to_thread` executava
    a função na thread, ela devolvia uma corrotina, e ninguém a aguardava --
    o vigia subia, escrevia no log que estava ativo, e NÃO FAZIA NADA. O
    Python só reclamou com um RuntimeWarning que nem aparece em produção.
    """
    global _falhas_seguidas
    if apenas_canal_id is None:
        linhas = banco.varios(
            "SELECT id, instancia FROM canal "
            "WHERE ativo AND gateway='evolution' AND instancia IS NOT NULL"
        )
    else:
        linhas = banco.varios(
            "SELECT id, instancia FROM canal WHERE id=%s AND instancia IS NOT NULL",
            (apenas_canal_id,),
        )
    for c in linhas:
        try:
            estado = canais.traduzir(evolution.estado(c["instancia"]))
            _falhas_seguidas = 0
        except evolution.ErroEvolution:
            _falhas_seguidas += 1
            if _falhas_seguidas == LIMITE_AVISO:
                log.warning(
                    "Evolution sem responder há %d rondas (~%d min) -- o canal "
                    "pode estar fora do ar", LIMITE_AVISO,
                    LIMITE_AVISO * INTERVALO_SEG // 60)
            # 🚨 NÃO registrar 'desconectado' aqui. Evolution fora do ar não é
            # canal desconectado, e gravar isso poluiria o histórico com uma
            # queda que nunca houve.
            continue

        if canais.registrar_evento(c["id"], estado, "observado pelo vigia"):
            log.info("canal %s mudou para %s (visto pelo vigia)", c["id"], estado)


async def rodar(parar: asyncio.Event) -> None:
    """Laço do vigia. Encerra quando `parar` for acionado."""
    log.info("vigia dos canais ativo (a cada %ds)", INTERVALO_SEG)
    while not parar.is_set():
        try:
            await asyncio.to_thread(_uma_ronda)
        except Exception:
            # Vigia que morre em silêncio é pior que vigia nenhum: o histórico
            # pararia de avançar e ninguém saberia.
            log.exception("ronda do vigia falhou -- segue tentando")
        try:
            await asyncio.wait_for(parar.wait(), timeout=INTERVALO_SEG)
        except asyncio.TimeoutError:
            pass
    log.info("vigia dos canais encerrado")
