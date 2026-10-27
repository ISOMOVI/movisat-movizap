"""Agendamento de serviço — o compromisso, de ponta a ponta.

🔵 Decisão 7 dele (19/10): **o MoviZap é o dono do agendamento**. A escrita no
Harmonit é 2º passo, e até ele mandar ligar, o compromisso vive só aqui e a OS
é citada pelo número (migração 069).

⚠️ ESTE ARQUIVO NÃO É O `agenda.py`. Aquele é a agenda do Google que alimenta
a tela Início, e o próprio topo dele diz, desde que nasceu, que **não é um
calendário**. O calendário é a tela `ATD_7.1`, e é servida por aqui.

🚨 "UMA OS NÃO ENTRA EM DOIS COMPROMISSOS ATIVOS" MORA AQUI, não no banco. A
tabela `agendamento_os` não carrega estado, e duplicar o estado nas duas
tabelas criaria duas versões do mesmo fato. A regra tem teste.
"""
import logging

from . import banco
from . import fpsl_ponte

log = logging.getLogger(__name__)

# Os estados do compromisso. O CHECK da migração 069 guarda os mesmos quatro.
ESTADOS = ("rascunho", "aguardando", "confirmado", "cancelado")

# "Ativo" = ainda vale como compromisso. Cancelado não prende a OS, e rascunho
# também não: ele é o que existe antes de o operador terminar o modal.
ESTADOS_ATIVOS = ("aguardando", "confirmado")


def os_ja_agendadas(numeros: list[int]) -> list[int]:
    """Quais destas OS já estão presas a um compromisso ativo.

    Devolve lista (não set) porque isto vai direto para JSON de resposta.
    """
    if not numeros:
        return []
    linhas = banco.varios(
        "SELECT DISTINCT ao.numero_os "
        "  FROM agendamento_os ao "
        "  JOIN agendamento a ON a.id = ao.agendamento_id "
        " WHERE ao.numero_os = ANY(%s) AND a.estado = ANY(%s)",
        (list(numeros), list(ESTADOS_ATIVOS)),
    )
    return [l["numero_os"] for l in linhas]


def ultimo_endereco(cliente_harmonit_id: str) -> str | None:
    """O endereço usado na última vez para aquele cliente.

    🔵 Decisão 11 dele: o operador **digita** o endereço, sugerido com o
    último usado. Sugestão, não preenchimento automático -- endereço errado
    herdado em silêncio manda técnico para o lugar errado.
    """
    linha = banco.um(
        "SELECT endereco FROM agendamento "
        " WHERE cliente_harmonit_id = %s AND endereco IS NOT NULL "
        "   AND estado <> 'cancelado' "
        " ORDER BY criado_em DESC LIMIT 1",
        (str(cliente_harmonit_id),),
    )
    return linha["endereco"] if linha else None


class OsJaAgendada(ValueError):
    """Alguma das OS escolhidas já está num compromisso ativo."""


# Os campos de endereço como ELES vivem nesta tabela. ⚠️ `logradouro` é o que
# o Harmonit chama de `endereco`: aqui esse nome já era da linha montada
# (migração 069), e a tradução mora no `_endereco_para_a_os`.
CAMPOS_DE_ENDERECO = ("cep", "logradouro", "numero", "bairro", "cidade", "uf",
                      "complemento")


def linha_do_endereco(e: dict) -> str | None:
    """Os campos viram a LINHA que sai na mensagem do cliente.

    🚨 A MENSAGEM NÃO PASSOU A LER OS SETE CAMPOS, e isto é deliberado: os
    compromissos criados antes da migração 073 só têm a linha, e trocar a
    fonte os faria sair sem endereço -- eles são o único histórico que existe.
    Então a linha continua sendo o texto, e passa a ser MONTADA quando há
    campos.

    ⚠️ Monta com o que existe, e nada de "—" no meio: endereço com buraco
    marcado parece defeito para quem recebe a mensagem.
    """
    rua = (e.get("logradouro") or "").strip()
    numero = (e.get("numero") or "").strip()
    primeiro = ", ".join(p for p in (rua, numero) if p)
    partes = [primeiro,
              (e.get("bairro") or "").strip(),
              (e.get("complemento") or "").strip()]
    cidade = (e.get("cidade") or "").strip()
    uf = (e.get("uf") or "").strip()
    local = " - ".join(p for p in (cidade, uf) if p)
    if local:
        partes.append(local)
    cep = (e.get("cep") or "").strip()
    if cep:
        partes.append(f"CEP {cep}")
    texto = " · ".join(p for p in partes if p)
    return texto or None


