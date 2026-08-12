"""Gera a lista dos vinculos telefone-cliente que NAO entram no banco.

Decisao do usuario em 06/08: os duvidosos nao sobem, para nao sujar a base
nova.

⚠️ A VALIDACAO CASO A CASO FOI DESCARTADA em 12/08, e a pasta `revisao/` foi
apagada. A trava continua -- numero em disputa fica sem dono --, mas ninguem
vai revisar a lista. Este script vira ferramenta de diagnostico: roda quando
alguem quiser SABER quantos casos existem, nao para alimentar uma fila.

🚨 Este arquivo e GERADO. Nao editar a mao -- rode o script de novo. O sync
rele o Harmonit inteiro a cada 12h, entao a lista muda sozinha quando o
cadastro de la mudar.

Uso:  ./venv/bin/python scripts/listar_revisao.py   (imprime na tela)
"""
import re
import sys
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from movizap import harmonit, telefone  # noqa: E402
from movizap.config import silenciar_clientes_http  # noqa: E402

silenciar_clientes_http()

MARCAS = re.compile(r"\[N[ÃA]O\s*USAR\]|\(INATIVADO\)", re.I)
RUIDO = re.compile(
    r"\b(LTDA|ME|EPP|EIRELI|S/?A|SA|COMERCIO|COM|INDUSTRIA|IND|E|DE|DA|DO|DOS|"
    r"DAS|LOCACAO|LOCACOES|SOLUCOES|SERVICOS|TRANSPORTES?|MATRIZ|FILIAL)\b\.?", re.I)


def nucleo(nome):
    n = RUIDO.sub(" ", (nome or "").upper())
    return " ".join(re.sub(r"[^A-Z0-9 ]", " ", n).split())


def parecidos(a, b):
    na, nb = nucleo(a), nucleo(b)
    if not na or not nb:
        return False
    if na == nb or na in nb or nb in na:
        return True
    return SequenceMatcher(None, na, nb).ratio() >= 0.72


def data_de(c):
    """🚨 0001-01-01 e o vazio do .NET, nao uma data."""
    d = c.get("dataCadastro")
    if not d:
        return None
    try:
        dt = datetime.fromisoformat(str(d).replace("Z", "+00:00"))
    except ValueError:
        return None
    return None if dt.year < 1900 else dt


brutos = {}
for _p, lista in harmonit.paginar_clientes():
    for c in lista:
        brutos[str(c.get("id"))] = c

donos = {}
for k, v in brutos.items():
    cp = v.get("contatoPrincipal") or {}
    for campo in ("telefone", "telefone2", "celular"):
        parte = cp.get(campo) or {}
        if not str(parte.get("phone") or "").strip():
            continue
        a = telefone.de_partes(ddi=parte.get("ddi"), ddd=parte.get("ddd"),
                               numero=parte.get("phone"))
        if a:
            donos.setdefault(a.e164, set()).add(k)

compartilhados = {e: sorted(ks, key=int) for e, ks in donos.items() if len(ks) > 1}

resolvidos, revisar = [], []
for e164, ks in sorted(compartilhados.items()):
    nomes = {k: brutos[k].get("nome") or "" for k in ks}
    pares = [(i, j) for i in range(len(ks)) for j in range(i + 1, len(ks))]
    iguais = sum(1 for i, j in pares if parecidos(nomes[ks[i]], nomes[ks[j]]))
    (resolvidos if iguais == len(pares) else revisar).append((e164, ks, nomes))

hoje = datetime.now().strftime("%d/%m/%Y")
print(f"# Números compartilhados — o que ficou de fora do banco\n")
print(f"> **Gerado por `scripts/listar_revisao.py` em {hoje}.** Não editar a mão.")
print(f"> Regerar depois de qualquer mudança no cadastro do Harmonit.\n")
print("Decisão do usuário em 06/08: os casos duvidosos **não sobem**, para não")
print("sujar a base nova. Ficam aqui para validação caso a caso.\n")
print("🚨 **Nada foi apagado.** Estes vínculos continuam no Harmonit e entram")
print("na próxima sincronização assim que a regra mudar.\n")
print(f"| | |\n|---|---|")
print(f"| Números compartilhados | **{len(compartilhados)}** |")
print(f"| Resolvidos sozinho (mesmo cliente) | **{len(resolvidos)}** |")
print(f"| **Esperando você** | **{len(revisar)}** |")
print(f"| Vínculos que ficaram de fora | **{sum(len(k) for _e, k, _n in revisar)}** |\n")

print("---\n")
print("## Esperando validação\n")
print("Cada bloco é um número que **nenhum contato recebeu**. Diga qual cliente")
print("fica com ele — ou que são todos a mesma empresa.\n")

for e164, ks, nomes in revisar:
    print(f"### `{e164}` — {len(ks)} clientes\n")
    print("| Id | Cadastrado | Situação | Nome |")
    print("|---|---|---|---|")
    for k in sorted(ks, key=lambda x: (data_de(brutos[x]) or datetime.max, int(x))):
        d = data_de(brutos[k])
        quando = f"{d:%d/%m/%Y}" if d else "*sem data*"
        marca = " 🚩" if MARCAS.search(nomes[k]) else ""
        situacao = "ativo" if brutos[k].get("ativo") else "**inativo**"
        print(f"| `{k}` | {quando} | {situacao} | {nomes[k]}{marca} |")
    print()

print("---\n")
print("## Resolvidos sozinho — o mesmo cliente, cadastrado mais de uma vez\n")
print("Aqui o número **entrou**, no cadastro mais antigo. Os demais não o receberam.\n")
for e164, ks, nomes in resolvidos:
    ordenados = sorted(ks, key=lambda x: (data_de(brutos[x]) or datetime.max, int(x)))
    dono = ordenados[0]
    d = data_de(brutos[dono])
    quando = f"{d:%d/%m/%Y}" if d else "sem data"
    print(f"- `{e164}` → **`{dono}`** {nomes[dono]} ({quando}) "
          f"· descartados: {', '.join('`' + k + '`' for k in ordenados[1:])}")

print("\n---\n")
print("## 🚩 Marcados `[NÃO USAR]` / `(INATIVADO)`\n")
marcados = {k: v for k, v in brutos.items() if MARCAS.search(v.get("nome") or "")}
print(f"{len(marcados)} clientes. **Descartá-los não resolve nenhum** dos números")
print("acima — é problema separado.\n")
print("| Id | Situação | Nome |\n|---|---|---|")
for k, v in sorted(marcados.items(), key=lambda x: int(x[0])):
    situacao = "ativo" if v.get("ativo") else "**inativo**"
    print(f"| `{k}` | {situacao} | {v.get('nome')} |")
