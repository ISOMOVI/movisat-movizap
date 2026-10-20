"""Distribuição automática da fila — 24/09.

🔵 Pedido dele: *"as conversas novas ou que fiquem 10min sem ninguem assumir,
vão automatiamente para a Ludmilla, coloque em uma caixa de seleção para que
eu mude isso quando quiser"*. E as respostas dele às perguntas:
  · 1a -- só entra conversa em que o cliente escreveu DEPOIS de ligar;
  · 2b -- nenhuma vai na hora: qualquer conversa sem dono vai após 10 min;
  · 3  -- *"se tiver time não vai a ela"*;
  · 4a -- *"Vão para Erika na mesma regra e depois fila se ambas estiverem
    offline"*, com aviso na tela.

🟡 Desenho meu: os 10 min contam da PRIMEIRA mensagem do cliente que ainda
espera (contar da última faria quem manda mensagem a cada 5 min nunca ser
distribuído); grupos ficam de fora; a nota na conversa é do SISTEMA.

🚨 A TRAVA DA CORRIDA é `conversas.transferir(..., so_se_sem_dono=True)`: quem
assumir no mesmo segundo ganha, e a distribuição não sobrescreve.
"""
import logging

from . import banco
from .operacao import DadoInvalido

log = logging.getLogger("movizap.distribuicao")

CHAVE_LIGADA = "distribuicao_ligada"
CHAVE_LIGADA_EM = "distribuicao_ligada_em"
CHAVE_PRIMEIRO = "distribuicao_primeiro"
CHAVE_RESERVA = "distribuicao_reserva"
CHAVE_MINUTOS = "distribuicao_minutos"
PADRAO_MINUTOS = 10


def _ler(chave: str) -> str | None:
    linha = banco.um("SELECT valor FROM config WHERE chave = %s", (chave,))
    return linha["valor"] if linha else None


def _int(valor: str | None) -> int | None:
    try:
        return int(valor) if valor not in (None, "") else None
    except ValueError:
        return None


def config() -> dict:
    return {
        "ligada": _ler(CHAVE_LIGADA) == "true",
        "ligada_em": _ler(CHAVE_LIGADA_EM),
        "primeiro_id": _int(_ler(CHAVE_PRIMEIRO)),
        "reserva_id": _int(_ler(CHAVE_RESERVA)),
        "minutos": _int(_ler(CHAVE_MINUTOS)) or PADRAO_MINUTOS,
    }


def definir_config(ligada: bool, primeiro_id: int | None, reserva_id: int | None,
                   minutos: int) -> dict:
    if not 1 <= int(minutos) <= 24 * 60:
        raise DadoInvalido("O tempo vai de 1 minuto a 24 horas.")
    if ligada and not primeiro_id:
        raise DadoInvalido("Escolha quem recebe antes de ligar.")
    if primeiro_id and reserva_id and int(primeiro_id) == int(reserva_id):
        raise DadoInvalido("A reserva tem de ser outra pessoa.")
    for aid in (primeiro_id, reserva_id):
        if aid and not banco.um(
                "SELECT 1 AS ok FROM atendente WHERE id = %s AND ativo AND transferivel",
                (aid,)):
            raise DadoInvalido("Essa pessoa não existe, está desligada ou não recebe conversa.")

    estava = config()["ligada"]
    with banco.cursor() as cur:
        def gravar(chave, valor, descricao):
            cur.execute(
                """INSERT INTO config (chave, valor, descricao, atualizado_em)
                   VALUES (%s, %s, %s, now())
                   ON CONFLICT (chave) DO UPDATE
                      SET valor = EXCLUDED.valor, atualizado_em = now()""",
                (chave, valor, descricao))
        gravar(CHAVE_LIGADA, "true" if ligada else "false",
               "Distribuição automática da fila. Nasce desligada.")
        gravar(CHAVE_PRIMEIRO, str(primeiro_id or ""), "Quem recebe a conversa parada.")
        gravar(CHAVE_RESERVA, str(reserva_id or ""), "Quem recebe se o primeiro estiver offline.")
        gravar(CHAVE_MINUTOS, str(int(minutos)), "Minutos sem ninguém assumir.")
        if ligada and not estava:
            # 🔵 1a: o que já estava parado ao ligar NÃO entra. O marco é este.
            cur.execute("SELECT now()::text AS agora")
            gravar(CHAVE_LIGADA_EM, cur.fetchone()["agora"],
                   "Quando a distribuição foi ligada: só entra mensagem depois disto.")
    log.info("distribuição %s (primeiro=%s reserva=%s, %s min)",
             "ligada" if ligada else "desligada", primeiro_id, reserva_id, minutos)
    return config()


