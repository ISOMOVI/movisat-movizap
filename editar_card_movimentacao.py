# -*- coding: utf-8 -*-
"""O card aberto da Movimentação, no mesmo vocabulário do resto — 25/11.

🔵 Ele: *"O card aberto na aba2, coluna movimentação permanece feia tbm"*.

O que estava feio, medido na marcação:
1. o resumo era uma **frase corrida** (*"a pagar X · serviço Y · km Z"*) com
   indentação fora do lugar, solta acima de tudo;
2. o filtro de datas era uma **linha solta** com dois `<input type="date">`
   crus e um "limpar" minúsculo, sem moldura e sem dizer do que é a data;
3. cada artefato empilhava `checkbox` + cinco campos dentro de uma `<label>` e
   depois três parágrafos — sem hierarquia, tudo no mesmo peso.

O conserto usa o que ele já aprovou hoje: **medidas** no topo (como as pílulas
do cabeçalho), **quadro com título** para o filtro (o vocabulário dos
`.acoes__grupo`) e o artefato como **card interno** com as linhas do
`CorpoDoCard` — que é o modelo ideal da aba 1 e agora mora na fonte única.
"""
import pathlib
import shutil
import sys
from datetime import datetime

ALVO = pathlib.Path("/home/claude/movizap_painel/frontend/src/telas/"
                    "PainelServicoDosTecnicos.vue")

RESUMO_DE = """        <template v-if="colunaAberta === 'movimentacao'">
          <span class="card__linha card__dado">
            <span>
              a pagar <strong>{{ moeda(totalDe(cardAberto)) }}</strong>
              &middot; serviço
              {{ moeda(somaDe(cardAberto, 'valor_pagamento')) }}
              &middot; km {{ moeda(somaDe(cardAberto, 'valor_km')) }}
            </span>
          </span>
"""

RESUMO_PARA = """        <template v-if="colunaAberta === 'movimentacao'">
          <!-- 🔵 25/11: O RESUMO EM MEDIDAS, e não numa frase corrida. Três
               números no meio de uma linha de texto obrigam a LER para achar o
               que importa; em medidas, o olho vai direto. É a mesma forma das
               pílulas do topo da tela. -->
          <div class="medidas">
            <span class="medida">
              <span class="medida__rotulo">a pagar</span>
              <strong class="medida__valor">{{ moeda(totalDe(cardAberto)) }}</strong>
            </span>
            <span class="medida">
              <span class="medida__rotulo">serviço</span>
              <span class="medida__valor">
                {{ moeda(somaDe(cardAberto, 'valor_pagamento')) }}
              </span>
            </span>
            <span class="medida">
              <span class="medida__rotulo">km</span>
              <span class="medida__valor">
                {{ moeda(somaDe(cardAberto, 'valor_km')) }}
              </span>
            </span>
            <span class="medida">
              <span class="medida__rotulo">artefatos</span>
              <span class="medida__valor">
                {{ artefatosVisiveis(cardAberto).length }} de
                {{ (cardAberto.artefatos || []).length }}
              </span>
            </span>
          </div>
"""

FILTRO_DE = """                  <div class="card__filtro">
                    <label>de
                      <input type="date" :value="filtroDo(cardAberto).de"
                             @change="definirFiltro(cardAberto, 'de', $event.target.value)" />
                    </label>
                    <label>até
                      <input type="date" :value="filtroDo(cardAberto).ate"
                             @change="definirFiltro(cardAberto, 'ate', $event.target.value)" />
                    </label>
                    <button v-if="filtroDo(cardAberto).de || filtroDo(cardAberto).ate"
                            class="botao botao--fantasma" type="button"
                            @click="limparFiltro(cardAberto)">
                      limpar
                    </button>
                  </div>"""

FILTRO_PARA = """          <!-- 🔵 25/11: o filtro em QUADRO, com título. Dois `<input
               type="date">` soltos numa linha não diziam de que data eram --
               e é a do SERVIÇO, não a do card. -->
          <div class="acoes">
            <div class="acoes__grupo">
              <p class="acoes__titulo">Filtrar pela data do serviço</p>
              <div class="card__filtro">
                <label class="campo__rotulo campo__rotulo--lado">
                  de
                  <input class="campo" type="date"
                         :value="filtroDo(cardAberto).de"
                         @change="definirFiltro(cardAberto, 'de', $event.target.value)" />
                </label>
                <label class="campo__rotulo campo__rotulo--lado">
                  até
                  <input class="campo" type="date"
                         :value="filtroDo(cardAberto).ate"
                         @change="definirFiltro(cardAberto, 'ate', $event.target.value)" />
                </label>
                <button v-if="filtroDo(cardAberto).de || filtroDo(cardAberto).ate"
                        class="botao botao--fantasma" type="button"
                        @click="limparFiltro(cardAberto)">
                  <i class="bi bi-x-lg" aria-hidden="true"></i>
                  Limpar o filtro
                </button>
              </div>
            </div>
          </div>"""

CSS_DE = """.card__filtro {
  display: flex; gap: var(--e-2); font-size: var(--txt-xs);
  align-items: center; flex-wrap: wrap;
}"""

CSS_PARA = """.card__filtro {
  display: flex; gap: var(--e-2); font-size: var(--txt-xs);
  align-items: flex-end; flex-wrap: wrap;
}

/* 🔵 25/11 — AS MEDIDAS DO CARD ABERTO: três números que eram uma frase.
   ⚠️ `rótulo em cima, valor embaixo` e não "rótulo: valor" na mesma linha: o
   valor é o que se procura, e ele tem de ser a coisa mais escura do bloco. */
.medidas {
  display: flex; flex-wrap: wrap; gap: var(--e-3);
  padding: var(--e-2) var(--e-3);
  background: var(--superficie-2);
  border-radius: var(--r-md);
}
.medida { display: flex; flex-direction: column; min-width: 0; }
.medida__rotulo {
  font-size: var(--txt-xs); color: var(--texto-fraco);
  text-transform: uppercase; letter-spacing: .04em;
}
.medida__valor { font-size: var(--txt-sm); font-weight: var(--peso-forte); }

/* O rótulo do campo de data fica ao LADO, não em cima: numa linha de filtro,
   "de" e "até" em cima de cada campo dobram a altura da faixa. */
.campo__rotulo--lado {
  display: flex; align-items: center; gap: var(--e-1);
  font-size: var(--txt-xs); color: var(--texto-fraco);
}
.campo__rotulo--lado .campo { width: auto; }"""

T = [("o resumo em medidas", RESUMO_DE, RESUMO_PARA),
     ("o filtro em quadro", FILTRO_DE, FILTRO_PARA),
     ("o CSS das medidas", CSS_DE, CSS_PARA)]


def main() -> int:
    texto = ALVO.read_text(encoding="utf-8")
    ruim = False
    for rotulo, de, _p in T:
        if texto.count(de) != 1:
            print(f"ABORTADO em '{rotulo}': {texto.count(de)} ocorrencias.",
                  file=sys.stderr)
            ruim = True
    if ruim:
        return 1
    novo = texto
    for _r, de, para in T:
        novo = novo.replace(de, para, 1)
    marca = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    shutil.copy2(ALVO, ALVO.with_suffix(ALVO.suffix + f".bak_{marca}_card_mov"))
    ALVO.write_text(novo, encoding="utf-8")
    print(f"linhas {len(texto.splitlines())} -> {len(novo.splitlines())}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
