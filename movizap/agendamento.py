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
        # de onde o técnico saiu e quanto se cobrou naquele dia.
        # ⚠️ 04/11: a origem ATUAL deixou de ser a memória `tecnico_origem` e
        # passou a ser o ENDEREÇO FIXO da ficha (`tecnico_ficha`, tela
        # `TEC_1.1`) -- `rotas.py` não lê mais aquela tabela. O desenho desta
        # linha não mudou e é por isso que ela importa mais agora: se o técnico
        # mudar de endereço na ficha, ou se alguém digitar outro só para aquele
        # cálculo, esta linha continua dizendo de onde se cobrou naquele dia.
        # Mesmo desenho do `tipo_nome`.
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

    # 🚨 O RASTRO POR OS (migração 112), e por que ele tinha de existir: um
    # compromisso do MoviZap cobre VÁRIAS OS, e no Harmonit cada OS tem a sua
    # linha e o seu compromisso. A coluna de 070 guarda só o primeiro id que
    # voltou -- serve para o selo ("foi para o Harmonit?") e não serve para
    # apagar, porque apagar com o id da OS errada arrancaria a linha errada.
    #
    # ⚠️ `vinculo_criado` É O CAMPO QUE DECIDE SE CANCELAR PODE: a medição na
    # Velasco provou que o DELETE do ERP leva o compromisso **e** a linha do
    # técnico, então só se apaga a linha que nós criamos.
    for r in resultados:
        if not r.get("ok"):
            continue
        banco.executar(
            "UPDATE agendamento_os "
            "   SET harmonit_agendamento_id = %s, harmonit_vinculo_id = %s, "
            "       vinculo_criado = %s, harmonit_em = now() "
            " WHERE agendamento_id = %s AND numero_os = %s",
            (r.get("agendamento_id"), r.get("vinculo_id"),
             bool(r.get("vinculo_criado")), agendamento_id,
             r.get("numero_os")))

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


def _rastro_no_harmonit(agendamento_id: int) -> list[dict]:
    """O que cada OS deste compromisso tem no Harmonit (migração 112).

    ⚠️ Só as OS cujo rastro existe: sem `harmonit_vinculo_id` não há o que
    apagar lá, e inventar um id seria apontar para a linha de outra pessoa.
    """
    return banco.varios(
        "SELECT numero_os, harmonit_agendamento_id, harmonit_vinculo_id, "
        "       vinculo_criado "
        "  FROM agendamento_os "
        " WHERE agendamento_id = %s AND harmonit_vinculo_id IS NOT NULL "
        " ORDER BY numero_os", (agendamento_id,))


def cancelar(agendamento_id: int, motivo: str, *,
             cfg: dict | None = None) -> bool:
    """Cancela preservando o histórico -- nada é apagado **deste lado**.

    A OS volta a poder ser agendada porque `cancelado` não é estado ativo.

    🚨 E DESDE 18/11 O CANCELAMENTO CHEGA AO HARMONIT, 🔵 a pedido dele. Lá
    não há "preservar": a medição na Velasco provou que o único caminho é o
    `DELETE`, e que ele leva o compromisso **e** a linha do técnico. Então só
    se apaga a linha que nós criamos -- 🔵 *"apaga, só se a linha for nossa"*.

    🚨 O ESTADO DESTE LADO MUDA PRIMEIRO, E DE PROPÓSITO. Se a escrita no ERP
    falhar, o compromisso continua cancelado aqui e o motivo fica gravado: é a
    decisão 7 dele, *"o MoviZap é o dono"*. O contrário -- travar o
    cancelamento porque o ERP não respondeu -- deixaria o operador preso a um
    compromisso que ele já desmarcou com o cliente.
    """
    mudou = banco.executar(
        "UPDATE agendamento SET estado = 'cancelado', cancelado_em = now(), "
        "       motivo_cancelamento = %s "
        " WHERE id = %s AND estado <> 'cancelado'",
        ((motivo or "").strip() or None, agendamento_id),
    ) > 0
    if not mudou or not escreve_no_harmonit(cfg):
        return mudou

    recusas = []
    for linha in _rastro_no_harmonit(agendamento_id):
        r = fpsl_ponte.cancelar_agendamento(
            numero_os=linha["numero_os"],
            agendamento_id=linha["harmonit_agendamento_id"],
            vinculo_id=linha["harmonit_vinculo_id"],
            # ⚠️ NULO conta como "não é nossa": rastro anterior à migração 112
            # não diz quem criou a linha, e quem não sabe não apaga.
            vinculo_criado=bool(linha["vinculo_criado"]))
        if r.get("ok"):
            banco.executar(
                "UPDATE agendamento_os SET harmonit_agendamento_id = NULL, "
                "       harmonit_vinculo_id = NULL, harmonit_em = now() "
                " WHERE agendamento_id = %s AND numero_os = %s",
                (agendamento_id, linha["numero_os"]))
        else:
            recusas.append(f"OS {linha['numero_os']}: "
                           f"{fpsl_ponte.frase_da_recusa(r)}")
    # 🚨 A recusa fica LEGÍVEL na própria linha, como no agendar: dizer só
    # "deu erro" obrigaria a abrir o log para saber em qual OS.
    if recusas:
        banco.executar(
            "UPDATE agendamento SET harmonit_erro = %s WHERE id = %s",
            ("; ".join(recusas), agendamento_id))
    return mudou


