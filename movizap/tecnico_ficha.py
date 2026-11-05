"""A ficha do técnico, o catálogo de serviços e o preço de custo de cada um.

É o que alimenta a `TEC_1.1` (Técnicos) — a tela que ele pediu em 04/11,
*"abaixo de 'orçamentos'"*, com *"uma ficha de cada 1. como no formulario de
credenciamento"*, o *"endereço fixo que aparecerá na tela de calculo de KM"* e
*"uma tabela de preço por serviços que ele oferece, padrão a todos"*.

🚨 TÉCNICO CONTINUA SENDO `contato` COM `relacao = 'tecnico'`. Esta ficha é uma
linha pendurada no contato, não uma entidade nova: `agendamento` e `orcamento`
já apontam para `contato(id)`, e criar um segundo cadastro de técnico faria o
orçamento emitido e a ficha falarem de dois sujeitos diferentes.

🚨 TÉCNICO SEM FICHA É ESTADO VÁLIDO, e a lista mostra os dois. Eram 303
contatos de técnico em 04/11, nenhum com ficha: se a tela só mostrasse quem tem
ficha, ela abriria vazia e pareceria quebrada. Quem não tem ficha aparece com
`tem_ficha: false`, e é assim que se vê o tamanho do trabalho.

🚨 O QUE VEM DO HARMONIT NÃO SE ESCREVE, SÓ SE LÊ — *"o acesso de fato deles ao
harmonit é feito como usuario do sistema, então esses dados só vamos trazer
mesmo"*. O vínculo com o cadastro de lá já existia desde 21/10
(`movizap/tecnico_vinculo.py`, rotas `/api/contatos/{id}/tecnico-harmonit`), e
esta tela o CHAMA em vez de refazer. Nada aqui tem caminho para escrever no
Harmonit.

⚠️ CUSTO, NÃO VENDA. O valor por serviço é o que o técnico cobra da Movisat
(decisão dele em 04/11). O nome da coluna é `custo_centavos` para que ninguém
a leia um dia como preço de cliente.
"""
import logging

import psycopg

from . import banco
from . import cadastro
from . import telefone as fone
from .operacao import DadoInvalido
# 🚨 O DINHEIRO SAI ESCRITO DAQUI, e é regra da casa desde a aba de orçamentos:
# *"o dinheiro vem ESCRITO do backend ('1.234,56'), nunca dividido por 100 na
# tela"*. `custo_centavos` vai junto porque é o que o campo de edição precisa --
# o nome diz a unidade, e é ele que a rota aceita de volta.
from .orcamento import reais

log = logging.getLogger("movizap.tecnico_ficha")

POR_PAGINA = 50

ESTADOS = ("candidato", "credenciado", "recusado")

# O código do formulário público de credenciamento. É a procedência dos
# candidatos — ver `candidatos()` e `sugestao_da_solicitacao()`.
CODIGO_DO_FORMULARIO = "CREDENCIAMENTO"

# 🚨 `DadoInvalido` É O DE `operacao`, IMPORTADO, não um novo. O `main.py` tem
# UM `@app.exception_handler(operacao.DadoInvalido)` (linha 3199) que já
# transforma isto no 400 com a frase que o usuário lê. Uma classe própria aqui,
# por mais parecida que fosse, escaparia desse handler e viraria 500 -- erro de
# programação que a suíte veria como "a rota respondeu", porque responder 500
# também é responder.
__all__ = ["DadoInvalido"]


# ---------------------------------------------------------------------------
# Os campos da ficha, declarados uma vez.
#
# 🚨 ESTA TABELA É A ÚNICA RÉGUA, e os limites são os do banco (migração 085).
# Até 29/10 o projeto já tinha aprendido isto duas vezes: campo novo que entra
# no banco e não entra na lista de quem grava fica para sempre vazio, e a suíte
# não vê o elo. Quem acrescentar coluna acrescenta aqui, e a rota, a gravação e
# a leitura passam a conhecê-la de uma vez.
#
# ⚠️ Os sete do endereço são os MESMOS da 073/077, nos mesmos limites:
# `agendamento.CAMPOS_DE_ENDERECO` e `rotas.CAMPOS_DE_ORIGEM` falam do mesmo
# endereço, e duas réguas para o mesmo campo é uma delas mentindo.
# ---------------------------------------------------------------------------
CAMPOS_TEXTO = {
    # bloco EMPRESA
    "nome_fantasia": 120,
    "razao_social": 120,
    "telefone_fixo": 20,
    "email_geral": 120,
    # bloco RESPONSÁVEL
    "responsavel_nome": 80,
    "responsavel_sobrenome": 80,
    "responsavel_celular": 20,
    "responsavel_email": 120,
    # bloco ENDEREÇO FIXO (os sete da 073)
    "cep": 8,
    "logradouro": 80,
    "numero": 10,
    "bairro": 60,
    "cidade": 50,
    "uf": 2,
    "complemento": 40,
    # bloco DESLOCAMENTO
    "area_cobertura": 120,
}

# 🔵 04/11, segunda volta: *"Banco ajuste para dados de pagamento, pode ser TED,
# PIX, ou boleto, oopção por lista e campo com os dados"*. As três são os
# valores NOSSOS, em slug, e são os mesmos que o formulário de credenciamento
# passou a oferecer — *"ajuste no formulario tbm, o mesmo formato. ai amarra
# eles"*. É esta tupla que amarra os dois lados.
FORMAS_DE_PAGAMENTO = ("ted", "pix", "boleto")

