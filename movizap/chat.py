"""ATD_6.1 — chat entre atendentes.

Resolve "falar sobre qualquer coisa". A **nota interna** resolve "falar sobre
ESTA conversa" e continua onde está — as duas convivem de propósito.

🚨 NADA AQUI TOCA EM `conversa` NEM EM `mensagem`. É a decisão da migração 026:
tabelas próprias, para que nenhuma consulta sobre conversa de cliente precise
lembrar de filtrar chat interno. Filtro que precisa ser lembrado em seis
lugares é defeito esperando data.

⚠️ NÃO É CANAL DE CLIENTE. Nada daqui sai para o WhatsApp, e não existe caminho
para isso — este módulo não conhece o `evolution`.
"""
import logging

from . import banco

log = logging.getLogger(__name__)

TETO_TEXTO = 4000

# 🔵 TETO MEU, ROTULADO COMO MEU. Não há decisão do usuário sobre quantas
# pessoas se pode chamar numa mensagem; 20 é maior que a equipe inteira (5
# atendentes hoje), então na prática ele não morde ninguém — existe só para
# que uma lista vinda do cliente não vire uma inserção sem fim.
# **Limite é decisão dele:** se um dia isto apertar, o número é dele, não meu.
TETO_MENCOES = 20


def _chave_do_par(a: int, b: int) -> str:
    """'menor:maior' — a chave que impede sala duplicada para o mesmo par.

    🚨 Precisa ser a MESMA string independente de quem começou a conversa.
    Ordenar é o que garante isso: sem ordenar, `12:34` e `34:12` seriam duas
    salas para as mesmas duas pessoas.
    """
    return f"{min(a, b)}:{max(a, b)}"


def abrir_direta(eu: int, outro: int) -> dict:
    """Acha ou cria a sala direta entre duas pessoas.

    🚨 `ON CONFLICT` NA CHAVE DO PAR, não "procura e depois insere". Dois
    atendentes clicando um no outro no mesmo segundo passariam os dois pela
    busca antes de qualquer inserção, e criariam duas salas -- a conversa se
    partiria em duas metades sem nada acusar.
    """
    if eu == outro:
        return {"ok": False, "motivo": "Não dá para conversar consigo mesmo."}

    alvo = banco.um("SELECT id, nome, ativo FROM atendente WHERE id = %s",
                    (outro,))
    if not alvo:
        return {"ok": False, "motivo": "Atendente não encontrado."}
    if not alvo["ativo"]:
        return {"ok": False, "motivo": f"{alvo['nome']} está inativo."}

    par = _chave_do_par(eu, outro)
    with banco.cursor() as cur:
        cur.execute(
            """INSERT INTO chat_sala (tipo, par) VALUES ('direta', %s)
               ON CONFLICT (par) DO UPDATE SET par = EXCLUDED.par
               RETURNING id""", (par,))
        sala_id = cur.fetchone()["id"]
        # Conflito esperado se ignora: reabrir a sala não pode zerar o
        # `lido_ate` de ninguém -- isso faria tudo voltar a parecer não lido.
        for pessoa in (eu, outro):
            cur.execute(
                """INSERT INTO chat_membro (sala_id, atendente_id)
                   VALUES (%s, %s) ON CONFLICT DO NOTHING""",
                (sala_id, pessoa))
    return {"ok": True, "sala_id": sala_id, "com": alvo["nome"]}


TETO_NOME_GRUPO = 60


