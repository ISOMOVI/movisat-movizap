"""A IA do atendimento — o passo 8, o que `docs/04_Contrato_IA.md` descreve.

Este módulo é a triagem: entende o que a pessoa quer, consulta o que dá para
consultar, resolve o simples e **entrega ao humano com contexto** o resto.
Quem fala com o modelo é o `movizap.llm`; quem sabe de conversa, contato e
cliente é este arquivo.

🚨 TRÊS TRAVAS, E NENHUMA DELAS É DISCIPLINA:

  1. **`canal.ia_ligada`** (migração 007), por canal. O informativo não tem
     como ligar. Nasce `false` -- "ninguém liga por acidente; ligar é um ato".
  2. **`relacao_automacao.ia_ligada`** (migração 032), por tipo de contato. É
     o filtro de desgaste pedido em 25/08.
  3. **`ia_atendeu_ate`** (migração 035), por mensagem. É o que impede
     responder duas vezes a mesma pergunta com duas threads rodando.

🚨 ELA CALA QUANDO UM HUMANO ASSUME, e não volta sozinha. `atendente_id` não
nulo ou `estado` em (`humano`, `fila`, `resolvida`) e este módulo sai sem
fazer nada. Devolver para o bot é ato de gente.

🚨 O QUE ELA NÃO CONSEGUE CONSULTAR ESTÁ ESCRITO NO PROMPT, EM VOZ ALTA.
`docs/04` prevê `listar_veiculos`, `posicao_veiculo` e `consultar_faturas`;
esses dados **não existem no banco do MoviZap** (não há tabela de veículo,
contrato nem fatura -- medido em 26/08) e o mesmo doc proíbe a IA de falar com
o Harmonit e com a WESO. Então elas NÃO são oferecidas, e o prompt diz que ela
não consegue -- em vez de deixá-la descobrir sozinha e inventar.
Essa é exatamente a classe de erro que reincidiu três vezes no MoviChat
(02/07, 15/07, 28/07): **a IA não distingue "não achei" de "não consigo ler",
e reporta ausência como fato.**
"""
import logging
import re

from . import banco, prompt as prompt_ia
from .llm import Params, SemChave, obter

log = logging.getLogger("movizap.ia")

# Teto do que sai para o cliente. WhatsApp aceita muito mais; parágrafo longo
# em tela de celular é o que ninguém lê.
TETO_RESPOSTA = 900

# 🚨 AGRUPAMENTO DE ENTRADA (`docs/04`): o cliente manda três mensagens
# seguidas e a IA trata as três como UMA. Responder cada uma isoladamente é a
# coisa que mais denuncia um robô. A espera é por SILÊNCIO -- se ele ainda
# está digitando, a varredura da próxima passada pega.
SILENCIO_S = 5

# Quantas mensagens da conversa em andamento vão no contexto. Não é a conversa
# inteira: `docs/04` limita o que ela enxerga, e mensagem antiga custa token
# em toda chamada.
JANELA = 12

# O que a IA NÃO consegue levantar hoje. Fica em constante e entra no prompt:
# é a diferença entre transferir e inventar.
SEM_ACESSO = ("veículo, placa ou rastreador", "posição ou localização",
              "contrato", "fatura, boleto ou pagamento")


