"""Extrai a definição dos 15 formulários do Bitrix24 — SÓ LEITURA.

🚨 O ACHADO QUE DESTRAVOU O CLONE (22/10): o loader de cada formulário é
PÚBLICO e sem autenticação nenhuma --

    https://cdn.bitrix24.com.br/b20668843/crm/form/loader_<ID>.js

-- e carrega a definição INTEIRA: campos, rótulos, obrigatoriedade, as opções
de cada lista com os IDs numéricos do Bitrix, as regras condicionais, o design
e os textos. Não precisa de credencial do portal.

A config é o argumento de `window.b24form.Loader.run({...})`, e é daí que este
script a arranca com `raw_decode` -- não é JSON puro num arquivo, é JS.

Como reobter os loaders (se o Bitrix mudar algum formulário):

    cd dados/formularios_bitrix
    for id in 30 220 96 32 98 14 16 10 36 34 164 184 238 64 70; do
      curl -s "https://cdn.bitrix24.com.br/b20668843/crm/form/loader_$id.js" \
           -o "loader_$id.js"
    done
    python ../../scripts/extrair_formularios_bitrix.py .

⚠️ ESTE SCRIPT NÃO FALA COM O NOSSO BANCO. Quem escreve nas tabelas é o
`scripts/carregar_formularios.py`, que lê o `mapa_bruto.json` gerado aqui.
A separação é de propósito: reobter do Bitrix e carregar no MoviZap são dois
atos, e o segundo tem de poder ser repetido sem a internet do primeiro.
"""
import collections
import json
import os
import sys

# Os 15 do `solicite.movisat.com.br`, na ordem em que foram levantados.
# ⚠️ O nome aqui é o APELIDO do levantamento, não o slug da nossa tabela --
# o slug nasce no `carregar_formularios.py`.
NOMES = {
    "30": "contato", "220": "demonstracao(LEAD)", "96": "teste-gratuito",
    "32": "suporte", "98": "ficha-cadastral", "14": "aditivo",
    "16": "substituicao", "10": "rescisao", "36": "adm", "34": "financeiro",
    "164": "credenciamento-tecnico", "184": "pagamento-tecnicos",
    "238": "fornecedores", "64": "NPS", "70": "CES",
}
ORDEM = ["30", "220", "96", "32", "98", "14", "16", "10", "36", "34", "164",
         "184", "238", "64", "70"]

MARCA = "window.b24form.Loader.run("


def do_loader(caminho: str) -> dict:
    """A config do `Loader.run(...)` de um arquivo de loader."""
    src = open(caminho, encoding="utf-8").read()
    i = src.index(MARCA) + len(MARCA)
    obj, _ = json.JSONDecoder().raw_decode(src[i:])
    return obj["form"]


def main(pasta: str) -> None:
    mapa = {}
    for fid in ORDEM:
        mapa[fid] = do_loader(os.path.join(pasta, f"loader_{fid}.js"))

    destino = os.path.join(pasta, "mapa_bruto.json")
    with open(destino, "w", encoding="utf-8") as f:
        json.dump(mapa, f, ensure_ascii=False, indent=1)

    tipos = collections.Counter()
    campos = 0
    for fid in ORDEM:
        dados = mapa[fid]["data"]
        flds = dados["fields"]
        campos += len(flds)
        regras = len(dados.get("dependencies") or [])
        print(f"[{fid}] {NOMES[fid]:<24} sec={mapa[fid]['sec']} "
              f"campos={len(flds):<3} regras={regras} "
              f"termo={'sim' if dados.get('agreements') else 'nao'}")
        for fl in flds:
            tipos[fl["type"]] += 1

    print(f"\n{len(ORDEM)} formularios, {campos} campos")
    for t, c in tipos.most_common():
        print(f"  {t:<16} {c}")
    print(f"\ngravado: {destino}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else ".")