# A conversa espera desde a PRIMEIRA mensagem do cliente depois da última
# resposta nossa (ou do marco de ligar, o que for mais recente).
_PARADAS = """
SELECT c.id,
       (SELECT min(m.criada_em) FROM mensagem m
         WHERE m.conversa_id = c.id AND m.direcao = 'entrada'
           AND m.criada_em > GREATEST(
                 %(marco)s::timestamptz,
                 COALESCE((SELECT max(s.criada_em) FROM mensagem s
                            WHERE s.conversa_id = c.id AND s.direcao = 'saida'),
                          '-infinity'::timestamptz))) AS esperando_desde
  FROM conversa c
  JOIN canal ca ON ca.id = c.canal_id
 WHERE c.atendente_id IS NULL
   AND c.estado IN ('nova', 'fila')
   AND c.time_id IS NULL
   AND c.tipo <> 'grupo'
   AND ca.tipo = 'atendimento'
   AND (%(somente)s::bigint[] IS NULL OR c.id = ANY(%(somente)s::bigint[]))
"""


def paradas(cfg: dict | None = None, somente: list[int] | None = None) -> list[dict]:
    """Conversas que já esperaram o tempo e ainda não têm dono."""
    cfg = cfg or config()
    if not cfg["ligada_em"]:
        return []
    linhas = banco.varios(
        "SELECT * FROM (" + _PARADAS + ") x "
        "WHERE esperando_desde IS NOT NULL "
        "  AND esperando_desde < now() - make_interval(mins => %(minutos)s) "
        "ORDER BY esperando_desde",
        {"marco": cfg["ligada_em"], "somente": somente, "minutos": cfg["minutos"]})
    return linhas


def _pode_receber_da_fila(aid: int, abertos: set[int]) -> tuple[bool, str]:
    """A régua da FILA, que é mais estreita que a da transferência à mão.

    🔵 19/10, decisão dele: dentro da jornada ninguém aparece como "fora do
    expediente" -- o máximo é "em pausa" --, **mas quem está com o painel
    fechado para de receber distribuição automática**. Separa o que a tela diz
    de quem recebe conversa.

    🚨 POR QUE AQUI E NÃO EM `presenca.pode_receber`: aquela função tem
    quatro chamadores, e três não são fila -- `transferir_abertas`, `afastar`
    (o substituto de quem sai de férias) e `operacao.inativar`. Barrar lá por
    painel fechado significaria **não conseguir afastar alguém porque o
    substituto não estava com a aba aberta**, e `_pode_substituir` já decidiu o
    oposto por escrito ("o que vale é o dia da saída"). Transferência à mão tem
    trava própria em `conversas.transferir` e fica intocada.

    ⚠️ O motivo volta em texto porque a tela precisa dele: "parada porque as
    duas estão offline" e "parada porque ninguém está com o painel aberto" não
    podem sair com a mesma frase (`M12`).
    """
    from .presenca import pode_receber
    ok, motivo = pode_receber(aid)
    if not ok:
        return False, motivo
    if aid not in abertos:
        return False, "painel fechado"
    return True, ""


def _destino(cfg: dict) -> int | None:
    from .presenca import painel_aberto_agora
    candidatos = [a for a in (cfg["primeiro_id"], cfg["reserva_id"]) if a]
    abertos = painel_aberto_agora(candidatos)
    for aid in candidatos:
        if _pode_receber_da_fila(aid, abertos)[0]:
            return aid
    return None


