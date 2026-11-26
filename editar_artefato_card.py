# -*- coding: utf-8 -*-
"""O artefato vira CARD INTERNO, no modelo da aba 1 — A23, 25/11.

🔵 Ele: *"O card aberto na aba2, coluna movimentação permanece feia"*. O resumo
e o filtro já saíram na primeira rodada; faltava a lista.

🚨 O QUE ESTAVA FEIO, na marcação: `checkbox` + **cinco** campos dentro de uma
`<label>` numa linha só, e depois **três parágrafos** soltos (dados da OS,
"casou por", "devolvido") — tudo no mesmo peso, sem hierarquia, com o valor
disputando espaço com o número da OS.

O conserto usa o **vocabulário do `CorpoDoCard`**, que é o modelo ideal da aba 1
e agora mora na fonte única (`estilo/painel.css`):

| linha | o que tem |
|---|---|
| 1 | os identificadores (Orç — OS — TERMO) à esquerda e o **valor à direita** |
| 2 | o cliente, o tipo e a data do serviço, em peso fraco |
| 3 | os selos: situação do ERP, *casou por* e *devolvido* — só quando há |

⚠️ A marcação continua sendo a `<label>` em volta do `checkbox`: é ela que faz
clicar no texto marcar o item, e tirar isso tornaria o alvo só a caixinha.
"""
import pathlib
import shutil
import sys
from datetime import datetime

ALVO = pathlib.Path("/home/claude/movizap_painel/frontend/src/telas/"
                    "PainelServicoDosTecnicos.vue")

DE = """                    <li v-for="a in artefatosVisiveis(cardAberto)" :key="a.id"
                        class="artefato">
                      <label class="artefato__marca">
                        <input type="checkbox"
                               :checked="estaMarcado(cardAberto, a.id)"
                               :disabled="!cardAberto.pode_preparar"
                               @change="alternar(cardAberto, a.id)" />
                        <!-- 🔵 A ordem é a dele: Orçamento — OS — TERMO. -->
                        <span v-if="a.orcamento_numero"
                              class="artefato__orcamento">
                          Orç {{ a.orcamento_numero }}
                        </span>
                        <span v-else
                              class="artefato__orcamento artefato__orcamento--sem">
                          <i class="bi bi-exclamation-circle" aria-hidden="true"></i>
                          sem orçamento
                        </span>
                        <button class="artefato__os" type="button"
                                @click.stop.prevent="abrirOs(a)">
                          OS {{ a.numero_os }}
                        </button>
                        <span v-if="a.termo" class="artefato__termo">
                          TERMO {{ a.termo }}
                        </span>
                        <span class="artefato__valor">
                          {{ moeda(valorDe(a)) }}
                        </span>
                      </label>

                      <!-- 🔵 19/11: os dados da OS, *"como a aba1 apresenta"*.
                           ⚠️ Cliente sem nome é DITO, não deixado em branco —
                           a frase é a mesma do card da aba 1. -->
                      <p class="artefato__os-dados">
                        <span v-if="a.cliente" class="artefato__cliente"
                              :title="a.cliente">{{ a.cliente }}</span>
                        <span v-else class="artefato__cliente artefato__cliente--sem">
                          cliente {{ a.cliente_id || '?' }}, fora do nosso cadastro
                        </span>
                        <span v-if="a.tipo_nome">&middot; {{ a.tipo_nome }}</span>
                        <span>&middot; serviço {{ dataCurta(a.data_os) }}</span>
                        <span v-if="a.status_str">&middot; {{ a.status_str }}</span>
                      </p>

                      <p v-if="casouPor(a)" class="artefato__casou">
                        casou por {{ casouPor(a) }}
                      </p>

                      <!-- 🔵 O devolvido é LARANJA e a justificativa fica à
                           vista: laranja sem motivo é cor sem informação. -->
                      <p v-if="a.semaforo === 'laranja'" class="artefato__devolvido">
                        <i class="bi bi-arrow-counterclockwise" aria-hidden="true"></i>
                        devolvido: {{ a.justificativa }}
                      </p>
                    </li>"""

