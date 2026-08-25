"""Leitura da base cadastral — CAD_1.1 (clientes) e CAD_1.2 (contatos).

🚨 A REGRA QUE MANDA AQUI: **busca de telefone nunca é por igualdade do que
foi digitado** (metodologia §2). Quem procura digita `18 99811-6168`,
`(18) 9811-6168` ou `5518998116168`, e as três têm que achar a mesma pessoa. O
termo passa pelo normalizador antes de virar consulta -- e quando ele reconhece
um telefone, a busca troca de coluna sozinha.

⚠️ A busca por nome usa `LIKE %termo%`, que **não** usa o índice
`ix_contato_nome`. É deliberado: com 1.050 clientes a varredura é instantânea,
e exigir que a pessoa digite o começo do nome para achar "Pastelaria Velasco"
seria trocar um problema real por um imaginário. Quando a base passar de umas
dezenas de milhares, isso vira índice trigram (`pg_trgm`) -- e aí a consulta
não muda, só o índice.
"""
import logging

from . import banco, telefone

log = logging.getLogger("movizap.cadastro")

POR_PAGINA_PADRAO = 50
POR_PAGINA_MAX = 200

# Medido na API em 06/08. O 0 existe em ~8% da base e não é erro.
TIPO_PESSOA = {0: "—", 1: "Jurídica", 2: "Física", 3: "Estrangeiro"}


def _paginacao(pagina: int, por_pagina: int) -> tuple[int, int]:
    pagina = max(1, int(pagina or 1))
    por_pagina = min(max(1, int(por_pagina or POR_PAGINA_PADRAO)), POR_PAGINA_MAX)
    return (pagina - 1) * por_pagina, por_pagina


def _so_alfanumerico(texto: str) -> str:
    return "".join(c for c in texto if c.isalnum()).upper()


def interpretar_busca(termo: str) -> dict:
    """O que o termo digitado PARECE ser. A tela mostra isso de volta.

    Devolver a interpretação junto com o resultado não é enfeite: quando
    alguém procura um telefone e não acha, a diferença entre "não existe" e
    "procurei pelo nome" é a diferença entre desistir e corrigir a digitação.
    """
    termo = (termo or "").strip()
    if not termo:
        return {"tipo": "vazio", "termo": termo}

    analise = telefone.analisar(termo)
    if analise:
        return {
            "tipo": "telefone",
            "termo": termo,
            "e164": analise.e164,
            # 🚨 Harmonit e WESO não garantem qual grafia gravaram, e a nossa
            # base nasceu deles. Procurar pelas duas é mais barato que perder.
            "variantes": sorted(telefone.variantes(analise.e164)),
        }

    limpo = _so_alfanumerico(termo)
    # CPF tem 11, CNPJ tem 14 -- e o CNPJ alfanumérico já existe na base
    # (a Pastelaria Velasco é `WQ0P6GLD000108`), então não dá para exigir dígito.
    if len(limpo) in (11, 14) and any(c.isdigit() for c in limpo):
        return {"tipo": "documento", "termo": termo, "limpo": limpo}

    return {"tipo": "nome", "termo": termo}


