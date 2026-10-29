"""Os formulários próprios — a definição é DADO, e a validação é NOSSA.

🔵 Decisão dele, 22/10: *"nenhuma possibilidade irá usar o bitrix, esse projeto
é movizap"*. Os 15 formulários de `solicite.movisat.com.br` passam a viver
aqui, e o link público sai em `forms.movisat.com.br`.

🚨 O BITRIX NÃO VALIDA OBRIGATÓRIO NO SERVIDOR -- medido em 22/10 enviando
`values=[]` vazio no formulário de Contato: foi aceito e criou o registro
`15620`. Toda a validação dos 15 era no navegador, e navegador é do cliente.
**Aqui a autoridade é este módulo.** Quem escreve a tela não escreve a regra.

🚨 CAMPO ESCONDIDO POR REGRA NÃO VIRA CAMPO VAZIO: ele SOME do registro. É o
comportamento do Bitrix (medido: campo oculto não é enviado nem em branco) e é
o certo -- "a pessoa não respondeu" e "a pergunta não foi feita" são coisas
diferentes, e guardar as duas como `""` perderia a diferença para sempre.

🚨 A VISIBILIDADE SE CALCULA AQUI E NO NAVEGADOR, DA MESMA ESTRUTURA. O espelho
é `frontend/src/util/regras_formulario.js`, e as duas suítes leem o MESMO
arquivo de casos (`tests/casos_regras_formulario.json`). Sem isso seriam duas
verdades -- e 22/10 já mostrou o preço de um `WHERE` copiado em dois lugares,
que divergiu no mesmo dia.

⚠️ O QUE ESTE MÓDULO NÃO FAZ: não fala com o Bitrix (nada neste projeto
manda dado para lá) e não fala com o Harmonit (a OS é da Etapa 2/3).
"""
import hashlib
import hmac
import json
import logging
import pathlib
import re
import secrets
import time
import unicodedata
import uuid

from . import banco, fpsl_ponte, ratelimit, telefone
from .operacao import DadoInvalido

log = logging.getLogger("movizap.formularios")

# ----------------------------------------------------------------------------
# Vocabulário
# ----------------------------------------------------------------------------
# Os 15 tipos medidos nos 239 campos dos 15 formulários. O CHECK da migração
# 074 tem a mesma lista: tipo desconhecido para na CARGA, não na tela do
# cliente -- onde viraria caixa de texto e ninguém notaria.
TIPOS = ("string", "text", "list", "double", "date", "file", "product",
         "phone", "email", "name", "last-name", "second-name",
         "company-name", "page", "layout")

# 🚨 ESTES NÃO SÃO PERGUNTA: `page` é quebra de página e `layout` é um traço
# decorativo. Não têm valor, não são obrigatórios e não entram no registro.
TIPOS_DECORATIVOS = ("page", "layout")

# `product` puxava catálogo do Bitrix. Sem equivalente nosso, nesta etapa é
# texto -- e está escrito aqui para que ninguém "descubra" isso na tela.
TIPOS_TEXTO_LONGO = ("text", "product")

ESTADOS = ("nova", "em_andamento", "concluida")

TETO_CURTO = 255
TETO_LONGO = 4000
# Teto de segurança por envio: 60 campos cobre o maior formulário (36 campos)
# com folga, e barra um POST inventado com mil chaves.
TETO_CAMPOS_NO_ENVIO = 60

# ----------------------------------------------------------------------------
# Anexos
# ----------------------------------------------------------------------------
# 🚨 FORA DO PROJETO, como o anexo de e-mail (`movizap/enviar.py`): dentro, o
# arquivo entraria no git e no `dist` -- e o `dist` é servido. E aqui o arquivo
# vem de QUALQUER UM na internet.
PASTA_ANEXOS = pathlib.Path("/home/claude/movizap_formularios_anexos")
TETO_ARQUIVO = 10 * 1024 * 1024
TETO_ENVIO = 25 * 1024 * 1024

# ⚠️ Lista BRANCA, por extensão. O `content-type` quem manda é o cliente, então
# ele não decide nada aqui -- é guardado só para o painel saber como abrir.
EXTENSOES_PERMITIDAS = (
    ".pdf", ".jpg", ".jpeg", ".png", ".webp", ".heic",
    ".doc", ".docx", ".xls", ".xlsx", ".csv", ".txt",
)


class FormularioNaoExiste(LookupError):
    """Slug que não existe, ou formulário desligado. Vira 404.

    🚨 OS DOIS CASOS DÃO A MESMA RESPOSTA, de propósito: um 404 que distingue
    "não existe" de "existe e está desligado" conta ao mundo quais formulários
    a casa tem.
    """


# ----------------------------------------------------------------------------
# Nome legível
# ----------------------------------------------------------------------------
def _sem_acento(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", texto)
                   if unicodedata.category(c) != "Mn")


def slugificar(texto: str, teto: int = 40) -> str:
    bruto = _sem_acento(texto or "").lower()
    limpo = re.sub(r"[^a-z0-9]+", "-", bruto).strip("-")
    return limpo[:teto].strip("-")


def nome_legivel(rotulo: str, nome_origem: str, usados: set) -> str:
    """O `nosso_nome` de um campo, derivado do rótulo.

    🚨 OS NOMES DE ORIGEM SÃO ILEGÍVEIS DE PROPÓSITO:
    `DEAL_UF_CRM_DEAL_1649449139431` é campo personalizado do Bitrix, e o
    número é o timestamp em que alguém o criou. O rótulo, esse sim, já é
    humano ('Primeiro Nome', 'Assunto'), então é dele que o nome sai.

    ⚠️ ISTO É RASCUNHO, E ELE REVISA. Dar nome humano aos 239 é o maior
    trabalho manual da etapa; o que este módulo garante é que nasça algo
    legível e ÚNICO -- nome repetido tornaria a leitura da solicitação ambígua.
    """
    base = slugificar(rotulo) or slugificar(nome_origem) or "campo"
    nome = base
    n = 2
    while nome in usados:
        nome = f"{base}-{n}"
        n += 1
    usados.add(nome)
    return nome