def reagendar(agendamento_id: int, inicio, fim=None, *,
              cfg: dict | None = None) -> bool:
    """Muda a data. Volta para `aguardando` e **esquece a confirmação**.

    🚨 Confirmação é de uma data, não do compromisso: manter `confirmado`
    depois de mudar o dia faria a tela afirmar que o cliente concordou com
    algo que ele não viu.

    🚨 E DESDE 18/11 A DATA NOVA VAI AO HARMONIT NA HORA, 🔵 a pedido dele.
    ⚠️ Antes, o compromisso do ERP ficava com a data velha até alguém
    reconfirmar -- e data velha na agenda do técnico faz alguém viajar no dia
    errado. O ERP não tem alteração: o caminho é criar o novo e apagar o
    antigo, **nessa ordem**.
    """
    rastro = _rastro_no_harmonit(agendamento_id)
    antes = por_id(agendamento_id)
    mudou = banco.executar(
        "UPDATE agendamento SET inicio = %s, fim = %s, estado = 'aguardando', "
        "       responsavel_cliente = NULL, confirmado_em = NULL "
        " WHERE id = %s AND estado <> 'cancelado'",
        (inicio, fim, agendamento_id),
    ) > 0
    if not mudou or not escreve_no_harmonit(cfg) or not rastro:
        return mudou

    contato = banco.um(
        """SELECT ct.harmonit_tecnico_id,
                  (SELECT e164 FROM contato_telefone
                    WHERE contato_id = ct.id
                    ORDER BY principal DESC, id LIMIT 1) AS e164
             FROM contato ct WHERE ct.id = %s""",
        (antes["tecnico_contato_id"],)) if antes else {}
    contato = contato or {}

    recusas = []
    for linha in rastro:
        r = fpsl_ponte.reagendar_tecnico(
            numero_os=linha["numero_os"], inicio=inicio, fim=fim,
            agendamento_id_antigo=linha["harmonit_agendamento_id"],
            vinculo_id_antigo=linha["harmonit_vinculo_id"],
            vinculo_criado=bool(linha["vinculo_criado"]),
            tecnico_telefone=contato.get("e164"),
            tecnico_id=contato.get("harmonit_tecnico_id"),
            tecnico_nome=(antes or {}).get("tecnico_nome"))
        if r.get("ok"):
            # 🚨 O rastro passa a apontar o compromisso NOVO. ⚠️ E
            # `apagou_o_antigo` falso NÃO invalida o reagendamento: o novo
            # está lá, o antigo é que sobrou -- e a frase diz qual.
            banco.executar(
                "UPDATE agendamento_os "
                "   SET harmonit_agendamento_id = %s, harmonit_vinculo_id = %s, "
                "       vinculo_criado = %s, harmonit_em = now() "
                " WHERE agendamento_id = %s AND numero_os = %s",
                (r.get("agendamento_id"), r.get("vinculo_id"),
                 bool(r.get("vinculo_criado")), agendamento_id,
                 linha["numero_os"]))
            if not r.get("apagou_o_antigo"):
                recusas.append(f"OS {linha['numero_os']}: "
                               f"{r.get('motivo') or 'o compromisso antigo ficou'}")
        else:
            recusas.append(f"OS {linha['numero_os']}: "
                           f"{fpsl_ponte.frase_da_recusa(r)}")
    banco.executar(
        "UPDATE agendamento SET harmonit_erro = %s WHERE id = %s",
        ("; ".join(recusas) or None, agendamento_id))
    return mudou


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