def criar_grupo(nome: str, criador: int, membros: list[int]) -> dict:
    """Cria um grupo e põe o criador junto com quem ele escolheu.

    ⚠️ O CRIADOR ENTRA SEMPRE, mesmo que não esteja na lista. Criar um grupo e
    ficar de fora dele não é caso de uso -- é engano de quem montou a lista.

    ⚠️ GRUPO NÃO TEM CHAVE DE PAR. Dois grupos com o mesmo nome são grupos
    diferentes, e é assim de propósito: "Financeiro" criado hoje e "Financeiro"
    criado ano que vem não são a mesma conversa. O CHECK do banco garante que
    grupo tem `nome` e não tem `par`.
    """
    nome = (nome or "").strip()
    if not nome:
        return {"ok": False, "motivo": "O grupo precisa de um nome."}
    if len(nome) > TETO_NOME_GRUPO:
        return {"ok": False,
                "motivo": f"Nome passa de {TETO_NOME_GRUPO} caracteres."}

    escolhidos = {int(m) for m in (membros or [])} | {criador}
    validos = {r["id"] for r in banco.varios(
        "SELECT id FROM atendente WHERE ativo AND id = ANY(%s)",
        (sorted(escolhidos),))}
    fora = escolhidos - validos
    if fora:
        return {"ok": False,
                "motivo": f"Atendente inativo ou inexistente: {sorted(fora)}"}
    if len(validos) < 2:
        return {"ok": False, "motivo": "Um grupo precisa de mais alguém."}

    with banco.cursor() as cur:
        cur.execute(
            "INSERT INTO chat_sala (tipo, nome) VALUES ('grupo', %s) RETURNING id",
            (nome,))
        sala_id = cur.fetchone()["id"]
        for pessoa in sorted(validos):
            cur.execute(
                """INSERT INTO chat_membro (sala_id, atendente_id)
                   VALUES (%s, %s) ON CONFLICT DO NOTHING""", (sala_id, pessoa))
    log.info("grupo %s criado por %s com %s membros",
             sala_id, criador, len(validos))
    return {"ok": True, "sala_id": sala_id, "nome": nome,
            "membros": len(validos)}


def membros(sala_id: int, eu: int | None = None) -> list[dict]:
    """Quem está na sala. Com `eu`, marca qual dos membros é quem perguntou.

    ⚠️ MESMO PADRÃO DO `minha` DAS MENSAGENS: quem sabe quem é "eu" nesta
    requisição é quem a atendeu. A tela comparando ids por conta própria é o
    tipo de coisa que passa a mentir quando a sessão muda de forma.
    """
    return banco.varios(
        """SELECT m.atendente_id, a.nome, m.entrou_em,
                  (m.atendente_id = %s) AS sou_eu
             FROM chat_membro m JOIN atendente a ON a.id = m.atendente_id
            WHERE m.sala_id = %s ORDER BY m.entrou_em, a.nome""", (eu, sala_id))


def adicionar_ao_grupo(sala_id: int, quem_pede: int, novo: int) -> dict:
    """Chama alguém para um grupo. Só quem está dentro pode chamar.

    ⚠️ NÃO VALE PARA SALA DIRETA: conversa de duas pessoas que vira de três é
    outra conversa, e transformá-la escondido faria as duas primeiras
    descobrirem a terceira lendo o histórico.
    """
    sala = banco.um("SELECT id, tipo FROM chat_sala WHERE id = %s", (sala_id,))
    if not sala:
        return {"ok": False, "motivo": "Conversa não encontrada."}
    if sala["tipo"] != "grupo":
        return {"ok": False,
                "motivo": "Conversa direta não recebe gente. Crie um grupo."}
    if not e_membro(sala_id, quem_pede):
        return {"ok": False, "motivo": "Você não está neste grupo."}

    alvo = banco.um("SELECT id, nome, ativo FROM atendente WHERE id = %s", (novo,))
    if not alvo:
        return {"ok": False, "motivo": "Atendente não encontrado."}
    if not alvo["ativo"]:
        return {"ok": False, "motivo": f"{alvo['nome']} está inativo."}
    if e_membro(sala_id, novo):
        return {"ok": True, "sala_id": sala_id, "nome": alvo["nome"],
                "ja_estava": True}

    # 🚨 `lido_ate` fica NULO de propósito: quem entra agora NÃO ganha o
    # histórico como "já lido", mas também não recebe um contador com tudo que
    # foi dito antes dele. Quem chega vê a conversa e o contador conta a partir
    # da próxima mensagem -- por isso o `lido_ate` recebe o último id atual.
    ultimo = banco.um(
        "SELECT max(id) AS id FROM chat_mensagem WHERE sala_id = %s", (sala_id,))
    # Sair do grupo apaga a linha, então voltar é INSERT limpo -- o
    # `DO NOTHING` é só a rede para o clique duplo.
    banco.executar(
        """INSERT INTO chat_membro (sala_id, atendente_id, lido_ate)
           VALUES (%s, %s, %s) ON CONFLICT DO NOTHING""",
        (sala_id, novo, (ultimo or {}).get("id")))
    return {"ok": True, "sala_id": sala_id, "nome": alvo["nome"]}