# ----------------------------------------------------------------------------
# Leitura da definição
# ----------------------------------------------------------------------------
def definicao(slug: str, so_ativo: bool = True) -> dict:
    """O formulário inteiro: cabeçalho, campos na ordem e regras.

    `so_ativo` é o que separa o público do painel: a internet só alcança
    formulário ligado, o painel vê todos.
    """
    linha = banco.um(
        """SELECT id, codigo, slug, titulo, setor, botao, descricao, ativo,
                  gera_os, problema_id, tipo_os_id, prioridade_id,
                  formato, etapas
             FROM formulario WHERE slug = %s""", (slug,))
    if not linha or (so_ativo and not linha["ativo"]):
        raise FormularioNaoExiste(slug)

    linha["campos"] = banco.varios(
        """SELECT nome, nosso_nome, rotulo, tipo, obrigatorio, multiplo,
                  visivel, ordem, opcoes, ajuda, validacao,
                  fantasma, linhas, fonte
             FROM formulario_campo WHERE formulario_id = %s
            ORDER BY ordem, id""", (linha["id"],))
    linha["regras"] = banco.varios(
        """SELECT ordem, logica, lista FROM formulario_regra
            WHERE formulario_id = %s ORDER BY ordem, id""", (linha["id"],))
    return linha


def lista_para_o_painel() -> list[dict]:
    """O que a FRM_1.1 mostra no alto: cada formulário e quanto chegou nele."""
    return banco.varios(
        """SELECT f.id, f.codigo, f.slug, f.titulo, f.setor, f.ativo, f.ordem,
                  count(s.id)                                  AS solicitacoes,
                  count(s.id) FILTER (WHERE s.estado = 'nova') AS novas,
                  max(s.criada_em)                             AS ultima_em
             FROM formulario f
             LEFT JOIN formulario_solicitacao s ON s.formulario_id = f.id
            GROUP BY f.id
            ORDER BY f.ordem, lower(f.titulo)""")


# ----------------------------------------------------------------------------
# As regras condicionais
# ----------------------------------------------------------------------------
# A estrutura é a do Bitrix, como veio:
#
#   {"condition": {"target": <campo>, "event": "change",
#                  "value": "<id da opcao>", "operation": "=" | "any"},
#    "action":    {"target": <campo>, "type": "show" | "hide"}}
#
# 🚨 CADA ITEM É INDEPENDENTE -- condição própria, ação própria --, e isso foi
# MEDIDO, não suposto: nos 62 itens dos 15 formulários, o único grupo com
# `logic: "and"` (ficha cadastral, grupo 2446) tem as OITO condições
# idênticas, então avaliar item por item dá exatamente o mesmo resultado. O
# `logica` fica guardado na tabela porque é dado de origem, não porque mude a
# conta.
#
# 🚨 E O `visible` DO LOADER NÃO DIZ QUEM NASCE ESCONDIDO: nos 15, NENHUM
# campo vem com `visible: false`, e ainda assim há 60 ações `show`. No Bitrix,
# ser alvo de `show` É o que esconde o campo no começo. Quem traduz isso é a
# carga (`gravar_definicao`), que grava `visivel = false` nesses alvos. Confiar
# no `visible` do loader faria todo campo condicional aparecer sempre -- e
# ninguém notaria, porque a tela ficaria "só um pouco mais comprida".
def _condicao_bate(condicao: dict, valores: dict) -> bool:
    alvo = condicao.get("target")
    valor = valores.get(alvo)
    if isinstance(valor, list):
        atuais = [str(v) for v in valor if str(v).strip() != ""]
    else:
        atuais = [] if valor is None or str(valor).strip() == "" else [str(valor)]

    operacao = condicao.get("operation")
    if operacao == "any":
        return bool(atuais)
    if operacao == "=":
        return str(condicao.get("value")) in atuais

    # ⚠️ Operação que não conhecemos NÃO mostra nem esconde: o campo fica como
    # nasceu, e o aviso vai para o log. Levantar aqui derrubaria o formulário
    # público por causa de uma regra que o Bitrix mudou.
    log.warning("regra com operacao desconhecida: %r", operacao)
    return False


def visiveis(d: dict, valores: dict) -> set:
    """Quais campos estão de pé, dados os valores já respondidos.

    🚨 CONDIÇÃO EM CAMPO ESCONDIDO NÃO VALE. As regras se encadeiam -- no
    credenciamento técnico, A mostra B e B mostra C --, então o valor de um
    campo que a pessoa nunca viu não pode mandar em nada. Por isso a conta
    repete até parar de mudar, em vez de passar uma vez na lista.
    """
    todos = {c["nome"] for c in d["campos"]}
    base = {c["nome"] for c in d["campos"] if c["visivel"]}
    vis = set(base)

    for _ in range(len(d["regras"]) + 2):
        novo = set(base)
        for regra in d["regras"]:
            for item in (regra["lista"] or []):
                acao = item.get("action") or {}
                condicao = item.get("condition") or {}
                alvo = acao.get("target")
                if alvo not in todos:
                    continue
                if condicao.get("target") not in vis:
                    continue
                if not _condicao_bate(condicao, valores):
                    continue
                if acao.get("type") == "show":
                    novo.add(alvo)
                elif acao.get("type") == "hide":
                    novo.discard(alvo)
        if novo == vis:
            break
        vis = novo
    return vis


# ----------------------------------------------------------------------------
# Validação
# ----------------------------------------------------------------------------
# 🚨 O CNPJ ALFANUMÉRICO (2026) OBRIGOU A `validacao` A VALER MAIS QUE O
# `tipo`. O campo "CNPJ" é `double` no Bitrix, e a regra do `double` é
# `float()` -- que recusa `WQ0P6GLD000108`, um CNPJ **válido** da nossa própria
# base (Pastelaria Velasco, DV conferido). Quando o campo diz qual documento
# é, é o documento que manda, não o tipo herdado.
#
# ⚠️ E ACEITA TODOS OS FORMATOS DE COLAGEM, por decisão dele: só dígitos, ou
# com ponto, barra e traço. O que se guarda é sempre a forma canônica -- sem
# pontuação, em maiúscula --, para não existirem duas escritas do mesmo
# documento na mesma coluna.
def _canonico(texto: str, regra: str) -> str:
    if regra == "cnpj":
        return re.sub(r"[^A-Za-z0-9]", "", texto).upper()
    return re.sub(r"\D", "", texto)


# Quantos caracteres cada documento tem. ⚠️ `placa` NÃO entra: o campo do
# Suporte é *"Veículo e Placa"*, e a pessoa escreve `SAVEIRO ABC1234` --
# cobrar 7 caracteres ali recusaria a resposta certa. Para a placa a regra é
# só mensagem na tela.
_TAMANHO_DO_DOCUMENTO = {"cnpj": 14, "cpf": 11, "cep": 8}


