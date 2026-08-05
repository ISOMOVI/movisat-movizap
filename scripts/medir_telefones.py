"""Mede QUANTOS clientes do Harmonit tem telefone de verdade.

Nao imprime nenhum numero -- so contagem e percentual. A pergunta e "a base
de contatos pode sair daqui?", e ela se responde com taxa de preenchimento.

🚨 Metodologia, item 6: a assercao precisa detectar VALOR CONSTANTE, nao so
NULL. Por isso conta tambem quantos valores DISTINTOS existem: um campo
preenchido com o mesmo numero em 100% das linhas nao e telefone, e defeito.

Uso:  ./venv/bin/python medir_telefones.py [quantidade]
"""
import asyncio
import sys
from collections import Counter

sys.path.insert(0, "/home/claude/fpsl_weso")
from fpsl_weso import harmonit_client as hc  # noqa: E402

ALVO = int(sys.argv[1]) if len(sys.argv) > 1 else 300
PAGINA = 100


def numero(bloco):
    """Junta ddd+phone. Devolve '' se nao houver numero utilizavel."""
    if not isinstance(bloco, dict):
        return ""
    ddd = (bloco.get("ddd") or "").strip()
    fone = (bloco.get("phone") or "").strip()
    return f"{ddd}{fone}" if fone else ""


async def main():
    await hc.start_harmonit_client()
    registros = []
    try:
        skip = 0
        while len(registros) < ALVO:
            r = await hc.harmonit_get("/ObterClientes", {"skip": skip, "take": PAGINA})
            lote = r.get("lista") if isinstance(r, dict) else None
            if not isinstance(lote, list) or not lote:
                break
            registros.extend(lote)
            skip += PAGINA
    finally:
        await hc.stop_harmonit_client()

    total = len(registros)
    if not total:
        print("nenhum registro lido")
        return

    campos = {"telefone": [], "telefone2": [], "celular": []}
    com_algum = 0
    emails = 0

    for reg in registros:
        cp = reg.get("contatoPrincipal") or {}
        achou = False
        for nome in campos:
            n = numero(cp.get(nome))
            if n:
                campos[nome].append(n)
                achou = True
        if achou:
            com_algum += 1
        if (cp.get("email") or "").strip():
            emails += 1

    print(f"Amostra: {total} clientes de /ObterClientes\n")
    print(f"{'campo':<14} {'preenchidos':>12} {'%':>7} {'distintos':>10}")
    for nome, valores in campos.items():
        n = len(valores)
        d = len(set(valores))
        print(f"{nome:<14} {n:>12} {n/total*100:>6.1f}% {d:>10}")

    print(f"\ncom ALGUM telefone: {com_algum} ({com_algum/total*100:.1f}%)")
    print(f"com e-mail:         {emails} ({emails/total*100:.1f}%)")

    todos = [v for lista in campos.values() for v in lista]
    if todos:
        distintos = len(set(todos))
        print(f"\nnumeros distintos: {distintos} de {len(todos)} preenchidos")
        if distintos < len(todos) * 0.5:
            print("🚨 muita repeticao -- pode ser telefone da Movisat, nao do cliente")
        mais = Counter(todos).most_common(1)[0]
        if mais[1] > total * 0.1:
            print(f"🚨 um mesmo numero aparece {mais[1]}x ({mais[1]/total*100:.0f}%)"
                  " -- suspeito de valor padrao")

    # Comprimento ajuda a ver se e fixo ou celular, sem revelar o numero
    if todos:
        comp = Counter(len(v) for v in todos)
        print("\ncomprimento (ddd+numero):",
              ", ".join(f"{k} digitos: {v}" for k, v in sorted(comp.items())))
        print("  10 = fixo com ddd · 11 = celular com nono digito")


asyncio.run(main())