# ── O catálogo ───────────────────────────────────────────────────────────────
#
# ⚠️ NENHUMA FERRAMENTA RECEBE ID DE OUTRA PESSOA. `docs/04` descreve
# `identificar_contato(telefone)` e `dados_cliente(cliente_id)` com parâmetro;
# aqui os dois são SEM ARGUMENTO e olham só para a conversa em curso. O
# parâmetro livre seria um caminho para convencer a IA a ler a ficha de outro
# cliente -- e a tabela do `docs/04` já diz que ela nunca enxerga "conversa de
# outro contato". Um parâmetro que só aceita um valor não é um parâmetro.
FERRAMENTAS = [
    {"type": "function", "function": {
        "name": "identificar_contato",
        "description": (
            "Quem é a pessoa desta conversa: nome, tipo de relação com a "
            "Movisat e a empresa dela, se estiver no cadastro. Use ANTES de "
            "supor qualquer coisa sobre quem está falando."),
        "parameters": {"type": "object", "properties": {}},
    }},
    {"type": "function", "function": {
        "name": "dados_cliente",
        "description": (
            "A empresa ligada a esta conversa: razão social, nome fantasia e "
            "situação do cadastro. Só funciona se o contato estiver "
            "identificado e vinculado a uma empresa."),
        "parameters": {"type": "object", "properties": {}},
    }},
    {"type": "function", "function": {
        "name": "historico_conversas",
        "description": (
            "Os atendimentos ANTERIORES desta mesma pessoa: quando, com que "
            "time e se foram resolvidos. Use quando ela disser que já falou "
            "com alguém, ou que é sobre o mesmo assunto de antes."),
        "parameters": {"type": "object", "properties": {}},
    }},
    {"type": "function", "function": {
        "name": "transferir",
        "description": (
            "Entrega a conversa para a fila de um time humano. Use quando "
            "não souber, quando o assunto exigir alguém, ou quando a pessoa "
            "pedir para falar com uma pessoa. Depois de transferir você não "
            "fala mais nesta conversa."),
        "parameters": {
            "type": "object",
            "properties": {
                "time": {"type": "string",
                         "description": "Nome exato de um dos times listados."},
                "resumo": {"type": "string", "description": (
                    "Nota INTERNA para o atendente, que o cliente não lê: "
                    "quem é, o que quer, o que você já apurou e o que falta.")},
                "despedida": {"type": "string", "description": (
                    "O que dizer ao cliente. Frase curta e natural. NUNCA "
                    "diga que vai transferir, nem cite time, fila ou "
                    "atendente.")},
            },
            "required": ["time", "resumo", "despedida"],
        },
    }},
    {"type": "function", "function": {
        "name": "encerrar",
        "description": (
            "Fecha o atendimento quando ele foi resolvido e a pessoa não "
            "precisa de mais nada. Na dúvida, não encerre: transfira."),
        "parameters": {
            "type": "object",
            "properties": {
                "motivo": {"type": "string",
                           "description": "Por que está resolvido. Nota interna."},
                "despedida": {"type": "string",
                              "description": "A última frase para o cliente."},
            },
            "required": ["motivo", "despedida"],
        },
    }},
]

# As regras que não dependem do texto versionado. Ficam em código de propósito:
# o prompt é editável na tela, e o que a IA NUNCA pode fazer não pode depender
# de ninguém lembrar de escrever de novo na versão seguinte.
CONDUTA = """\
REGRAS QUE VALEM SEMPRE, ACIMA DO TEXTO ACIMA:
- Nunca prometa prazo. Nem "amanhã", nem "em breve", nem "logo".
- Nunca dê desconto, isente ou negocie valor.
- Nunca confirme pagamento: quem dá baixa é o financeiro.
- Nunca cancele, suspenda nem altere contrato.
- Nunca fale de sistema, consulta, cadastro, base, API, erro ou falha. Se algo
  não deu certo do seu lado, transfira sem explicar por quê.
- Nunca invente. Se não sabe, transfira.
- Nunca repita CPF ou CNPJ inteiro na conversa.
- 🚨 SE VOCÊ DECIDIR PASSAR PARA UMA PESSOA, CHAME A FERRAMENTA transferir.
  Escrever "vou te passar para o time X" SEM chamar a ferramenta deixa o
  cliente esperando alguém que nunca vem: ninguém fica sabendo, a conversa não
  entra em fila nenhuma, e ele fica olhando para o WhatsApp. Anunciar não
  transfere; a ferramenta transfere.
- Não diga que vai transferir nem cite o nome do time: chame a ferramenta e
  escreva na despedida algo natural, como "já já alguém te responde por aqui".
- Não repita o nome de ninguém no começo da resposta. Responda direto.
- Se a pessoa pedir para falar com um humano, transfira na hora, sem insistir.
- Responda em uma mensagem curta, em português do Brasil.
- Você escreve no WhatsApp, não em markdown. Negrito é *assim*, itálico é
  _assim_. Nunca use **, ##, listas com - nem tabelas.
"""