def _um_valor(campo: dict, bruto) -> str:
    tipo = campo["tipo"]
    texto = str(bruto).strip()

    regra = campo.get("validacao")
    if regra in _TAMANHO_DO_DOCUMENTO:
        limpo = _canonico(texto, regra)
        if len(limpo) != _TAMANHO_DO_DOCUMENTO[regra]:
            raise DadoInvalido(
                f"{campo['rotulo']}: informe os "
                f"{_TAMANHO_DO_DOCUMENTO[regra]} caracteres.")
        # ⚠️ O dígito verificador NÃO é conferido aqui, e é escolha: a frase
        # que a pessoa lê é da tela (`validacao_campo.js`), e o servidor
        # garante o FORMATO. Passar a recusar DV aqui é mudança de régua, e
        # régua é decisão dele.
        return limpo

    if tipo == "list":
        ids = {str(o.get("value")) for o in (campo["opcoes"] or [])}
        if texto not in ids:
            raise DadoInvalido(f"{campo['rotulo']}: escolha uma das opções.")
        return texto

    if tipo == "double":
        # ⚠️ Vírgula é como o Brasil escreve número, e o campo "CNPJ" do Bitrix
        # é `double` -- então aqui não se exige ponto nem se recusa máscara: o
        # que se guarda é o que dá para ler como número.
        limpo = texto.replace(".", "").replace(",", ".")
        try:
            float(limpo)
        except ValueError:
            raise DadoInvalido(f"{campo['rotulo']}: informe um número.")
        return texto[:TETO_CURTO]

    if tipo == "date":
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", texto):
            raise DadoInvalido(f"{campo['rotulo']}: informe a data.")
        return texto

    if tipo == "email":
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", texto):
            raise DadoInvalido(f"{campo['rotulo']}: informe um e-mail válido.")
        return texto[:TETO_CURTO]

    if tipo == "phone":
        # 🚨 O TELEFONE SE NORMALIZA PELO MÓDULO DA CASA, não por regex nova:
        # `telefone.normalizar` é o mesmo que o atendimento usa, com o 9 do
        # celular e o DDI. ⚠️ E não recusa o que ele não entende: número de
        # fora do padrão brasileiro existe, e perder o contato por isso seria
        # pior que guardar o texto como veio.
        return (telefone.normalizar(texto) or texto)[:TETO_CURTO]

    if tipo in TIPOS_TEXTO_LONGO:
        if len(texto) > TETO_LONGO:
            raise DadoInvalido(f"{campo['rotulo']}: passa de {TETO_LONGO} caracteres.")
        return texto

    if len(texto) > TETO_CURTO:
        raise DadoInvalido(f"{campo['rotulo']}: passa de {TETO_CURTO} caracteres.")
    return texto


def validar(d: dict, valores: dict, arquivos: dict | None = None) -> dict:
    """Devolve só o que vale: campo visível, com valor limpo.

    🚨 Levanta `DadoInvalido` -- que a rota vira 400 com a frase que a pessoa
    lê. É aqui que o obrigatório é cobrado, e é por isso que o nosso não
    repete o buraco do Bitrix.
    """
    valores = valores or {}
    arquivos = arquivos or {}
    if len(valores) > TETO_CAMPOS_NO_ENVIO:
        raise DadoInvalido("Envio com campos demais.")

    de_pe = visiveis(d, valores)
    limpo = {}

    for campo in d["campos"]:
        nome = campo["nome"]
        if campo["tipo"] in TIPOS_DECORATIVOS:
            continue

        if nome not in de_pe:
            # 🚨 Escondido SOME, não vira vazio. Mesmo que o cliente mande.
            continue

        if campo["tipo"] == "file":
            if campo["obrigatorio"] and not arquivos.get(nome):
                raise DadoInvalido(f"{campo['rotulo']}: anexe o arquivo.")
            continue

        bruto = valores.get(nome)
        if isinstance(bruto, list):
            partes = [_um_valor(campo, v) for v in bruto if str(v).strip() != ""]
            if partes:
                limpo[nome] = partes if campo["multiplo"] else partes[0]
        elif bruto is not None and str(bruto).strip() != "":
            limpo[nome] = _um_valor(campo, bruto)

        if campo["obrigatorio"] and nome not in limpo:
            raise DadoInvalido(f"{campo['rotulo']}: preencha este campo.")

    return limpo


# ----------------------------------------------------------------------------
# Escrita
# ----------------------------------------------------------------------------
def guardar_arquivo(nome: str, dados: bytes) -> dict:
    """Guarda um anexo da solicitação e devolve o que vai para a tabela.

    ⚠️ O NOME VEM DA INTERNET E NUNCA VIRA CAMINHO -- é o mesmo cuidado do
    `enviar.guardar_anexo`: cada arquivo ganha uma pasta com id próprio, e só
    o nome-base é preservado, para o painel mostrar o arquivo com o nome que a
    pessoa enviou. Um anexo chamado `../../.env` é um nome esquisito, e nada
    além disso.
    """
    if len(dados) > TETO_ARQUIVO:
        raise DadoInvalido(f"Arquivo maior que {TETO_ARQUIVO // (1024 * 1024)} MB.")

    seguro = pathlib.Path(str(nome).replace("\\", "/")).name or "arquivo"
    if not seguro.lower().endswith(EXTENSOES_PERMITIDAS):
        raise DadoInvalido(
            "Tipo de arquivo não aceito. Vale: "
            + ", ".join(e.lstrip(".") for e in EXTENSOES_PERMITIDAS) + ".")

    ident = uuid.uuid4().hex
    pasta = PASTA_ANEXOS / ident
    pasta.mkdir(parents=True, exist_ok=True)
    caminho = pasta / seguro
    caminho.write_bytes(dados)
    return {"nome_original": seguro, "caminho": str(caminho), "bytes": len(dados)}


def registrar(d: dict, valores: dict, arquivos: list | None = None,
              ip: str | None = None, vinculo: dict | None = None,
              placas_conferidas: bool | None = None) -> dict:
    """Grava a solicitação. `valores` já passou por `validar`.

    `arquivos` é a lista que `guardar_arquivo` devolveu, cada item com o
    `campo` a que pertence. `vinculo` é da Etapa 2 (conversa/contato/cliente) e
    na Etapa 1 é nulo -- formulário genérico é anônimo, e é o desenho.
    """
    vinculo = vinculo or {}
    linha = banco.um(
        """INSERT INTO formulario_solicitacao
               (formulario_id, ip, valores, conversa_id, contato_id, cliente_id,
                placas_conferidas)
           VALUES (%s, %s, %s, %s, %s, %s, %s)
        RETURNING id, criada_em""",
        (d["id"], ip, json.dumps(valores, ensure_ascii=False),
         vinculo.get("conversa_id"), vinculo.get("contato_id"),
         vinculo.get("cliente_id"), placas_conferidas))

    for arq in (arquivos or []):
        banco.executar(
            """INSERT INTO formulario_arquivo
                   (solicitacao_id, campo, nome_original, caminho, bytes, mime)
               VALUES (%s, %s, %s, %s, %s, %s)""",
            (linha["id"], arq["campo"], arq["nome_original"], arq["caminho"],
             arq.get("bytes") or 0, arq.get("mime")))

    log.info("solicitacao %s no formulario %s (%s campos, %s anexos)",
             linha["id"], d["slug"], len(valores), len(arquivos or []))
    return {"id": linha["id"], "criada_em": linha["criada_em"],
            "mensagem": "Recebemos sua solicitação. Em breve entraremos em contato."}


