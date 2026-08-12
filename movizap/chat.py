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


def membros(sala_id: int) -> list[dict]:
    return banco.varios(
        """SELECT m.atendente_id, a.nome, m.entrou_em
             FROM chat_membro m JOIN atendente a ON a.id = m.atendente_id
            WHERE m.sala_id = %s ORDER BY m.entrou_em, a.nome""", (sala_id,))


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
                SELECT texto, criada_em, atendente_id FROM chat_mensagem c
                 WHERE c.sala_id = s.id ORDER BY c.id DESC LIMIT 1
          ) u ON true
          LEFT JOIN atendente ua ON ua.id = u.atendente_id
         WHERE m.atendente_id = %s
         ORDER BY COALESCE(u.criada_em, s.criada_em) DESC
        """, (eu, eu, eu))


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
    return banco.varios(
        """SELECT * FROM (
               SELECT c.id, c.texto, c.criada_em, c.atendente_id,
                      a.nome AS autor, (c.atendente_id = %s) AS minha
                 FROM chat_mensagem c
                 JOIN atendente a ON a.id = c.atendente_id
                WHERE c.sala_id = %s
                ORDER BY c.id DESC LIMIT %s
           ) recentes ORDER BY id""", (eu, sala_id, limite))


def escrever(sala_id: int, eu: int, texto: str) -> dict:
    texto = (texto or "").strip()
    if not texto:
        return {"ok": False, "motivo": "Mensagem vazia."}
    if len(texto) > TETO_TEXTO:
        return {"ok": False,
                "motivo": f"Mensagem passa de {TETO_TEXTO} caracteres."}
    if not e_membro(sala_id, eu):
        return {"ok": False, "motivo": "Você não está nesta conversa."}

    linha = banco.um(
        """INSERT INTO chat_mensagem (sala_id, atendente_id, texto)
           VALUES (%s, %s, %s) RETURNING id, criada_em""",
        (sala_id, eu, texto))
    # ⚠️ Quem escreve leu o que escreveu: sem isto a própria mensagem entraria
    # como não lida para o autor no próximo carregamento.
    marcar_lido(sala_id, eu, linha["id"])
    return {"ok": True, "mensagem_id": linha["id"]}


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
        """SELECT id, nome, login FROM atendente
            WHERE ativo AND id <> %s AND btrim(COALESCE(email, '')) <> ''
            ORDER BY lower(nome)""", (eu,))