def do_periodo(inicio, fim, visto_por: int | None = None) -> list[dict]:
    """Os compromissos entre duas datas, inclusive — o carrossel da semana.

    🔵 `visto_por` (26/11): o selo **Visto** da pessoa que pediu. Pedido dele:
    *"pode ter um flag de 'Visto' para que o usuário saiba o que já viu e o que
    não, pois podem aparecer agendamentos no dia mesmo"*.

    🚨 O VISTO É FUNDIDO AQUI, EM PYTHON, E NÃO ENTRA NO `_CAMPOS`/`_DE`. Esses
    dois fragmentos são compartilhados por `do_dia`, `por_id` e
    `aguardando_do_cliente` -- e a última serve a aba **Confirmar** do
    `ModalAgendar`, que não tem atendente no contexto. Pôr o `LEFT JOIN` no SQL
    comum obrigaria os três a carregar um parâmetro que só um deles tem.

    ⚠️ UMA consulta para a semana inteira, nunca uma por cartão -- a mesma
    régua do `_anexar_comprovantes_no_quadro` e do `_orcamento_por_os`.
    """
    linhas = _montar(banco.varios(
        f"SELECT {_CAMPOS} {_DE} "
        " WHERE a.inicio::date BETWEEN %s AND %s ORDER BY a.inicio",
        (inicio, fim),
    ))
    return _com_visto(linhas, visto_por)


def _com_visto(linhas: list[dict], atendente_id: int | None) -> list[dict]:
    """Pendura `visto_em` e `visto_automatico` em cada compromisso.

    ⚠️ SEM `atendente_id` OS CAMPOS NEM APARECEM, e isso é de propósito: nulo
    diria *"esta pessoa não viu"*, e a verdade é *"ninguém perguntou por
    pessoa"*. Chave ausente é a única resposta honesta.

    🚨 E SE A CONSULTA FALHAR, A LISTA VOLTA INTEIRA, sem selo: perder o
    *"Visto"* é aceitável, perder a agenda do dia não é.
    """
    if not atendente_id or not linhas:
        return linhas
    ids = [x["id"] for x in linhas]
    try:
        vistos = {
            v["agendamento_id"]: v
            for v in banco.varios(
                "SELECT agendamento_id, visto_em, automatico "
                "  FROM agendamento_visto "
                " WHERE atendente_id = %s AND agendamento_id = ANY(%s)",
                (atendente_id, ids))
        }
    except Exception:
        log.exception("nao li o visto do atendente %s; a lista vai sem selo",
                      atendente_id)
        return linhas
    for x in linhas:
        marca = vistos.get(x["id"])
        x["visto_em"] = marca["visto_em"] if marca else None
        x["visto_automatico"] = bool(marca["automatico"]) if marca else False
    return linhas


def marcar_visto(agendamento_id: int, atendente_id: int, *,
                 automatico: bool = False) -> dict | None:
    """Carimba que ESTA pessoa viu ESTE compromisso. Idempotente.

    🚨 `ON CONFLICT DO NOTHING`, E NÃO `DO UPDATE`. Reabrir o cartão não pode
    reescrever a hora em que a pessoa viu -- o selo diz *"Visto 08:12"*, e
    08:12 é quando ela viu da primeira vez. E um visto que ela MARCOU não pode
    ser rebaixado a `automatico` só porque o cartão abriu depois.

    ⚠️ Devolve a linha que VALE (a de antes, quando já havia), não a que se
    tentou gravar: a tela mostra o que está no banco, nunca o que se pediu.
    """
    if not banco.um("SELECT id FROM agendamento WHERE id = %s",
                    (agendamento_id,)):
        return None
    banco.executar(
        "INSERT INTO agendamento_visto (agendamento_id, atendente_id, automatico) "
        "VALUES (%s, %s, %s) ON CONFLICT DO NOTHING",
        (agendamento_id, atendente_id, bool(automatico)))
    return banco.um(
        "SELECT visto_em, automatico FROM agendamento_visto "
        " WHERE agendamento_id = %s AND atendente_id = %s",
        (agendamento_id, atendente_id))


def desmarcar_visto(agendamento_id: int, atendente_id: int) -> bool:
    """Desfaz o visto DESTA pessoa. 🔵 Ele pediu o desfazer junto do botão.

    ⚠️ Volta `False` quando não havia marca -- e a rota responde 200 do mesmo
    jeito: desfazer o que já está desfeito é o estado que a pessoa queria.
    """
    return banco.executar(
        "DELETE FROM agendamento_visto "
        " WHERE agendamento_id = %s AND atendente_id = %s",
        (agendamento_id, atendente_id)) > 0


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