def gravar_definicao(bruto: dict, codigo: str, slug: str, setor: str,
                     titulo: str | None = None, painel: str | None = None,
                     ordem: int = 100, formato: str = "classico",
                     etapas: list | None = None,
                     validacoes: dict | None = None,
                     ajustes: dict | None = None) -> dict:
    """Escreve (ou reescreve) um formulário a partir da definição do Bitrix.

    🚨 IDEMPOTENTE PELO `bitrix_id`: rodar de novo não duplica nem apaga
    solicitação -- reescreve campos e regras, que são definição. A solicitação
    é retrato e fica onde está.

    🚨 ALVO DE `show` NASCE ESCONDIDO -- é aqui que a tradução acontece, e o
    porquê está em `visiveis()`.

    🚨 `formato`, `etapas` e `validacoes` SÃO REESCRITOS A CADA CARGA, como o
    `painel` e ao contrário de `ativo`: são decisão dele e vivem no
    `scripts/carregar_formularios.py`, então mudar o agrupamento das etapas ou
    ligar o formato novo no 2º formulário não exige migração nem deploy.

    ⚠️ `validacoes` é `{nosso_nome: regra}`, e as etapas também citam campo
    pelo `nosso_nome`. Casar pelo nome do Bitrix
    (`DEAL_UF_CRM_1647530180887`) seria ilegível para quem revisa -- e quem
    revisa é ele.
    """
    dados = bruto["data"]
    campos = dados["fields"]
    regras = dados.get("dependencies") or []

    alvos_de_show = {
        item["action"]["target"]
        for regra in regras for item in regra["list"]
        if (item.get("action") or {}).get("type") == "show"
    }

    for campo in campos:
        if campo["type"] not in TIPOS:
            raise DadoInvalido(
                f"Tipo de campo desconhecido no formulário {codigo}: "
                f"{campo['type']!r} em {campo['name']!r}.")

    # ----------------------------------------------------------------------
    # OS AJUSTES NOSSOS, em cima da definição do Bitrix
    # ----------------------------------------------------------------------
    # 🔵 Decisão dele, 29/10: *"vamos mudar as opções do 'Tipo de solicitação',
    # pois são do bitrix e não nos satisfazem mais"*. A definição continua
    # vindo de lá -- o que muda é que ela deixa de ser a palavra final.
    #
    # 🚨 ISTO NÃO EDITA O `mapa_bruto.json`. O bruto é **procedência**: diz de
    # onde a definição foi lida em 22/10. Reescrevê-lo apagaria a prova de como
    # o formulário era no Bitrix, e é essa prova que permite responder *"o que
    # foi perdido em relação ao original?"* -- pergunta que ele já fez.
    ajustes = ajustes or {}
    fora = set(ajustes.get("fora") or [])
    por_campo = ajustes.get("campos") or {}
    nao_casados = set(fora) | set(por_campo)
    sobraram = []
    for campo in campos:
        nosso = nome_legivel(campo.get("label") or "", campo["name"], set())
        nao_casados.discard(nosso)
        if nosso in fora:
            # ⚠️ Campo TIRADO não é campo escondido: ele não existe, não vem na
            # definição e não entra no registro. Quem some por regra é outra
            # coisa, e continua sendo.
            continue
        mudar = por_campo.get(nosso) or {}
        # 🚨 O RÓTULO NOVO VAI NUM CAMPO À PARTE, e isto não é estilo: o
        # `nosso_nome` é DERIVADO do rótulo (`nome_legivel`). Trocar
        # `campo["label"]` aqui renomearia o campo -- "Primeiro Nome" viraria
        # `nome-completo` --, e aí as tabelas `ETAPAS` e `VALIDACOES`, que
        # citam `primeiro-nome`, apontariam para um campo que não existe mais.
        # O nome continua saindo do rótulo ORIGINAL; o rótulo novo é só o que
        # a pessoa lê.
        campo["_rotulo"] = mudar.get("rotulo")
        if "opcoes" in mudar:
            campo["items"] = [{"value": o["value"], "label": o["label"]}
                              for o in mudar["opcoes"]]
        if "obrigatorio" in mudar:
            campo["required"] = mudar["obrigatorio"]
        campo["_fantasma"] = mudar.get("fantasma")
        campo["_linhas"] = mudar.get("linhas")
        campo["_fonte"] = mudar.get("fonte")
        sobraram.append(campo)

    # 🚨 AJUSTE QUE NÃO ACHOU CAMPO PARA NA CARGA. Um `nosso_nome` escrito
    # errado aqui seria ajuste que não acontece -- e o formulário ficaria com a
    # cara antiga sem ninguém saber por quê.
    if nao_casados:
        raise DadoInvalido(
            f"{codigo}: ajuste citando campo que nao existe: "
            + ", ".join(sorted(nao_casados)))

    # ⚠️ As REGRAS continuam as do Bitrix, e podem apontar para campo tirado.
    # Regra com alvo inexistente é ignorada por `visiveis()` (`if alvo not in
    # todos`), então não há o que limpar -- e deixá-las registradas preserva a
    # procedência.
    campos = sobraram

    linha = banco.um(
        """INSERT INTO formulario (codigo, slug, titulo, setor, botao,
                                   bitrix_id, bitrix_sec, painel, ordem,
                                   formato, etapas)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
           ON CONFLICT (codigo) DO UPDATE
              SET slug = EXCLUDED.slug, titulo = EXCLUDED.titulo,
                  setor = EXCLUDED.setor, botao = EXCLUDED.botao,
                  bitrix_id = EXCLUDED.bitrix_id,
                  bitrix_sec = EXCLUDED.bitrix_sec,
                  -- 🚨 O PAINEL E REESCRITO A CADA CARGA, ao contrario de
                  -- `ativo`: o mapa e decisao dele e vive no script, entao
                  -- mudar de painel nao exige migracao nem deploy. `ativo`
                  -- NAO entra nesta lista de proposito -- recarregar nao pode
                  -- publicar formulario nenhum.
                  painel = EXCLUDED.painel,
                  formato = EXCLUDED.formato, etapas = EXCLUDED.etapas,
                  ordem = EXCLUDED.ordem, atualizado_em = now()
        RETURNING id, ativo""",
        (codigo, slug,
         (titulo or dados.get("title") or "").strip() or slug,
         setor, (dados.get("buttonCaption") or "Enviar").strip()[:60],
         str(bruto.get("id")), bruto.get("sec"), painel, ordem,
         formato,
         json.dumps(etapas, ensure_ascii=False) if etapas else None))

    banco.executar("DELETE FROM formulario_campo WHERE formulario_id = %s",
                   (linha["id"],))
    banco.executar("DELETE FROM formulario_regra WHERE formulario_id = %s",
                   (linha["id"],))

    usados = set()
    validacoes = validacoes or {}
    sem_campo = set(validacoes)
    nossos_todos: list[str] = []
    nossas_perguntas: list[str] = []
    for i, campo in enumerate(campos):
        opcoes = [{"value": str(it.get("value")), "label": it.get("label") or ""}
                  for it in (campo.get("items") or [])]
        nosso = nome_legivel(campo.get("label") or "", campo["name"], usados)
        sem_campo.discard(nosso)
        nossos_todos.append(nosso)
        if campo["type"] not in TIPOS_DECORATIVOS:
            nossas_perguntas.append(nosso)
        banco.executar(
            """INSERT INTO formulario_campo
                   (formulario_id, nome, nosso_nome, rotulo, tipo, obrigatorio,
                    multiplo, visivel, ordem, opcoes, ajuda, validacao,
                    fantasma, linhas, fonte)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                       %s, %s, %s)""",
            (linha["id"], campo["name"][:80], nosso,
             # 🚨 O rotulo pode ter sido trocado pelos AJUSTES, mas o
             # `nosso_nome` sai do rotulo ORIGINAL -- ver o comentario em
             # `campo["_rotulo"]`, acima.
             (campo.get("_rotulo") or campo.get("label") or "").strip(),
             campo["type"],
             bool(campo.get("required")), bool(campo.get("multiple")),
             campo["name"] not in alvos_de_show, i,
             json.dumps(opcoes, ensure_ascii=False),
             (campo.get("hint") or "").strip() or None,
             validacoes.get(nosso),
             campo.get("_fantasma"), campo.get("_linhas"),
             campo.get("_fonte")))

    # 🚨 MÁSCARA SEM CAMPO PARA NA CARGA, nunca na tela do cliente. Um
    # `nosso_nome` escrito errado na tabela viraria campo sem máscara -- e
    # ninguém notaria, porque a tela ficaria só um pouco mais permissiva.
    if sem_campo:
        raise DadoInvalido(
            f"{codigo}: validacao citando campo que nao existe: "
            + ", ".join(sorted(sem_campo)))

    # 🚨 E A MESMA RÉGUA PARA AS ETAPAS, com os dois erros possíveis:
    #   · etapa que cita campo inexistente -> some da tela em silêncio;
    #   · pergunta que ficou fora de toda etapa -> o cliente NUNCA a vê, e o
    #     formulário segue "funcionando" com uma pergunta menos.
    # O segundo é o perigoso, e é por isso que a conferência é dos dois lados.
    if etapas:
        citados = [n for e in etapas for n in (e.get("campos") or [])]
        fantasmas = sorted(set(citados) - set(nossos_todos))
        de_fora = sorted(set(nossas_perguntas) - set(citados))
        if fantasmas or de_fora:
            raise DadoInvalido(
                f"{codigo}: etapas erradas -- "
                f"campos que nao existem: {fantasmas or 'nenhum'}; "
                f"perguntas fora de toda etapa: {de_fora or 'nenhuma'}")

    for i, regra in enumerate(regras):
        banco.executar(
            """INSERT INTO formulario_regra (formulario_id, ordem, logica, lista)
               VALUES (%s, %s, %s, %s)""",
            (linha["id"], i, regra.get("logic") or "or",
             json.dumps(regra["list"], ensure_ascii=False)))

    log.info("definicao do formulario %s gravada: %s campos, %s regras, "
             "%s campos escondidos por regra",
             codigo, len(campos), len(regras), len(alvos_de_show))
    return {"id": linha["id"], "ativo": linha["ativo"], "campos": len(campos),
            "regras": len(regras), "escondidos": len(alvos_de_show)}


