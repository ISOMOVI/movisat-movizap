"""Ler as ligações do MicroSIP: a aba Ligações e o modal da ficha (Bloco 3, 15/10).

🔵 *"um grid simples que tenha as ligações do historico do MicroSip,
consultadas por cliente - ja da base Movizap, ou por Atendente, ou por data ou
por numero, etc"* e, na conversa, *"o modal só trará ultimos 7 dias"*.

Módulo separado de propósito: `ligacoes.py` é o caminho de ESCRITA do agente,
que está no ar desde 25/09 e não se mexe para acrescentar consulta — a mesma
divisão de `ligacoes_ca.py` e `ligacoes_alistar.py`.

🚨 **Duas fontes.** A ligação vem do PC (número, ramal, duração). Quem é o
CLIENTE e quem é o ATENDENTE vem da base do MoviZap: `telefone_e164` →
`contato_telefone` → `contato` → `cliente`, e `ramal` → `atendente`. O PC não
sabe nada disso.

🚨 **Um número pode cair em VÁRIAS empresas** (é o "empresas do mesmo
responsável" que a ficha já mostra), e a maioria das ligações não tem cadastro
nenhum — `08000028000`, `1925172200`, ramal interno `3407` estão no histórico
real. Por isso `clientes` é uma LISTA, e lista vazia significa "sem cadastro",
não "não consultei".

🚨 **Uma ligação pode ter mais de uma gravação:** quando o MicroSIP reinicia o
arquivo no meio da chamada, o agente manda os dois pedaços para a mesma
ligação. Daí `gravacoes` ser lista também.
"""
import logging

from . import banco, telefone
from .ligacoes import SENTIDOS
from .operacao import DadoInvalido

log = logging.getLogger("movizap.ligacoes.consulta")

POR_PAGINA = 50
POR_PAGINA_MAX = 200
DIAS_PADRAO_FICHA = 7
TETO_CSV = 5000

# As gravações e os clientes de cada linha, em uma consulta só. Subconsulta em
# vez de JOIN: com JOIN, uma ligação de duas gravações em duas empresas viraria
# quatro linhas no grid.
_GRAVACOES = """(SELECT json_agg(json_build_object(
                       'id', g.id, 'bytes', g.arquivo_bytes,
                       'nome', g.nome_original, 'inicio', g.inicio)
                     ORDER BY g.inicio NULLS LAST, g.id)
                   FROM ligacao_gravacao g WHERE g.ligacao_id = l.id) AS gravacoes"""

_CLIENTES = """(SELECT json_agg(DISTINCT jsonb_build_object(
                       'id', cl.id, 'nome', cl.nome, 'ativo', cl.ativo,
                       'contato_id', ct.id, 'contato_nome', ct.nome))
                   FROM contato_telefone t
                   JOIN contato ct ON ct.id = t.contato_id
                   JOIN cliente cl ON cl.id = ct.cliente_id
                  WHERE t.e164 = l.telefone_e164) AS clientes"""


