"""AS ETAPAS DOS 15 FORMULÁRIOS — deriva por regra e aplica (11/11).

🔵 Dele: *"Os formulários devem seguir como a padronização do formulário de
suporte, no quesito de estilo, validação de campos, disposição e lógica"* ·
*"os erros de bitrix ficam para tras"* · *"tudo que foi pedido deve ser
entregue, principalmente os formularios que ainda nao sairam"*.

🚨 **O AGRUPAMENTO NÃO É INVENTADO: ELE JÁ VEM NO FORMULÁRIO.** Quatro deles
trazem campos de tipo `page` -- que são, no Bitrix, os marcadores de etapa que
quem desenhou o formulário escolheu. Onde eles existem, a etapa é a dele, com o
rótulo dele. Onde não existem, aplico o molde do **Suporte**, que é a base que
ele mandou seguir.

⚠️ **NENHUM CAMPO É CRIADO, REMOVIDO OU REESCRITO.** A régua dele: *"Os
formulários que não tem os dados que existem no suporte, por exemplo, não
inventar - Só ajustar"*. Este script só decide **em que etapa** cada campo que
já existe aparece.

🚨 **E A CONFERÊNCIA É DOS DOIS LADOS, como a do `registrar`:** etapa que cita
campo inexistente faz a pergunta sumir da tela em silêncio; pergunta que ficou
fora de toda etapa o cliente **nunca vê**, e o formulário segue "funcionando"
com uma pergunta menos. O segundo é o perigoso.

⚠️ **ELE NÃO ESCREVE SE A CONFERÊNCIA FALHAR** -- nem naquele formulário, nem
nos outros: ou os 15 ficam coerentes, ou nada muda.

Roda:
    venv/bin/python scripts/etapas_dos_formularios.py            # só relata
    venv/bin/python scripts/etapas_dos_formularios.py --aplicar
"""
import json
import sys

sys.path.insert(0, "/home/claude/movizap_painel")
from movizap import banco  # noqa: E402

# Os tipos que não são pergunta: não entram em etapa nenhuma.
DECORATIVOS = ("page", "layout")

# ---------------------------------------------------------------------------
# O MOLDE DO SUPORTE, para quem não traz `page`
# ---------------------------------------------------------------------------
# 🚨 A ORDEM DAS ETAPAS É A DO SUPORTE, e os baldes são por `nosso_nome` --
# nunca por posição. Posição muda quando alguém reordena um campo no Bitrix; o
# nome, não.
#
# ⚠️ E O QUE NÃO CAI EM BALDE NENHUM VAI PARA "A solicitação", **na ordem
# original**. É o balde que garante que nenhuma pergunta fique fora -- e ficar
# fora é o defeito que o cliente não vê.
DO_CONTRATO = (
    "contrato-pessoa-fisica-ou-juridica", "empresa", "nome-da-empresa",
    "nome-da-empresa-fantasia", "razao-social", "cnpj", "cpf",
)
DOS_DADOS = (
    "primeiro-nome", "sobrenome", "nome-completo-do-responsavel-em-assinar",
    "cargo", "cargo-departamento", "e-mail", "telefone",
    "telefone-celular-whatsapp",
)


def _etapas_pelo_molde(campos: list[dict]) -> list[dict]:
    contrato, dados, solicitacao, anexos = [], [], [], []
    for c in campos:
        nome = c["nosso_nome"]
        # 🚨 DECORATIVO NAO E PERGUNTA. O `page` que sobrou de um agrupamento
        # recusado e o traco (`layout`) nao entram em etapa nenhuma -- citar
        # qualquer um deles poria no trilho um "campo" que a tela nao sabe
        # desenhar, e ele sumiria em silencio.
        if c["tipo"] in DECORATIVOS:
            continue
        if c["tipo"] == "file":
            anexos.append(nome)
        elif nome in DO_CONTRATO:
            contrato.append(nome)
        elif nome in DOS_DADOS:
            dados.append(nome)
        else:
            solicitacao.append(nome)

    etapas = []
    if contrato:
        etapas.append({"titulo": "Contrato", "campos": contrato})
    if dados:
        etapas.append({"titulo": "Seus dados", "campos": dados})
    if solicitacao:
        etapas.append({"titulo": "A solicitação", "campos": solicitacao})
    if anexos:
        etapas.append({"titulo": "Anexos", "campos": anexos})
    return etapas


def _etapas_pelas_paginas(campos: list[dict]) -> list[dict]:
    """O agrupamento que o próprio formulário carrega.

    🚨 O `page` marca o INÍCIO de uma etapa, e o rótulo dele é o título. Campo
    antes do primeiro `page` (acontece) entra na primeira etapa -- jogá-lo fora
    seria perder uma pergunta.
    """
    etapas: list[dict] = []
    for c in campos:
        if c["tipo"] == "page":
            etapas.append({"titulo": (c["rotulo"] or "").strip() or "Etapa",
                           "campos": []})
            continue
        if c["tipo"] in DECORATIVOS:
            continue
        if not etapas:
            etapas.append({"titulo": "Dados", "campos": []})
        etapas[-1]["campos"].append(c["nosso_nome"])
    # ⚠️ Etapa que ficou sem campo nenhum sai: um `page` seguido de outro `page`
    # existe, e um passo vazio no trilho é um clique que não faz nada.
    return [e for e in etapas if e["campos"]]