# ----------------------------------------------------------------------------
# A tela interna (FRM_1.1)
# ----------------------------------------------------------------------------
def listar_solicitacoes(slug: str | None = None, estado: str | None = None,
                        limite: int = 50, antes_de: int | None = None) -> list[dict]:
    where = ["TRUE"]
    params: list = []
    if slug:
        where.append("f.slug = %s")
        params.append(slug)
    if estado:
        if estado not in ESTADOS:
            raise DadoInvalido("Estado desconhecido.")
        where.append("s.estado = %s")
        params.append(estado)
    if antes_de:
        where.append("s.id < %s")
        params.append(antes_de)
    params.append(min(max(int(limite), 1), 200))

    return banco.varios(
        f"""SELECT s.id, s.criada_em, s.estado, s.valores,
                   f.slug, f.titulo, f.setor,
                   a.nome AS lida_por_nome, s.lida_em,
                   (SELECT count(*) FROM formulario_arquivo x
                     WHERE x.solicitacao_id = s.id) AS anexos
              FROM formulario_solicitacao s
              JOIN formulario f ON f.id = s.formulario_id
              LEFT JOIN atendente a ON a.id = s.lida_por
             WHERE {' AND '.join(where)}
             ORDER BY s.id DESC
             LIMIT %s""", tuple(params))