# 🚨 ACHADO NO PRIMEIRO EXERCÍCIO CONTRA O MODELO REAL (26/08): ele devolveu
# "**Fulano**", e no WhatsApp isso aparece com os asteriscos, literalmente.
# A instrução acima reduz; esta função é o que garante -- instrução em prompt
# é pedido, não regra. O caminho `**x**` -> `*x*` preserva a intenção do
# negrito em vez de apagá-la.
_NEGRITO_MD = re.compile(r"\*\*(.+?)\*\*", re.DOTALL)
_CABECALHO_MD = re.compile(r"^\s{0,3}#{1,6}\s*", re.MULTILINE)


def para_whatsapp(texto: str) -> str:
    texto = _NEGRITO_MD.sub(r"*\1*", texto or "")
    return _CABECALHO_MD.sub("", texto).strip()


# ── Contexto ─────────────────────────────────────────────────────────────────

def _contexto(conversa_id: int) -> dict | None:
    """Tudo que a IA pode ver desta conversa, numa consulta só."""
    return banco.um(
        """SELECT c.id, c.estado, c.atendente_id, c.tipo, c.telefone_e164,
                  c.contato_id, c.nome_whatsapp, c.ia_atendeu_ate,
                  ca.id AS canal_id, ca.tipo AS canal_tipo, ca.instancia,
                  ca.ia_ligada AS canal_ia, ca.ia_ligada_em,
                  ct.nome AS contato_nome, ct.relacao, ct.cliente_id,
                  cl.nome AS cliente_nome, cl.nome_fantasia,
                  cl.ativo AS cliente_ativo
             FROM conversa c
             JOIN canal ca ON ca.id = c.canal_id
        LEFT JOIN contato ct ON ct.id = c.contato_id
        LEFT JOIN cliente cl ON cl.id = ct.cliente_id
            WHERE c.id = %s""", (conversa_id,))


def _ultima_entrada(conversa_id: int) -> dict | None:
    """A mensagem mais nova que o cliente mandou, e há quanto tempo."""
    return banco.um(
        """SELECT id, conteudo, tipo, criada_em,
                  EXTRACT(EPOCH FROM (now() - criada_em)) AS segundos
             FROM mensagem
            WHERE conversa_id = %s AND direcao = 'entrada'
            ORDER BY id DESC LIMIT 1""", (conversa_id,))


def _janela(conversa_id: int) -> list[dict]:
    """As últimas mensagens, mais velha primeiro. Nota interna fica de fora:
    ela é conversa entre nós, e a IA não precisa ler o que o atendente
    escreveu para o atendente."""
    linhas = banco.varios(
        """SELECT direcao, autor, tipo, conteudo FROM mensagem
            WHERE conversa_id = %s AND direcao <> 'interna'
            ORDER BY id DESC LIMIT %s""", (conversa_id, JANELA))
    return list(reversed(linhas))


def _times() -> list[dict]:
    return banco.varios(
        "SELECT id, nome, descricao FROM time WHERE ativo ORDER BY nome")


# ── O prompt de sistema ──────────────────────────────────────────────────────

