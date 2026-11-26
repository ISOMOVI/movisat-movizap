# -*- coding: utf-8 -*-
"""A FONTE ÚNICA do CSS dos painéis — v2, 25/11. Agora com os valores À MÃO.

🚨 **POR QUE A v1 NÃO SERVIU, e é lição:** eu deixei a ESCOLHA dos valores para
uma regra de prioridade por arquivo, e ela elegeu justamente os corpos errados
— o `card__abrir` ficou com o da aba 2 (com sombra e borda forte) em vez do
`CorpoDoCard`, e o cabeçalho não pareou com o da Operação porque ela chama a
classe por outro nome. O parser por regex também perdia blocos cujo comentário
tem `{`. **Escolha de desenho não se delega a uma heurística.**

Nesta versão:
- os comentários saem ANTES de parsear, e os blocos são lidos com contador de
  chaves (não regex);
- as classes que ele reclamou têm o corpo **escrito à mão aqui**, declarado;
- o resto é unido por prioridade, e o relatório diz quem venceu.
"""
import pathlib
import re
import shutil
import sys
from datetime import datetime

RAIZ = pathlib.Path("/home/claude/movizap_painel/frontend/src")
SAIDA = RAIZ / "estilo" / "painel.css"

ABA1 = "telas/PainelAba.vue"
CORPO = "componentes/CorpoDoCard.vue"
ABA2 = "telas/PainelServicoDosTecnicos.vue"
OPER = "telas/PainelOperacao.vue"
ARQUIVOS = [ABA1, CORPO, ABA2, OPER]

# ===========================================================================
# 1. O QUE EU ESCOLHI À MÃO — e por quê. É a parte que não se delega.
# ===========================================================================
CANON = {
    # 🔵 *"os cards fechados na aba1 do financeiro ja tem o modelo ideal"*:
    # este é o corpo do `CorpoDoCard`, com o `width: 100%` e o `text-align`
    # que o botão precisa. SAI a sombra e SAI a `--borda-forte` da aba 2.
    ".card__abrir": """display: flex;
  flex-direction: column;
  gap: var(--e-1);
  width: 100%;
  padding: var(--e-2) var(--e-3);
  background: var(--superficie);
  border: var(--borda-fina) solid var(--borda);
  border-left: 3px solid transparent;
  border-radius: var(--r-md);
  text-align: left;
  cursor: pointer;""",
    # ⚠️ O realce do hover é o MESMO nas três: era sombra numa e nada nas
    # outras. Borda de acento diz "clicável" sem mudar a altura da linha.
    ".card__abrir:hover": """border-color: var(--acento);""",

    # 🔵 *"a proporção e posição dos cabeçalhos tbm está divergindo"*: UM
    # arranjo para as três telas. A identidade é EM LINHA (título e ajuda lado
    # a lado), que é o que ele aprovou no mockup de hoje; a Operação tinha em
    # coluna e passa a ser igual.
    ".painel__topo": """display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: var(--e-3);""",
    ".painel__identidade": """display: flex;
  align-items: center;
  gap: var(--e-2);
  min-width: 0;""",
    ".painel__medidas": """display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--e-2);""",
    ".painel__titulo": """margin: 0;
  font-size: var(--txt-lg);""",

    # 🚨 A PÍLULA ERA DUAS COISAS COM O MESMO NOME: com borda e peso normal no
    # card da aba 1, sem borda e em negrito no topo. Fica a do card (com
    # borda), que é o modelo ideal, e o `align-self` que o topo precisava.
    ".pilula": """display: inline-flex;
  align-items: center;
  gap: var(--e-1);
  align-self: flex-start;
  padding: 1px var(--e-2);
  border: var(--borda-fina) solid var(--borda);
  border-radius: var(--r-full);
  background: var(--superficie-2);
  color: var(--texto-fraco);
  font-size: var(--txt-xs);""",
    # O selo é a MESMA forma da pílula: eram a mesma ideia com dois nomes, e
    # duas formas diferentes para a mesma ideia é o que faz a aba 2 parecer
    # outra tela.
    ".selo": """display: inline-flex;
  align-items: center;
  gap: var(--e-1);
  padding: 1px var(--e-2);
  border: var(--borda-fina) solid var(--borda);
  border-radius: var(--r-full);
  font-size: var(--txt-xs);
  color: var(--texto-fraco);""",
}

# Pares de nomes que significam a mesma coisa (abas / Operação).
PARES = {".painel__topo": ".tela__cabecalho",
         ".painel__identidade": ".cabecalho__identidade",
         ".painel__medidas": ".cabecalho__controles"}

PRIORIDADE = {"card": [CORPO, ABA2, ABA1, OPER],
              "cabecalho": [OPER, ABA2, ABA1, CORPO],
              "resto": [ABA2, ABA1, CORPO, OPER]}