def _filtros(de=None, ate=None, atendente_id=None, ramal=None, sentido=None,
             numero=None, cliente_id=None, com_gravacao=None) -> tuple[str, list]:
    """Monta o WHERE. Devolve sempre pedaço válido, mesmo sem filtro nenhum."""
    onde, valores = ["TRUE"], []

    if de:
        onde.append("l.inicio >= %s")
        valores.append(de)
    if ate:
        # A data de fim é INCLUSIVA: quem filtra "até 15/10" espera o dia 15
        # inteiro, não até a meia-noite dele.
        onde.append("l.inicio < (%s::date + 1)")
        valores.append(ate)
    if atendente_id:
        onde.append("l.atendente_id = %s")
        valores.append(int(atendente_id))
    if ramal:
        onde.append("l.ramal = %s")
        valores.append(str(ramal).strip())
    if sentido:
        if sentido not in SENTIDOS:
            raise DadoInvalido(f"Sentido inválido. Vale: {', '.join(SENTIDOS)}.")
        onde.append("l.sentido = %s")
        valores.append(sentido)
    if numero:
        bruto = str(numero).strip()
        analise = telefone.analisar(bruto)
        if analise.e164:
            # Número inteiro: as duas grafias (com e sem o nono dígito).
            onde.append("l.telefone_e164 = ANY(%s)")
            valores.append(sorted(telefone.variantes(analise.e164)))
        else:
            # Pedaço de número ("9811", "0800"): compara só dígitos, dos dois
            # lados. É o que faz a busca parcial do grid funcionar.
            digitos = "".join(c for c in bruto if c.isdigit())
            if not digitos:
                raise DadoInvalido("Para buscar por número, digite ao menos um dígito.")
            onde.append("regexp_replace(COALESCE(l.telefone_e164, l.numero_bruto), "
                        "'\\D', '', 'g') LIKE %s")
            valores.append(f"%{digitos}%")
    if cliente_id:
        onde.append("""EXISTS (SELECT 1 FROM contato_telefone t
                                 JOIN contato ct ON ct.id = t.contato_id
                                WHERE t.e164 = l.telefone_e164 AND ct.cliente_id = %s)""")
        valores.append(int(cliente_id))
    if com_gravacao is True:
        onde.append("EXISTS (SELECT 1 FROM ligacao_gravacao g WHERE g.ligacao_id = l.id)")
    elif com_gravacao is False:
        onde.append("NOT EXISTS (SELECT 1 FROM ligacao_gravacao g WHERE g.ligacao_id = l.id)")

    return " AND ".join(onde), valores