# Só dígitos, e o tamanho é o do documento — não o do campo.
CAMPOS_DOCUMENTO = {"cnpj": 14, "cpf": 11}

# 🔵 `preenche_os` entrou em 04/11, no fechamento: *"crie um campo de flag,
# junto com os do deslocamento chamado 'Preenche OS'"*. ⚠️ Mora com os do
# deslocamento porque ele pediu ali, não porque preencher OS seja deslocamento.
# ⚠️ E não condiciona nada hoje: a tela grava e mostra. Fazer a criação de OS
# depender dela seria regra nova sobre o fluxo do Harmonit.
CAMPOS_BOOLEANOS = ("ponto_fixo", "vai_ao_cliente", "cobra_deslocamento",
                    "preenche_os")

# ⚠️ `pagamento_dados` é TEXTO LIVRE: chave PIX é CPF, CNPJ, telefone, e-mail ou
# chave aleatória; conta é banco + agência + conta; boleto é um combinado.
# Validar formato aqui recusaria o que o técnico mandou do jeito que ele tem.
CAMPOS_LONGOS = ("observacao", "pagamento_dados")

CAMPOS_DE_ENDERECO = ("cep", "logradouro", "numero", "bairro", "cidade", "uf",
                      "complemento")

# A ordem em que a leitura devolve, e a lista que a gravação aceita.
#
# 🚨 `km_valor_centavos` E `titular_tipo` ENTRAM À MÃO AQUI porque não caem em
# nenhuma das listas acima (um é inteiro, o outro tem CHECK próprio). E o
# `km_valor_centavos` já provou por que esta linha importa: na primeira escrita
# ele ficou fora, `salvar()` o GRAVAVA (vem do dict de valores) e `ficha()` não
# o LIA (vem desta tupla) -- o valor entrava no banco e a tela nunca o via.
# É o elo "quem devolve → quem grava → quem lê" que suíte verde não vê, e aqui
# foi o teste da origem do KM que esbarrou nele.
CAMPOS = (tuple(CAMPOS_TEXTO) + tuple(CAMPOS_DOCUMENTO) + CAMPOS_BOOLEANOS
          + CAMPOS_LONGOS + ("pagamento_forma", "km_valor_centavos"))


def _texto(valor, campo: str, maximo: int) -> str | None:
    """Vazio vira NULL, nunca string vazia.

    ⚠️ `''` e `NULL` no mesmo campo são dois jeitos de dizer "não sei", e
    depois ninguém consegue perguntar "quem está sem cidade?" de um jeito só.
    """
    limpo = (valor or "").strip()
    if not limpo:
        return None
    if len(limpo) > maximo:
        raise DadoInvalido(f"{campo} passa de {maximo} caracteres.")
    return limpo


def _digitos(valor, campo: str, tamanho: int) -> str | None:
    """CNPJ e CPF guardados só com dígitos, como o resto do projeto.

    ⚠️ NÃO VALIDA O DÍGITO VERIFICADOR, de propósito: recusar um CNPJ que o
    cliente digitou do jeito que está no contrato dele trava o credenciamento
    por causa de uma régua nossa. O tamanho é conferido porque é o limite da
    coluna; a correção é de quem confere.
    """
    limpo = "".join(c for c in (valor or "") if c.isdigit())
    if not limpo:
        return None
    if len(limpo) > tamanho:
        raise DadoInvalido(
            f"{campo} tem {len(limpo)} dígitos; o esperado são {tamanho}.")
    return limpo


def _booleano(valor):
    """Três estados: sim, não e NÃO RESPONDEU.

    🚨 `None` não pode virar `False`. "Não disse se tem ponto fixo" e "disse que
    não tem" são fatos diferentes, e achatá-los faria a ficha afirmar o que
    ninguém respondeu — o mesmo defeito que o `0` ≠ `NULL` da situação da OS.
    """
    if valor is None or valor == "":
        return None
    return bool(valor)


def _centavos(valor, campo: str) -> int | None:
    """Vazio é "não oferece"; zero é "cobra zero". São coisas diferentes."""
    if valor is None or valor == "":
        return None
    try:
        n = int(valor)
    except (TypeError, ValueError):
        raise DadoInvalido(f"{campo} não é um valor em centavos.") from None
    if n < 0:
        raise DadoInvalido(f"{campo} não pode ser negativo.")
    return n


# ===========================================================================
# O CATÁLOGO — igual para todos os técnicos
# ===========================================================================

def servicos(incluir_inativos: bool = False) -> list[dict]:
    return banco.varios(
        """SELECT id, nome, ordem, ativo FROM servico_tecnico
            WHERE (%s OR ativo) ORDER BY ordem, nome""",
        (incluir_inativos,))


def criar_servico(nome: str, ordem: int | None = None) -> dict:
    nome = _texto(nome, "O nome do serviço", 60)
    if not nome:
        raise DadoInvalido("O nome do serviço é obrigatório.")
    if ordem is None:
        maior = banco.um("SELECT COALESCE(MAX(ordem), 0) AS m FROM servico_tecnico")
        ordem = int(maior["m"]) + 1
    try:
        linha = banco.um(
            "INSERT INTO servico_tecnico (nome, ordem) VALUES (%s, %s) RETURNING id",
            (nome, int(ordem)))
    except psycopg.errors.UniqueViolation as e:
        raise DadoInvalido(f"Já existe o serviço {nome!r}.") from e
    return banco.um("SELECT id, nome, ordem, ativo FROM servico_tecnico "
                    "WHERE id = %s", (linha["id"],))


