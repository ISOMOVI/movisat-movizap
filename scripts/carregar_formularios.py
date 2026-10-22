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
        r = formularios.gravar_definicao(bruto, codigo=codigo, slug=slug,
                                         setor=setor, titulo=titulo,
                                         painel=painel, ordem=ordem * 10)
        print(f"{codigo:<20} /f/{slug:<24} painel={(painel or '-'):<11} "
              f"campos={r['campos']:<3} "
              f"regras={r['regras']} escondidos_por_regra={r['escondidos']} "
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