def sair_do_grupo(sala_id: int, eu: int) -> dict:
    """Sai de um grupo. A sala continua para os outros.

    ⚠️ Não apaga a sala nem quando sai o último: as mensagens são o registro
    do que foi combinado, e apagar conversa por esvaziamento perderia isso sem
    ninguém pedir.
    """
    sala = banco.um("SELECT id, tipo FROM chat_sala WHERE id = %s", (sala_id,))
    if not sala:
        return {"ok": False, "motivo": "Conversa não encontrada."}
    if sala["tipo"] != "grupo":
        return {"ok": False, "motivo": "Não dá para sair de uma conversa direta."}
    if not e_membro(sala_id, eu):
        return {"ok": False, "motivo": "Você não está neste grupo."}
    banco.executar(
        "DELETE FROM chat_membro WHERE sala_id = %s AND atendente_id = %s",
        (sala_id, eu))
    return {"ok": True, "sala_id": sala_id}


def esconder(sala_id: int, eu: int) -> dict:
    """Tira a conversa da MINHA lista. Não apaga nada, e não afeta o outro.

    Pedido dele em 27/08: *"botão de excluir conversa"*, na tela que ele mandou
    desenhar como a caixa de entrada do WhatsApp.

    🚨 É O QUE "EXCLUIR CONVERSA" FAZ NO WHATSAPP, e é a única versão segura.
    Apagar a sala levaria junto o histórico da OUTRA pessoa, que não pediu nada
    e não tem como desfazer -- e conversa interna é prova de combinado: quem
    disse o quê sobre um atendimento.

    ⚠️ VOLTA SOZINHA na próxima mensagem. Guardar ATÉ QUE MENSAGEM foi
    escondida, em vez de um booleano, é o que permite isso sem um segundo
    lugar para saber quando ela reaparece.
    """
    if not e_membro(sala_id, eu):
        return {"ok": False, "motivo": "Você não está nesta conversa."}
    ultima = banco.um(
        "SELECT COALESCE(MAX(id), 0) AS id FROM chat_mensagem WHERE sala_id = %s",
        (sala_id,))
    banco.executar(
        "UPDATE chat_membro SET oculta_ate_id = %s "
        " WHERE sala_id = %s AND atendente_id = %s",
        (ultima["id"], sala_id, eu))
    log.info("chat: sala %s escondida para %s ate a mensagem %s",
             sala_id, eu, ultima["id"])
    return {"ok": True, "sala_id": sala_id, "ate_id": ultima["id"]}


def mostrar(sala_id: int, eu: int) -> dict:
    """Desfaz o esconder. Abrir a conversa pelo endereço dela já faz isto."""
    banco.executar(
        "UPDATE chat_membro SET oculta_ate_id = NULL "
        " WHERE sala_id = %s AND atendente_id = %s", (sala_id, eu))
    return {"ok": True, "sala_id": sala_id}


