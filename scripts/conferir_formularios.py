"""Confere os formulários carregados ANTES de alguém os ligar. SÓ LEITURA.

🚨 POR QUE ISTO EXISTE. Ligar um formulário é abrir uma porta para a internet,
e um defeito de definição só aparece quando um cliente real fica preso numa
tela que não deixa enviar. Este script tenta PREENCHER cada formulário como
gente preencheria -- em voltas, porque escolher uma opção faz nascer campo
novo -- e diz quais passam e quais travam.

O que ele mede, formulário por formulário:

  1. a contagem de campos bate com `dados/formularios_bitrix/mapa_bruto.json`;
  2. o `nosso_nome` é único e legível (sem o lixo `uf-crm` do nome de origem);
  3. 🚨 o formulário É ENVIÁVEL: preenchendo todos os campos de pé, a
     validação do servidor aceita. E tenta UMA VEZ POR OPÇÃO do primeiro campo
     de lista, que nos 15 é sempre o gatilho (pessoa física/jurídica, tipo de
     solicitação) -- é por ali que nascem os campos escondidos;
  4. campo obrigatório que NENHUMA regra alcança, se houver: seria um
     formulário impossível de enviar;
  5. quanto de `file` e de `product` cada um tem (o `product` vira texto nesta
     etapa, e é bom saber onde).

Uso:  venv/bin/python scripts/conferir_formularios.py
      venv/bin/python scripts/conferir_formularios.py --nomes CREDENCIAMENTO

⚠️ `--nomes` imprime, campo por campo, o nome de ORIGEM e o `nosso_nome`
derivado do rótulo. É a lista para ELE revisar: dar nome humano aos 239 é o
maior trabalho manual desta etapa, e o derivado é rascunho. A lista sai do
BANCO, não de um documento à parte -- documento com 239 linhas copiadas
envelhece na primeira troca de nome.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, "/home/claude/movizap_painel")

from movizap import banco, formularios  # noqa: E402
from movizap.operacao import DadoInvalido  # noqa: E402

RAIZ = Path("/home/claude/movizap_painel")
MAPA = json.loads((RAIZ / "dados" / "formularios_bitrix" / "mapa_bruto.json")
                  .read_text(encoding="utf-8"))


def valor_de(campo: dict) -> str:
    """Um valor plausível do TIPO certo. ⚠️ "zz valor" em campo `double` (o
    CNPJ do Bitrix é `double`) reprovaria no código certo."""
    if campo["tipo"] == "list":
        return str(campo["opcoes"][0]["value"]) if campo["opcoes"] else ""
    if campo["tipo"] == "double":
        return "12345678000199"
    if campo["tipo"] == "date":
        return "2026-10-22"
    if campo["tipo"] == "email":
        return "conferencia@movisat.com.br"
    if campo["tipo"] == "phone":
        return "+5518998116168"
    return "conferencia"


def preencher(d: dict, escolhas: dict | None = None) -> dict:
    """Preenche em VOLTAS, como gente: opção escolhida faz nascer campo novo."""
    valores = dict(escolhas or {})
    for _ in range(len(d["regras"]) + 3):
        de_pe = formularios.visiveis(d, valores)
        antes = len(valores)
        for c in d["campos"]:
            if c["nome"] in valores or c["nome"] not in de_pe:
                continue
            if c["tipo"] in formularios.TIPOS_DECORATIVOS or c["tipo"] == "file":
                continue
            valores[c["nome"]] = valor_de(c)
        if len(valores) == antes:
            break
    return valores


def anexos_de(d: dict, valores: dict) -> dict:
    de_pe = formularios.visiveis(d, valores)
    return {c["nome"]: [{"nome_original": "conferencia.pdf"}]
            for c in d["campos"]
            if c["tipo"] == "file" and c["obrigatorio"] and c["nome"] in de_pe}


def nomes(codigo: str) -> None:
    """O de-para de nomes de um formulário, para ele revisar."""
    banco.abrir()
    linha = banco.um("SELECT slug, codigo FROM formulario WHERE codigo = %s",
                     (codigo.upper(),))
    if not linha:
        sys.exit(f"nao achei o formulario {codigo!r}")
    d = formularios.definicao(linha["slug"], so_ativo=False)
    print(f"{linha['codigo']} -- /f/{linha['slug']}")
    print()
    print(f"{'nosso_nome':<44} {'tipo':<14} obrig  rotulo")
    for c in d["campos"]:
        if c["tipo"] in formularios.TIPOS_DECORATIVOS:
            continue
        print(f"{c['nosso_nome']:<44} {c['tipo']:<14} "
              f"{'sim' if c['obrigatorio'] else '   '}    {c['rotulo']}")
        print(f"{'  origem: ' + c['nome']:<44}")


def main() -> None:
    banco.abrir()
    linhas = banco.varios(
        "SELECT codigo, slug, bitrix_id, ativo FROM formulario ORDER BY ordem")
    if not linhas:
        sys.exit("nenhum formulario carregado -- rode scripts/carregar_formularios.py")

    problemas: list[str] = []
    for linha in linhas:
        d = formularios.definicao(linha["slug"], so_ativo=False)
        campos = d["campos"]
        esperado = MAPA[linha["bitrix_id"]]["data"]["fields"]

        if len(campos) != len(esperado):
            problemas.append(f"{linha['codigo']}: {len(campos)} campos no banco "
                             f"e {len(esperado)} no mapa")

        nomes = [c["nosso_nome"] for c in campos]
        if len(nomes) != len(set(nomes)):
            problemas.append(f"{linha['codigo']}: `nosso_nome` repetido")
        ilegiveis = [n for n in nomes if "uf-crm" in n or n.startswith("campo")]
        if ilegiveis:
            problemas.append(f"{linha['codigo']}: nome ilegivel {ilegiveis}")

        gatilhos = [c for c in campos if c["tipo"] == "list" and c["opcoes"]]
        tentativas = [{}]
        if gatilhos:
            primeiro = gatilhos[0]
            tentativas = [{primeiro["nome"]: str(o["value"])}
                          for o in primeiro["opcoes"]]

        travados = []
        for escolha in tentativas:
            valores = preencher(d, escolha)
            try:
                formularios.validar(d, valores, anexos_de(d, valores))
            except DadoInvalido as e:
                travados.append(f"{escolha or '(sem escolha)'} -> {e}")

        de_pe_sempre = formularios.visiveis(d, {})
        alcancaveis = set(de_pe_sempre)
        for regra in d["regras"]:
            for item in (regra["lista"] or []):
                if (item.get("action") or {}).get("type") == "show":
                    alcancaveis.add(item["action"]["target"])
        orfaos = [c["nome"] for c in campos
                  if c["obrigatorio"] and c["nome"] not in alcancaveis
                  and c["tipo"] not in formularios.TIPOS_DECORATIVOS]
        if orfaos:
            problemas.append(f"{linha['codigo']}: obrigatorio que nenhuma regra "
                             f"alcanca: {orfaos}")

        arquivos = sum(1 for c in campos if c["tipo"] == "file")
        produtos = sum(1 for c in campos if c["tipo"] == "product")
        print(f"{linha['codigo']:<20} {len(campos):>3} campos · "
              f"{len(de_pe_sempre):>2} de pe no inicio · "
              f"{len(d['regras'])} regra(s) · {arquivos} arquivo(s) · "
              f"{produtos} produto(s) · "
              f"{len(tentativas)} caminho(s) testado(s) · "
              f"{'ENVIAVEL' if not travados else 'TRAVA'} · "
              f"{'ligado' if linha['ativo'] else 'desligado'}")
        for t in travados:
            print(f"    🔴 {t}")
            problemas.append(f"{linha['codigo']}: {t}")

    print()
    if problemas:
        print(f"🔴 {len(problemas)} problema(s):")
        for p in problemas:
            print(f"  - {p}")
        sys.exit(1)
    print("✅ os 15 batem com o mapa, têm nome legível e são enviáveis")


if __name__ == "__main__":
    if len(sys.argv) > 2 and sys.argv[1] == "--nomes":
        nomes(sys.argv[2])
    else:
        main()