def listar_clientes(busca: str = "", pagina: int = 1,
                    por_pagina: int = POR_PAGINA_PADRAO,
                    apenas_ativos: bool = False) -> dict:
    interpretacao = interpretar_busca(busca)
    salto, limite = _paginacao(pagina, por_pagina)

    onde = []
    params: list = []

    if apenas_ativos:
        onde.append("cl.ativo")

    if interpretacao["tipo"] == "telefone":
        onde.append("""EXISTS (SELECT 1 FROM contato c
                                 JOIN contato_telefone t ON t.contato_id = c.id
                                WHERE c.cliente_id = cl.id
                                  AND t.e164 = ANY(%s))""")
        params.append(interpretacao["variantes"])
    elif interpretacao["tipo"] == "documento":
        onde.append("upper(regexp_replace(cl.documento, '[^a-zA-Z0-9]', '', 'g')) = %s")
        params.append(interpretacao["limpo"])
    elif interpretacao["tipo"] == "nome":
        onde.append("(lower(cl.nome) LIKE lower(%s) OR lower(cl.nome_fantasia) LIKE lower(%s))")
        curinga = f"%{interpretacao['termo']}%"
        params += [curinga, curinga]

    filtro = (" WHERE " + " AND ".join(onde)) if onde else ""

    total = banco.um(f"SELECT count(*) AS n FROM cliente cl{filtro}", tuple(params))["n"]

    linhas = banco.varios(
        f"""
        SELECT cl.id, cl.nome, cl.nome_fantasia, cl.documento, cl.tipo_pessoa,
               cl.email, cl.origem, cl.harmonit_id, cl.ativo, cl.atualizado_em,
               (SELECT count(*) FROM contato c WHERE c.cliente_id = cl.id)
                   AS contatos,
               (SELECT count(*) FROM contato c
                  JOIN contato_telefone t ON t.contato_id = c.id
                 WHERE c.cliente_id = cl.id) AS telefones
          FROM cliente cl{filtro}
         ORDER BY cl.ativo DESC, lower(cl.nome)
         LIMIT %s OFFSET %s
        """,
        tuple(params) + (limite, salto),
    )
    for linha in linhas:
        linha["tipo_pessoa_desc"] = TIPO_PESSOA.get(linha["tipo_pessoa"], "—")

    return {
        "busca": interpretacao,
        "total": total,
        "pagina": max(1, int(pagina or 1)),
        "por_pagina": limite,
        "paginas": max(1, -(-total // limite)),
        "itens": linhas,
    }


def cliente(cliente_id: int) -> dict | None:
    linha = banco.um("SELECT * FROM cliente WHERE id = %s", (cliente_id,))
    if not linha:
        return None
    linha["tipo_pessoa_desc"] = TIPO_PESSOA.get(linha["tipo_pessoa"], "—")
    linha["contatos"] = [
        _com_telefones_e_papeis(c)
        for c in banco.varios(
            "SELECT * FROM contato WHERE cliente_id = %s ORDER BY lower(nome)",
            (cliente_id,))
    ]
    return linha


def _com_telefones_e_papeis(contato: dict) -> dict:
    contato["telefones"] = banco.varios(
        """SELECT id, e164, bruto, origem_campo, principal,
                  tem_whatsapp, verificado_em
             FROM contato_telefone WHERE contato_id = %s
            ORDER BY principal DESC, origem_campo""",
        (contato["id"],))
    contato["papeis"] = [
        p["papel"] for p in banco.varios(
            "SELECT papel FROM contato_papel WHERE contato_id = %s ORDER BY papel",
            (contato["id"],))
    ]
    return contato


def listar_contatos(busca: str = "", pagina: int = 1,
                    por_pagina: int = POR_PAGINA_PADRAO,
                    apenas_ativos: bool = False,
                    relacoes: list[str] | None = None) -> dict:
    interpretacao = interpretar_busca(busca)
    salto, limite = _paginacao(pagina, por_pagina)

    onde = []
    params: list = []

    if apenas_ativos:
        onde.append("c.ativo")

    if interpretacao["tipo"] == "telefone":
        onde.append("""EXISTS (SELECT 1 FROM contato_telefone t
                                WHERE t.contato_id = c.id AND t.e164 = ANY(%s))""")
        params.append(interpretacao["variantes"])
    elif interpretacao["tipo"] == "documento":
        onde.append("""EXISTS (SELECT 1 FROM cliente cl
                                WHERE cl.id = c.cliente_id
                                  AND upper(regexp_replace(cl.documento,
                                      '[^a-zA-Z0-9]', '', 'g')) = %s)""")
        params.append(interpretacao["limpo"])
    elif interpretacao["tipo"] == "nome":
        onde.append("lower(c.nome) LIKE lower(%s)")
        params.append(f"%{interpretacao['termo']}%")

    # ⚠️ O filtro por tipo COMBINA com a busca, não a substitui: procurar
    # "silva" entre os fornecedores é uma pergunta só.
    if relacoes:
        onde.append("c.relacao = ANY(%s)")
        params.append(list(relacoes))

    filtro = (" WHERE " + " AND ".join(onde)) if onde else ""

    total = banco.um(f"SELECT count(*) AS n FROM contato c{filtro}", tuple(params))["n"]

    linhas = banco.varios(
        f"""
        SELECT c.id, c.nome, c.relacao, c.email, c.origem, c.harmonit_id,
               c.ativo, c.cliente_id, cl.nome AS cliente_nome,
               (SELECT t.e164 FROM contato_telefone t
                 WHERE t.contato_id = c.id AND t.principal LIMIT 1) AS telefone,
               (SELECT count(*) FROM contato_telefone t
                 WHERE t.contato_id = c.id) AS telefones,
               (SELECT count(*) FROM contato_telefone t
                 WHERE t.contato_id = c.id AND t.tem_whatsapp) AS com_whatsapp
          FROM contato c LEFT JOIN cliente cl ON cl.id = c.cliente_id{filtro}
         ORDER BY c.ativo DESC, lower(c.nome)
         LIMIT %s OFFSET %s
        """,
        tuple(params) + (limite, salto),
    )

    return {
        "busca": interpretacao,
        "total": total,
        "pagina": max(1, int(pagina or 1)),
        "por_pagina": limite,
        "paginas": max(1, -(-total // limite)),
        "itens": linhas,
    }


def contato(contato_id: int) -> dict | None:
    linha = banco.um(
        """SELECT c.*, cl.nome AS cliente_nome, cl.documento AS cliente_documento
             FROM contato c LEFT JOIN cliente cl ON cl.id = c.cliente_id
            WHERE c.id = %s""",
        (contato_id,))
    if not linha:
        return None
    return _com_telefones_e_papeis(linha)


# 🚨 A LISTA VIVE NO BANCO, NÃO AQUI. O CHECK `contato_relacao_check` é o
# contrato (docs/02); esta tupla existe só para a tela montar o <select> e para
# a rota recusar cedo, com mensagem legível, em vez de deixar o psycopg
# devolver CheckViolation. Ampliar o vocabulário é migração, não edição aqui.
# 🚨 ESTA TUPLA TINHA FICADO PARA TRÁS. A migração 029 acrescentou
# `sem_identificacao` ao CHECK em 25/08 e esta lista não foi junto -- a rota
# recusaria, com "relação inválida", um valor que o banco aceita. Espelho que
# não se atualiza junto vira mentira: é a mesma lição das duas tabelas de
# telas no `docs/03`.
RELACOES = ('cliente', 'fornecedor', 'parceiro', 'tecnico', 'lead',
            'colaborador', 'teste', 'sem_identificacao')


def definir_relacao(contato_id: int, relacao: str) -> dict:
    """Diz o que a pessoa é para a Movisat. Editável desde 12/08.

    ⚠️ O SYNC NÃO ESCREVE NEM DESFAZ ISTO (migração 031, 25/08). Ele casa por
    número; o `ON CONFLICT ... DO UPDATE` de `_gravar_contato` atualiza nome,
    e-mail, cliente_id e ativo, e não toca em `relacao`. É isso que faz o que
    a pessoa marcar aqui sobreviver ao sync de madrugada.

    🚨 O NÚMERO DA BASE NÃO MEDE A REALIDADE. Medido em 25/08: 1.750 dos 1.754
    contatos estão como 'cliente' porque até a 031 o INSERT do sync gravava
    essa palavra literal. É constante no código virada estatística -- e é por
    isso que a marcação em LOTE existe: ninguém corrige 1.750 linhas uma a uma.
    """
    if relacao not in RELACOES:
        return {"ok": False,
                "motivo": f"Relação inválida. Vale uma de: {', '.join(RELACOES)}."}
    linha = banco.um(
        """UPDATE contato SET relacao = %s, atualizado_em = now()
            WHERE id = %s RETURNING id, nome, relacao""",
        (relacao, contato_id))
    if not linha:
        return {"ok": False, "motivo": "Contato não encontrado."}
    return {"ok": True, **linha}


TETO_LOTE = 500


def definir_relacao_em_lote(ids: list[int], relacao: str) -> dict:
    """Marca o tipo de vários contatos de uma vez — a CAD_1.2.

    🚨 EXISTE PORQUE 1.750 CONTATOS DIZEM "cliente" SEM QUE NINGUÉM TENHA
    MARCADO. Até a migração 031 o INSERT do sync gravava essa palavra literal.
    Corrigir isso um contato por vez são 1.750 idas ao painel: sem lote, a
    base nunca fica honesta, e sem base honesta o interruptor de automação por
    tipo dispara para quem não devia.

    ⚠️ TETO NO TAMANHO DO LOTE. Não é medo do banco -- é que um lote sem teto
    aceita "marcar a base inteira" num clique, e não existe desfazer. 500 é
    grande para o trabalho real e pequeno para o acidente.

    ⚠️ Devolve QUANTOS mudaram, não "ok". Pedir 40 e mudar 37 quer dizer que 3
    ids não existem, e quem marcou precisa saber disso -- silêncio aqui vira
    "marquei e não pegou".
    """
    if relacao not in RELACOES:
        return {"ok": False,
                "motivo": f"Relação inválida. Vale uma de: {', '.join(RELACOES)}."}

    limpos = sorted({int(i) for i in (ids or []) if i})
    if not limpos:
        return {"ok": False, "motivo": "Nenhum contato selecionado."}
    if len(limpos) > TETO_LOTE:
        return {"ok": False,
                "motivo": f"São {len(limpos)} contatos. O lote vai até "
                          f"{TETO_LOTE} por vez."}

    mudados = banco.executar(
        """UPDATE contato SET relacao = %s, atualizado_em = now()
            WHERE id = ANY(%s) AND relacao IS DISTINCT FROM %s""",
        (relacao, limpos, relacao))
    log.info("relação em lote: %s contatos marcados como %s", mudados, relacao)
    return {"ok": True, "pedidos": len(limpos), "mudados": mudados,
            "relacao": relacao}


def por_telefone(bruto: str) -> list[dict]:
    """Quem atende por este número. É o que o webhook vai chamar no passo 4.

    🚨 Devolve LISTA, não um contato. Dez números da base estão em mais de um
    contato -- um deles em oito -- porque são centrais de empresa repetidas no
    cadastro de cada filial. Um `contato | None` aqui obrigaria a escolher
    arbitrariamente, e a escolha arbitrária é justamente o que não se pode
    esconder de quem vai atender.
    """
    analise = telefone.analisar(bruto)
    if not analise:
        return []
    variantes = sorted(telefone.variantes(analise.e164))
    # `EXISTS` em vez de JOIN + DISTINCT: o contato que tiver as DUAS grafias
    # gravadas apareceria duas vezes no JOIN, e o DISTINCT não resolveria --
    # as linhas seriam diferentes, porque o e164 seria diferente em cada uma.
    return banco.varios(
        """SELECT c.id, c.nome, c.relacao, c.ativo,
                  c.cliente_id, cl.nome AS cliente_nome,
                  (SELECT t.e164 FROM contato_telefone t
                    WHERE t.contato_id = c.id AND t.e164 = ANY(%s)
                    ORDER BY t.principal DESC LIMIT 1) AS e164
             FROM contato c
             LEFT JOIN cliente cl ON cl.id = c.cliente_id
            WHERE EXISTS (SELECT 1 FROM contato_telefone t
                           WHERE t.contato_id = c.id AND t.e164 = ANY(%s))
            ORDER BY c.ativo DESC, lower(c.nome)""",
        (variantes, variantes))
