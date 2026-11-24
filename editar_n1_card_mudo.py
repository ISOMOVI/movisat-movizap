# -*- coding: utf-8 -*-
"""N1, a parte que SOBROU depois do card nascer: o card era MUDO.

🔵 ELE, sobre o formulário de pagamento: *"deveria estar gerando já os dados"*.

🚨 MEDIDO EM 23/11, enviando um teste de verdade pela internet (solicitação
5990, card 4051 na etapa 875): **o mecanismo está inteiro e o card nasce em
14 ms**. As 13 respostas chegam no payload do card. E, apesar disso, o card no
quadro **não mostra nenhuma delas** -- porque `cards_da_aba` nunca devolveu
`resumo`, e é `card.resumo` que o `CorpoDoCard` desenha.

🚨 E NÃO É RECURSO NOVO: os outros painéis (Operação e Financeiro aba 1) já
mostram esse resumo, pelo `paineis._resumo`. O quadro de aba era o único sem
ele. Então aqui não se inventa régua nenhuma -- chama-se a MESMA função, para
não nascer um segundo resumo com outra regra.

⚠️ O QUE ISTO NÃO FAZ, e é decisão dele: **quais dos 16 campos viram quais
campos do card** continua desenho que ele não disse. O `_resumo` mostra as duas
primeiras respostas de texto, que é a régua que a casa já usa nos outros
painéis (*"card não é ficha"*). Se ele quiser campos escolhidos a dedo -- por
exemplo nº do orçamento e valor total --, é uma decisão dele e uma linha a mais.

⚠️ Import LOCAL, de propósito: `paineis` importa `pipeline`, então importar
`paineis` no topo daqui seria ciclo. É o mesmo padrão que o `main.py` já usa
para o `json` dentro das rotas de multipart.
"""
import pathlib

p = pathlib.Path("movizap/pipeline.py")
bruto = p.read_bytes()
CRLF = b"\r\n" in bruto
t = bruto.decode("utf-8").replace("\r\n", "\n")


def troca(velho, novo, rotulo):
    global t
    assert velho in t, "NAO ACHOU (%s)" % rotulo
    assert t.count(velho) == 1, "AMBIGUO %dx (%s)" % (t.count(velho), rotulo)
    t = t.replace(velho, novo, 1)
    print("  ok:", rotulo)


troca('''    ⚠️ **UMA consulta para a aba toda**, como o `quantas_observacoes` faz: uma
    por card seriam N idas ao banco por abertura de tela.
    """
    return banco.varios(''',
      '''    ⚠️ **UMA consulta para a aba toda**, como o `quantas_observacoes` faz: uma
    por card seriam N idas ao banco por abertura de tela.

    🚨 **O `resumo` ENTROU EM 23/11, e o card era MUDO sem ele.** Medido
    enviando um teste de verdade no `pagamento-tecnicos` (solicitação 5990,
    card 4051): as 13 respostas vinham no payload e a tela não mostrava
    nenhuma, porque `CorpoDoCard` desenha `card.resumo` e esta consulta nunca
    devolveu esse campo. Os outros painéis já tinham o resumo (`paineis._resumo`
    em três lugares); o quadro de aba era o único sem.
    """
    linhas = banco.varios(''',
      "1. a consulta deixa de ser o retorno direto")

troca('''            WHERE c.aba_id = %s
            ORDER BY (c.desfecho IS NOT NULL), c.criado_em DESC, c.id DESC
            LIMIT %s""", (int(aba_id), int(teto)))''',
      '''            WHERE c.aba_id = %s
            ORDER BY (c.desfecho IS NOT NULL), c.criado_em DESC, c.id DESC
            LIMIT %s""", (int(aba_id), int(teto)))

    # 🚨 A MESMA FUNÇÃO DOS OUTROS PAINÉIS, e não uma segunda régua: o resumo
    # é "as duas primeiras respostas de texto", decisão já tomada (*"card não
    # é ficha"*). Escrever outra aqui faria o mesmo card ter dois resumos
    # diferentes dependendo da tela que o abre.
    #
    # ⚠️ Import local: `paineis` importa `pipeline`, então no topo seria ciclo.
    from .paineis import _resumo
    for linha in linhas:
        # ⚠️ `None` quando não há resposta nenhuma, nunca string vazia: o
        # `v-if` do card não desenha o parágrafo, em vez de desenhar um vazio.
        linha["resumo"] = _resumo(linha.get("valores")) or None
    return linhas''',
      "2. o resumo entra em cada card")

saida = t.replace("\n", "\r\n") if CRLF else t
p.write_bytes(saida.encode("utf-8"))
print("gravado:", p, len(saida), "bytes")