def _endereco_para_a_os(linha: dict) -> dict:
    """Do vocabulário desta tabela para o do Harmonit."""
    return {
        "cep": linha.get("cep"),
        # 🚨 A única tradução de nome que existe no caminho.
        "endereco": linha.get("logradouro"),
        "numero": linha.get("numero"),
        "bairro": linha.get("bairro"),
        "cidade": linha.get("cidade"),
        "uf": linha.get("uf"),
        "complemento": linha.get("complemento"),
    }


def criar(*, conversa_id: int, tecnico_contato_id: int, cliente_harmonit_id: str,
          cliente_nome: str, inicio, fim=None, endereco: str | None,
          ordens: list[dict], criado_por: int, orcamento_id: int | None = None,
          estado: str = "aguardando", campos_endereco: dict | None = None,
          origem_endereco: str | None = None, km=None) -> int:
    """Grava o compromisso e as OS dele. Devolve o id.

    `ordens` são dicts `{"numero_os": int, "placa": str | None,
    "tipo_nome": str | None}`.

    ⚠️ `tipo_nome` é RETRATO, como a placa (migração 072): o nome do tipo da
    OS no momento do agendamento. Nulo é o caso comum -- 173 das 547 OS têm
    `tipo` fora da lista do Harmonit --, e quem monta a mensagem omite o
    segmento do cabeçalho em vez de inventar rótulo.

    🚨 A CHECAGEM DE OS REPETIDA ACONTECE NA MESMA TRANSAÇÃO DA INSERÇÃO. Fora
    dela, dois operadores no mesmo segundo passariam os dois -- e o segundo só
    descobriria quando o técnico chegasse e encontrasse outro lá.
    """
    if estado not in ESTADOS:
        raise ValueError(f"estado inválido: {estado!r}")
    if not ordens:
        raise ValueError("compromisso sem OS não é compromisso")

    numeros = [int(o["numero_os"]) for o in ordens]
    with banco.cursor() as cur:
        # ⚠️ SEM `DISTINCT`: o Postgres recusa `FOR UPDATE` junto com ele
        # ("FOR UPDATE is not allowed with DISTINCT clause") -- achado por
        # teste, não por leitura. A deduplicação é feita aqui embaixo, e o
        # travamento é o que importa nesta consulta.
        cur.execute(
            "SELECT ao.numero_os "
            "  FROM agendamento_os ao "
            "  JOIN agendamento a ON a.id = ao.agendamento_id "
            " WHERE ao.numero_os = ANY(%s) AND a.estado = ANY(%s) "
            "   FOR UPDATE OF a",
            (numeros, list(ESTADOS_ATIVOS)),
        )
        presas = sorted({r["numero_os"] for r in cur.fetchall()})
        if presas:
            raise OsJaAgendada(
                "estas OS já estão em outro compromisso ativo: "
                + ", ".join(str(n) for n in presas)
            )

        campos = {c: (campos_endereco or {}).get(c) or None
                  for c in CAMPOS_DE_ENDERECO}
        # 🚨 A LINHA É MONTADA DOS CAMPOS quando eles existem, e só então o
        # texto digitado deixa de valer: é o mesmo endereço dito de duas
        # formas, e duas fontes para o mesmo fato divergem na primeira edição.
        linha = linha_do_endereco(campos) or endereco
        # 🆕 Migração 077: a origem e o km são RETRATO deste compromisso --
        # de onde o técnico saiu e quanto se cobrou naquele dia. A memória
        # atual da origem vive em `tecnico_origem` (ver `movizap/rotas.py`);
        # se o técnico mudar de endereço, a memória muda e esta linha
        # continua dizendo de onde se cobrou. Mesmo desenho do `tipo_nome`.
        cur.execute(
            "INSERT INTO agendamento (conversa_id, tecnico_contato_id, "
            "    cliente_harmonit_id, cliente_nome, inicio, fim, endereco, "
            "    estado, orcamento_id, criado_por, cep, logradouro, numero, "
            "    bairro, cidade, uf, complemento, origem_endereco, km) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) "
            "RETURNING id",
            (conversa_id, tecnico_contato_id, str(cliente_harmonit_id),
             cliente_nome, inicio, fim, linha, estado, orcamento_id, criado_por,
             campos["cep"], campos["logradouro"], campos["numero"],
             campos["bairro"], campos["cidade"], campos["uf"],
             campos["complemento"], (origem_endereco or None), km),
        )
        novo = cur.fetchone()["id"]
        for o in ordens:
            cur.execute(
                "INSERT INTO agendamento_os (agendamento_id, numero_os, placa, "
                "    tipo_nome) VALUES (%s,%s,%s,%s)",
                (novo, int(o["numero_os"]), (o.get("placa") or None),
                 (o.get("tipo_nome") or None)),
            )
    log.info("agendamento %s criado com %s OS", novo, len(ordens))
    return novo


