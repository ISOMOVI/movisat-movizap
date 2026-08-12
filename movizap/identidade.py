"""De quem é o número — a regra medida em `docs/08_Identidade.md`.

Vive em módulo próprio porque **três lugares precisam da mesma resposta**: o
sync, o gerador da lista de revisão e, no futuro, a IA quando perguntar de qual
empresa a pessoa fala. Heurística duplicada é heurística que diverge.

🚨 A REGRA, EM UMA FRASE: quando um número está em mais de um cliente, ele só
entra no banco se **todos** aqueles cadastros forem a mesma empresa. Se houver
qualquer dúvida, **ninguém** recebe o número e o caso vai para revisão.

Por quê, medido em 06/08 contra 1.050 clientes reais:

  (a) mesmo cliente cadastrado várias vezes : 12 números
  (b) empresas genuinamente diferentes      : 20 números
  (c) misto -- grupo econômico + terceiro   : 12 números

"O mais antigo fica" acerta (a) e chuta (b) e (c). E o chute produz ficha
errada na tela do atendente, que é pior que ficha nenhuma.
"""
import re
from datetime import datetime
from difflib import SequenceMatcher

# Marca que o próprio Harmonit usa para dizer "este cadastro morreu".
MARCAS_REVISAO = re.compile(r"\[N[ÃA]O\s*USAR\]|\(INATIVADO\)", re.I)

# Sufixo societário e palavra de ramo não distinguem empresa: `FAXT
# TELECOMUNICACOES LTDA.` e `FAXT TELECOMUNICACOES LTDA` são a mesma.
_RUIDO = re.compile(
    r"\b(LTDA|ME|EPP|EIRELI|S/?A|SA|COMERCIO|COM|INDUSTRIA|IND|E|DE|DA|DO|DOS|"
    r"DAS|LOCACAO|LOCACOES|SOLUCOES|SERVICOS|TRANSPORTES?|MATRIZ|FILIAL)\b\.?",
    re.I)

SEMELHANCA_MINIMA = 0.72


def nucleo(nome: str) -> str:
    """O que sobra do nome depois de tirar o que não distingue empresa."""
    limpo = _RUIDO.sub(" ", (nome or "").upper())
    return " ".join(re.sub(r"[^A-Z0-9 ]", " ", limpo).split())


def mesma_empresa(a: str, b: str) -> bool:
    """⚠️ Heurística, e heurística erra.

    Por isso ela só decide o caso fácil: quando TODOS os nomes de um grupo se
    parecem. Qualquer mistura cai em revisão. Errar para mais custa uma linha
    a revisar; errar para menos põe a ficha errada na frente do atendente.
    """
    na, nb = nucleo(a), nucleo(b)
    if not na or not nb:
        return False
    if na == nb or na in nb or nb in na:
        return True
    return SequenceMatcher(None, na, nb).ratio() >= SEMELHANCA_MINIMA


def data_cadastro(bruto: dict) -> datetime | None:
    """`dataCadastro` do Harmonit, ou None quando ele não sabe.

    🚨 `0001-01-01T00:00:00` é o vazio do .NET, não uma data. Ele parseia sem
    erro e vira o ano 1 -- gravado como data, o registro SEM data ganharia
    toda disputa de antiguidade, e a regra ficaria invertida sem nada acusar.
    """
    valor = bruto.get("dataCadastro")
    if not valor:
        return None
    try:
        quando = datetime.fromisoformat(str(valor).replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None
    return None if quando.year < 1900 else quando


def motivo_de_revisao(bruto: dict) -> str | None:
    """Por que este cadastro precisa de olho humano. None = não precisa."""
    achado = MARCAS_REVISAO.search(bruto.get("nome") or "")
    return f"nome marcado: {achado.group(0)}" if achado else None


def _antiguidade(bruto: dict) -> tuple:
    """Chave de ordenação. Quem não tem data perde o desempate."""
    quando = data_cadastro(bruto)
    return (quando or datetime.max, int(bruto.get("id") or 0))


def decidir_donos(brutos: dict, telefones_por_cliente: dict) -> tuple[dict, dict]:
    """Quem fica com cada número compartilhado.

    `brutos`                 {harmonit_id: cliente}
    `telefones_por_cliente`  {harmonit_id: {e164, ...}}

    Devolve `(donos, em_revisao)`:
      donos      {e164: harmonit_id}  -- só os que têm dono definido
      em_revisao {e164: motivo}       -- ninguém recebe, alguém precisa olhar
    """
    candidatos: dict[str, list[str]] = {}
    for harmonit_id, numeros in telefones_por_cliente.items():
        for e164 in numeros:
            candidatos.setdefault(e164, []).append(harmonit_id)

    donos: dict[str, str] = {}
    em_revisao: dict[str, str] = {}

    for e164, ids in candidatos.items():
        if len(ids) == 1:
            donos[e164] = ids[0]
            continue

        nomes = [brutos[i].get("nome") or "" for i in ids if i in brutos]
        todos_iguais = all(
            mesma_empresa(nomes[i], nomes[j])
            for i in range(len(nomes)) for j in range(i + 1, len(nomes))
        )
        if todos_iguais:
            # (a) o mesmo cliente cadastrado várias vezes: o número é dele.
            donos[e164] = min(ids, key=lambda i: _antiguidade(brutos[i]))
        else:
            # (b) e (c): ninguém recebe -- ver docs/08_Identidade.md.
            # A pasta revisao/ foi apagada em 12/08: o relatório saiu, a
            # trava ficou. Ninguém valida esses casos caso a caso.
            em_revisao[e164] = f"{len(ids)} clientes distintos disputam o número"

    return donos, em_revisao