def salas(eu: int) -> list[dict]:
    """As salas desta pessoa, com quem é, a última mensagem e o não lido.

    ⚠️ Ordena por atividade e não por nome: o que acabou de chegar tem de
    estar no topo, como em qualquer chat.
    """
    return banco.varios(
        """
        SELECT s.id, s.tipo, s.nome,
               -- 🚨 SÓ NA SALA DIRETA o "com" é a outra pessoa. Sem o
               -- `CASE`, um grupo de cinco mostraria o nome de UM membro
               -- qualquer (o LIMIT 1 escolhe sem critério) no lugar do nome
               -- do grupo -- e a lista ficaria com salas que ninguém
               -- reconhece.
               CASE WHEN s.tipo = 'direta' THEN
                 (SELECT a.nome FROM chat_membro m2
                    JOIN atendente a ON a.id = m2.atendente_id
                   WHERE m2.sala_id = s.id AND m2.atendente_id <> %s
                   LIMIT 1)
               END AS com,
               -- 🚨 O ESTADO DA OUTRA PESSOA. `atendente.estado` existe desde
               -- a migração 001 e NENHUMA tela o usava. Num canal interno é
               -- ele que responde a pergunta que se faz antes de escrever:
               -- adianta chamar agora? Só na sala direta -- num grupo de
               -- cinco, o estado de quem?
               CASE WHEN s.tipo = 'direta' THEN
                 (SELECT a.estado FROM chat_membro m4
                    JOIN atendente a ON a.id = m4.atendente_id
                   WHERE m4.sala_id = s.id AND m4.atendente_id <> %s
                   LIMIT 1)
               END AS com_estado,
               (SELECT count(*) FROM chat_membro m3
                 WHERE m3.sala_id = s.id) AS qtd_membros,
               u.texto  AS ultima_mensagem,
               u.criada_em AS ultima_em,
               ua.nome  AS ultimo_autor,
               (SELECT count(*) FROM chat_mensagem x
                 WHERE x.sala_id = s.id
                   AND x.atendente_id <> %s
                   AND x.id > COALESCE(m.lido_ate, 0)) AS nao_lidas
          FROM chat_membro m
          JOIN chat_sala s ON s.id = m.sala_id
          LEFT JOIN LATERAL (
                SELECT id, texto, criada_em, atendente_id FROM chat_mensagem c
                 WHERE c.sala_id = s.id ORDER BY c.id DESC LIMIT 1
          ) u ON true
          LEFT JOIN atendente ua ON ua.id = u.atendente_id
         WHERE m.atendente_id = %s
           -- 🚨 A CONVERSA ESCONDIDA SOME DA LISTA, E VOLTA SOZINHA quando
           -- chega mensagem nova (migração 038). Esconder não pode virar um
           -- jeito de deixar de receber recado da equipe.
           --
           -- ⚠️ SALA VAZIA ESCONDIDA CONTINUA ESCONDIDA: sem o `COALESCE`, uma
           -- conversa sem nenhuma mensagem teria `u.id` NULL e o `>` daria
           -- NULL -- que não é verdadeiro, mas também não é o que se quer
           -- dizer. Com o zero, a comparação é explícita.
           AND (m.oculta_ate_id IS NULL
                OR COALESCE(u.id, 0) > m.oculta_ate_id)
         ORDER BY COALESCE(u.criada_em, s.criada_em) DESC
        """,
        # 🚨 QUATRO `%s`, NÃO TRÊS. O `com_estado` acrescentou um placeholder no
        # meio da consulta, e psycopg casa por POSIÇÃO.
        #
        # ⚠️ E ESTE COMENTÁRIO FICA FORA DAS ASPAS. Escrevi-o dentro da string
        # na primeira tentativa: o `%s` do próprio texto virou um QUINTO
        # placeholder e o psycopg recusou a consulta. Comentário dentro de SQL
        # é SQL.
        (eu, eu, eu, eu))


def e_membro(sala_id: int, eu: int) -> bool:
    """A régua de acesso: só quem está na sala lê e escreve nela.

    🚨 DIFERENTE DA CONVERSA DE CLIENTE, AQUI O ISOLAMENTO É REAL. Conversa de
    cliente é responsabilidade coletiva e qualquer atendente pode ler. Conversa
    entre duas pessoas não é -- ler a conversa alheia não é "colaborar".
    """
    return banco.um(
        "SELECT 1 FROM chat_membro WHERE sala_id = %s AND atendente_id = %s",
        (sala_id, eu)) is not None


def mensagens(sala_id: int, eu: int, limite: int = 500) -> list[dict]:
    """As mensagens da sala, das mais antigas para as mais novas.

    ⚠️ Pega as N mais RECENTES e reordena — o mesmo cuidado do `conversas`:
    `ORDER BY id ASC LIMIT n` devolveria o começo da sala e esconderia o que
    acabou de ser dito.
    """
    linhas = banco.varios(
        """SELECT * FROM (
               SELECT c.id, c.texto, c.criada_em, c.atendente_id,
                      a.nome AS autor, (c.atendente_id = %s) AS minha
                 FROM chat_mensagem c
                 JOIN atendente a ON a.id = c.atendente_id
                WHERE c.sala_id = %s
                ORDER BY c.id DESC LIMIT %s
           ) recentes ORDER BY id""", (eu, sala_id, limite))
    _juntar_mencoes(linhas, eu)
    return linhas