def montar_sistema(ctx: dict) -> tuple[str, int | None]:
    """O texto que o modelo recebe. Devolve `(texto, prompt_versao_id)`.

    🚨 A VERSÃO VOLTA JUNTO PORQUE A CONVERSA GRAVA QUAL VERSÃO A ATENDEU.
    Sem `conversa.prompt_versao_id`, "a IA respondeu errado semana passada" é
    uma frase irrespondível: o texto já mudou.

    ⚠️ ORDEM PENSADA PARA O CACHE DO PROVEDOR: o que é igual em toda mensagem
    vem primeiro (prompt publicado, conduta, times), e o que muda por conversa
    vem no fim. Prefixo estável é o que a DeepSeek consegue reaproveitar.
    """
    try:
        montado = prompt_ia.montado()
    except prompt_ia.SemVersao:
        return "", None

    partes = [montado["texto"], "", CONDUTA, ""]

    partes.append("VOCÊ NÃO CONSEGUE CONSULTAR, DE JEITO NENHUM:")
    for item in SEM_ACESSO:
        partes.append(f"- {item}")
    partes.append(
        "Isso não é falta de dado: você simplesmente não tem essa consulta. "
        "Quando pedirem qualquer uma dessas coisas, transfira. Não diga que "
        "não encontrou, não diga que não tem acesso, não peça para aguardar.")
    partes.append("")

    partes.append("QUEM ESTÁ FALANDO COM VOCÊ:")
    if ctx.get("contato_nome"):
        partes.append(f"- Nome no cadastro: {ctx['contato_nome']}")
        partes.append(f"- Relação com a Movisat: {ctx.get('relacao') or 'não informada'}")
    elif ctx.get("nome_whatsapp"):
        partes.append(f"- Nome no WhatsApp: {ctx['nome_whatsapp']} (NÃO está no cadastro)")
    else:
        partes.append("- Não identificada: não está no cadastro e não tem nome no WhatsApp.")
    if ctx.get("cliente_nome"):
        partes.append(f"- Empresa: {ctx['cliente_nome']}")
    elif ctx.get("contato_id"):
        # 🚨 O CASO DO NÚMERO COMPARTILHADO (`docs/08_Identidade.md`): 44
        # números estavam em mais de um cliente e os duvidosos ficaram SEM
        # DONO. Devolver vazio é o comportamento certo -- chutar produziria
        # ficha errada na tela do atendente, que é pior que ficha nenhuma.
        partes.append("- Sem empresa vinculada. Se o assunto exigir saber de "
                      "qual empresa ela fala, PERGUNTE uma vez.")
    partes.append("")

    return "\n".join(partes), montado["id"]


def montar_mensagens(ctx: dict) -> tuple[list[dict], int | None]:
    sistema, versao_id = montar_sistema(ctx)
    if not sistema:
        return [], None
    mensagens = [{"role": "system", "content": sistema}]
    for m in _janela(ctx["id"]):
        texto = (m["conteudo"] or "").strip()
        if not texto:
            # Áudio, imagem e afins entram como o que são: a IA não os lê, e
            # fingir que a mensagem foi vazia faria ela responder ao nada.
            texto = f"[{m['tipo']}]"
        papel = "user" if m["direcao"] == "entrada" else "assistant"
        mensagens.append({"role": papel, "content": texto})
    if len(mensagens) == 1:
        return [], None
    return mensagens, versao_id


# ── As ferramentas ───────────────────────────────────────────────────────────