def consultar(pagina: int = 1, por_pagina: int = POR_PAGINA, **filtros) -> dict:
    """O grid da aba: uma página de ligações, com totais por sentido.

    Os totais são do FILTRO INTEIRO, não da página — senão o rodapé mentiria a
    cada vez que alguém virasse a página.
    """
    pagina = max(1, int(pagina or 1))
    por_pagina = min(POR_PAGINA_MAX, max(1, int(por_pagina or POR_PAGINA)))
    onde, valores = _filtros(**filtros)

    total = banco.um(f"SELECT count(*) AS n FROM ligacao l WHERE {onde}", tuple(valores))["n"]
    por_sentido = {r["sentido"]: r["n"] for r in banco.varios(
        f"SELECT l.sentido, count(*) AS n FROM ligacao l WHERE {onde} GROUP BY 1",
        tuple(valores))}

    itens = banco.varios(
        f"""SELECT l.id, l.inicio, l.sentido, l.situacao, l.duracao_s, l.ramal,
                   l.numero_bruto, l.telefone_e164, l.pc, l.recebida_em,
                   l.atendente_id, a.nome AS atendente,
                   {_GRAVACOES}, {_CLIENTES}
              FROM ligacao l
              LEFT JOIN atendente a ON a.id = l.atendente_id
             WHERE {onde}
             ORDER BY l.inicio DESC, l.id DESC
             LIMIT %s OFFSET %s""",
        tuple(valores) + (por_pagina, (pagina - 1) * por_pagina))

    return {"itens": [_enfeitar(i) for i in itens], "total": total,
            "pagina": pagina, "por_pagina": por_pagina,
            "paginas": max(1, -(-total // por_pagina)),
            "por_sentido": {s: por_sentido.get(s, 0) for s in SENTIDOS}}


def para_csv(**filtros) -> list[dict]:
    """As linhas do filtro inteiro, para exportar. Teto de segurança: ninguém
    exporta a base toda por acidente."""
    onde, valores = _filtros(**filtros)
    itens = banco.varios(
        f"""SELECT l.id, l.inicio, l.sentido, l.situacao, l.duracao_s, l.ramal,
                   l.numero_bruto, l.telefone_e164, l.pc,
                   a.nome AS atendente, {_GRAVACOES}, {_CLIENTES}
              FROM ligacao l
              LEFT JOIN atendente a ON a.id = l.atendente_id
             WHERE {onde}
             ORDER BY l.inicio DESC, l.id DESC
             LIMIT %s""",
        tuple(valores) + (TETO_CSV + 1,))
    if len(itens) > TETO_CSV:
        raise DadoInvalido(
            f"A exportação passa de {TETO_CSV} linhas. Aperte o período ou o filtro.")
    return [_enfeitar(i) for i in itens]


def do_telefone(e164: str, dias: int = DIAS_PADRAO_FICHA) -> dict:
    """O modal da ficha: as ligações daquele número nos últimos `dias`,
    separadas por sentido — *"importante a separação basica entre, feitas,
    recebidas, etc"*.

    ⚠️ Devolve `cobertura`: quantos ramais têm agente. Sem isso a tela diz
    "nenhuma ligação" quando a verdade é "aquele PC não tem agente" — e tela
    que mente é defeito.
    """
    analise = telefone.analisar(e164 or "")
    if not analise.e164:
        raise DadoInvalido("Número inválido para consultar ligações.")
    dias = min(365, max(1, int(dias or DIAS_PADRAO_FICHA)))
    numeros = sorted(telefone.variantes(analise.e164))

    itens = banco.varios(
        f"""SELECT l.id, l.inicio, l.sentido, l.situacao, l.duracao_s, l.ramal,
                   l.telefone_e164, l.numero_bruto,
                   l.atendente_id, a.nome AS atendente, {_GRAVACOES}
              FROM ligacao l
              LEFT JOIN atendente a ON a.id = l.atendente_id
             WHERE l.telefone_e164 = ANY(%s)
               AND l.inicio >= now() - make_interval(days => %s)
             ORDER BY l.inicio DESC, l.id DESC""",
        (numeros, dias))
    itens = [_enfeitar(i) for i in itens]

    cobertura = banco.um(
        """SELECT count(*) AS com_agente,
                  (SELECT count(*) FROM atendente WHERE ativo) AS atendentes
             FROM agente_ligacao WHERE revogado_em IS NULL""")

    return {"dias": dias, "telefone_e164": analise.e164, "total": len(itens),
            "por_sentido": {s: [i for i in itens if i["sentido"] == s] for s in SENTIDOS},
            "cobertura": dict(cobertura)}


def gravacao(gravacao_id: int) -> dict | None:
    """A gravação e a ligação dela. O caminho no disco vem daqui; quem serve o
    arquivo é a rota."""
    return banco.um(
        """SELECT g.id, g.caminho, g.nome_original, g.arquivo_bytes, g.arquivo_sha256,
                  l.id AS ligacao_id, l.inicio, l.sentido, l.ramal, l.telefone_e164,
                  l.atendente_id
             FROM ligacao_gravacao g JOIN ligacao l ON l.id = g.ligacao_id
            WHERE g.id = %s""", (int(gravacao_id),))


# 🚨 O AGENTE SÓ FALA DO PROBLEMA. Ele manda aviso quando a gravação
# automática está DESLIGADA no MicroSIP (`Settings.autoRecording` ≠ 1); quando
# está ligada, não diz nada. Então "ligado" é dedução da ausência do aviso na
# ÚLTIMA passada -- e por isso só vale para quem já falou. PC que nunca falou
# fica em `desconhecido`: dizer "ligado" ali seria a tela mentindo (`M12`).
AVISO_REC_DESLIGADO = "gravacao automatica desligada"


def rec_do_agente(linha: dict) -> str | None:
    """O estado da gravação automática daquele PC: `ligado`, `desligado`,
    `desconhecido` -- ou `None` para quem não tem agente, onde a pergunta nem
    existe.

    🚨 26/10: PASSOU A PREFERIR O DADO EXPLÍCITO (`auto_gravacao`, migração
    078). A dedução por ausência de aviso continua existindo e vale só para
    agente velho -- e ela quebra de dois jeitos: se a frase do agente mudar, a
    dedução inverte; se chegar aviso novo sobre outra coisa, o REC "desliga"
    sozinho. O agente `0.7` manda o booleano, e aí não há o que deduzir.

    ⚠️ `auto_gravacao` nulo em quem JÁ FALOU é **agente velho**, não
    "desligado": dizer desligado ali seria afirmar sobre um PC que nunca foi
    perguntado. Cai na dedução de antes, que é o melhor que existe para ele.
    """
    if not linha.get("agente_id"):
        return None
    if not linha.get("ultimo_contato_em"):
        return "desconhecido"
    explicito = linha.get("auto_gravacao")
    if explicito is not None:
        return "ligado" if explicito else "desligado"
    aviso = (linha.get("ultimo_aviso") or "").lower()
    return "desligado" if AVISO_REC_DESLIGADO in aviso else "ligado"


# Como a pasta foi decidida, em português e com o que cada caso QUER DIZER.
# 🚨 A tela não escreve a sua versão: o rótulo e a explicação saem daqui, um
# lugar só -- e `palpite` é o único que pede ação.
ORIGEM_DA_PASTA = {
    "vps": ("mandada daqui", "Alguém definiu este caminho no painel."),
    "escolhida": ("confirmada na instalação",
                  "A pessoa conferiu a pasta quando instalou o agente."),
    "ini": ("lida do MicroSIP", "Veio do `recordingPath` do MicroSIP.ini."),
    "relativa": ("lida do MicroSIP (relativa)",
                 "O MicroSIP guardou um caminho relativo; foi resolvido contra "
                 "a pasta do .ini."),
    "busca": ("achada procurando pelo nome",
              "O .ini não disse onde era, e o agente encontrou a pasta pelo "
              "nome dentro do perfil do usuário."),
    "palpite": ("PALPITE do agente antigo",
                "O agente chutou a Área de Trabalho. Com OneDrive ela muda de "
                "lugar -- é o caso que motivou esta frente. Reinstale com o "
                "agente novo, ou defina o caminho aqui."),
}


def pasta_do_agente(linha: dict) -> dict | None:
    """O que a tela mostra sobre a pasta daquele PC.

    ⚠️ `None` quando o agente não informou -- e a tela diz **"agente antigo"**,
    não "sem pasta": o PC pode estar coletando perfeitamente e só não saber
    contar onde. Os 7 PCs estão neste estado em 26/10 (rodam o `0.4`).
    """
    if not linha.get("agente_id"):
        return None
    caminho = linha.get("pasta")
    if not caminho:
        return None
    rotulo, explicacao = ORIGEM_DA_PASTA.get(
        linha.get("pasta_origem") or "",
        ("origem não informada", "O agente não disse como decidiu este caminho."))
    return {"caminho": caminho, "origem": linha.get("pasta_origem"),
            "rotulo": rotulo, "explicacao": explicacao,
            "atencao": linha.get("pasta_origem") == "palpite"}


def agentes() -> list[dict]:
    """A faixa de cobertura da aba: quem tem agente, desde quando, e se o PC
    está gravando.

    🚨 É o que impede a aba de mentir por omissão: ausência de ligação de
    alguém significa "aquele PC não tem agente", não "não ligou".

    🔴 19/10, pedido dele: cada linha diz se o REC está ativado. Medido no
    dia: 4 dos 5 PCs com agente tinham a gravação desligada e ninguém via isso
    na tela -- só o histórico subia, o áudio não.
    """
    linhas = banco.varios(
        """SELECT a.id AS atendente_id, a.nome, a.ramal,
                  g.id AS agente_id, g.criado_em, g.ultimo_contato_em, g.ultimo_pc,
                  g.ultima_versao, g.cert_validade, g.pendentes,
                  g.ultimo_erro, g.ultimo_aviso,
                  -- 🆕 26/10 (migração 078): ONDE o agente procura, e como
                  -- decidiu. É o que transforma "sem comunicação" em
                  -- diagnóstico -- antes disto, o aviso dizia que a pasta não
                  -- existe sem dizer qual pasta.
                  g.pasta, g.pasta_origem, g.auto_gravacao, g.pastas_extra,
                  (SELECT count(*) FROM ligacao l WHERE l.atendente_id = a.id) AS ligacoes
             FROM atendente a
             LEFT JOIN agente_ligacao g
                    ON g.atendente_id = a.id AND g.revogado_em IS NULL
            WHERE a.ativo
            ORDER BY (g.id IS NULL), a.nome""")
    for linha in linhas:
        linha["rec"] = rec_do_agente(linha)
        linha["pasta_info"] = pasta_do_agente(linha)
        linha["pastas_extra"] = list(linha.get("pastas_extra") or [])
    return linhas


def _enfeitar(linha: dict) -> dict:
    """Listas no lugar de NULL: a tela não precisa saber que o Postgres devolve
    `None` quando o `json_agg` não acha nada."""
    linha["gravacoes"] = linha.get("gravacoes") or []
    if "clientes" in linha:
        linha["clientes"] = linha.get("clientes") or []
    return linha
