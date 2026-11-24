# -*- coding: utf-8 -*-
"""23/11 — o documento do PARCEIRO deixa de ser obrigatório, e quem busca na
base passa a ser dado.

🔵 Ele, 23/11: *"formulario de pagamento de parceiros esta errado, ele nao
precisa de cpf e cnpj, obviamente pois nao puxa de base alguma, devem ser
somente preencheiveis"*.
🔵 Alcance, decidido por ele na mesma rodada: **os 2 de técnico** —
`PAGAMENTO_TECNICOS` e `CREDENCIAMENTO`. Os de cliente (`TESTE_GRATUITO`,
`FICHA_CADASTRAL`, `FORNECEDORES`) **não entram**: lá o documento é o próprio
assunto do formulário, e afrouxar seria mudança de régua.
🔵 E o botão: **tirar onde não há base**.

🚨 POR QUE AQUI, E NÃO NO BANCO: `gravar_definicao` APAGA e reescreve
`formulario_campo` a cada carga. `obrigatorio` editado no banco funciona hoje e
desaparece na próxima rodada, sem erro e sem aviso — foi exatamente a bomba de
11/11 ([[feedback_duas_verdades_script_x_banco]]).
"""
import pathlib

p = pathlib.Path("scripts/carregar_formularios.py")
bruto = p.read_bytes()
CRLF = b"\r\n" in bruto
t = bruto.decode("utf-8").replace("\r\n", "\n")


def troca(velho, novo, rotulo):
    global t
    assert velho in t, "NAO ACHOU (%s)" % rotulo
    assert t.count(velho) == 1, "AMBIGUO %dx (%s)" % (t.count(velho), rotulo)
    t = t.replace(velho, novo, 1)
    print("  ok:", rotulo)


# --------------------------------------------------------- 1. o conjunto novo
troca("""FORMATO_NOVO = None""",
"""FORMATO_NOVO = None


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
}""",
      "1. o conjunto BUSCA_CLIENTE")


# ------------------------------------------------- 2. o ajuste dos dois de técnico
troca("""AJUSTES = {""",
"""AJUSTES = {
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
    },""",
      "2. PAGAMENTO_TECNICOS: os dois documentos deixam de ser obrigatorios")


# O CREDENCIAMENTO já tem bloco próprio (04/11) -- entra dentro dele.
troca("""            "banco-2": {
                "rotulo": "Dados para pagamento (chave PIX, ou banco, agência e conta)",
            },
        },
    },""",
"""            "banco-2": {
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
    },""",
      "3. CREDENCIAMENTO: idem, dentro do bloco de 04/11")


# -------------------------------------------- 4. a carga leva o busca_cliente
troca("""                                         painel=painel, ordem=ordem * 10,
                                         formato=formato,""",
"""                                         painel=painel, ordem=ordem * 10,
                                         formato=formato,
                                         # 🚨 REESCRITO A CADA CARGA, como o
                                         # `painel` e o `formato`: a lista
                                         # acima é a fonte, e mudar quem
                                         # procura cliente não exige migração
                                         # nem deploy.
                                         busca_cliente=codigo in BUSCA_CLIENTE,""",
      "4. a carga passa busca_cliente")


saida = t.replace("\n", "\r\n") if CRLF else t
p.write_bytes(saida.encode("utf-8"))
print("gravado:", p, len(saida), "bytes")
