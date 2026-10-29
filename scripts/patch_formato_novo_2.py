# -*- coding: utf-8 -*-
"""Patch 29/10 (parte 2): a rota publica entrega o formato novo, e a carga o escreve.

  · movizap/main.py -- `_publico_do_formulario` passa a devolver `formato`,
    `etapas` (TRADUZIDAS para o nome de origem) e a `validacao` de cada campo;
  · scripts/carregar_formularios.py -- as tabelas do formato novo, com o
    SUPORTE ligado e os outros 14 intactos.

🚨 Idempotente, e para sem gravar nada se o trecho velho nao estiver exatamente
uma vez no arquivo.
"""
import pathlib
import sys

RAIZ = pathlib.Path("/home/claude/movizap_painel")


def trocar(caminho: pathlib.Path, velho: str, novo: str, rotulo: str) -> None:
    texto = caminho.read_text(encoding="utf-8")
    if novo in texto:
        print(f"  = {rotulo}: ja aplicado")
        return
    if texto.count(velho) != 1:
        sys.exit(f"  ! {rotulo}: achei {texto.count(velho)} ocorrencias do "
                 f"trecho velho, esperava 1 -- PAREI sem gravar nada")
    caminho.write_text(texto.replace(velho, novo), encoding="utf-8")
    print(f"  + {rotulo}")


# ---------------------------------------------------------------------------
# 1. A rota publica
# ---------------------------------------------------------------------------
m = RAIZ / "movizap" / "main.py"
print(m.name)

trocar(m, '''def _publico_do_formulario(d: dict, ip: str | None) -> dict:''',
       '''def _etapas_publicas(d: dict) -> list | None:
    """As etapas da página, com os campos no nome de ORIGEM.

    🚨 A TRADUÇÃO ACONTECE AQUI, e é o motivo desta função existir: as etapas
    são escritas no `carregar_formularios.py` citando o `nosso_nome`
    (`veiculo-e-placa-...`), porque é o único dos dois nomes que uma pessoa
    revisa. Mas `nosso_nome` NÃO SAI para a internet -- é nome interno --, e a
    tela casa campo por `nome`. Então o que vai no ar é o nome de origem.

    ⚠️ Campo citado que não existe mais já parou na carga
    (`formularios.gravar_definicao`); aqui ele é só ignorado, porque uma
    etapa a menos na tela é melhor que a página inteira em branco.
    """
    etapas = d.get("etapas")
    if not etapas:
        return None
    de_nosso = {c["nosso_nome"]: c["nome"] for c in d["campos"]}
    saida = []
    for etapa in etapas:
        nomes = [de_nosso[n] for n in (etapa.get("campos") or [])
                 if n in de_nosso]
        saida.append({"titulo": etapa.get("titulo") or "", "campos": nomes})
    return saida


def _publico_do_formulario(d: dict, ip: str | None) -> dict:''',
       "main.py: _etapas_publicas")

trocar(m, '''        "slug": d["slug"], "titulo": d["titulo"], "botao": d["botao"],
        "descricao": d["descricao"],
        "campos": [{"nome": c["nome"], "rotulo": c["rotulo"], "tipo": c["tipo"],
                    "obrigatorio": c["obrigatorio"], "multiplo": c["multiplo"],
                    "visivel": c["visivel"], "opcoes": c["opcoes"],
                    "ajuda": c["ajuda"]}
                   for c in d["campos"]],''',
       '''        "slug": d["slug"], "titulo": d["titulo"], "botao": d["botao"],
        "descricao": d["descricao"],
        # 🚨 `formato` E `etapas` SAO APRESENTACAO, nao permissao nem regra:
        # dizem a tela como se desenhar. A validacao do envio nao olha para
        # eles -- um POST cru sem etapa nenhuma e conferido igual.
        "formato": d.get("formato") or "classico",
        "etapas": _etapas_publicas(d),
        "campos": [{"nome": c["nome"], "rotulo": c["rotulo"], "tipo": c["tipo"],
                    "obrigatorio": c["obrigatorio"], "multiplo": c["multiplo"],
                    "visivel": c["visivel"], "opcoes": c["opcoes"],
                    "ajuda": c["ajuda"], "validacao": c.get("validacao")}
                   for c in d["campos"]],''',
       "main.py: formato, etapas e validacao no corpo publico")

# ---------------------------------------------------------------------------
# 2. A carga
# ---------------------------------------------------------------------------
c = RAIZ / "scripts" / "carregar_formularios.py"
print(c.name)

trocar(c, '''def main(pedidos: list[str]) -> None:''',
       '''# ----------------------------------------------------------------------------
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
        {"titulo": "Seus dados",
         "campos": ["primeiro-nome", "sobrenome", "e-mail", "telefone"]},
        {"titulo": "A solicitacao",
         "campos": ["tipo-de-solicitacao", "assunto", "detalhe-a-ocorrencia"]},
        {"titulo": "Veiculos e anexos",
         "campos": ["veiculo-e-placa-somente-se-for-referente",
                    "arquivo-ou-print-caso-desejar"]},
    ],
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


def main(pedidos: list[str]) -> None:''',
       "carga: FORMATO_NOVO, ETAPAS e VALIDACOES")

trocar(c, '''        r = formularios.gravar_definicao(bruto, codigo=codigo, slug=slug,
                                         setor=setor, titulo=titulo,
                                         painel=painel, ordem=ordem * 10)
        print(f"{codigo:<20} /f/{slug:<24} painel={(painel or '-'):<11} "
              f"campos={r['campos']:<3} "
              f"regras={r['regras']} escondidos_por_regra={r['escondidos']} "
              f"ativo={'sim' if r['ativo'] else 'NAO'}")''',
       '''        formato = "novo" if codigo in FORMATO_NOVO else "classico"
        r = formularios.gravar_definicao(bruto, codigo=codigo, slug=slug,
                                         setor=setor, titulo=titulo,
                                         painel=painel, ordem=ordem * 10,
                                         formato=formato,
                                         etapas=ETAPAS.get(codigo),
                                         validacoes=VALIDACOES.get(codigo))
        etapas = len(ETAPAS.get(codigo) or [])
        print(f"{codigo:<20} /f/{slug:<24} painel={(painel or '-'):<11} "
              f"campos={r['campos']:<3} "
              f"regras={r['regras']} escondidos_por_regra={r['escondidos']} "
              f"formato={formato:<8} etapas={etapas} "
              f"ativo={'sim' if r['ativo'] else 'NAO'}")''',
       "carga: passa formato, etapas e validacoes")

print()
print("ok. Falta o frontend.")
