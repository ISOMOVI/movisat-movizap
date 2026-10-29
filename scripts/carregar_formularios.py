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
FORMATO_NOVO = {"SUPORTE"}

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
    "SUPORTE": {
        "cnpj": "cnpj",
        "cpf": "cpf",
        "e-mail": "email",
        "telefone": "telefone",
        "veiculo-e-placa-somente-se-for-referente": "placa",
    },
}


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
        formato = "novo" if codigo in FORMATO_NOVO else "classico"
        r = formularios.gravar_definicao(bruto, codigo=codigo, slug=slug,
                                         setor=setor, titulo=titulo,
                                         painel=painel, ordem=ordem * 10,
                                         formato=formato,
                                         etapas=ETAPAS.get(codigo),
                                         validacoes=VALIDACOES.get(codigo),
                                         ajustes=AJUSTES.get(codigo))
        etapas = len(ETAPAS.get(codigo) or [])
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