CHAVE_ESCREVE_HARMONIT = "agendamento_escreve_harmonit"


def escreve_no_harmonit(cfg: dict | None = None) -> bool:
    """O interruptor. 🚨 Mora no `config`, como todo interruptor do sistema.

    `cfg` existe para o TESTE não tocar na configuração de produção — mesmo
    desenho de `distribuicao.distribuir(cfg=...)`. Foi um teste meu escrevendo
    direto na `config` que desligou a distribuição por nove minutos em 19/10.
    """
    if cfg is not None:
        return str(cfg.get(CHAVE_ESCREVE_HARMONIT, "false")).lower() == "true"
    linha = banco.um("SELECT valor FROM config WHERE chave = %s",
                     (CHAVE_ESCREVE_HARMONIT,))
    return bool(linha) and str(linha["valor"]).lower() == "true"


def levar_ao_harmonit(agendamento_id: int, *, cfg: dict | None = None) -> dict:
    """Cria o compromisso na OS do Harmonit e grava o rastro (migração 070).

    🚨 NUNCA DERRUBA O COMPROMISSO. O MoviZap é o dono (decisão 7 dele): se o
    Harmonit recusar, o agendamento continua de pé e o motivo fica GRAVADO,
    legível, na própria linha. Falha silenciosa viraria "achei que tinha ido".

    ⚠️ UMA CHAMADA POR OS. Um compromisso pode cobrir várias OS, e do lado de
    lá cada OS tem o seu técnico e o seu compromisso -- não existe "agendar as
    três de uma vez".
    """
    if not escreve_no_harmonit(cfg):
        return {"ligado": False, "resultados": []}

    linha = por_id(agendamento_id)
    if not linha:
        raise ValueError("agendamento não encontrado")

    # 🔵 A trava é o E-MAIL do cadastro do Harmonit, e quem o encontra é o
    # TELEFONE do contato (decisão dele, 21/10). O nome vai junto só para a
    # recusa ficar legível.
    # 🔵 21/10: se o contato já tem VÍNCULO gravado, ele manda -- é
    # identidade (`usuarioId` da OS = `tecnico_id` do cadastro), não
    # semelhança. O telefone fica como caminho de quem ainda não foi
    # vinculado, e é o que a varredura diária vai resolvendo.
    contato = banco.um(
        """SELECT ct.harmonit_tecnico_id,
                  (SELECT e164 FROM contato_telefone
                    WHERE contato_id = ct.id
                    ORDER BY principal DESC, id LIMIT 1) AS e164
             FROM contato ct WHERE ct.id = %s""",
        (linha["tecnico_contato_id"],)) or {}

    resultados = []
    for ordem in linha["ordens"]:
        resultados.append(fpsl_ponte.agendar_tecnico(
            numero_os=ordem["numero_os"],
            inicio=linha["inicio"],
            fim=linha["fim"],
            tecnico_telefone=contato.get("e164"),
            tecnico_id=contato.get("harmonit_tecnico_id"),
            tecnico_nome=linha.get("tecnico_nome"),
        ))

    bons = [r for r in resultados if r.get("ok")]
    # 🚨 O rastro guarda o PRIMEIRO id que voltou e TODOS os motivos de recusa:
    # dizer só "deu erro" obrigaria a abrir o log para saber em qual OS.
    erros = "; ".join(
        f"OS {r.get('numero_os')}: {r.get('motivo')}"
        for r in resultados if not r.get("ok"))
    banco.executar(
        "UPDATE agendamento SET harmonit_agendamento_id = %s, "
        "       harmonit_em = CASE WHEN %s THEN now() ELSE NULL END, "
        "       harmonit_erro = %s WHERE id = %s",
        (bons[0]["agendamento_id"] if bons else None, bool(bons),
         erros or None, agendamento_id))
    return {"ligado": True, "resultados": resultados,
            "quantas_foram": len(bons), "erro": erros or None}