def _juntar_mencoes(linhas: list[dict], eu: int) -> None:
    """Pendura em cada mensagem quem ela chamou.

    ⚠️ UMA CONSULTA PARA A JANELA INTEIRA, não uma por mensagem. São até 500
    mensagens por sala; consultar de uma em uma seria 500 idas ao banco para
    desenhar uma tela.

    ⚠️ `me_chamou` vem pronto do backend. A tela não deve descobrir isso
    comparando ids: quem sabe quem é "eu" nesta requisição é quem a atendeu.
    """
    if not linhas:
        return
    ids = [linha["id"] for linha in linhas]
    por_mensagem: dict[int, list[dict]] = {}
    for m in banco.varios(
        """SELECT mc.mensagem_id, mc.atendente_id, a.nome
             FROM chat_mencao mc
             JOIN atendente a ON a.id = mc.atendente_id
            WHERE mc.mensagem_id = ANY(%s)
            ORDER BY a.nome""", (ids,)):
        por_mensagem.setdefault(m["mensagem_id"], []).append(
            {"id": m["atendente_id"], "nome": m["nome"]})
    for linha in linhas:
        chamados = por_mensagem.get(linha["id"], [])
        linha["mencionados"] = chamados
        linha["me_chamou"] = any(c["id"] == eu for c in chamados)


def escrever(sala_id: int, eu: int, texto: str,
             mencionados: list[int] | None = None) -> dict:
    """Grava a mensagem e, com ela, quem foi chamado por `@`.

    🚨 QUEM RESOLVE O `@` É QUEM ESCREVE. O compositor manda os IDS que a
    pessoa escolheu na lista; aqui só se CONFERE que cada um é membro da sala.
    Um regex lendo o texto teria de adivinhar onde o nome termina
    ("@Suporte Erika" tem espaço no meio), casar apelido e desempatar homônimo
    -- e erraria em silêncio nos três casos.

    🚨 CHAMAR QUEM NÃO ESTÁ NA SALA É RECUSA, NÃO REMENDO. Aceitar e ignorar
    faria a pessoa achar que avisou alguém que nunca vai ver a mensagem -- é o
    "parâmetro aceito e ignorado", que é o pior defeito que este projeto
    cataloga. A recusa diz o nome de quem não está.

    ⚠️ A MENSAGEM E AS MENÇÕES ENTRAM NA MESMA TRANSAÇÃO. Meia gravação --
    mensagem sem menção -- seria pior que nenhuma: a pessoa veria a mensagem
    enviada e ninguém seria chamado.
    """
    texto = (texto or "").strip()
    if not texto:
        return {"ok": False, "motivo": "Mensagem vazia."}
    if len(texto) > TETO_TEXTO:
        return {"ok": False,
                "motivo": f"Mensagem passa de {TETO_TEXTO} caracteres."}
    if not e_membro(sala_id, eu):
        return {"ok": False, "motivo": "Você não está nesta conversa."}

    chamados = _conferir_mencionados(sala_id, mencionados)
    if isinstance(chamados, dict):          # veio recusa, não lista
        return chamados

    with banco.cursor() as cur:
        cur.execute(
            """INSERT INTO chat_mensagem (sala_id, atendente_id, texto)
               VALUES (%s, %s, %s) RETURNING id, criada_em""",
            (sala_id, eu, texto))
        linha = cur.fetchone()
        for quem in chamados:
            cur.execute(
                """INSERT INTO chat_mencao (mensagem_id, atendente_id)
                   VALUES (%s, %s) ON CONFLICT DO NOTHING""",
                (linha["id"], quem))

    # ⚠️ Quem escreve leu o que escreveu: sem isto a própria mensagem entraria
    # como não lida para o autor no próximo carregamento.
    marcar_lido(sala_id, eu, linha["id"])
    return {"ok": True, "mensagem_id": linha["id"], "mencionados": chamados}