def atualizar_servico(servico_id: int, nome: str, ordem: int, ativo: bool) -> dict:
    if not banco.um("SELECT id FROM servico_tecnico WHERE id = %s", (servico_id,)):
        raise DadoInvalido("Serviço não encontrado.")
    nome = _texto(nome, "O nome do serviço", 60)
    if not nome:
        raise DadoInvalido("O nome do serviço é obrigatório.")
    # ⚠️ Desativar NÃO apaga preço nenhum: o serviço sai da ficha de quem ainda
    # não precificou e continua explicando os orçamentos antigos.
    try:
        banco.executar(
            "UPDATE servico_tecnico SET nome = %s, ordem = %s, ativo = %s "
            " WHERE id = %s", (nome, int(ordem), bool(ativo), servico_id))
    except psycopg.errors.UniqueViolation as e:
        raise DadoInvalido(f"Já existe o serviço {nome!r}.") from e
    return banco.um("SELECT id, nome, ordem, ativo FROM servico_tecnico "
                    "WHERE id = %s", (servico_id,))


# ===========================================================================
# A LISTA
# ===========================================================================

def listar(busca: str = "", estado: str | None = None, com_ficha=None,
           pagina: int = 1, por_pagina: int = POR_PAGINA) -> dict:
    """Os contatos de técnico, com o que a ficha de cada um já diz.

    ⚠️ A interpretação do termo é a MESMA do cadastro (`interpretar_busca`):
    telefone, documento ou nome, e a coluna da consulta muda sozinha. Escrever
    uma segunda régua de busca aqui faria a mesma palavra achar coisas
    diferentes em duas telas.
    """
    interpretacao = cadastro.interpretar_busca(busca)
    salto, limite = cadastro._paginacao(pagina, por_pagina)

    onde = ["c.relacao = 'tecnico'"]
    params: list = []

    if interpretacao["tipo"] == "telefone":
        onde.append("""EXISTS (SELECT 1 FROM contato_telefone t
                                WHERE t.contato_id = c.id AND t.e164 = ANY(%s))""")
        params.append(interpretacao["variantes"])
    elif interpretacao["tipo"] == "documento":
        # 🚨 AQUI O DOCUMENTO É O DA FICHA, não o da empresa cliente. Técnico
        # não tem `cliente_id` (é pessoa/prestador, não contato de cliente), e
        # procurar pelo documento do `cliente` como faz a CAD_1.2 não acharia
        # nunca um CNPJ de prestador.
        onde.append("(f.cnpj = %s OR f.cpf = %s)")
        params.extend([interpretacao["limpo"], interpretacao["limpo"]])
    elif interpretacao["tipo"] == "nome":
        onde.append("(lower(c.nome) LIKE lower(%s) "
                    " OR lower(coalesce(f.nome_fantasia, '')) LIKE lower(%s) "
                    " OR lower(coalesce(f.razao_social, '')) LIKE lower(%s) "
                    " OR lower(coalesce(c.harmonit_tecnico_nome, '')) LIKE lower(%s))")
        params.extend([f"%{interpretacao['termo']}%"] * 4)

    if estado:
        if estado not in ESTADOS:
            raise DadoInvalido(f"Estado inválido: {estado!r}.")
        onde.append("f.estado = %s")
        params.append(estado)

    if com_ficha is True:
        onde.append("f.contato_id IS NOT NULL")
    elif com_ficha is False:
        onde.append("f.contato_id IS NULL")

    filtro = " WHERE " + " AND ".join(onde)
    de = " FROM contato c LEFT JOIN tecnico_ficha f ON f.contato_id = c.id"

    total = banco.um(f"SELECT count(*) AS n{de}{filtro}", tuple(params))["n"]

    linhas = banco.varios(
        f"""
        SELECT c.id AS contato_id, c.nome, c.ativo,
               c.harmonit_tecnico_id, c.harmonit_tecnico_nome,
               (SELECT t.e164 FROM contato_telefone t
                 WHERE t.contato_id = c.id
                 ORDER BY t.principal DESC, t.id LIMIT 1) AS telefone,
               (f.contato_id IS NOT NULL) AS tem_ficha,
               f.estado, f.nome_fantasia, f.razao_social, f.cnpj,
               f.cidade, f.uf, f.km_valor_centavos, f.atualizado_em,
               -- 🚨 Quantos serviços ELE OFERECE, que é quantos têm preço
               -- gravado. É a única coluna da lista que responde "esta ficha
               -- está utilizável?" -- ficha preenchida sem preço nenhum não
               -- serve para montar orçamento.
               (SELECT count(*) FROM tecnico_preco p
                 WHERE p.contato_id = c.id AND p.custo_centavos IS NOT NULL)
                 AS servicos_com_preco
        {de}{filtro}
        ORDER BY (f.contato_id IS NULL), f.estado, lower(
                 coalesce(nullif(f.nome_fantasia, ''), c.harmonit_tecnico_nome, c.nome))
        LIMIT %s OFFSET %s
        """,
        tuple(params) + (limite, salto))

    for linha in linhas:
        linha["km_valor_texto"] = (reais(linha["km_valor_centavos"])
                                   if linha["km_valor_centavos"] is not None
                                   else None)

    return {
        "busca": interpretacao,
        "total": total,
        "pagina": max(1, int(pagina or 1)),
        "por_pagina": limite,
        "paginas": max(1, -(-total // limite)),
        "itens": linhas,
        # A soma é do FILTRO INTEIRO, não da página — a régua do
        # `orcamento_consulta`. Aqui o que interessa é quantos ainda não têm
        # ficha, porque é isso que diz o tamanho do trabalho que falta.
        "sem_ficha": banco.um(
            f"SELECT count(*) AS n{de}{filtro} AND f.contato_id IS NULL",
            tuple(params))["n"],
    }


# ===========================================================================
# A FICHA
# ===========================================================================

def ficha(contato_id: int) -> dict | None:
    """O técnico inteiro: contato, ficha (ou `None`), os dez preços e o vínculo.

    🚨 OS PREÇOS VÊM SEMPRE COM O CATÁLOGO INTEIRO, não só o que tem valor. A
    tela precisa desenhar as dez linhas para alguém poder preencher a décima;
    devolver só as preenchidas faria a ficha nova nascer sem onde digitar.
    """
    contato = banco.um(
        # ⚠️ `c.id` VEM NAS DUAS CHAVES de propósito: `contato_id` é o nome que
        # a tela usa em toda esta tela, e `id` é o que
        # `cadastro._com_telefones_e_papeis` procura. Renomear só para uma das
        # duas foi o primeiro defeito que o teste desta entrega pegou.
        """SELECT c.id, c.id AS contato_id, c.nome, c.relacao, c.email, c.ativo,
                  c.origem, c.harmonit_id,
                  c.harmonit_tecnico_id, c.harmonit_tecnico_nome,
                  c.harmonit_vinculo_origem, c.harmonit_vinculo_em
             FROM contato c WHERE c.id = %s""", (contato_id,))
    if not contato:
        return None

    linha = banco.um(
        f"""SELECT contato_id, estado, estado_em, estado_nota, estado_por,
                   {', '.join(CAMPOS)}, solicitacao_id, criado_em, atualizado_em
              FROM tecnico_ficha WHERE contato_id = %s""", (contato_id,))

    precos = banco.varios(
        """SELECT s.id AS servico_id, s.nome, s.ordem,
                  p.custo_centavos, p.atualizado_em
             FROM servico_tecnico s
             LEFT JOIN tecnico_preco p
                    ON p.servico_id = s.id AND p.contato_id = %s
            WHERE s.ativo OR p.custo_centavos IS NOT NULL
            ORDER BY s.ordem, s.nome""", (contato_id,))
    for p in precos:
        # ⚠️ "não oferece" é o texto, e NÃO "0,00" nem "—": é o que ele quis
        # dizer com *"serviços que ele oferece"*, e um traço deixaria quem lê
        # em dúvida se é zero ou vazio.
        p["custo_texto"] = (reais(p["custo_centavos"])
                            if p["custo_centavos"] is not None else None)

    ficha_dict = dict(linha) if linha else None
    if ficha_dict:
        ficha_dict["km_valor_texto"] = (
            reais(ficha_dict["km_valor_centavos"])
            if ficha_dict["km_valor_centavos"] is not None else None)

    return {
        "contato": cadastro._com_telefones_e_papeis(dict(contato)),
        "ficha": ficha_dict,
        "precos": precos,
        # Quem credenciou pela solicitação vê de onde veio. NULL = à mão (D3).
        "solicitacao": _solicitacao(linha["solicitacao_id"]) if linha else None,
    }


def _solicitacao(solicitacao_id) -> dict | None:
    if not solicitacao_id:
        return None
    return banco.um(
        """SELECT s.id, s.criada_em, s.valores, f.codigo, f.titulo
             FROM formulario_solicitacao s JOIN formulario f ON f.id = s.formulario_id
            WHERE s.id = %s""", (solicitacao_id,))


def _e_tecnico(contato_id: int) -> None:
    linha = banco.um("SELECT relacao FROM contato WHERE id = %s", (contato_id,))
    if not linha:
        raise DadoInvalido("Contato não encontrado.")
    if linha["relacao"] != "tecnico":
        # 🚨 A FICHA NÃO MUDA O TIPO DO CONTATO. Quem é técnico se decide na
        # ficha da conversa (`PUT /api/conversas/{id}/tipo`), e essa decisão
        # tem travas próprias — criar ficha de técnico em cima de um contato
        # de cliente mudaria o tipo dele pela porta de trás.
        raise DadoInvalido(
            "Este contato não é do tipo técnico. Mude o tipo na ficha da "
            "conversa antes de credenciar.")


def salvar(contato_id: int, dados: dict) -> dict:
    """Cria ou atualiza a ficha. O estado NÃO se muda por aqui.

    🚨 SALVAR E VALIDAR SÃO DUAS AÇÕES, e separá-las é o ponto do pedido dele
    (*"o cadastro do tecnico e validação dele passará por essa tela"*).
    Corrigir uma agência bancária não pode credenciar ninguém por acidente, e
    credenciar não deve exigir reenviar a ficha inteira.
    """
    _e_tecnico(contato_id)

    valores = {}
    for campo, maximo in CAMPOS_TEXTO.items():
        valores[campo] = _texto(dados.get(campo), campo, maximo)
    for campo, tamanho in CAMPOS_DOCUMENTO.items():
        valores[campo] = _digitos(dados.get(campo), campo.upper(), tamanho)
    for campo in CAMPOS_BOOLEANOS:
        valores[campo] = _booleano(dados.get(campo))
    for campo in CAMPOS_LONGOS:
        valores[campo] = (dados.get(campo) or "").strip() or None

    if valores.get("uf"):
        valores["uf"] = valores["uf"].upper()

    forma = (dados.get("pagamento_forma") or "").strip().lower() or None
    if forma and forma not in FORMAS_DE_PAGAMENTO:
        raise DadoInvalido(
            "A forma de pagamento é TED, PIX ou boleto.")
    valores["pagamento_forma"] = forma

    valores["km_valor_centavos"] = _centavos(
        dados.get("km_valor_centavos"), "O valor do km")

    solicitacao_id = dados.get("solicitacao_id")

    colunas = list(valores)
    marcas = ", ".join(["%s"] * len(colunas))
    atribuicoes = ", ".join(f"{c} = EXCLUDED.{c}" for c in colunas)
    params = [contato_id] + [valores[c] for c in colunas]

    banco.executar(
        f"""INSERT INTO tecnico_ficha (contato_id, {', '.join(colunas)})
            VALUES (%s, {marcas})
            ON CONFLICT (contato_id) DO UPDATE
               SET {atribuicoes}, atualizado_em = now()""",
        tuple(params))

    # A procedência só se grava uma vez, e nunca se apaga: ficha que nasceu de
    # uma solicitação continua sabendo de qual, mesmo depois de corrigida.
    if solicitacao_id:
        banco.executar(
            "UPDATE tecnico_ficha SET solicitacao_id = %s "
            " WHERE contato_id = %s AND solicitacao_id IS NULL",
            (int(solicitacao_id), contato_id))

    log.info("ficha do tecnico %s gravada", contato_id)
    return ficha(contato_id)


def definir_precos(contato_id: int, precos: dict) -> dict:
    """Os valores de custo, por serviço. Chave = `servico_id`.

    🚨 VALOR AUSENTE DA CHAMADA NÃO É VALOR APAGADO. Só mexe no que vier:
    enviar a ficha inteira para corrigir uma linha é o caminho mais curto para
    zerar nove preços sem perceber.

    Para dizer "não oferece mais", manda-se o serviço com valor `None` — e aí a
    linha é apagada, porque ausência e nulo significam a mesma coisa e duas
    formas de dizer o mesmo acabam discordando.
    """
    _e_tecnico(contato_id)
    validos = {s["id"] for s in servicos(incluir_inativos=True)}

    gravados = 0
    with banco.cursor() as cur:
        for chave, valor in (precos or {}).items():
            servico_id = int(chave)
            if servico_id not in validos:
                raise DadoInvalido(f"Serviço {servico_id} não existe.")
            centavos = _centavos(valor, "O valor do serviço")
            if centavos is None:
                cur.execute("DELETE FROM tecnico_preco "
                            " WHERE contato_id = %s AND servico_id = %s",
                            (contato_id, servico_id))
            else:
                cur.execute(
                    """INSERT INTO tecnico_preco (contato_id, servico_id, custo_centavos)
                       VALUES (%s, %s, %s)
                       ON CONFLICT (contato_id, servico_id) DO UPDATE
                          SET custo_centavos = EXCLUDED.custo_centavos,
                              atualizado_em = now()""",
                    (contato_id, servico_id, centavos))
            gravados += 1

    log.info("tecnico %s: %s preco(s) gravado(s)", contato_id, gravados)
    return ficha(contato_id)


def definir_estado(contato_id: int, estado: str, nota: str | None = None,
                   atendente_id: int | None = None) -> dict:
    """Credencia, recusa ou devolve para candidato.

    ⚠️ Recusar NÃO apaga a ficha. Mesmo CNPJ volta amanhã, e sem o registro da
    recusa ninguém lembra por que saiu.
    """
    if estado not in ESTADOS:
        raise DadoInvalido(f"Estado inválido: {estado!r}.")
    if not banco.um("SELECT contato_id FROM tecnico_ficha WHERE contato_id = %s",
                    (contato_id,)):
        raise DadoInvalido("Este técnico ainda não tem ficha para validar.")

    if estado == "credenciado":
        # 🚨 CREDENCIAR EXIGE O MÍNIMO PARA SER USADO DEPOIS. Sem endereço não
        # há cálculo de KM, e sem nenhum preço não há orçamento: credenciado
        # assim, o técnico aparece como pronto numa tela e falha na outra.
        # Isto não é regra inventada sobre o negócio dele — é a recusa de
        # marcar como pronto o que as outras duas telas não conseguem usar.
        atual = banco.um(
            "SELECT logradouro, cidade FROM tecnico_ficha WHERE contato_id = %s",
            (contato_id,))
        if not (atual["logradouro"] and atual["cidade"]):
            raise DadoInvalido(
                "Para credenciar, a ficha precisa de rua e cidade — é o "
                "endereço que a calculadora de KM usa como origem.")
        tem_preco = banco.um(
            "SELECT count(*) AS n FROM tecnico_preco "
            " WHERE contato_id = %s AND custo_centavos IS NOT NULL",
            (contato_id,))["n"]
        if not tem_preco:
            raise DadoInvalido(
                "Para credenciar, pelo menos um serviço precisa de valor.")

    banco.executar(
        """UPDATE tecnico_ficha
              SET estado = %s, estado_em = now(), estado_por = %s,
                  estado_nota = %s, atualizado_em = now()
            WHERE contato_id = %s""",
        (estado, atendente_id, (nota or "").strip() or None, contato_id))
    log.info("tecnico %s: estado %s por atendente %s", contato_id, estado,
             atendente_id)
    return ficha(contato_id)


def criar_tecnico(nome: str, telefone: str | None = None) -> dict:
    """Cria o contato do técnico e a ficha vazia, em uma transação.

    🚨 TELEFONE JÁ CADASTRADO RECUSA, com os candidatos na mão. É a mesma trava
    de `conversas.definir_tipo`, e existe pelo mesmo motivo: dois cadastros com
    o mesmo número fazem a conversa escolher um deles sozinha, e em 02/10 isso
    já produziu 274 técnicos que ninguém conseguia ligar.
    """
    nome = _texto(nome, "O nome do técnico", 120)
    if not nome:
        raise DadoInvalido("O nome do técnico é obrigatório.")

    e164 = None
    if (telefone or "").strip():
        e164 = fone.normalizar(telefone)
        if not e164:
            raise DadoInvalido(f"Não reconheci {telefone!r} como telefone.")
        donos = banco.varios(
            """SELECT c.id, c.nome, c.relacao FROM contato c
                JOIN contato_telefone t ON t.contato_id = c.id
               WHERE t.e164 = ANY(%s)""", (list(fone.variantes(e164)),))
        if donos:
            raise DadoInvalido(
                "Este telefone já é de " + ", ".join(
                    f"{d['nome']} ({d['relacao']})" for d in donos)
                + ". Abra a ficha dele em vez de criar um segundo cadastro.")

    with banco.cursor() as cur:
        cur.execute(
            """INSERT INTO contato (cliente_id, nome, relacao, origem, ativo)
               VALUES (NULL, %s, 'tecnico', 'movizap', true) RETURNING id""",
            (nome,))
        contato_id = cur.fetchone()["id"]
        if e164:
            cur.execute(
                """INSERT INTO contato_telefone
                       (contato_id, e164, bruto, origem_campo, principal)
                   VALUES (%s, %s, %s, 'manual', true)
                   ON CONFLICT DO NOTHING""",
                (contato_id, e164, telefone.strip()))
        cur.execute(
            "INSERT INTO tecnico_ficha (contato_id) VALUES (%s) "
            " ON CONFLICT DO NOTHING", (contato_id,))

    log.info("tecnico %s criado a mao (%s)", contato_id, e164 or "sem telefone")
    return ficha(contato_id)


# ===========================================================================
# A PORTA DE ENTRADA: o formulário de credenciamento
#
# 🔵 D3 dele (04/11): o formulário alimenta a tela *"mas não de forma
# exclusiva. Ainda é permitido fazer a mão."*
#
# 🚨 NADA AQUI GRAVA SOZINHO. `sugestao_da_solicitacao` só devolve o que a
# pessoa respondeu, mapeado para os campos da ficha; quem credencia confere e
# salva. Em 04/11 havia 0 solicitações recebidas, então a primeira a chegar
# será também o primeiro teste ao vivo deste de-para.
# ===========================================================================

# De `nosso_nome` do campo do formulário para a coluna da ficha.
#
# ⚠️ O FORMULÁRIO PERGUNTA O ENDEREÇO COMO UMA LINHA (`endereco`), mais
# cidade / estado / CEP. A ficha tem sete colunas. A linha inteira vai para
# `logradouro` e quem confere distribui — partir "Rua X, 123 - fundos" por
# vírgula acertaria às vezes, e errado em cadastro é pior que vazio.
#
# ⚠️ `estado` do formulário é TEXTO LIVRE ("São Paulo", "SP", "sp"), e `uf` é
# `varchar(2)`. Ver `_uf_de`.
DE_PARA = {
    "nome-da-empresa-fantasia": "nome_fantasia",
    "razao-social": "razao_social",
    "cnpj": "cnpj",
    "endereco": "logradouro",
    "cidade": "cidade",
    "cep": "cep",
    "telefone-fixo": "telefone_fixo",
    "e-mail-geral-da-empresa": "email_geral",
    "nome-do-responsavel-pela-empresa": "responsavel_nome",
    "sobrenome-do-responsavel-pela-empresa": "responsavel_sobrenome",
    "cpf": "cpf",
    "telefone-celular-whatsapp": "responsavel_celular",
    "e-mail": "responsavel_email",
    # 🔵 04/11: o campo que era "Banco" passou a ser **"Dados para pagamento"**
    # no formulário, e `agencia`/`conta` saíram de lá. O `nosso_nome` continua
    # `banco-2` porque ele é derivado do rótulo ORIGINAL do Bitrix e é a chave
    # estável — renomeá-lo quebraria o de-para sem necessidade. O rótulo que a
    # pessoa lê é o novo; este nome é interno.
    "banco-2": "pagamento_dados",
    "area-de-cobertura-ex-ate-50km": "area_cobertura",
    "caso-tenha-alguma-consideracao-ou-observ": "observacao",
}

# As três listas de Sim/Não, pelos IDs que o formulário grava.
SIM = {"5850", "5854", "5858"}
NAO = {"5852", "5856", "5860"}
DE_PARA_LISTA = {
    "possui-ponto-fixo-para-receber-servicos": "ponto_fixo",
    "possivel-deslocamento-ate-o-cliente": "vai_ao_cliente",
    "e-cobrado-a-parte-o-deslocamento": "cobra_deslocamento",
}

UFS = ("AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA", "MT", "MS",
       "MG", "PA", "PB", "PR", "PE", "PI", "RJ", "RN", "RS", "RO", "RR", "SC",
       "SP", "SE", "TO")

# As seis perguntas de preço do formulário, que NÃO são os dez serviços da
# ficha. Ficam nomeadas para a tela poder mostrar "o que ele respondeu" ao lado
# da tabela de preço — sem virar preço sozinho (decisão dele: os dez mandam).
PRECOS_DO_FORMULARIO = {
    "instalacao-simples-positivo-negativo-e-p": "Instalação simples",
    "instalacao-com-bloqueio": "Instalação com bloqueio",
    "manutencao-correcao-do-equipamento-ou-da": "Manutenção / correção",
    "substituicao-de-equipamento-troca-de-equ": "Substituição no mesmo veículo",
    "substituicao-de-um-equipamento-de-um-vei": "Substituição entre veículos",
    "remocao-de-um-equipamento": "Remoção",
    "qual-o-valor-cobrado-pelo-deslocamento": "Deslocamento",
}


def _uf_de(valor) -> str | None:
    """A sigla, quando o que a pessoa escreveu é reconhecível como sigla.

    🚨 `uf` É `varchar(2)` E O FORMULÁRIO PERGUNTA "Estado" EM TEXTO LIVRE.
    Truncar "São Paulo" em "Sã" gravaria lixo com cara de dado; devolver `None`
    deixa o campo vazio na tela, para quem confere escolher. Vazio é honesto.
    """
    limpo = (valor or "").strip().upper()
    return limpo if limpo in UFS else None


def _valor(valores: dict, nome_de_origem: str):
    """O valor de um campo da solicitação.

    ⚠️ `valores` é chaveado pelo NOME DE ORIGEM (o do Bitrix), que é o estável
    — `nosso_nome` pode ser renomeado. E campo múltiplo guarda lista: a ficha
    tem um campo só, então fica o primeiro, e os demais continuam visíveis na
    solicitação para quem conferir.
    """
    bruto = valores.get(nome_de_origem)
    if isinstance(bruto, list):
        bruto = bruto[0] if bruto else None
    return bruto


def _por_nosso_nome(formulario_id: int) -> dict:
    return {c["nosso_nome"]: c["nome"] for c in banco.varios(
        "SELECT nome, nosso_nome FROM formulario_campo WHERE formulario_id = %s",
        (formulario_id,))}


def candidatos() -> dict:
    """As solicitações de credenciamento que ainda não têm ficha.

    ⚠️ Lista vazia e formulário inexistente são respostas diferentes: se o
    código `CREDENCIAMENTO` sumir do banco, a tela precisa dizer isso em vez de
    mostrar "nenhum candidato" e parecer em dia.
    """
    formulario = banco.um(
        "SELECT id, codigo, titulo, slug, ativo FROM formulario WHERE codigo = %s",
        (CODIGO_DO_FORMULARIO,))
    if not formulario:
        return {"formulario": None, "itens": [],
                "motivo": f"O formulário {CODIGO_DO_FORMULARIO} não está "
                          "carregado neste banco."}

    itens = banco.varios(
        """SELECT s.id, s.criada_em, s.estado, s.valores, s.contato_id
             FROM formulario_solicitacao s
            WHERE s.formulario_id = %s
              AND NOT EXISTS (SELECT 1 FROM tecnico_ficha f
                               WHERE f.solicitacao_id = s.id)
            ORDER BY s.criada_em DESC
            LIMIT 100""", (formulario["id"],))

    de_para = _por_nosso_nome(formulario["id"])
    for item in itens:
        valores = item.get("valores") or {}
        item["resumo"] = {
            rotulo: _valor(valores, de_para.get(nosso, nosso))
            for nosso, rotulo in (
                ("nome-da-empresa-fantasia", "empresa"),
                ("cnpj", "cnpj"),
                ("cidade", "cidade"),
                ("telefone-celular-whatsapp", "celular"),
            )
        }
    return {"formulario": formulario, "itens": itens}


def sugestao_da_solicitacao(solicitacao_id: int) -> dict:
    """O que aquela solicitação preenche na ficha. NÃO GRAVA NADA.

    Devolve também `nao_mapeado` — o que a pessoa respondeu e a ficha não tem
    onde guardar. 🚨 Sem essa lista, as seis perguntas de preço do formulário
    desapareceriam da tela, e quem credencia digitaria os dez valores no
    escuro, tendo a resposta dele a um clique.
    """
    linha = banco.um(
        """SELECT s.id, s.formulario_id, s.criada_em, s.valores, s.contato_id,
                  f.codigo, f.titulo
             FROM formulario_solicitacao s JOIN formulario f ON f.id = s.formulario_id
            WHERE s.id = %s""", (solicitacao_id,))
    if not linha:
        raise DadoInvalido("Solicitação não encontrada.")
    if linha["codigo"] != CODIGO_DO_FORMULARIO:
        raise DadoInvalido(
            f"A solicitação {solicitacao_id} é do formulário {linha['codigo']}, "
            f"não do credenciamento.")

    valores = linha.get("valores") or {}
    de_para = _por_nosso_nome(linha["formulario_id"])

    sugestao: dict = {}
    for nosso, coluna in DE_PARA.items():
        bruto = _valor(valores, de_para.get(nosso, nosso))
        if bruto in (None, ""):
            continue
        texto = str(bruto).strip()
        if coluna in CAMPOS_DOCUMENTO:
            texto = "".join(c for c in texto if c.isdigit())[:CAMPOS_DOCUMENTO[coluna]]
        elif coluna == "cep":
            texto = "".join(c for c in texto if c.isdigit())[:8]
        elif coluna in CAMPOS_TEXTO:
            texto = texto[:CAMPOS_TEXTO[coluna]]
        sugestao[coluna] = texto or None

    sugestao["uf"] = _uf_de(_valor(valores, de_para.get("estado", "estado")))

    for nosso, coluna in DE_PARA_LISTA.items():
        bruto = _valor(valores, de_para.get(nosso, nosso))
        marca = str(bruto).strip() if bruto is not None else ""
        sugestao[coluna] = True if marca in SIM else (False if marca in NAO else None)

    # 🔵 04/11: o mesmo campo de lista que perguntava "titular é física ou
    # jurídica?" passou a perguntar a FORMA DE PAGAMENTO, com os nossos três
    # valores. 🚨 E É POR ISSO QUE A SUGESTÃO É DIRETA, sem tradução de id: o
    # formulário grava `ted`/`pix`/`boleto`, que é exatamente o que a coluna
    # aceita. Era aqui que morava um `{"5846": "F", "5848": "J"}` — tradução de
    # id do Bitrix, que deixou de existir junto com a pergunta antiga.
    forma = str(_valor(valores, de_para.get(
        "titular-da-conta-e-pessoa-fisica-ou-juri",
        "titular-da-conta-e-pessoa-fisica-ou-juri")) or "").strip().lower()
    sugestao["pagamento_forma"] = forma if forma in FORMAS_DE_PAGAMENTO else None

    respondeu = {
        rotulo: _valor(valores, de_para.get(nosso, nosso))
        for nosso, rotulo in PRECOS_DO_FORMULARIO.items()
        if _valor(valores, de_para.get(nosso, nosso)) not in (None, "")
    }

    return {
        "solicitacao_id": linha["id"],
        "criada_em": linha["criada_em"],
        "contato_id": linha["contato_id"],
        "sugestao": sugestao,
        # 🚨 O que a ficha não guarda, à vista. Os valores das seis perguntas
        # de preço do formulário caem aqui de propósito: os dez serviços da
        # ficha são outros, e traduzir um no outro é decisão de quem credencia.
        "precos_respondidos": respondeu,
        "avisos": _avisos_da_sugestao(valores, de_para, sugestao),
    }


def _avisos_da_sugestao(valores: dict, de_para: dict, sugestao: dict) -> list[str]:
    avisos = []
    bruto_uf = _valor(valores, de_para.get("estado", "estado"))
    if bruto_uf and not sugestao.get("uf"):
        avisos.append(
            f"O estado respondido foi {str(bruto_uf).strip()!r}, que não é uma "
            "sigla de duas letras — escolha a UF à mão.")
    if sugestao.get("logradouro"):
        avisos.append(
            "O endereço veio como uma linha só; separe número, bairro e "
            "complemento antes de credenciar, porque é esta origem que a "
            "calculadora de KM usa.")
    return avisos


# ===========================================================================
# O QUE O ORÇAMENTO LÊ
# ===========================================================================

def precos_para_orcamento(contato_id: int) -> list[dict]:
    """Os serviços que ESTE técnico oferece, prontos para a linha do orçamento.

    🔵 04/11, e a premissa é dele: *"o orçamento não vai ao cliente, somente ao
    técnico."* Se o papel é o acerto do que será pago a ele, o custo cadastrado
    pode preencher a linha direto — não há margem a proteger.

    🚨 SÓ O QUE TEM PREÇO. Linha ausente ou `custo_centavos` nulo significa *"não
    oferece"*, e oferecer no `<select>` um serviço que ele não faz é convidar ao
    erro. **Zero entra**, e é decisão dele: na ficha, zero é cortesia e é um fato
    diferente de ausente.

    ⚠️ O FORMATO É O DO CATÁLOGO DO ORÇAMENTO, não o da ficha: `servico`,
    `unidade` e `preco_unit_centavos`. É o que o modal já sabe consumir, e
    traduzir de um lado só evita que o `orcamento.py` aprenda o esquema da ficha.

    ⚠️ **SEM `harmonit_id`**, de propósito: estes dez não têm id de produto no
    Harmonit, e devolver o campo vazio sugeriria que alguém o lê. As duas linhas
    fixas do catálogo continuam com os seus, que são procedência de 21/10.
    """
    return banco.varios(
        """SELECT s.nome AS servico, s.unidade,
                  p.custo_centavos AS preco_unit_centavos
             FROM tecnico_preco p
             JOIN servico_tecnico s ON s.id = p.servico_id
            WHERE p.contato_id = %s AND p.custo_centavos IS NOT NULL
              -- ⚠️ Serviço desativado no catálogo não é oferecido de novo, mas o
              -- preço dele continua gravado e explicando os orçamentos antigos.
              AND s.ativo
            ORDER BY s.ordem, s.nome""",
        (int(contato_id),))


# ===========================================================================
# O QUE O KM LÊ
# ===========================================================================

def origem_do_tecnico(contato_id: int) -> dict | None:
    """O endereço FIXO da ficha, que é a origem do cálculo de KM.

    🔵 Decisão dele em 04/11: *"o cadastro alimenta a memória, pode tirá-la.
    Caso mudem na hora só servirá para aquele orçamento. Os demais ja vem com o
    do cad."* Então esta é a única fonte, e o modal não grava mais nada de
    volta — o que foi usado naquele dia fica em `agendamento.origem_endereco`,
    que já existe desde a 077.

    ⚠️ Ficha sem rua devolve `None`, não um dicionário de vazios: a tela
    precisa distinguir "não tem endereço cadastrado" de "tem endereço em
    branco", e um dict com sete `None` desenharia a segunda frase.
    """
    linha = banco.um(
        f"SELECT {', '.join(CAMPOS_DE_ENDERECO)}, atualizado_em, estado "
        "  FROM tecnico_ficha WHERE contato_id = %s", (int(contato_id),))
    if not linha or not (linha["logradouro"] or linha["cep"]):
        return None
    return dict(linha)