def _executor(ctx: dict, ensaio: bool, acoes: list):
    """Devolve a função que o gateway chama. `acoes` recolhe o que foi feito.

    ⚠️ EM ENSAIO, `transferir` E `encerrar` NÃO ESCREVEM. A sala de ensaio
    existe para exercitar o motor contra uma conversa de verdade sem mexer
    nela -- se ela transferisse, ensaiar seria operar.
    """
    def executar(nome: str, argumentos: dict):
        if nome == "identificar_contato":
            if not ctx.get("contato_id"):
                return {"identificado": False,
                        "como_responder": (
                            "Esta pessoa não está no cadastro. Pergunte o nome "
                            "e de qual empresa ela fala, uma vez.")}
            return {"identificado": True,
                    "nome": ctx.get("contato_nome"),
                    "relacao": ctx.get("relacao"),
                    "tem_empresa": bool(ctx.get("cliente_id"))}

        if nome == "dados_cliente":
            if not ctx.get("cliente_id"):
                return {"tem_empresa": False,
                        "como_responder": (
                            "Não há empresa vinculada a esta pessoa. Pergunte "
                            "de qual empresa ela fala, uma vez, e siga.")}
            return {"tem_empresa": True,
                    "razao_social": ctx.get("cliente_nome"),
                    "nome_fantasia": ctx.get("nome_fantasia"),
                    # ⚠️ Situação como palavra, não como booleano: "ativo:
                    # false" o modelo traduz para o cliente como "seu cadastro
                    # está inativo", que é falar do mecanismo.
                    "situacao": "em dia" if ctx.get("cliente_ativo") else "a confirmar"}

        if nome == "historico_conversas":
            if not ctx.get("contato_id"):
                return {"anteriores": []}
            linhas = banco.varios(
                """SELECT c.id, c.criada_em, c.estado, t.nome AS time_nome
                     FROM conversa c LEFT JOIN time t ON t.id = c.time_id
                    WHERE c.contato_id = %s AND c.id <> %s
                    ORDER BY c.id DESC LIMIT 5""",
                (ctx["contato_id"], ctx["id"]))
            return {"anteriores": [
                {"quando": str(l["criada_em"])[:10],
                 "time": l["time_nome"] or "sem triagem",
                 "resolvida": l["estado"] == "resolvida"} for l in linhas]}

        if nome == "transferir":
            alvo = (argumentos.get("time") or "").strip()
            times = _times()
            escolhido = next(
                (t for t in times if t["nome"].lower() == alvo.lower()), None)
            if escolhido is None:
                # ⚠️ Time inventado NÃO vira erro devolvido ao modelo: vira o
                # transbordo. Devolver "time inexistente" o faria tentar outro
                # nome, gastar rodada e às vezes desistir de transferir --
                # deixando o cliente com a IA. Perder a precisão do time é
                # muito menos grave que perder a transferência.
                escolhido = next(
                    (t for t in times if t["nome"].lower() == "geral"),
                    times[0] if times else None)
                log.warning("conversa %s: IA pediu time %r, caiu em %s",
                            ctx["id"], alvo, escolhido["nome"] if escolhido else "nenhum")
            despedida = (argumentos.get("despedida") or "").strip()
            resumo = (argumentos.get("resumo") or "").strip()
            acoes.append({"acao": "transferir",
                          "time": escolhido["nome"] if escolhido else None,
                          "resumo": resumo})
            if not ensaio and escolhido:
                _transferir(ctx, escolhido["id"], resumo)
            return {"__final__": despedida, "encerrou": True}

        if nome == "encerrar":
            despedida = (argumentos.get("despedida") or "").strip()
            motivo = (argumentos.get("motivo") or "").strip()
            acoes.append({"acao": "encerrar", "motivo": motivo})
            if not ensaio:
                _encerrar(ctx, motivo)
            return {"__final__": despedida, "encerrou": True}

        log.warning("conversa %s: ferramenta desconhecida %r", ctx["id"], nome)
        return {"erro": "ferramenta_desconhecida"}

    return executar


def _anotar_da_ia(conversa_id: int, texto: str) -> None:
    """A nota do handoff. `autor = 'ia'`, `atendente_id` NULO.

    🚨 Atribuir a nota da IA a uma pessoa faria o histórico dizer que alguém
    escreveu o que a máquina escreveu -- a mesma razão de
    `gravar_saida_automatica` deixar `atendente_id` nulo. O CHECK do banco
    amarra `tipo = 'nota'` a `direcao = 'interna'`: ela não tem como vazar
    para o cliente.
    """
    if not (texto or "").strip():
        return
    banco.executar(
        """INSERT INTO mensagem
               (conversa_id, direcao, autor, tipo, conteudo, criada_em)
           VALUES (%s, 'interna', 'ia', 'nota', %s, now())""",
        (conversa_id, texto.strip()[:4000]))


def _transferir(ctx: dict, time_id: int, resumo: str) -> None:
    from . import conversas
    _anotar_da_ia(ctx["id"], resumo)
    conversas.transferir(ctx["id"], time_id, None, motivo="ia_triagem",
                         texto_resumo=resumo or None)


def _encerrar(ctx: dict, motivo: str) -> None:
    _anotar_da_ia(ctx["id"], motivo)
    # ⚠️ NÃO passa pelo `conversas.encerrar`: aquele caminho pede atendente e
    # grava tempo de atendimento humano. `resolvida_pela_ia` existe desde a
    # migração 001 justamente para separar as duas coisas na estatística.
    banco.executar(
        """UPDATE conversa
              SET estado = 'resolvida', resolvida_em = now(),
                  resolvida_pela_ia = true, resolvida_por = NULL,
                  atualizada_em = now()
            WHERE id = %s AND estado <> 'resolvida'""", (ctx["id"],))


# ── O ponto de entrada ───────────────────────────────────────────────────────