def _conferir_mencionados(sala_id: int, mencionados: list[int] | None):
    """A lista limpa de quem foi chamado, ou a recusa com o motivo."""
    if not mencionados:
        return []
    # Sem repetido e sem ordem do cliente: a chave da tabela é (mensagem, quem).
    pedidos = sorted({int(m) for m in mencionados})
    if len(pedidos) > TETO_MENCOES:
        return {"ok": False,
                "motivo": f"Dá para chamar no máximo {TETO_MENCOES} pessoas "
                          f"numa mensagem."}
    # ⚠️ `membros()` devolve `atendente_id`, NÃO `id` -- a trava pegou isto na
    # primeira rodada. Ler a chave errada num dict dá KeyError alto e claro;
    # o mesmo erro num `.get()` daria conjunto vazio e recusaria TODA menção,
    # em silêncio.
    da_sala = {m["atendente_id"] for m in membros(sala_id)}
    fora = [p for p in pedidos if p not in da_sala]
    if fora:
        nomes = banco.varios(
            "SELECT nome FROM atendente WHERE id = ANY(%s) ORDER BY nome", (fora,))
        quem = ", ".join(n["nome"] for n in nomes) or "alguém"
        return {"ok": False,
                "motivo": f"{quem} não está nesta conversa — chame só quem "
                          f"está aqui, senão a pessoa nunca vê o aviso."}
    return pedidos


def mencoes_nao_lidas(eu: int) -> list[dict]:
    """As salas em que me chamaram e eu ainda não li, com a contagem.

    🚨 MENÇÃO NÃO LIDA É DIFERENTE DE MENSAGEM NÃO LIDA, e por isso tem conta
    própria: 40 mensagens não lidas numa sala de grupo é rotina; UMA em que
    alguém te chamou pelo nome é a que não pode esperar.

    ⚠️ Usa o mesmo `lido_ate` do resto — não há segundo marcador para
    dessincronizar.
    """
    return banco.varios(
        """SELECT s.id AS sala_id, s.tipo, s.nome, COUNT(*) AS quantas
             FROM chat_mencao mc
             JOIN chat_mensagem cm ON cm.id = mc.mensagem_id
             JOIN chat_membro mb ON mb.sala_id = cm.sala_id
                                AND mb.atendente_id = mc.atendente_id
             JOIN chat_sala s ON s.id = cm.sala_id
            WHERE mc.atendente_id = %s
              AND cm.id > COALESCE(mb.lido_ate, 0)
            GROUP BY s.id, s.tipo, s.nome
            ORDER BY s.id""", (eu,))


def marcar_lido(sala_id: int, eu: int, ate_id: int | None = None) -> dict:
    """Avança o marcador de leitura.

    🚨 SÓ AVANÇA, NUNCA VOLTA. `GREATEST` impede que abrir uma sala antiga
    depois de já ter lido tudo faça mensagens voltarem a contar como não
    lidas -- que é o tipo de defeito que ninguém reporta e todo mundo sente.
    """
    if ate_id is None:
        ultimo = banco.um(
            "SELECT max(id) AS id FROM chat_mensagem WHERE sala_id = %s",
            (sala_id,))
        ate_id = (ultimo or {}).get("id")
    if ate_id is None:
        return {"ok": True, "lido_ate": None}
    banco.executar(
        """UPDATE chat_membro
              SET lido_ate = GREATEST(COALESCE(lido_ate, 0), %s)
            WHERE sala_id = %s AND atendente_id = %s""",
        (ate_id, sala_id, eu))
    return {"ok": True, "lido_ate": ate_id}


def nao_lidas(eu: int) -> int:
    """Total de não lidas, para o selo do menu."""
    linha = banco.um(
        """SELECT count(*) AS n
             FROM chat_membro m
             JOIN chat_mensagem c ON c.sala_id = m.sala_id
            WHERE m.atendente_id = %s
              AND c.atendente_id <> %s
              AND c.id > COALESCE(m.lido_ate, 0)""", (eu, eu))
    return (linha or {}).get("n", 0)


def com_quem_falar(eu: int) -> list[dict]:
    """Os atendentes ativos, menos eu — a lista de quem dá para chamar.

    ⚠️ Exige e-mail, a mesma régua do vínculo de atendimento: quem não tem
    vínculo não aparece como destinatário, porque não teria como responder.
    """
    return banco.varios(
        """SELECT id, nome, login, estado FROM atendente
            WHERE ativo AND id <> %s AND btrim(COALESCE(email, '')) <> ''
            ORDER BY lower(nome)""", (eu,))