def uma(solicitacao_id: int) -> dict | None:
    """Uma solicitação, com os valores já traduzidos para o nome legível.

    🚨 A TRADUÇÃO É NA LEITURA, NÃO NA GRAVAÇÃO: o registro guarda a chave de
    origem (que é estável), e o rótulo vem da definição de agora. Campo que
    saiu da definição continua aparecendo -- pela chave crua, porque some-lo
    seria a tela mentir sobre o que a pessoa respondeu.
    """
    linha = banco.um(
        """SELECT s.id, s.criada_em, s.estado, s.valores, s.ip,
                  s.conversa_id, s.contato_id, s.cliente_id,
                  s.os_id, s.numero_ordem, s.lida_em,
                  a.nome AS lida_por_nome,
                  f.id AS formulario_id, f.slug, f.titulo, f.setor
             FROM formulario_solicitacao s
             JOIN formulario f ON f.id = s.formulario_id
             LEFT JOIN atendente a ON a.id = s.lida_por
            WHERE s.id = %s""", (solicitacao_id,))
    if not linha:
        return None

    campos = banco.varios(
        """SELECT nome, nosso_nome, rotulo, tipo, ordem, opcoes
             FROM formulario_campo WHERE formulario_id = %s
            ORDER BY ordem, id""", (linha["formulario_id"],))
    por_nome = {c["nome"]: c for c in campos}

    respostas = []
    valores = linha["valores"] or {}
    for campo in campos:
        if campo["nome"] not in valores:
            continue
        respostas.append({**_rotular(campo, valores[campo["nome"]])})
    for nome, valor in valores.items():
        if nome not in por_nome:
            respostas.append({"nome": nome, "nosso_nome": nome,
                              "rotulo": nome, "tipo": "string",
                              "valor": valor, "fora_da_definicao": True})

    linha["respostas"] = respostas
    linha["anexos"] = banco.varios(
        """SELECT id, campo, nome_original, bytes, mime
             FROM formulario_arquivo WHERE solicitacao_id = %s ORDER BY id""",
        (solicitacao_id,))
    return linha


def _rotular(campo: dict, valor) -> dict:
    """O valor como gente lê: opção de lista vira o rótulo dela.

    ⚠️ Opção que saiu da lista mostra o ID cru, e não um rótulo inventado --
    é a mesma régua do grid do FPSL: *"estado desconhecido mostra o valor
    cru"*.
    """
    mostrado = valor
    if campo["tipo"] == "list":
        rotulos = {str(o.get("value")): o.get("label") for o in (campo["opcoes"] or [])}
        if isinstance(valor, list):
            mostrado = [rotulos.get(str(v)) or str(v) for v in valor]
        else:
            mostrado = rotulos.get(str(valor)) or str(valor)
    return {"nome": campo["nome"], "nosso_nome": campo["nosso_nome"],
            "rotulo": campo["rotulo"] or campo["nosso_nome"],
            "tipo": campo["tipo"], "valor": mostrado}


def definir_estado(solicitacao_id: int, estado: str, atendente_id: int | None) -> dict:
    if estado not in ESTADOS:
        raise DadoInvalido("Estado desconhecido.")
    linha = banco.um(
        """UPDATE formulario_solicitacao
              SET estado = %s,
                  lida_por = COALESCE(%s, lida_por),
                  lida_em = CASE WHEN %s = 'nova' THEN lida_em ELSE now() END
            WHERE id = %s
        RETURNING id, estado, lida_em""",
        (estado, atendente_id, estado, solicitacao_id))
    if not linha:
        raise DadoInvalido("Solicitação não encontrada.")
    return linha


def arquivo(solicitacao_id: int, arquivo_id: int) -> dict | None:
    """O anexo, para a rota AUTENTICADA do painel baixar.

    🚨 O HOST PÚBLICO NUNCA SERVE ANEXO. Quem envia o arquivo é a internet;
    quem o lê é a casa.
    """
    return banco.um(
        """SELECT id, campo, nome_original, caminho, mime
             FROM formulario_arquivo
            WHERE id = %s AND solicitacao_id = %s""",
        (arquivo_id, solicitacao_id))


# ----------------------------------------------------------------------------
# As defesas do envio público
# ----------------------------------------------------------------------------
# 🔵 Decisão dele, 22/10: *"1 + 2, talvez, pensar em isolar os anexos sem
# perder controle na VPS pode ser o caminho, captcha no final pode se legal,
# mas tbm usam pelo cel então não pode virar entrave de processo"*.
#
# 🚨 O PROBLEMA É REAL E JÁ VALE HOJE NO BITRIX: o envio deles é anônimo e
# aberto -- sem token, sem sessão, sem CORS restritivo --, e 13 dos 15
# formulários estão assim em produção. Qualquer um com `id`+`sec` enche o CRM.
# O nosso não repete isso.
#
# 🚨 E A ORDEM É PENSADA PARA NÃO ATRAPALHAR QUEM PREENCHE DE VERDADE:
#   1. isca   -- custa zero para a pessoa, pega robô burro;
#   2. tempo  -- robô preenche em menos de 3 s, gente não;
#   3. conta  -- quantos envios deste IP na última hora;
#   4. desafio -- SÓ depois de estourar a conta, e é uma conta de somar servida
#      por nós: sem imagem, sem terceiro, sem JavaScript de fora, e dá para
#      responder no celular com uma mão.
#
# ⚠️ NENHUMA DELAS BLOQUEIA PARA SEMPRE. O pior caso de um falso positivo é a
# pessoa responder "3 + 4"; não é "ligue para o suporte", que é justamente o
# que ela está tentando fazer.
CHAVE_DESAFIO_SEMPRE = "formulario_desafio_sempre"
ENVIOS_ANTES_DO_DESAFIO = 5
SEGUNDOS_MINIMOS = 3
# Duas horas: ficha cadastral tem 36 campos, e ninguém a preenche com pressa.
ABERTURA_VALE_SEG = 2 * 60 * 60
DESAFIO_VALE_SEG = 30 * 60


def desafio_sempre() -> bool:
    """O interruptor do sistema, em `/config › Geral`. Nasce DESLIGADO."""
    linha = banco.um("SELECT valor FROM config WHERE chave = %s",
                     (CHAVE_DESAFIO_SEMPRE,))
    return bool(linha) and linha["valor"] == "true"


def definir_desafio_sempre(ligado: bool) -> dict:
    banco.executar(
        """INSERT INTO config (chave, valor, descricao, atualizado_em)
           VALUES (%s, %s, %s, now())
           ON CONFLICT (chave) DO UPDATE
              SET valor = EXCLUDED.valor, atualizado_em = now()""",
        (CHAVE_DESAFIO_SEMPRE, "true" if ligado else "false",
         "Formulario publico pede a conta de somar em todo envio. Nasce "
         "desligada: por padrao ela so aparece depois de 5 envios do mesmo IP "
         "na hora."))
    log.info("desafio sempre %s", "ligado" if ligado else "desligado")
    return {"ok": True, "desafio_sempre": ligado}