def levar_endereco_ao_harmonit(agendamento_id: int, *,
                               cfg: dict | None = None) -> dict:
    """Grava o endereço do compromisso nas OS dele, no Harmonit.

    🔵 Pedido dele, 21/10: *"dai vai enviar para o endereço da OS e salvar ela
    lá no harmonit corretamente"*.

    🚨 USA O MESMO INTERRUPTOR DA ESCRITA DO COMPROMISSO. Endereço e
    compromisso vão para a mesma OS, pela mesma ponte: dois interruptores para
    a mesma decisão seriam dois lugares para esquecer de ligar.

    🚨 NUNCA DERRUBA O COMPROMISSO, e grava o motivo na própria linha -- igual
    ao `levar_ao_harmonit`. ⚠️ Sem rua, não tenta: mandar CEP sozinho
    sobrescreveria o endereço que a OS já tem por um que não leva ninguém a
    lugar nenhum.
    """
    if not escreve_no_harmonit(cfg):
        return {"ligado": False, "resultados": []}
    linha = por_id(agendamento_id)
    if not linha:
        raise ValueError("agendamento não encontrado")
    endereco = _endereco_para_a_os(linha)
    if not endereco.get("endereco"):
        return {"ligado": True, "resultados": [],
                "erro": "o compromisso não tem rua, então não mexi na OS"}

    resultados = [fpsl_ponte.gravar_endereco_da_os(o["numero_os"], endereco)
                  for o in linha["ordens"]]
    bons = [r for r in resultados if r.get("ok")]
    erros = "; ".join(
        f"OS {r.get('numero_os')}: {r.get('motivo') or r.get('fora_do_endereco')}"
        for r in resultados if not r.get("ok"))
    banco.executar(
        "UPDATE agendamento SET endereco_os_em = CASE WHEN %s THEN now() END, "
        "       endereco_os_erro = %s WHERE id = %s",
        (bool(bons), erros or None, agendamento_id))
    return {"ligado": True, "resultados": resultados,
            "quantas_foram": len(bons), "erro": erros or None}


def confirmar(agendamento_id: int, responsavel_cliente: str) -> bool:
    """O cliente confirmou, e disse quem acompanha o técnico.

    🔵 A aba Confirmar **exige** o responsável: é campo da mensagem que sai
    para os dois lados ("RESPONSÁVEL DO CLIENTE POR ACOMPANHAR O TÉCNICO").
    """
    responsavel = (responsavel_cliente or "").strip()
    if not responsavel:
        raise ValueError("confirmar exige o nome de quem acompanha o técnico")
    return banco.executar(
        "UPDATE agendamento SET estado = 'confirmado', "
        "       responsavel_cliente = %s, confirmado_em = now() "
        " WHERE id = %s AND estado IN ('rascunho','aguardando')",
        (responsavel, agendamento_id),
    ) > 0


def cancelar(agendamento_id: int, motivo: str) -> bool:
    """Cancela preservando o histórico -- nada é apagado.

    A OS volta a poder ser agendada porque `cancelado` não é estado ativo.
    """
    return banco.executar(
        "UPDATE agendamento SET estado = 'cancelado', cancelado_em = now(), "
        "       motivo_cancelamento = %s "
        " WHERE id = %s AND estado <> 'cancelado'",
        ((motivo or "").strip() or None, agendamento_id),
    ) > 0