FAMILIA = {
    "cabecalho": [".painel__topo", ".tela__cabecalho", ".painel__identidade",
                  ".cabecalho__identidade", ".painel__medidas",
                  ".cabecalho__controles", ".painel__titulo"],
    "card": [".card", ".card__abrir", ".card__abrir:hover", ".card__linha",
             ".card__cliente", ".card__cliente--sem", ".card__direita",
             ".card__direita--dado", ".card__dado", ".card__ident",
             ".card__os", ".card__termo", ".card__resumo"],
    "resto": [".painel", ".painel__casco", ".painel__quadro", ".coluna",
              ".coluna--vazia", ".coluna__titulo", ".coluna__botao",
              ".coluna__nome", ".coluna__conta", ".coluna__conta--zero",
              ".coluna__corpo", ".abas", ".abas__item", ".abas__item--atual",
              ".controles", ".controles__busca", ".controles__ordem",
              ".pilula", ".selo", ".selo--verde", ".selo--amarelo",
              ".selo--laranja", ".selo--vermelho", ".acoes", ".acoes__grupo",
              ".acoes__titulo", ".acoes__grade", ".acao", ".acao__nome",
              ".acao__nota", ".acao--principal", ".acao--perigo",
              ".card__rodape", ".card__acoes"],
}
TODOS = {s for lista in FAMILIA.values() for s in lista}


def partes(nome: str):
    texto = (RAIZ / nome).read_text(encoding="utf-8")
    m = re.search(r"(<style[^>]*>)(.*)(</style>)", texto, re.S)
    if not m:
        raise SystemExit(f"nao achei <style> em {nome}")
    return texto[:m.start(2)], m.group(2), texto[m.end(2):]


def blocos(css: str):
    """(seletores, corpo, texto_inteiro) de cada regra de 1º nível.

    ⚠️ Comentários saem antes: a prosa desta casa tem `{` e `}` dentro, e foi
    isso que fez o parser da v1 perder blocos.
    """
    limpo = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    saida, i, n = [], 0, len(limpo)
    while i < n:
        j = limpo.find("{", i)
        if j < 0:
            break
        sel = limpo[i:j].strip()
        nivel, k = 1, j + 1
        while k < n and nivel:
            if limpo[k] == "{":
                nivel += 1
            elif limpo[k] == "}":
                nivel -= 1
            k += 1
        corpo = limpo[j + 1:k - 1]
        if sel and not sel.startswith("@"):
            saida.append(([s.strip() for s in sel.split(",")], corpo,
                          limpo[i:k]))
        i = k
    return saida


def props(corpo: str) -> dict:
    fora = {}
    for parte in corpo.split(";"):
        if ":" in parte:
            nome, _, valor = parte.partition(":")
            if nome.strip():
                fora[nome.strip()] = valor.strip()
    return fora