def por_que_nao(ctx: dict) -> str | None:
    """O motivo de a IA não falar nesta conversa, ou `None` se ela pode.

    Separado de `responder` porque a sala de ensaio precisa do MESMO
    julgamento sem executá-lo -- e porque um motivo com nome é o que a tela
    mostra em vez de "nada aconteceu".
    """
    if ctx["tipo"] != "direta":
        return "grupo"                     # `docs/04`: nunca responde em grupo
    if ctx["canal_tipo"] != "atendimento":
        return "canal não atende"
    if not ctx["instancia"]:
        return "canal sem instância"
    if ctx["atendente_id"]:
        return "humano assumiu"
    if ctx["estado"] in ("humano", "fila", "resolvida"):
        return f"conversa {ctx['estado']}"
    return None


def _tipo_do_contato(contato_id: int | None) -> str:
    # ⚠️ A MESMA função da saudação, de propósito. Duas cópias da regra
    # divergiriam no dia em que ela mudasse, e `sem_cadastro` -- 64% dos casos
    # em 25/08 -- é onde isso doeria.
    from . import automacao
    return automacao.chave_do_contato(contato_id)


def responder(conversa_id: int, ensaio: bool = False,
              texto_de_ensaio: str | None = None) -> dict:
    """Faz a IA atender uma conversa. Sai sem fazer nada na maioria das vezes.

    `ensaio=True` roda o motor inteiro -- prompt, ferramentas, modelo -- sem
    enviar, sem gravar e sem transferir. É o passo 3 da sequência de ativação
    do `docs/04`: *validar o bot respondendo, em conversa de teste*.
    """
    from . import conversas, evolution

    ctx = _contexto(conversa_id)
    if not ctx:
        return {"respondeu": False, "motivo": "conversa inexistente"}

    impedimento = por_que_nao(ctx)
    if impedimento:
        return {"respondeu": False, "motivo": impedimento}

    if not ensaio:
        if not ctx["canal_ia"]:
            return {"respondeu": False, "motivo": "IA desligada no canal"}
        tipo = _tipo_do_contato(ctx["contato_id"])
        regra = banco.um(
            "SELECT ia_ligada FROM relacao_automacao WHERE relacao = %s", (tipo,))
        if not regra or not regra["ia_ligada"]:
            return {"respondeu": False, "motivo": "IA desligada para este tipo",
                    "tipo": tipo}

    entrada = _ultima_entrada(conversa_id)
    if not entrada:
        return {"respondeu": False, "motivo": "nada a responder"}
    if not ensaio:
        # 🚨 SÓ O QUE CHEGOU DEPOIS DE ELA SER LIGADA. Achado ao escrever o
        # teste da varredura, em 26/08: a base tem 357 conversas abertas, e
        # sem esta linha ligar o interruptor faria a IA responder a TODAS de
        # uma vez -- inclusive a mensagens de dias atrás, no meio de conversas
        # que já seguiram sem ela. É a MESMA lição da saudação automática, que
        # em 25/08 mandaria "seja bem-vindo" para gente no meio da conversa.
        #
        # ⚠️ `ia_ligada_em` já existia e existe para isto: "ligar é um ato", e
        # o ato tem hora. Antes da hora não é assunto dela.
        if not ctx["ia_ligada_em"] or entrada["criada_em"] <= ctx["ia_ligada_em"]:
            return {"respondeu": False, "motivo": "anterior a IA ser ligada"}
        if ctx["ia_atendeu_ate"] is not None and ctx["ia_atendeu_ate"] >= entrada["id"]:
            return {"respondeu": False, "motivo": "ja atendida"}
        if (entrada["segundos"] or 0) < SILENCIO_S:
            # Ainda digitando. A varredura da próxima passada pega -- e aí as
            # três mensagens viram uma.
            return {"respondeu": False, "motivo": "aguardando silencio"}

    gateway = obter()
    if not gateway.disponivel:
        return {"respondeu": False, "motivo": "motor sem chave"}

    mensagens, versao_id = montar_mensagens(ctx)
    if not mensagens:
        return {"respondeu": False, "motivo": "nenhuma versao de prompt publicada"}

    if ensaio and texto_de_ensaio:
        mensagens.append({"role": "user", "content": texto_de_ensaio.strip()})

    # 🚨 A MARCA VEM ANTES DA CHAMADA, e é o UPDATE condicionado que decide
    # quem manda. Mesma lição de `boas_vindas`: se marcar depois, duas threads
    # chamam o modelo e o cliente recebe duas respostas. Se a chamada falhar
    # depois da marca, ele fica sem resposta desta vez -- perda pequena, e a
    # próxima mensagem dele destrava (o id novo é maior que a marca).
    if not ensaio:
        ganhou = banco.executar(
            """UPDATE conversa SET ia_atendeu_ate = %s, atualizada_em = now()
                WHERE id = %s
                  AND (ia_atendeu_ate IS NULL OR ia_atendeu_ate < %s)""",
            (entrada["id"], conversa_id, entrada["id"]))
        if not ganhou:
            return {"respondeu": False, "motivo": "ja atendida"}

    acoes: list = []
    try:
        r = gateway.conversar(mensagens, FERRAMENTAS,
                              _executor(ctx, ensaio, acoes), Params())
    except SemChave:
        return {"respondeu": False, "motivo": "motor sem chave"}
    except Exception as e:                                    # noqa: BLE001
        log.exception("conversa %s: o motor falhou", conversa_id)
        return {"respondeu": False, "motivo": "falha no motor",
                "erro": e.__class__.__name__}

    texto = para_whatsapp(r["texto"])[:TETO_RESPOSTA]
    saida = {"respondeu": False, "texto": texto, "tokens": r["tokens"],
             "provedor": r["provedor"], "ferramentas": r["ferramentas_usadas"],
             "acoes": acoes, "prompt_versao_id": versao_id}

    if not texto:
        # 🚨 SILÊNCIO NÃO É RESPOSTA. Sem texto e sem ação, a conversa ficaria
        # marcada como atendida e ninguém apareceria. Transfere.
        log.warning("conversa %s: o motor devolveu vazio", conversa_id)
        saida["motivo"] = "motor devolveu vazio"
        if not ensaio:
            times = _times()
            alvo = next((t for t in times if t["nome"].lower() == "geral"),
                        times[0] if times else None)
            if alvo:
                _transferir(ctx, alvo["id"],
                            "A IA não conseguiu formular resposta. Assumido por "
                            "um humano sem que o cliente percebesse.")
                saida["acoes"] = [{"acao": "transferir", "time": alvo["nome"]}]
        return saida

    if ensaio:
        saida["motivo"] = "ensaio: nada foi enviado"
        return saida

    try:
        enviado = evolution.enviar_texto(ctx["instancia"], ctx["telefone_e164"], texto)
    except Exception as e:                                    # noqa: BLE001
        log.warning("conversa %s: envio da IA falhou (%s)",
                    conversa_id, e.__class__.__name__)
        saida["motivo"] = "falha no envio"
        return saida

    _gravar_saida_da_ia(conversa_id, texto, enviado, versao_id)
    if not acoes:
        # Continua com a IA. `estado = 'bot'` é o que a fila lê para saber que
        # esta não está "sem triagem" e sim sendo atendida pela máquina.
        banco.executar(
            "UPDATE conversa SET estado = 'bot' WHERE id = %s AND estado = 'nova'",
            (conversa_id,))
    log.info("conversa %s: IA respondeu (%s tokens, ferramentas=%s)",
             conversa_id, r["tokens"], r["ferramentas_usadas"] or "nenhuma")
    saida["respondeu"] = True
    return saida


