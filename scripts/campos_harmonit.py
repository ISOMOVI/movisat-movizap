"""Descobre QUAIS CAMPOS o /ObterClientes do Harmonit devolve.

Le 1 registro (validar 1 antes do lote) e imprime SO OS NOMES das chaves --
nunca os valores. Dado de cliente nao precisa aparecer em log para responder
"a API tem telefone?".

Uso:  ./venv/bin/python campos_harmonit.py
"""
import asyncio
import sys

sys.path.insert(0, "/home/claude/fpsl_weso")
from fpsl_weso import harmonit_client as hc  # noqa: E402


def achatar(prefixo, valor, saida):
    """Percorre o objeto e registra o CAMINHO de cada campo, com o tipo."""
    if isinstance(valor, dict):
        for k, v in valor.items():
            achatar(f"{prefixo}.{k}" if prefixo else k, v, saida)
    elif isinstance(valor, list):
        saida.append((f"{prefixo}[]", f"lista de {len(valor)}"))
        if valor:
            achatar(f"{prefixo}[0]", valor[0], saida)
    else:
        preenchido = "com valor" if valor not in (None, "", 0) else "vazio"
        saida.append((prefixo, f"{type(valor).__name__}, {preenchido}"))


async def main():
    await hc.start_harmonit_client()
    try:
        r = await hc.harmonit_get("/ObterClientes", {"skip": 0, "take": 1})
    finally:
        await hc.stop_harmonit_client()

    # 🚨 O Harmonit responde "encontrado" como list e "nao encontrado" como
    # dict truthy. Checar o TIPO, nao a veracidade.
    dados = (r.get("lista") or r.get("data")) if isinstance(r, dict) else r
    if isinstance(dados, dict):
        dados = dados.get("items") or dados.get("data") or dados
    if isinstance(dados, list):
        if not dados:
            print("resposta VAZIA (nao e erro -- a numeracao tem buracos)")
            return
        registro = dados[0]
    elif isinstance(dados, dict):
        registro = dados
    else:
        print(f"formato inesperado: {type(dados).__name__}")
        print("chaves do envelope:", list(r.keys()) if isinstance(r, dict) else "-")
        return

    campos = []
    achatar("", registro, campos)

    print(f"{len(campos)} campo(s) em /ObterClientes:\n")
    for caminho, tipo in campos:
        marca = "  "
        baixo = caminho.lower()
        if any(t in baixo for t in ("fone", "tel", "celul", "whats", "contato")):
            marca = "->"
        print(f"  {marca} {caminho:<44} {tipo}")

    print()
    telefones = [c for c, _ in campos
                 if any(t in c.lower() for t in ("fone", "tel", "celul", "whats"))]
    if telefones:
        print("TEM TELEFONE:", ", ".join(telefones))
    else:
        print("NAO HA CAMPO DE TELEFONE em /ObterClientes.")
        print("Se o Harmonit guarda telefone, esta em outro endpoint.")


asyncio.run(main())