def main() -> int:
    achados: dict = {}
    for nome in ARQUIVOS:
        for sels, corpo, inteiro in blocos(partes(nome)[1]):
            if len(sels) != 1 or sels[0] not in TODOS:
                continue
            achados.setdefault(sels[0], {})[nome] = (props(corpo), inteiro)

    faltando = [s for s in CANON if s not in achados]
    if faltando:
        print(f"AVISO: nao achei nos arquivos: {faltando}", file=sys.stderr)

    grupo_de = {s: g for g, lista in FAMILIA.items() for s in lista}
    regras, relatorio = {}, []
    for sel, porArquivo in achados.items():
        if sel in CANON:
            regras[sel] = CANON[sel]
            relatorio.append(f"  {sel:<26} À MÃO (estava em {len(porArquivo)})")
            continue
        ordem = [a for a in PRIORIDADE[grupo_de[sel]] if a in porArquivo]
        base = dict(porArquivo[ordem[0]][0])
        unidas = []
        for outro in ordem[1:]:
            for p, v in porArquivo[outro][0].items():
                if p not in base:
                    base[p] = v
                    unidas.append(f"{p}←{pathlib.Path(outro).stem}")
        regras[sel] = "\n  ".join(f"{p}: {v};" for p, v in base.items())
        relatorio.append(
            f"  {sel:<26} {pathlib.Path(ordem[0]).stem:<26} "
            f"(em {len(porArquivo)}) {' '.join(unidas)}")

    # os nomes da Operação herdam o corpo do par
    for a, b in PARES.items():
        if a in regras:
            regras.setdefault(b, None)

    linhas = [CABECA]
    for grupo, titulo in (("cabecalho", "O CABEÇALHO — um arranjo para as três"),
                          ("card", "O CARD — o modelo da aba 1"),
                          ("resto", "COLUNA · ABAS · CONTROLES · PÍLULA · "
                                    "SELO · QUADROS DE AÇÃO")):
        linhas.append(f"\n/* {'=' * 72}\n   {titulo}\n   {'=' * 72} */")
        feitos = set()
        for sel in FAMILIA[grupo]:
            if sel in feitos or regras.get(sel) is None:
                continue
            alvos = [sel]
            if sel in PARES:
                alvos.append(PARES[sel])
            feitos.update(alvos)
            sels = ",\n".join(f".escala-operacao {s}" for s in alvos)
            linhas.append(f"{sels} {{\n  {regras[sel]}\n}}")

    linhas.append("""
/* ⚠️ A ÚNICA diferença que fica, e é de contexto, não de forma: nas abas o
   `.painel` é uma coluna `flex` com `gap`, e o cabeçalho não precisa de margem;
   na Operação ele não está numa coluna, então a margem é dele. */
.escala-operacao .tela__cabecalho { margin-bottom: var(--e-4); }""")

    SAIDA.write_text("\n".join(linhas) + "\n", encoding="utf-8")

    marca = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    for nome in ARQUIVOS:
        antes, miolo, depois = partes(nome)
        novo, tirados = miolo, 0
        for sel, porArquivo in achados.items():
            if nome not in porArquivo:
                continue
            # 🚨 Remove pelo bloco SEM comentário: acha o seletor no texto
            # original e corta do seletor até a chave que fecha.
            alvo_sel = re.escape(sel)
            m = re.search(rf"(?m)^\s*{alvo_sel}\s*(,[^{{]*)?\{{", novo)
            if not m:
                continue
            k, nivel = m.end(), 1
            while k < len(novo) and nivel:
                if novo[k] == "{":
                    nivel += 1
                elif novo[k] == "}":
                    nivel -= 1
                k += 1
            novo = novo[:m.start()] + novo[k:]
            tirados += 1
        alvo = RAIZ / nome
        shutil.copy2(alvo, alvo.with_suffix(alvo.suffix + f".bak_{marca}_fonte_unica2"))
        alvo.write_text(antes + novo + depois, encoding="utf-8")
        print(f"{pathlib.Path(nome).stem}: {tirados} blocos movidos")

    print(f"\n{SAIDA} escrito com "
          f"{len([s for s in regras if regras[s] is not None])} regras")
    print("\n== quem decidiu cada classe ==")
    print("\n".join(sorted(relatorio)))
    return 0


CABECA = '''/*
 * A FONTE ÚNICA DO CSS DOS PAINÉIS — 25/11/2026
 * ============================================================================
 * 🔵 Ele, olhando as telas: *"as fontes ainda estão erradas entre as abas,
 * tamanho, proporção"*, *"a proporção e posição dos cabeçalhos tbm está
 * divergindo"*, *"os cards fechados não estão como nos mockups"*, e direto:
 * *"porque não está fazendo corretamente?"*
 *
 * 🚨 A CAUSA, MEDIDA: `card__abrir` em **4** arquivos com **3 corpos
 * diferentes**, `pilula` em **7**, `coluna` em **5** — e o CSS global
 * declarava **nenhum**. Cada tela tinha a sua cópia: `gap` e-1 contra e-2,
 * borda `--borda` contra `--borda-forte`, sombra só numa, pílula com e sem
 * borda, cabeçalho centrado numa e `flex-end` na outra. No mockup as duas
 * folhas ficaram empilhadas e o card pegou o corpo bom — é por isso que o
 * mockup mostrou o card certo e a tela, outro.
 *
 * 🚨 ESTA É A ÚNICA CASA DESSAS REGRAS. Mudar o card de um painel é mudar
 * aqui, e muda nos quatro — que é o ponto. A **12ª conferência** do
 * `conferir_css_publicado.mjs` reprova o build se alguma voltar a ser
 * declarada duas vezes com corpos diferentes.
 *
 * 🚨 O ANCESTRAL `.escala-operacao` FOI MEDIDO: exatamente as três telas de
 * painel o carregam, e o `ChatInterno` e a `CaixaDeEntrada` — que também têm
 * `.coluna`, significando outra coisa — não. Sem ele, um `.coluna` global
 * invadiria as duas.
 *
 * ⚠️ A OPERAÇÃO NÃO FOI RENOMEADA: os nomes dela (`tela__cabecalho`,
 * `cabecalho__identidade`, `cabecalho__controles`) e os das abas
 * (`painel__topo`, `painel__identidade`, `painel__medidas`) são declarados no
 * MESMO corpo.
 *
 * ⚠️ VARIANTE DE UMA TELA SÓ FICOU ONDE ESTAVA (`card__abrir--chamado`,
 * `coluna--alvo`, `pilula--valor`, …): mover o que não é compartilhado só
 * engordaria o arquivo comum.
 */
'''


if __name__ == "__main__":
    raise SystemExit(main())