def _gravar_saida_da_ia(conversa_id: int, texto: str, enviado: dict,
                        versao_id: int | None) -> None:
    """`autor = 'ia'`, e a versão do prompt fica gravada na conversa.

    ⚠️ NÃO MEXE EM `primeira_resposta_em`, pela mesma razão da saudação
    automática: se contasse, o tempo de primeira resposta humana viraria zero
    no dia em que a IA fosse ligada, e a métrica pareceria excelente
    justamente porque ninguém atendeu.
    """
    with banco.cursor() as cur:
        cur.execute(
            """INSERT INTO mensagem
                   (conversa_id, id_externo, direcao, autor, tipo, conteudo,
                    entrega, criada_em)
               VALUES (%s, %s, 'saida', 'ia', 'texto', %s, 'enviada', now())
               ON CONFLICT (id_externo) WHERE id_externo IS NOT NULL DO NOTHING""",
            (conversa_id, enviado.get("id_externo"), texto))
        cur.execute(
            """UPDATE conversa
                  SET ultima_atividade_em = now(), atualizada_em = now(),
                      prompt_versao_id = COALESCE(%s, prompt_versao_id)
                WHERE id = %s""", (versao_id, conversa_id))


# ── A varredura ──────────────────────────────────────────────────────────────

def pendentes(limite: int = 20) -> list[int]:
    """As conversas com pergunta esperando resposta da IA.

    🚨 NÃO É A FILA DO WEBHOOK. O `processar_pendentes` consome evento; esta
    lê ESTADO. É o que faz o agrupamento de entrada funcionar: quando a
    terceira mensagem chega, a conversa continua aqui, e a resposta sai uma
    vez só, depois do silêncio.

    🚨 `m.criada_em > ca.ia_ligada_em` NÃO É DETALHE. Sem essa linha, ligar o
    interruptor faria a IA responder às 357 conversas abertas de uma vez --
    mensagens de dias atrás, no meio de conversas que já seguiram sem ela.
    Achado ao escrever o teste da varredura, em 26/08.

    ⚠️ ORDEM PELA MAIS ANTIGA, COM TETO: quem espera há mais tempo é atendido
    primeiro. **`ORDER BY ... ASC LIMIT n` devolve as mais ANTIGAS** -- aqui
    isso é o certo, e é o oposto do defeito de corte sem paginação.
    """
    linhas = banco.varios(
        """SELECT c.id
             FROM conversa c
             JOIN canal ca ON ca.id = c.canal_id
            WHERE ca.ia_ligada AND ca.tipo = 'atendimento'
              AND ca.ia_ligada_em IS NOT NULL
              AND c.tipo = 'direta' AND c.atendente_id IS NULL
              AND c.estado IN ('nova', 'bot')
              AND EXISTS (SELECT 1 FROM mensagem m
                           WHERE m.conversa_id = c.id AND m.direcao = 'entrada'
                             AND (c.ia_atendeu_ate IS NULL OR m.id > c.ia_atendeu_ate)
                             AND m.criada_em > ca.ia_ligada_em
                             AND m.criada_em < now() - make_interval(secs => %s))
            ORDER BY c.ultima_atividade_em
            LIMIT %s""", (SILENCIO_S, limite))
    return [l["id"] for l in linhas]