# 🚨 O SUPORTE NÃO SE TOCA. Ele é a BASE que ele aprovou (*"o formulario suporte
# é a base"*), com os títulos que ELE escreveu -- inclusive *"Veiculos e
# anexos"*, que o meu molde chamaria de "Anexos". Reescrevê-lo pelo molde seria
# trocar a palavra dele pela minha no único formulário que já estava certo.
INTOCAVEIS = ("suporte",)

# ⚠️ Título de página GENÉRICO não serve: *"Página 1"* no trilho não diz nada a
# quem preenche, e o molde do Suporte diz. Quando as páginas do formulário vêm
# sem nome de verdade, o molde ganha.
import re as _re  # noqa: E402

_GENERICO = _re.compile(r"^\s*(p[áa]gina|page|etapa|step)\s*\d*\s*$", _re.I)


def _paginas_tem_nome(campos: list[dict]) -> bool:
    titulos = [(c["rotulo"] or "").strip() for c in campos
               if c["tipo"] == "page"]
    uteis = [t for t in titulos if t and not _GENERICO.match(t)]
    return bool(uteis) and len(uteis) == len(titulos)


def derivar(slug: str, campos: list[dict]) -> tuple[list[dict], str]:
    if any(c["tipo"] == "page" for c in campos) and _paginas_tem_nome(campos):
        pelas = _etapas_pelas_paginas(campos)
        # 🚨 UMA ETAPA SÓ NÃO É TRILHO. A tela só desenha o trilho com mais de
        # uma (`temEtapas`), então um único `page` com 12 campos devolve a mesma
        # página comprida de antes -- com um título novo e nada mais. O molde do
        # Suporte quebra em partes, que é o que ele pediu.
        if len(pelas) > 1:
            return pelas, "as páginas do próprio formulário"
    return _etapas_pelo_molde(campos), "o molde do Suporte"


def conferir(slug: str, campos: list[dict], etapas: list[dict]) -> list[str]:
    perguntas = [c["nosso_nome"] for c in campos
                 if c["tipo"] not in DECORATIVOS]
    citados = [n for e in etapas for n in e["campos"]]
    erros = []
    fantasmas = sorted(set(citados) - set(perguntas))
    de_fora = sorted(set(perguntas) - set(citados))
    repetidos = sorted({n for n in citados if citados.count(n) > 1})
    if fantasmas:
        erros.append("cita campo que nao existe: %s" % fantasmas)
    if de_fora:
        erros.append("PERGUNTA FORA DE TODA ETAPA: %s" % de_fora)
    if repetidos:
        erros.append("campo em duas etapas: %s" % repetidos)
    if not etapas:
        erros.append("nenhuma etapa derivada")
    return erros


def main() -> None:
    aplicar = "--aplicar" in sys.argv
    banco.abrir()

    planos, problemas = [], []
    for form in banco.varios(
            "SELECT id, slug, formato FROM formulario ORDER BY slug"):
        if form["slug"] in INTOCAVEIS:
            print("\n%s  INTOCAVEL -- e a base que ele aprovou, fica como esta"
                  % form["slug"])
            continue
        campos = banco.varios(
            """SELECT nosso_nome, rotulo, tipo FROM formulario_campo
                WHERE formulario_id = %s ORDER BY ordem, id""", (form["id"],))
        etapas, origem = derivar(form["slug"], campos)
        erros = conferir(form["slug"], campos, etapas)
        planos.append((form, etapas, origem, erros))
        if erros:
            problemas.append(form["slug"])

    for form, etapas, origem, erros in planos:
        print("\n%s  (%s -> novo)  por %s"
              % (form["slug"], form["formato"], origem))
        for i, e in enumerate(etapas, 1):
            print("   %d. %-26s %2d campos" % (i, e["titulo"][:26],
                                               len(e["campos"])))
        for erro in erros:
            print("   !! %s" % erro)

    print("\n" + "=" * 70)
    if problemas:
        print("NADA FOI ESCRITO: %d formulario(s) com problema -> %s"
              % (len(problemas), problemas))
        print("⚠️ Ou os 15 ficam coerentes, ou nada muda.")
        sys.exit(1)

    print("os %d formularios derivaram etapas coerentes (o Suporte ficou fora)"
          % len(planos))
    if not aplicar:
        print("(so relato; rode com --aplicar para escrever)")
        return

    for form, etapas, _origem, _erros in planos:
        banco.executar(
            "UPDATE formulario SET formato = 'novo', etapas = %s, "
            "atualizado_em = now() WHERE id = %s",
            (json.dumps(etapas, ensure_ascii=False), form["id"]))
    print("APLICADO: %d formularios em `formato = novo` com etapas" % len(planos))


# 🚨 O GUARDA E A CONDICAO DE ESTE SCRIPT PODER SER IMPORTADO: sem ele,
# `import` roda o relatorio dos 16 e pode chamar `sys.exit(1)` na cara de
# quem importou. O `carregar_formularios.py` deriva as etapas chamando o
# `derivar()` daqui, para nao haver uma segunda derivacao.
if __name__ == "__main__":
    main()