def distribuir(forcar: bool = False, somente: list[int] | None = None,
               cfg: dict | None = None) -> dict:
    """Uma passada. `forcar`/`somente`/`cfg` existem só para o teste -- a
    suíte roda em produção e não pode ligar a distribuição de verdade."""
    from . import conversas

    cfg = cfg or config()
    if not cfg["ligada"] and not forcar:
        return {"ligada": False, "distribuidas": [], "paradas_sem_destino": 0}
    lista = paradas(cfg, somente)
    if not lista:
        return {"ligada": True, "distribuidas": [], "paradas_sem_destino": 0}
    destino = _destino(cfg)
    if not destino:
        # 🔵 4a: as duas offline -> fica na fila, e a tela avisa.
        return {"ligada": True, "distribuidas": [], "paradas_sem_destino": len(lista)}

    feitas = []
    for linha in lista:
        r = conversas.transferir(linha["id"], None, destino, "inatividade",
                                 so_se_sem_dono=True)
        if not r.get("ok"):
            continue  # alguém assumiu antes, ou o destino ficou offline agora
        banco.executar(
            """INSERT INTO mensagem (conversa_id, direcao, autor, tipo, conteudo, criada_em)
               VALUES (%s, 'interna', 'sistema', 'nota', %s, now())""",
            (linha["id"], f"Distribuída automaticamente: {cfg['minutos']} min "
                          "sem ninguém assumir."))
        feitas.append(linha["id"])
    if feitas:
        log.info("distribuição: %d conversa(s) para o atendente %s", len(feitas), destino)
    return {"ligada": True, "distribuidas": feitas, "destino": destino,
            "paradas_sem_destino": 0}


def situacao(cfg: dict | None = None) -> dict:
    """O que a Fila e o Início mostram: se está ligada, para quem vai, e **por
    que** parou, quando parou.

    🚨 19/10: tem de passar pela MESMA `_pode_receber_da_fila` do
    `_destino`. Enquanto esta função tinha a sua própria conta, ela podia dizer
    "vai para a Ludmila" enquanto a fila ia para a Erika -- e a tela mentiria
    sem nada no log.

    ⚠️ `cfg` existe SÓ PARA O TESTE, como em `distribuir` e `paradas`, e entrou
    em 19/10 pagando um estrago: sem ele, o teste que eu escrevi para esta
    função chamou `definir_config` e **apagou a configuração real da
    distribuição** -- ela ficou desligada, apontando para atendentes de teste,
    até eu restaurar do dump das 02:40. Função que lê `config()` sem porta de
    teste é convite para o teste escrever em produção.
    """
    from .presenca import painel_aberto_agora

    cfg = cfg or config()
    if not cfg["ligada"]:
        return {"ligada": False}
    nomes = {r["id"]: r["nome"] for r in banco.varios(
        "SELECT id, nome FROM atendente WHERE id = ANY(%s)",
        ([x for x in (cfg["primeiro_id"], cfg["reserva_id"]) if x],))}
    candidatos = [x for x in (cfg["primeiro_id"], cfg["reserva_id"]) if x]
    abertos = painel_aberto_agora(candidatos)
    destino = _destino(cfg)
    primeiro_ok = False
    motivo_parada = ""
    if cfg["primeiro_id"]:
        primeiro_ok = _pode_receber_da_fila(cfg["primeiro_id"], abertos)[0]
    if destino is None and candidatos:
        motivos = {aid: _pode_receber_da_fila(aid, abertos)[1] for aid in candidatos}
        # Se todos pararam pelo mesmo motivo, a frase é esse motivo; se
        # pararam por motivos diferentes, a tela diz "ninguém disponível" em vez
        # de escolher um deles e mentir sobre o outro.
        distintos = set(motivos.values())
        motivo_parada = distintos.pop() if len(distintos) == 1 else "motivos diferentes"
    return {
        "ligada": True,
        "minutos": cfg["minutos"],
        "primeiro": nomes.get(cfg["primeiro_id"]),
        "reserva": nomes.get(cfg["reserva_id"]),
        "destino_agora": nomes.get(destino),
        "parada": destino is None,
        "esperando": len(paradas(cfg)) if destino is None else 0,
        "primeiro_disponivel": primeiro_ok,
        # 🔵 19/10: o MOTIVO, para o aviso da tela não chamar "painel fechado"
        # de "offline". Vazio quando a fila não parou.
        "parada_motivo": motivo_parada,
    }