def reagendar(agendamento_id: int, inicio, fim=None) -> bool:
    """Muda a data. Volta para `aguardando` e **esquece a confirmação**.

    🚨 Confirmação é de uma data, não do compromisso: manter `confirmado`
    depois de mudar o dia faria a tela afirmar que o cliente concordou com
    algo que ele não viu.
    """
    return banco.executar(
        "UPDATE agendamento SET inicio = %s, fim = %s, estado = 'aguardando', "
        "       responsavel_cliente = NULL, confirmado_em = NULL "
        " WHERE id = %s AND estado <> 'cancelado'",
        (inicio, fim, agendamento_id),
    ) > 0


def _montar(linhas: list[dict]) -> list[dict]:
    """Pendura as OS em cada compromisso, numa consulta só.

    Uma consulta por linha seria N+1 numa tela que abre com a semana inteira.
    """
    if not linhas:
        return []
    ids = [l["id"] for l in linhas]
    ordens = banco.varios(
        "SELECT agendamento_id, numero_os, placa, tipo_nome FROM agendamento_os "
        " WHERE agendamento_id = ANY(%s) ORDER BY numero_os",
        (ids,),
    )
    por_agendamento: dict[int, list[dict]] = {i: [] for i in ids}
    for o in ordens:
        por_agendamento[o["agendamento_id"]].append(
            # `tipo_nome` sai daqui para o cabeçalho da mensagem (ponta 1). Vem
            # nulo com frequência, e a tela OMITE o segmento nesse caso.
            {"numero_os": o["numero_os"], "placa": o["placa"],
             "tipo_nome": o["tipo_nome"]}
        )
    for l in linhas:
        l["ordens"] = por_agendamento.get(l["id"], [])
    return linhas


_CAMPOS = (
    "a.id, a.conversa_id, a.tecnico_contato_id, a.cliente_harmonit_id, "
    "a.cliente_nome, a.inicio, a.fim, a.endereco, a.responsavel_cliente, "
    "a.estado, a.orcamento_id, a.criado_em, a.confirmado_em, a.cancelado_em, "
    "a.motivo_cancelamento, a.harmonit_agendamento_id, a.harmonit_em, "
    "a.harmonit_erro, a.cep, a.logradouro, a.numero, a.bairro, a.cidade, "
    "a.uf, a.complemento, a.endereco_os_em, a.endereco_os_erro, "
    "c.nome AS tecnico_nome, at.nome AS criado_por_nome, "
    "o.numero AS orcamento_numero"
)
_DE = (
    "  FROM agendamento a "
    "  LEFT JOIN contato c ON c.id = a.tecnico_contato_id "
    "  LEFT JOIN atendente at ON at.id = a.criado_por "
    "  LEFT JOIN orcamento o ON o.id = a.orcamento_id "
)


def do_dia(dia) -> list[dict]:
    """Os compromissos de um dia, para o grid da tela `ATD_7.1`.

    ⚠️ Inclui os cancelados: a tela mostra o estado, e esconder cancelamento
    faz o operador remarcar achando que nunca houve nada.
    """
    return _montar(banco.varios(
        f"SELECT {_CAMPOS} {_DE} "
        " WHERE a.inicio::date = %s ORDER BY a.inicio",
        (dia,),
    ))


def do_periodo(inicio, fim) -> list[dict]:
    """Os compromissos entre duas datas, inclusive — o carrossel da semana."""
    return _montar(banco.varios(
        f"SELECT {_CAMPOS} {_DE} "
        " WHERE a.inicio::date BETWEEN %s AND %s ORDER BY a.inicio",
        (inicio, fim),
    ))


def por_id(agendamento_id: int) -> dict | None:
    linhas = _montar(banco.varios(
        f"SELECT {_CAMPOS} {_DE} WHERE a.id = %s", (agendamento_id,)))
    return linhas[0] if linhas else None


def aguardando_do_cliente(cliente_harmonit_id: str) -> list[dict]:
    """O que espera confirmação daquele cliente — a aba Confirmar."""
    return _montar(banco.varios(
        f"SELECT {_CAMPOS} {_DE} "
        " WHERE a.cliente_harmonit_id = %s AND a.estado = 'aguardando' "
        " ORDER BY a.inicio",
        (str(cliente_harmonit_id),),
    ))
