"""Automação por tipo de contato — o filtro de uso pedido em 25/08.

Pedido do usuário: *"terá um interruptor nela que aciona IA ou bot, por tipo
de contato, então quando a mensagem chegar, será um filtro de uso ou não,
assim evitamos desgaste"*.

🚨 O QUE ACIONA HOJE É **BOAS-VINDAS**, E SÓ ISSO. Medido em 25/08:
`canal.ia_ligada` é lido em quatro lugares do código e nenhum age sobre ele --
não existe motor de IA no painel (o `services/llm/` do `IA_agente_Movichat`
nunca migrou) e não existe bot. `ia_ligada` fica guardado por relação e a tela
o mostra travado, com o motivo. `docs/09`, item 4: configuração não afirma o
que o código não faz.

🚨 O TIPO DE QUEM ESCREVEU, NÃO O DA CONVERSA. A conversa não tem tipo: quem
tem é a pessoa. E quando não há pessoa no cadastro -- 64% dos casos em 25/08 --
a linha que vale é `sem_cadastro`, que existe justamente porque é o caso
majoritário.
"""
import logging

from . import banco

log = logging.getLogger("movizap.automacao")

# ⚠️ Espelho do CHECK de `relacao_automacao` (migração 032). O banco é quem
# manda; esta tupla existe para a tela montar a lista e a rota recusar cedo.
CHAVES = ('cliente', 'fornecedor', 'parceiro', 'tecnico', 'lead',
          'colaborador', 'teste', 'sem_identificacao', 'sem_cadastro')

# O teto do texto é o mesmo da mensagem normal: quem escreve aqui está
# escrevendo uma mensagem de WhatsApp, não um documento.
TETO_TEXTO = 4000


def listar() -> list[dict]:
    """Uma linha por tipo, na ordem em que a tela mostra."""
    return banco.varios(
        """SELECT relacao, boas_vindas_ligado, boas_vindas_texto, ia_ligada,
                  atualizado_em,
                  -- Quantos contatos existem hoje com este tipo. É o número
                  -- que diz o ALCANCE de ligar o interruptor -- sem ele,
                  -- ligar "cliente" parece inofensivo e atinge 1.750 pessoas.
                  (SELECT count(*) FROM contato c
                    WHERE c.relacao = a.relacao AND c.ativo) AS contatos
             FROM relacao_automacao a
            ORDER BY a.relacao""")


def definir(relacao: str, boas_vindas_ligado: bool | None = None,
            boas_vindas_texto: str | None = None) -> dict:
    """Liga, desliga ou reescreve a mensagem de um tipo.

    🚨 NÃO SE LIGA SEM TEXTO. Interruptor ligado com texto vazio mandaria uma
    mensagem em branco para o cliente -- e o defeito só apareceria do lado
    dele. A recusa é aqui, com o motivo, e não no envio.
    """
    if relacao not in CHAVES:
        return {"ok": False, "motivo": f"Tipo desconhecido: {relacao!r}."}

    atual = banco.um(
        "SELECT boas_vindas_ligado, boas_vindas_texto FROM relacao_automacao "
        " WHERE relacao = %s", (relacao,))
    if not atual:
        return {"ok": False, "motivo": "Tipo sem linha de automação."}

    ligado = (atual["boas_vindas_ligado"] if boas_vindas_ligado is None
              else bool(boas_vindas_ligado))
    texto = (atual["boas_vindas_texto"] if boas_vindas_texto is None
             else (boas_vindas_texto or "").strip() or None)

    if texto and len(texto) > TETO_TEXTO:
        return {"ok": False,
                "motivo": f"A mensagem passa de {TETO_TEXTO} caracteres."}
    if ligado and not texto:
        return {"ok": False,
                "motivo": "Escreva a mensagem antes de ligar: ligado sem texto "
                          "mandaria uma mensagem em branco para o cliente."}

    banco.executar(
        """UPDATE relacao_automacao
              SET boas_vindas_ligado = %s, boas_vindas_texto = %s,
                  atualizado_em = now()
            WHERE relacao = %s""", (ligado, texto, relacao))
    log.info("automação de %s: boas-vindas %s", relacao,
             "ligada" if ligado else "desligada")
    return {"ok": True, "relacao": relacao, "boas_vindas_ligado": ligado}