def atender_pendentes(limite: int = 20) -> dict:
    """Uma passada da varredura. Chamada pelo laço de `conversas`."""
    contas = {"olhadas": 0, "respondidas": 0, "falhas": 0}
    for conversa_id in pendentes(limite):
        contas["olhadas"] += 1
        try:
            if responder(conversa_id).get("respondeu"):
                contas["respondidas"] += 1
        except Exception:                                     # noqa: BLE001
            contas["falhas"] += 1
            log.exception("IA falhou na conversa %s", conversa_id)
    return contas


# ── O que a tela pergunta ────────────────────────────────────────────────────

def estado() -> dict:
    """Se o motor existe, e por quê não, quando não existe.

    🚨 É AQUI QUE O INTERRUPTOR DA CFG_5.1 DESTRAVA, num lugar só. A tela não
    decide: ela desenha o que vem. `docs/09`, item 4 -- configuração não
    afirma o que o código não faz.
    """
    g = obter()
    e = g.estado()
    if not e["disponivel"]:
        e["motivo"] = ("O motor está no painel, mas não há chave de modelo no "
                       ".env (MOVIZAP_DEEPSEEK_API_KEY).")
        return e
    try:
        prompt_ia.montado()
    except prompt_ia.SemVersao:
        e["disponivel"] = False
        e["motivo"] = ("Nenhuma versão de prompt foi publicada ainda. Escreva "
                       "e publique o prompt na CFG_2.1 antes de ligar a IA.")
    return e