PARA = """                    <!-- 🔵 25/11 (A23): O ARTEFATO É UM CARD INTERNO, no
                         vocabulário do `CorpoDoCard` -- o modelo da aba 1, que
                         agora mora na fonte única. Antes eram cinco campos
                         numa `<label>` e três parágrafos soltos, tudo no mesmo
                         peso. ⚠️ A `<label>` em volta FICA: é ela que faz
                         clicar no texto marcar o item. -->
                    <li v-for="a in artefatosVisiveis(cardAberto)" :key="a.id"
                        class="artefato"
                        :class="{ 'artefato--marcado': estaMarcado(cardAberto, a.id) }">
                      <label class="artefato__marca">
                        <input type="checkbox"
                               :checked="estaMarcado(cardAberto, a.id)"
                               :disabled="!cardAberto.pode_preparar"
                               @change="alternar(cardAberto, a.id)" />
                        <span class="artefato__corpo">
                          <!-- LINHA 1 — os identificadores e o VALOR à direita.
                               🔵 A ordem é a dele: Orçamento — OS — TERMO. -->
                          <span class="card__linha">
                            <span class="card__ident">
                              <span v-if="a.orcamento_numero"
                                    class="artefato__orcamento">
                                Orç {{ a.orcamento_numero }}
                              </span>
                              <span v-else
                                    class="artefato__orcamento artefato__orcamento--sem">
                                <i class="bi bi-exclamation-circle" aria-hidden="true"></i>
                                sem orçamento
                              </span>
                              <button class="card__os" type="button"
                                      @click.stop.prevent="abrirOs(a)">
                                OS {{ a.numero_os }}
                              </button>
                              <span v-if="a.termo" class="card__termo">
                                TERMO {{ a.termo }}
                              </span>
                            </span>
                            <span class="card__direita card__direita--dado">
                              <strong>{{ moeda(valorDe(a)) }}</strong>
                            </span>
                          </span>

                          <!-- LINHA 2 — de quem é e quando foi.
                               ⚠️ Cliente sem nome é DITO, não deixado em
                               branco — a frase é a do card da aba 1. -->
                          <span class="card__linha card__dado">
                            <span v-if="a.cliente" class="card__cliente"
                                  :title="a.cliente">{{ a.cliente }}</span>
                            <span v-else class="card__cliente card__cliente--sem">
                              cliente {{ a.cliente_id || '?' }}, fora do nosso cadastro
                            </span>
                            <span class="card__direita">
                              <template v-if="a.tipo_nome">{{ a.tipo_nome }} &middot; </template>
                              serviço {{ dataCurta(a.data_os) }}
                            </span>
                          </span>

                          <!-- LINHA 3 — os selos, e só quando há o que dizer. -->
                          <span v-if="a.status_str || casouPor(a)
                                      || a.semaforo === 'laranja'"
                                class="artefato__selos">
                            <span v-if="a.status_str" class="selo">
                              {{ a.status_str }}
                            </span>
                            <span v-if="casouPor(a)" class="selo">
                              casou por {{ casouPor(a) }}
                            </span>
                            <!-- 🔵 O devolvido é LARANJA e a justificativa fica
                                 à vista: laranja sem motivo é cor sem
                                 informação. -->
                            <span v-if="a.semaforo === 'laranja'"
                                  class="selo selo--laranja">
                              <i class="bi bi-arrow-counterclockwise" aria-hidden="true"></i>
                              devolvido: {{ a.justificativa }}
                            </span>
                          </span>
                        </span>
                      </label>
                    </li>"""

CSS_DE = """.comprovante__anexo { display: flex; flex-direction: column; gap: var(--e-1);
                      margin-bottom: var(--e-2); }"""

CSS_PARA = """.comprovante__anexo { display: flex; flex-direction: column; gap: var(--e-1);
                      margin-bottom: var(--e-2); }

/* 🔵 25/11 (A23) — o artefato como card interno.
   ⚠️ `align-items: flex-start` na marcação: a caixinha alinha com a PRIMEIRA
   linha do corpo, não no meio do bloco de três linhas. */
.artefato__marca {
  display: flex; align-items: flex-start; gap: var(--e-2);
  width: 100%; cursor: pointer;
}
.artefato__marca input[type="checkbox"] { margin-top: 3px; flex: none; }
/* `min-width: 0` para o nome do cliente poder encurtar em vez de empurrar o
   valor para fora do card -- a armadilha clássica do flex. */
.artefato__corpo {
  display: flex; flex-direction: column; gap: 2px; min-width: 0; flex: 1 1 auto;
}
/* 🚨 O MARCADO SE VÊ, e não só pela caixinha: numa lista de 39 itens, a
   marcação de um checkbox sozinho se perde. */
.artefato--marcado {
  border-color: var(--acento);
  background: var(--acento-suave);
}"""

T = [("o artefato como card interno", DE, PARA),
     ("o CSS do artefato", CSS_DE, CSS_PARA)]


def main() -> int:
    texto = ALVO.read_text(encoding="utf-8")
    for rotulo, de, _p in T:
        if texto.count(de) != 1:
            print(f"ABORTADO em '{rotulo}': {texto.count(de)} ocorrencias.",
                  file=sys.stderr)
            return 1
    novo = texto
    for _r, de, para in T:
        novo = novo.replace(de, para, 1)
    marca = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    shutil.copy2(ALVO, ALVO.with_suffix(ALVO.suffix + f".bak_{marca}_artefato_card"))
    ALVO.write_text(novo, encoding="utf-8")
    print(f"linhas {len(texto.splitlines())} -> {len(novo.splitlines())}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
