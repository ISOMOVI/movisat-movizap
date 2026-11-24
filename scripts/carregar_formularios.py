"""Carrega a definição dos formulários nas tabelas da migração 074.

Lê `dados/formularios_bitrix/mapa_bruto.json` (que o
`scripts/extrair_formularios_bitrix.py` gera a partir dos loaders públicos do
Bitrix24) e escreve `formulario`, `formulario_campo` e `formulario_regra`.

🚨 NÃO FALA COM O BITRIX. A separação entre reobter e carregar é de propósito:
carregar tem de poder ser repetido sem a internet do primeiro passo.

🚨 IDEMPOTENTE: rodar de novo reescreve campos e regras do mesmo `codigo`, e
NÃO toca em `ativo` nem em solicitação já recebida. Quem liga o formulário é
ele, pela tela.

⚠️ CÓDIGO, SLUG, TÍTULO E SETOR SÃO NOSSOS, e moram aqui. O título do Bitrix
vem vazio em vários (o de Contato, por exemplo), e o `slug` é o que aparece na
URL pública -- mudá-lo depois quebra todo link já distribuído.

Uso:
    venv/bin/python scripts/carregar_formularios.py            # todos os 15
    venv/bin/python scripts/carregar_formularios.py CES NPS    # só esses
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, "/home/claude/movizap_painel")

from movizap import banco, formularios  # noqa: E402

RAIZ = Path("/home/claude/movizap_painel")
MAPA = RAIZ / "dados" / "formularios_bitrix" / "mapa_bruto.json"

# codigo -> (id no Bitrix, slug publico, titulo, setor, painel)
# A ordem desta lista é a ordem na tela.
#
# 🔵 O PAINEL É O MAPA DELE (plano, §2.1), e mora AQUI -- uma fonte só. A
# coluna `formulario.painel` (migração 075) é reescrita a cada carga, então
# mover um formulário de painel é editar esta tabela e rodar a carga: sem
# migração, sem deploy. `None` = *"SEM PAINEL — Contato"*, decisão dele.
NOSSOS = [
    ("CES",                 "70",  "ces",                    "Pesquisa CES",                          "Qualidade", "pos_venda"),
    ("NPS",                 "64",  "nps",                    "Pesquisa NPS",                          "Qualidade", "pos_venda"),
    ("SUPORTE",             "32",  "suporte",                "Suporte",                               "Suporte", "operacao"),
    ("DEMONSTRACAO",        "220", "demonstracao",           "Solicitação de demonstração",           "Comercial", "operacao"),
    ("TESTE_GRATUITO",      "96",  "teste-gratuito",         "Teste gratuito",                        "Comercial", "operacao"),
    ("CONTATO",             "30",  "contato",                "Contato",                               "Comercial", None),
    ("FICHA_CADASTRAL",     "98",  "ficha-cadastral",        "Ficha cadastral de novos clientes",     "Contratual", "contratual"),
    ("ADITIVO",             "14",  "aditivo",                "Aditivo contratual",                    "Contratual", "contratual"),
    ("SUBSTITUICAO",        "16",  "substituicao-veiculos",  "Substituição de veículos",              "Contratual", "contratual"),
    ("RESCISAO",            "10",  "rescisao",               "Rescisão contratual",                   "Contratual", "contratual"),
    ("ADMINISTRATIVO",      "36",  "administrativo",         "Solicitações administrativas",          "Administrativo", "financeiro"),
    ("FINANCEIRO",          "34",  "financeiro",             "Solicitações financeiras",              "Financeiro", "financeiro"),
    ("CREDENCIAMENTO",      "164", "credenciamento-tecnico", "Credenciamento de parceiros técnicos",  "Operações", "operacao"),
    ("PAGAMENTO_TECNICOS",  "184", "pagamento-tecnicos",     "Pagamento de parceiros técnicos",       "Financeiro", "financeiro"),
    ("FORNECEDORES",        "238", "fornecedores",           "Fornecedores",                          "Administrativo", "financeiro"),
    ("IDEIAS",              "38",  "ideias-sugestoes",       "Ideias e sugestões",                    "Produto", None),
]


# ----------------------------------------------------------------------------
# O FORMATO NOVO (29/10)
# ----------------------------------------------------------------------------
# 🔵 Pedido dele, 29/10, sobre o Suporte: *"ele ainda nao passou por aqueles
# ajustes de UX/UI e customizacao, certo? igual outros, ajuste ele no novo
# formato 'etapas, logo, cor, placas, etc'"*.
#
# 🚨 SO QUEM ESTA AQUI MUDA DE CARA. Os outros 14 continuam `classico` -- a
# pagina de 22/10, um rolo so --, porque o formato novo muda o que a internet
# ve e ele valida formulario por formulario no navegador. Ligar o proximo e
# acrescentar o codigo a este conjunto e rodar a carga: sem migracao, sem
# deploy.
# 🚨 ERA `{"SUPORTE"}` E O BANCO TINHA OS 15 EM `novo`: o
# `etapas_dos_formularios.py` os passou todos em 11/11, e este script teria
# revertido 14 para `classico` na proxima carga completa -- mudando o que a
# internet ve, sem erro nenhum.
#
# ⚠️ `None` aqui significa TODOS. Nao e lista: lista volta a divergir no dia em
# que o 17o formulario nascer e ninguem lembrar de acrescentar.
FORMATO_NOVO = None


# ----------------------------------------------------------------------------
# QUEM PROCURA CLIENTE NA NOSSA BASE (23/11)
# ----------------------------------------------------------------------------
# 🔵 Decisão dele, 23/11, sobre o botão *Buscar* do CNPJ: **tirar onde não há
# base**.
#
# 🚨 O DEFEITO QUE ISTO FECHA: o botão não era decisão de ninguém. A tela o
# desenhava por `ehNovo && campo.validacao === 'cnpj'`, e `FORMATO_NOVO = None`
# põe os 16 em `novo` -- então todo formulário com CNPJ ganhou o botão. O
# `cliente_por_documento` varre a tabela `cliente` (os clientes NOSSOS): um
# parceiro técnico, um fornecedor ou um interessado em teste gratuito nunca
# está lá. O botão aparecia e a resposta certa era sempre "não achou".
#
# ⚠️ AQUI É LISTA DE PROPÓSITO, ao contrário do `FORMATO_NOVO`. São duas
# naturezas diferentes: formato é cara da tela e vale para todos; procurar
# cliente é POR FORMULÁRIO -- quem pergunta a quem já tem contrato procura,
# quem cadastra gente nova não tem onde procurar. Formulário fora desta lista
# nasce SEM busca, que é o lado seguro: oferecer busca que não acha é pior que
# não oferecer.
#
# ⚠️ A FICHA_CADASTRAL FICA FORA: é a ficha de clientes NOVOS -- quem preenche,
# por definição, ainda não está na base.
BUSCA_CLIENTE = {
    "SUPORTE", "ADITIVO", "ADMINISTRATIVO", "FINANCEIRO", "RESCISAO",
    "SUBSTITUICAO",
}

# As etapas, por codigo. Os campos sao citados pelo `nosso_nome`.
#
# 🚨 O SUPORTE NAO TEM NENHUMA `page`, e isso muda a natureza desta tabela:
# nos outros formularios as 15 `page` do Bitrix JA SAO as etapas e nao se
# inventa nada (Bloco 5 do plano). Aqui o agrupamento e NOSSO, proposto por
# mim, e esta em dado exatamente para ele poder rever sem mexer em codigo.
#
# ⚠️ A ORDEM DOS CAMPOS DENTRO DA ETAPA E A DESTA LISTA, nao a do Bitrix --
# etapa e agrupamento, e agrupar sem poder ordenar nao serve.
#
# 🚨 A ETAPA 1 PARECE TER 4 CAMPOS E MOSTRA 2: `empresa` e `cnpj` so aparecem
# para Pessoa Juridica (1756) e `cpf` so para Pessoa Fisica (1754) -- as 3
# regras condicionais do proprio formulario. Nao e etapa meia vazia: e a
# pergunta PF/PJ fazendo o seu trabalho.
ETAPAS = {
    "SUPORTE": [
        {"titulo": "Contrato",
         "campos": ["contrato-pessoa-fisica-ou-juridica", "empresa",
                    "cnpj", "cpf"]},
        # ⚠️ Sem `sobrenome` e sem `assunto`: os dois sairam em 29/10 (ver
        # `AJUSTES`). Etapa que cita campo que nao existe PARA na carga, e e
        # por isso que as duas tabelas tem de andar juntas.
        {"titulo": "Seus dados",
         "campos": ["primeiro-nome", "e-mail", "telefone"]},
        {"titulo": "A solicitacao",
         "campos": ["tipo-de-solicitacao", "detalhe-a-ocorrencia"]},
        {"titulo": "Veiculos e anexos",
         "campos": ["veiculo-e-placa-somente-se-for-referente",
                    "arquivo-ou-print-caso-desejar"]},
    ],
}

# ----------------------------------------------------------------------------
# OS AJUSTES NOSSOS em cima da definicao do Bitrix (29/10)
# ----------------------------------------------------------------------------
# 🔵 *"vamos mudar as opcoes do 'Tipo de solicitacao', pois sao do bitrix e nao
# nos satisfazem mais"*. A partir daqui a definicao do Bitrix e ponto de
# partida, nao palavra final.
#
# 🚨 E PRECISA MORAR AQUI: `gravar_definicao` APAGA e reescreve os campos a cada
# carga. Ajuste editado no banco funciona hoje e desaparece na proxima rodada,
# sem erro e sem aviso.
#
# ⚠️ `fora` TIRA o campo (ele deixa de existir, nao fica escondido). O resto
# muda o campo que fica.
AJUSTES = {
    # 🔵 23/11: *"formulario de pagamento de parceiros esta errado, ele nao
    # precisa de cpf e cnpj, obviamente pois nao puxa de base alguma, devem ser
    # somente preencheiveis"*.
    #
    # 🚨 O QUE ESTAVA ERRADO, MEDIDO: os DOIS documentos `obrigatorio = True`,
    # os dois VISÍVEIS e **nenhuma regra** condicional no formulário. Quem é
    # pessoa física era obrigado a inventar um CNPJ para o botão Enviar
    # funcionar, e quem é jurídica, um CPF. Não é campo demais -- é exigência
    # impossível de cumprir, nos dois sentidos.
    #
    # ⚠️ OS CAMPOS FICAM, e isto é o pedido dele ao pé da letra: *"somente
    # preencheiveis"*. Quem tiver CNPJ informa o CNPJ; quem só tem CPF informa
    # o CPF. `fora` tiraria a pergunta, e ele não pediu isso.
    #
    # ⚠️ A VALIDAÇÃO DE FORMATO CONTINUA (`VALIDACOES` abaixo), e não há
    # contradição: ela só fala quando a pessoa escreve algo. Campo vazio passa;
    # CPF pela metade, não. Tirar a validação junto seria aceitar documento
    # quebrado -- outra coisa, que ele não pediu.
    "PAGAMENTO_TECNICOS": {
        "campos": {
            "cpf": {"obrigatorio": False},
            "cnpj": {"obrigatorio": False},
        },
    },
    # 🚨 A RESCISAO, E POR QUE ESTA LINHA EXISTE: a migracao 104 consertou o
    # tipo destes dois NO BANCO, e a carga os devolvia a `string` -- o tipo vem
    # do Bitrix. Aqui o conserto sobrevive a qualquer rodada.
    #
    # ⚠️ Sao os campos do NOVO TITULAR: quem assume o contrato. Validacao que
    # fica so no navegador, nesses dois, e validacao que nao existe.
    "RESCISAO": {
        "campos": {
            "e-mail-do-novo-titular": {"tipo": "email"},
            "telefone-com-ddd-do-novo-titular": {"tipo": "phone"},
        },
    },
    # 🔵 11/11, o 16o formulario (Bitrix 38, "Ideias e sugestoes").
    #
    # 🚨 *"os erros de bitrix ficam para tras"* (dele, 11/11): o campo que pede
    # *"Detalhe ao maximo a melhoria"* vinha como UMA LINHA de texto no
    # Bitrix. Pedir o maximo de detalhe numa caixa de uma linha e o proprio
    # formulario desencorajando a resposta que ele quer. Seis linhas, como o
    # `detalhe-a-ocorrencia` do Suporte.
    "IDEIAS": {
        "campos": {
            "detalhe-ao-maximo-a-melhoria-o-que-ela-r": {"linhas": 6},
        },
    },
    # 🔵 04/11: o bloco BANCO virou DADOS DE PAGAMENTO -- *"pode ser TED, PIX,
    # ou boleto, oopção por lista e campo com os dados"*, e *"ajuste no
    # formulario tbm, o mesmo formato. ai amarra eles"*.
    #
    # 🚨 NENHUM CAMPO NOVO FOI INVENTADO, e não é limitação: `gravar_definicao`
    # lê a definição do Bitrix, e campo que não existe lá não tem como nascer
    # por ajuste. O que se fez foi REAPROVEITAR os dois campos que já
    # perguntavam sobre pagamento -- a lista e um texto --, e tirar os outros
    # dois. Resultado: a mesma dupla (forma + dados) que a ficha da `TEC_1.1`
    # tem, com os MESMOS três valores.
    #
    # ⚠️ O QUE ISSO CUSTA, DITO: a pergunta "titular é pessoa física ou
    # jurídica?" deixou de existir, e as de agência e conta saíram. Quem paga
    # por TED vai escrever banco, agência e conta no campo de dados. O custo é
    # aceitável porque CNPJ e CPF já são perguntados antes, no formulário, e
    # porque **nenhuma solicitação havia sido recebida** (medido: 0 em 04/11) --
    # não há resposta antiga para ficar sem lugar.
    "CREDENCIAMENTO": {
        "fora": ["agencia", "conta"],
        "campos": {
            # O TÍTULO DA SEÇÃO. 🚨 `banco` é a PÁGINA e `banco-2` é o campo de
            # texto -- dois campos, dois nomes, e foi justamente a confusão
            # entre eles que recusou a primeira carga desta volta. Sem este
            # ajuste, a seção continuaria anunciando "BANCO" para quem escolhe
            # PIX.
            "banco": {"rotulo": "DADOS DE PAGAMENTO"},
            # A lista que perguntava o titular passa a perguntar a FORMA.
            # 🚨 Os `value` são NOSSOS, em slug, e batem com o CHECK da coluna
            # `tecnico_ficha.pagamento_forma` (migração 086). Os ids do Bitrix
            # (5846, 5848) não significavam nada aqui.
            "titular-da-conta-e-pessoa-fisica-ou-juri": {
                "rotulo": "Forma de pagamento",
                "opcoes": [
                    {"value": "pix", "label": "PIX"},
                    {"value": "ted", "label": "TED / depósito em conta"},
                    {"value": "boleto", "label": "Boleto"},
                ],
            },
            # O campo "Banco" passa a ser o campo dos DADOS. O `nosso_nome`
            # continua `banco-2` -- ele vem do rótulo ORIGINAL e é a chave
            # estável do de-para; o que muda é o que a pessoa lê.
            "banco-2": {
                "rotulo": "Dados para pagamento (chave PIX, ou banco, agência e conta)",
            },
            # 🔵 23/11, o mesmo alcance do `PAGAMENTO_TECNICOS`: é o OUTRO
            # formulário de parceiro técnico, com o mesmo defeito medido --
            # CPF e CNPJ visíveis e os dois obrigatórios, sem regra PF/PJ.
            #
            # ⚠️ E aqui a exigência impossível custava mais que lá: este é o
            # formulário de CREDENCIAMENTO, a porta de entrada do parceiro.
            # Técnico pessoa física que não tem CNPJ não conseguia se
            # credenciar -- e o credenciamento é o que ele quer que aconteça.
            "cpf": {"obrigatorio": False},
            "cnpj": {"obrigatorio": False},
        },
    },
    "SUPORTE": {
        # 🔵 *"na aba 2, somente 1 caixa para o nome ja serve"* e *"o assunto
        # ja e o proprio tipo de solicitacao"*.
        "fora": ["sobrenome", "assunto"],
        "campos": {
            "primeiro-nome": {"rotulo": "Nome completo"},
            # 🔵 *"deixar em fantasma o modelo de preenchimento"* -- as palavras
            # dele, inclusive o exemplo. O espaco e o tracinho a tela poe
            # sozinha enquanto se digita (`validacao_campo.mascarar`).
            "telefone": {"fantasma": "(00) 123456789"},
            # 🔵 As 4 opcoes dele, EM ORDEM ALFABETICA ("so coloque em ordem
            # alfabetica").
            #
            # 🚨 OS VALORES SAO NOSSOS, e de proposito: os do Bitrix (1340,
            # 1342, ...) eram ids da base deles e nao significam nada aqui. Em
            # slug porque e deste campo que vai sair o mapa para o `problemaId`
            # do Harmonit -- e ler "rastreamento" numa decisao e melhor que ler
            # "1348".
            #
            # ⚠️ SAIRAM 8 OPCOES do Bitrix, entre elas as DUAS de Backup
            # (ativacao e desativacao) que nao tinham candidato em nenhum dos 24
            # problemas do Harmonit. A pendencia dos "dois Backup" morre aqui:
            # viraram uma, "Acesso ao Backup de dados".
            "tipo-de-solicitacao": {"opcoes": [
                {"value": "backup",       "label": "Acesso ao Backup de dados"},
                {"value": "veiculo",      "label": "Problemas com o veículo"},
                {"value": "rastreamento", "label": "Problemas com rastreamento"},
                {"value": "sugestao",     "label": "Sugestão de melhoria"},
            ]},
            # 🔵 *"pode ser um pouco mais alto para exprimir que pode colocar
            # mais texto"*. ⚠️ O campo e `string` no Bitrix -- sem isto ele
            # seria uma linha so, que diz a quem preenche "escreva pouco".
            "detalhe-a-ocorrencia": {"linhas": 6},
            # 🔵 *"se ja tem o cliente validado, ja podemos trazer no campo de
            # veiculo placa os veiculos que ele tem ativo na Weso"*.
            "veiculo-e-placa-somente-se-for-referente": {
                "rotulo": "Veículo e placa",
                "fonte": "weso_placas",
            },
        },
    },
}

# A mascara e a conferencia de cada campo, por `nosso_nome`.
#
# 🚨 ISTO EXISTE PORQUE O TIPO DO BITRIX NAO DIZ O BASTANTE: `cnpj` e `cpf`
# sao `double` nos 15 formularios -- o tipo sugere numero decimal e o campo e
# documento. Sem esta tabela nao ha mascara nem digito verificador.
#
# 🚨 E NAO E BARREIRA: quem recusa o envio e o servidor
# (`movizap/formularios.py:validar`). Aqui se decide a mascara e a frase que a
# pessoa le -- no Bitrix era o contrario, toda a validacao no navegador, e um
# POST cru criou registro em 22/10.
VALIDACOES = {
    # 🚨 RETRATO DO BANCO em 11/11, trazido para ca porque ESTE arquivo e a
    # fonte: a carga apaga e reescreve os campos, e o que nao estiver aqui
    # nao volta. As 55 linhas abaixo do Suporte vieram das migracoes 103 e
    # 104, que escreveram direto no banco -- entao o script tinha 5 e a
    # verdade eram 60, e a proxima carga completa teria apagado 55 sem dizer
    # nada.
    #
    # ⚠️ `rg`, `website`, data e lista ficam DE FORA de proposito (decisao de
    # 11/11): nao sao formato fechado, e exigir um formato que a pessoa nao
    # tem recusa a resposta certa.
    "SUPORTE": {
        "cnpj": "cnpj",
        "cpf": "cpf",
        "e-mail": "email",
        "telefone": "telefone",
        "veiculo-e-placa-somente-se-for-referente": "placa",
    },
    "ADITIVO": {
        "cnpj": "cnpj",
        "cpf": "cpf",
        "e-mail": "email",
        "telefone": "telefone",
        "veiculo-e-placa": "placa",
    },
    "ADMINISTRATIVO": {
        "cnpj": "cnpj",
        "cpf": "cpf",
        "e-mail": "email",
        "telefone": "telefone",
    },
    "CONTATO": {
        "cnpj": "cnpj",
        "e-mail": "email",
        "telefone": "telefone",
    },
    "CREDENCIAMENTO": {
        "cnpj": "cnpj",
        "cpf": "cpf",
        "cep": "cep",
        "telefone-fixo": "telefone",
        "telefone-celular-whatsapp": "telefone",
        "e-mail-geral-da-empresa": "email",
        "e-mail": "email",
    },
    "DEMONSTRACAO": {
        "cnpj": "cnpj",
        "e-mail": "email",
        "telefone": "telefone",
    },
    "FICHA_CADASTRAL": {
        "cnpj": "cnpj",
        "cpf": "cpf",
        "telefone-da-empresa-com-ddd": "telefone",
        "telefone": "telefone",
        "e-mail": "email",
    },
    "FINANCEIRO": {
        "cnpj": "cnpj",
        "cpf": "cpf",
        "e-mail": "email",
        "telefone": "telefone",
    },
    "FORNECEDORES": {
        "cnpj": "cnpj",
        "e-mail": "email",
        "e-mail-2": "email",
        "telefone": "telefone",
        "telefone-2": "telefone",
    },
    "NPS": {
        "e-mail": "email",
        "telefone": "telefone",
    },
    "PAGAMENTO_TECNICOS": {
        "cnpj": "cnpj",
        "cpf": "cpf",
    },
    "RESCISAO": {
        "cnpj": "cnpj",
        "cpf": "cpf",
        "e-mail": "email",
        "telefone": "telefone",
        "veiculo-e-placa": "placa",
        # 🚨 Os dois do NOVO TITULAR vinham `string` do Bitrix e o servidor
        # decide pelo TIPO: sem a migracao 104 a validacao ficava so no
        # navegador, no campo que define o DONO DO CONTRATO.
        "e-mail-do-novo-titular": "email",
        "telefone-com-ddd-do-novo-titular": "telefone",
    },
    "SUBSTITUICAO": {
        "cnpj": "cnpj",
        "cpf": "cpf",
        "e-mail": "email",
        "telefone": "telefone",
    },
    "TESTE_GRATUITO": {
        "cnpj": "cnpj",
        "cpf": "cpf",
        "e-mail": "email",
        "telefone": "telefone",
    },
    # 🔵 11/11, o 16o formulario (Bitrix 38), o cartao de "Ideias e sugestoes"
    # do SAC -- o unico dos 8 cartoes que nunca foi reconstruido.
    "IDEIAS": {
        "cnpj": "cnpj",
        "cpf": "cpf",
        "e-mail": "email",
        "telefone": "telefone",
    },
}


def _derivar_etapas(codigo: str) -> list[dict] | None:
    """As etapas de um formulario, pela MESMA regra do script de etapas.

    🚨 Importado, nao copiado: `etapas_dos_formularios.derivar` e a unica
    derivacao, e as 13 travas dele valem para esta chamada tambem.
    """
    import importlib.util
    cam = RAIZ / "scripts" / "etapas_dos_formularios.py"
    spec = importlib.util.spec_from_file_location("_etapas", cam)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    f = banco.um("SELECT id, slug FROM formulario WHERE codigo = %s",
                 (codigo,))
    if not f or f["slug"] in mod.INTOCAVEIS:
        return None
    campos = banco.varios(
        "SELECT nosso_nome, rotulo, tipo FROM formulario_campo"
        " WHERE formulario_id = %s ORDER BY ordem, id", (f["id"],))
    etapas, _origem = mod.derivar(f["slug"], campos)
    erros = mod.conferir(f["slug"], campos, etapas)
    if erros:
        # ⚠️ NAO escreve etapa incoerente: formulario sem etapa continua
        # mostrando todos os campos, que e ruim; com etapa errada ele ESCONDE
        # campo, que e pior.
        print("   !! etapas de %s nao derivaram: %s" % (codigo, erros))
        return None
    return etapas


def derivadas_do_banco(codigo: str) -> list:
    """Quantas etapas o formulario tem AGORA -- para o relato dizer a verdade."""
    r = banco.um("SELECT etapas FROM formulario WHERE codigo = %s", (codigo,))
    e = (r or {}).get("etapas")
    if isinstance(e, str):
        e = json.loads(e)
    return e or []


def main(pedidos: list[str]) -> None:
    mapa = json.loads(MAPA.read_text(encoding="utf-8"))
    banco.abrir()

    alvo = [n for n in NOSSOS if not pedidos or n[0] in pedidos]
    if pedidos and len(alvo) != len(pedidos):
        conhecidos = ", ".join(n[0] for n in NOSSOS)
        sys.exit(f"codigo desconhecido. Conheco: {conhecidos}")

    for ordem, (codigo, bitrix_id, slug, titulo, setor, painel) in enumerate(alvo, start=1):
        bruto = mapa.get(bitrix_id)
        if not bruto:
            sys.exit(f"{codigo}: o mapa nao tem o formulario {bitrix_id}")
        formato = ("novo" if FORMATO_NOVO is None
                   or codigo in FORMATO_NOVO else "classico")
        r = formularios.gravar_definicao(bruto, codigo=codigo, slug=slug,
                                         setor=setor, titulo=titulo,
                                         painel=painel, ordem=ordem * 10,
                                         formato=formato,
                                         # 🚨 REESCRITO A CADA CARGA, como o
                                         # `painel` e o `formato`: a lista
                                         # acima é a fonte, e mudar quem
                                         # procura cliente não exige migração
                                         # nem deploy.
                                         busca_cliente=codigo in BUSCA_CLIENTE,
                                         etapas=ETAPAS.get(codigo),
                                         validacoes=VALIDACOES.get(codigo),
                                         ajustes=AJUSTES.get(codigo))
        # 🚨 AS ETAPAS DOS OUTROS 15 NAO MORAM AQUI, E E DE PROPOSITO: elas
        # SAO DERIVADAS da definicao, pelo `etapas_dos_formularios.derivar`,
        # que ja existe e ja tem 13 travas. Copiar os 15 agrupamentos para
        # este arquivo criaria uma TERCEIRA verdade -- e foi a segunda que
        # causou o defeito que este conserto fecha.
        #
        # ⚠️ O Suporte continua com o agrupamento EXPLICITO acima: e a base
        # que ele aprovou, e o derivador o trata como INTOCAVEL.
        if codigo not in ETAPAS:
            derivadas = _derivar_etapas(codigo)
            if derivadas:
                banco.executar(
                    "UPDATE formulario SET etapas = %s, formato = 'novo',"
                    " atualizado_em = now() WHERE codigo = %s",
                    (json.dumps(derivadas, ensure_ascii=False), codigo))
        etapas = len(ETAPAS.get(codigo) or derivadas_do_banco(codigo))
        print(f"{codigo:<20} /f/{slug:<24} painel={(painel or '-'):<11} "
              f"campos={r['campos']:<3} "
              f"regras={r['regras']} escondidos_por_regra={r['escondidos']} "
              f"formato={formato:<8} etapas={etapas} "
              f"ativo={'sim' if r['ativo'] else 'NAO'}")

    # A prova é RELER o estado, nunca o retorno da escrita.
    print()
    for linha in banco.varios(
            """SELECT f.codigo, f.slug, f.ativo, count(c.id) AS campos
                 FROM formulario f
                 LEFT JOIN formulario_campo c ON c.formulario_id = f.id
                GROUP BY f.id ORDER BY f.ordem"""):
        print(f"  {linha['codigo']:<20} {linha['campos']:>3} campos  "
              f"{'ligado' if linha['ativo'] else 'desligado'}")


if __name__ == "__main__":
    main([a.upper() for a in sys.argv[1:]])