def _segredo() -> bytes:
    """O segredo dos tokens públicos.

    ⚠️ VAZIO NÃO DERRUBA NADA: deriva do `jwt_secret` e avisa. Recurso novo não
    pode impedir o serviço de subir -- mas o aviso tem de existir, senão a
    derivação viraria o normal sem ninguém decidir isso.
    """
    from .config import settings
    bruto = (settings.formularios_segredo or "").strip()
    if bruto:
        return bruto.encode("utf-8")
    log.warning("MOVIZAP_FORMULARIOS_SEGREDO vazio: derivando do jwt_secret")
    return hmac.new(settings.jwt_secret.encode("utf-8"), b"formularios",
                    hashlib.sha256).digest()


def _assinar(corpo: str) -> str:
    mac = hmac.new(_segredo(), corpo.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{corpo}.{mac[:32]}"


def _conferir(token: str) -> str | None:
    """O corpo, se a assinatura confere. `None` em qualquer outro caso."""
    corpo, _, mac = (token or "").rpartition(".")
    if not corpo or not mac:
        return None
    esperado = _assinar(corpo).rpartition(".")[2]
    return corpo if secrets.compare_digest(mac, esperado) else None


def abertura() -> str:
    """O carimbo de "o formulário abriu agora", que volta no envio."""
    return _assinar(f"a{int(time.time())}")


def conferir_abertura(token: str) -> None:
    """🚨 Levanta `DadoInvalido` com frase que a PESSOA lê, não "token".

    ⚠️ Sem token também é recusa, e é o caso de quem chama a rota por fora da
    nossa página -- que é exatamente quem não queremos. Mas a frase fala de
    recarregar a página, porque é isso que resolve para gente de verdade (aba
    aberta desde ontem, por exemplo).
    """
    corpo = _conferir(token)
    if not corpo or not corpo.startswith("a"):
        raise DadoInvalido("Recarregue a página e envie de novo.")
    try:
        quando = int(corpo[1:])
    except ValueError:
        raise DadoInvalido("Recarregue a página e envie de novo.")
    idade = time.time() - quando
    if idade < SEGUNDOS_MINIMOS:
        raise DadoInvalido("Confira os dados e envie de novo.")
    if idade > ABERTURA_VALE_SEG:
        raise DadoInvalido("A página ficou muito tempo aberta. "
                           "Recarregue e envie de novo.")


def exige_desafio(ip: str | None) -> bool:
    if desafio_sempre():
        return True
    if not ip:
        return False
    return ratelimit.quantos_eventos(f"formulario|{ip}") >= ENVIOS_ANTES_DO_DESAFIO


def registrar_envio(ip: str | None) -> None:
    if ip:
        ratelimit.registrar_evento(f"formulario|{ip}")


# ----------------------------------------------------------------------------
# Buscar o cliente pelo documento (29/10)
# ----------------------------------------------------------------------------
# 🔵 Pedido dele: *"ao colocar CPF CNPJ, ter botao de buscar pelo CNPJ para
# preenchimento automatico da base do harmonit"*.
#
# 🚨 NÃO FALA COM O HARMONIT. A base dele já está espelhada aqui (`cliente`,
# pela `CFG_3.1`), e esta rota é alcançável por QUALQUER UM na internet -- uma
# chamada ao vivo daqui seria um caminho de fora para dentro do ERP. A resposta
# sai do nosso banco.
#
# 🚨 DEVOLVE SÓ O NOME. Nem documento, nem e-mail, nem id: quem preenche está
# confirmando a empresa dele, não consultando a nossa carteira.
#
# 🚨 E AINDA ASSIM É UM ORÁCULO ("este CNPJ é cliente?"), por isso tem teto por
# hora (`BUSCAS_POR_HORA`) e exige o carimbo de abertura da página.
BUSCAS_POR_HORA = 20

# ⚠️ 8 dos 960 clientes têm `documento` com 14 zeros -- é preenchimento de
# fachada da base, não CNPJ. Sem esta guarda, quem digitasse zeros casaria com
# oito empresas de verdade.
_DOCUMENTO_DE_FACHADA = "0" * 14


def passou_do_teto_de_buscas(ip: str | None) -> bool:
    """⚠️ O mesmo teto da busca por CNPJ, e de propósito: as duas rotas
    consultam a nossa base a partir da internet, e somar no mesmo contador
    impede que alguém use uma para contornar o limite da outra."""
    if not ip:
        return False
    return ratelimit.quantos_eventos(f"busca|{ip}") >= BUSCAS_POR_HORA


def cliente_por_documento(documento: str, ip: str | None = None) -> dict:
    """`{achou, nome, varios}` -- e nada mais que isso.

    ⚠️ "Não achou" NÃO é erro: a maior parte de quem preenche o formulário
    público não é cliente nosso ainda, e dizer "falhou" ali seria mentira.
    """
    # 🚨 ALFANUMÉRICO, e todos os formatos de colagem: `WQ0P6GLD000108`,
    # `WQ.0P6.GLD/0001-08`, só dígitos, com ponto, barra ou traço. Tudo cai na
    # mesma forma canônica -- foi ele quem achou isto colando o CNPJ da
    # Velasco, que a versão só-numérica recusava.
    so = re.sub(r"[^A-Za-z0-9]", "", documento or "").upper()
    if len(so) not in (11, 14):
        raise DadoInvalido("Informe o CNPJ completo, com 14 caracteres.")
    if ip and ratelimit.quantos_eventos(f"busca|{ip}") >= BUSCAS_POR_HORA:
        raise DadoInvalido("Muitas consultas seguidas. Tente mais tarde.")
    if ip:
        ratelimit.registrar_evento(f"busca|{ip}")
    if set(so) == {"0"} or so == _DOCUMENTO_DE_FACHADA:
        return {"achou": False}

    # ⚠️ O documento é comparado SÓ POR DÍGITO dos dois lados: na base há 1
    # registro com letra e a máscara varia. São 960 linhas -- a varredura é
    # barata, e casar por texto cru perderia o cliente por causa de um ponto.
    # ⚠️ Os DOIS LADOS são comparados na forma canônica: na base há documento
    # com letra (o da Velasco) e a pontuação varia. São 960 linhas -- a
    # varredura é barata, e casar por texto cru perderia o cliente por um
    # ponto.
    linhas = banco.varios(
        """SELECT nome, nome_fantasia, harmonit_id FROM cliente
            WHERE upper(regexp_replace(coalesce(documento, ''),
                                       '[^A-Za-z0-9]', '', 'g')) = %s
            ORDER BY ativo DESC, id
            LIMIT 5""", (so,))
    if not linhas:
        return {"achou": False}
    # 🚨 MAIS DE UM COM O MESMO DOCUMENTO EXISTE (10 pares na base). A tela diz
    # que há mais de um em vez de escolher calada.
    achado = {"achou": True, "nome": linhas[0]["nome"],
              "varios": len(linhas) > 1}

    # 🔵 As placas ativas, pedido dele em 29/10. ⚠️ `harmonit_id` NÃO SAI na
    # resposta -- é id interno; o que sai são as placas.
    #
    # 🚨 FALHA DA PONTE NÃO VIRA "SEM VEÍCULO": `placas_erro` existe para a
    # tela dizer *"não deu para consultar seus veículos"* e deixar digitar. Um
    # `[]` silencioso faria o cliente concluir que a frota dele saiu do ar.
    if linhas[0]["harmonit_id"]:
        try:
            achado["placas"] = fpsl_ponte.placas_ativas(linhas[0]["harmonit_id"])
        except Exception as e:  # noqa: BLE001 -- qualquer falha da ponte
            log.warning("placas do cliente %s: %s", linhas[0]["harmonit_id"], e)
            achado["placas"] = []
            achado["placas_erro"] = True
    else:
        # ⚠️ 1 dos 960 clientes não tem `harmonit_id` -- cadastro nascido no
        # MoviZap. Sem id não há frota para cruzar, e isso não é erro.
        achado["placas"] = []
    return achado


# ----------------------------------------------------------------------------
# A REGRA DA PLACA (29/10)
# ----------------------------------------------------------------------------
# 🔵 Dita por ele em uma linha: *"so e possivel abrir chamados para placas
# ativas na weso. o match e basicamente de 100% mesmo. essa e a regra"*.
#
# 🚨 ISTO INVERTEU O QUE EU HAVIA ESCRITO de manha. Eu tratava a lista da frota
# como SUGESTAO -- *"lista nossa incompleta nao pode barrar chamado"* -- e a
# regra dele diz o contrario: placa ativa na WESO e a CONDICAO do chamado.
#
# 🚨 E A MINHA CONTA DE 95% ESTAVA GROSSEIRA. Medido em 29/10, normalizando a
# placa dos dois lados, nas 1.998 linhas da WESO: **50 nao sao placa** (a
# coluna tem chassi e numero de serie) e **30 sao placa que o Harmonit nao
# tem**. Entre as que SAO placa o casamento e 1.918 de 1.948 = **98,5%** -- e
# os 80 restantes sao dado sujo de um lado, nao cliente de fora. A frase dele
# bate com o dado; o meu "1 em 20 vai digitar" nao batia.
#
# ⚠️ POR QUE NAO ENTRA NO `validar`: ele e sincrono, puro, e roda na suite sem
# rede. Pendurar nele uma chamada a outro servico faria 1.874 testes
# depenaderem do FPSL de pe. A conferencia mora na ROTA, ao lado da guarda de
# anexo.
def placas_informadas(d: dict, valores: dict) -> list[str]:
    """O que a pessoa escreveu nos campos de placa -- os que declaram
    `fonte = 'weso_placas'`."""
    saida = []
    for campo in d["campos"]:
        if campo.get("fonte") != "weso_placas":
            continue
        bruto = valores.get(campo["nome"])
        partes = bruto if isinstance(bruto, list) else [bruto]
        saida += [str(p).strip() for p in partes if str(p or "").strip()]
    return saida


def conferir_regra_da_placa(d: dict, valores: dict) -> bool | None:
    """Levanta `DadoInvalido` se alguma placa informada não está ativa na WESO.

    Devolve `True` (conferidas), `False` (**não deu para conferir** -- a ponte
    não respondeu) ou `None` (não havia placa).

    🚨 PONTE FORA DO AR DEIXA PASSAR, MARCADO. Recusar o chamado por causa de
    uma indisponibilidade nossa transformaria o nosso problema no problema do
    cliente -- e o cliente não tem como consertar. O rastro fica em
    `formulario_solicitacao.placas_conferidas` (migração 081).
    """
    placas = placas_informadas(d, valores)
    if not placas:
        return None
    try:
        resposta = fpsl_ponte.conferir_placas(placas)
    except Exception as e:  # noqa: BLE001 -- qualquer falha da ponte
        log.warning("regra da placa: nao deu para conferir %s: %s", placas, e)
        return False

    inativas = [p for p in placas
                if not (resposta.get(p) or {}).get("ativa")]
    if inativas:
        # ⚠️ A FRASE DIZ O QUE FAZER. "Placa não permitida" deixaria a pessoa
        # sem saída; ela não sabe o que é a WESO nem tem como consertar o
        # cadastro sozinha.
        raise DadoInvalido(
            "Só conseguimos abrir chamado para veículo com rastreador ativo. "
            + ("Esta placa não está ativa no seu cadastro: "
               if len(inativas) == 1 else
               "Estas placas não estão ativas no seu cadastro: ")
            + ", ".join(inativas)
            + ". Confira a placa ou fale com a Movisat pelo WhatsApp.")
    return True


def novo_desafio() -> dict:
    """Uma conta de somar e o token que guarda a resposta certa.

    🚨 A RESPOSTA NÃO FICA NO SERVIDOR: ela vai assinada dentro do token, que
    volta no envio. Sem sessão, sem tabela, e funciona com o serviço
    reiniciando no meio -- que é o que acontece em dia de entrega.
    """
    a = secrets.randbelow(9) + 1
    b = secrets.randbelow(9) + 1
    corpo = f"d{int(time.time())}:{a + b}"
    return {"pergunta": f"Quanto é {a} + {b}?", "token": _assinar(corpo)}


def conferir_desafio(token: str, resposta) -> None:
    corpo = _conferir(token)
    if not corpo or not corpo.startswith("d"):
        raise DadoInvalido("Responda a conta para enviar.")
    carimbo, _, certa = corpo[1:].partition(":")
    try:
        if time.time() - int(carimbo) > DESAFIO_VALE_SEG:
            raise DadoInvalido("A conta expirou. Peça outra e envie de novo.")
    except ValueError:
        raise DadoInvalido("Responda a conta para enviar.")
    if str(resposta).strip() != certa:
        raise DadoInvalido("A conta não está certa. Tente de novo.")

def contar_novas() -> int:
    """Quantas solicitações ainda estão em `nova` — o selo do menu.

    🚨 UMA FONTE SÓ. O selo e a tela contam pela MESMA coluna `estado`, e é de
    propósito: em 22/10 um selo de e-mail nasceu de uma CÓPIA do `WHERE` da
    aba e mostrou 61 onde a verdade era 5. Selo que discorda da lista manda a
    pessoa procurar o que a tela não mostra.
    """
    linha = banco.um("SELECT count(*) AS n FROM formulario_solicitacao "
                     "WHERE estado = 'nova'")
    return int(linha["n"] if linha else 0)