def _chave_do_contato(contato_id: int | None) -> str:
    """Qual linha de `relacao_automacao` vale para quem escreveu."""
    if not contato_id:
        return "sem_cadastro"
    linha = banco.um("SELECT relacao FROM contato WHERE id = %s", (contato_id,))
    if not linha:
        return "sem_cadastro"
    return linha["relacao"] if linha["relacao"] in CHAVES else "sem_cadastro"


def boas_vindas(conversa_id: int) -> dict:
    """Manda a mensagem automática, se for o caso. Devolve o que aconteceu.

    Chamada quando uma mensagem de ENTRADA é gravada. Sai sem fazer nada na
    imensa maioria das vezes, e isso é o normal.

    🚨 A TRAVA DE "UMA VEZ SÓ" É DO BANCO. `UPDATE ... WHERE boas_vindas_em IS
    NULL` só passa uma vez, mesmo com dois processos entrando juntos -- e o
    Evolution reentrega webhook por desenho. Trava em `if` perderia a corrida,
    e o cliente receberia "seja bem-vindo" duas vezes.

    🚨 MARCA ANTES DE ENVIAR. Se o envio falhar depois da marca, o cliente fica
    sem a saudação -- perda pequena. Na ordem inversa, uma falha entre enviar e
    marcar faria a próxima mensagem dele disparar outra saudação, e mais outra.
    Repetir é pior do que faltar.

    ⚠️ NUNCA em grupo. Saudação automática num grupo de quinze pessoas é ruído
    para catorze delas.
    """
    from . import conversas, evolution  # tardio: os dois conhecem este módulo

    linha = banco.um(
        """SELECT c.id, c.contato_id, c.tipo, c.boas_vindas_em,
                  c.telefone_e164, ca.instancia, ca.tipo AS canal_tipo
             FROM conversa c JOIN canal ca ON ca.id = c.canal_id
            WHERE c.id = %s""", (conversa_id,))
    if not linha:
        return {"enviou": False, "motivo": "conversa inexistente"}
    if linha["tipo"] == "grupo":
        return {"enviou": False, "motivo": "grupo"}
    if linha["boas_vindas_em"]:
        return {"enviou": False, "motivo": "ja recebeu"}
    if linha["canal_tipo"] != "atendimento" or not linha["instancia"]:
        return {"enviou": False, "motivo": "canal nao atende"}

    chave = _chave_do_contato(linha["contato_id"])
    regra = banco.um(
        """SELECT boas_vindas_ligado, boas_vindas_texto FROM relacao_automacao
            WHERE relacao = %s""", (chave,))
    if not regra or not regra["boas_vindas_ligado"] or not regra["boas_vindas_texto"]:
        return {"enviou": False, "motivo": "desligado", "tipo": chave}

    # A corrida se resolve aqui: quem ganhar o UPDATE manda.
    ganhou = banco.executar(
        """UPDATE conversa SET boas_vindas_em = now()
            WHERE id = %s AND boas_vindas_em IS NULL""", (conversa_id,))
    if not ganhou:
        return {"enviou": False, "motivo": "ja recebeu"}

    try:
        enviado = evolution.enviar_texto(
            linha["instancia"], linha["telefone_e164"],
            regra["boas_vindas_texto"])
    except Exception as e:                                    # noqa: BLE001
        # ⚠️ A marca FICA. Tentar de novo na próxima mensagem transformaria
        # uma indisponibilidade momentânea em saudação atrasada e fora de
        # contexto, no meio de uma conversa já em andamento.
        log.warning("boas-vindas falhou na conversa %s (%s)",
                    conversa_id, e.__class__.__name__)
        return {"enviou": False, "motivo": "falha no envio", "tipo": chave}

    conversas.gravar_saida_automatica(
        conversa_id, regra["boas_vindas_texto"], enviado)
    log.info("boas-vindas enviada na conversa %s (tipo %s)", conversa_id, chave)
    return {"enviou": True, "tipo": chave}
