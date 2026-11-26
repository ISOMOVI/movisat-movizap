# -*- coding: utf-8 -*-
"""O G2 NO `PainelAba.vue` — ajuda, busca e ordenador no topo, 25/11.

🔵 Ele, 25/11: *"faltam recursos no topo da aba1 tbm"* e, sobre o mockup,
*"1b igual para ambas"* / *"Todo proposto está ótimo - pode seguir"*.

🚨 **ESTA TELA SERVE QUATRO PAINÉIS** (`PNL_1.2`, `PNL_1.3`, `PNL_1.4`,
`PNL_1.5`): o que entra aqui aparece no Pós-venda, no Financeiro e no
Contratual de uma vez. Por isso o texto da ajuda é **sobre o que uma aba é**, e
não sobre um painel — texto com o nome do Financeiro apareceria no Pós-venda.
É o mesmo erro que o `h1` literal causou e que ele achou em 06/11.

📏 Medido em 25/11: a Operação tem ajuda, busca e ordenador; esta tela tem
**nenhum** dos três.

🟡 **UMA DECISÃO MINHA, DECLARADA: a ordem padrão continua sendo a do
servidor.** Pôr "mais recentes" como padrão mudaria a ordem dos cards nos
quatro painéis sem ninguém pedir — limite, filtro e ordem são decisão dele
(`feedback_nao_mudar_regras`). O ordenador nasce em "a ordem do servidor", e as
outras três opções ficam à mão.
"""
import pathlib
import shutil
import sys
from datetime import datetime

ALVO = pathlib.Path("/home/claude/movizap_painel/frontend/src/telas/"
                    "PainelAba.vue")

IMPORT_DE = "import CorpoDoCard from '../componentes/CorpoDoCard.vue'\n"
IMPORT_PARA = ("import AjudaDaTela from '../componentes/AjudaDaTela.vue'\n"
               "import CorpoDoCard from '../componentes/CorpoDoCard.vue'\n")

SCRIPT_DE = "const total = computed(() => quadro.value?.total ?? 0)"

SCRIPT_PARA = '''const total = computed(() => quadro.value?.total ?? 0)

/* ==========================================================================
   🔵 25/11 — BUSCA E ORDENADOR, os recursos que faltavam neste topo.
   ==========================================================================
   📏 Medido: a Operação tem busca, ordenador e ajuda desde 05/11; esta tela,
   que serve QUATRO painéis, não tinha nenhum dos três.

   🚨 PENEIRA NO CLIENTE, e isto é escolha com motivo: o quadro já vem INTEIRO
   do servidor (`/api/paineis/aba/<codigo>`), então filtrar aqui não esconde
   nada que não esteja na tela nem cobra uma segunda volta do banco. Rota nova
   com `?busca=` seria outro caminho para o mesmo dado -- e dois caminhos é
   como um deles envelhece.

   ⚠️ A busca varre os campos com que se cruza papel -- cliente, OS, termo,
   placa, formulário e tipo --, os mesmos que o card mostra. Buscar no que a
   tela não mostra faria o card "casar" sem a pessoa ver por quê. */
const busca = ref('')

/* 🟡 A ORDEM PADRÃO É A DO SERVIDOR, e é decisão minha declarada: trocá-la por
   "mais recentes" mudaria a ordem dos cards nos quatro painéis sem ninguém
   pedir. Ordem, filtro e limite são decisão dele. */
const ROTULO_ORDEM = {
  servidor: 'a ordem do servidor',
  recentes: 'mais recentes',
  parado: 'parado há mais tempo',
  cliente: 'cliente A–Z',
}
const ordem = ref('servidor')

function textoDoCard(card) {
  const placas = Array.isArray(card.placas)
    ? card.placas.map((p) => p.placa).filter(Boolean).join(' ') : ''
  return [card.cliente, card.numero_os, card.numero_ordem, card.os_id,
          card.termo, card.formulario, card.tipo_nome, placas]
    .filter(Boolean).join(' ').toLowerCase()
}

function casa(card) {
  const termo = busca.value.trim().toLowerCase()
  return !termo || textoDoCard(card).includes(termo)
}

function emMs(iso) {
  const t = new Date(iso || 0).getTime()
  return Number.isNaN(t) ? 0 : t
}

/* Os cards de uma coluna, peneirados e ordenados.
   ⚠️ Cópia antes de ordenar: `sort` mexe no array no lugar, e ele é o do
   `quadro` -- ordenar ali embaralharia a fonte a cada desenho. */
function cardsDa(coluna) {
  const cards = (coluna.cards || []).filter(casa)
  if (ordem.value === 'servidor') return cards
  const copia = [...cards]
  if (ordem.value === 'recentes') {
    copia.sort((a, b) => emMs(b.criada_em) - emMs(a.criada_em))
  } else if (ordem.value === 'parado') {
    /* 🚨 Card SEM passagem registrada vai para o FIM: "não medido" não é
       "parado há mais tempo" -- é a régua que a Operação escreveu. */
    copia.sort((a, b) => (emMs(a.etapa_desde) || Infinity)
                         - (emMs(b.etapa_desde) || Infinity))
  } else if (ordem.value === 'cliente') {
    copia.sort((a, b) => String(a.cliente || '\\uffff')
      .localeCompare(String(b.cliente || '\\uffff'), 'pt-BR'))
  }
  return copia
}

/* 🚨 A CONTA DIZ O QUE A BUSCA ESCONDEU (`M12`): dizer "7 cards" com 2 à
   vista é a tela mentindo por omissão -- foi assim que o corte de data da aba
   2 pareceu defeito em 19/11. */
const totalVisivel = computed(() => (quadro.value?.colunas || [])
  .reduce((soma, c) => soma + (c.cards || []).filter(casa).length, 0))
const buscando = computed(() => !!busca.value.trim())'''

TOPO_DE = """      <h1 class="painel__titulo">{{ tituloDoPainel }}</h1>
      <div class="painel__medidas">
        <span class="pilula">{{ total }} {{ total === 1 ? 'card' : 'cards' }}</span>
        <button class="botao botao--contorno" type="button"
                :disabled="carregando" @click="carregar">
          <i class="bi bi-arrow-clockwise" aria-hidden="true"></i>
          Atualizar
        </button>
      </div>"""

TOPO_PARA = """      <!-- 🔵 25/11: A IDENTIDADE E OS CONTROLES, como na Operação desde
           05/11 (*"o cabeçalho esta porco, organize de forma profissional"*).
           🚨 O TEXTO DA AJUDA É SOBRE UMA ABA, não sobre um painel: esta tela
           serve quatro, e escrever "Financeiro" aqui faria o Pós-venda dizer
           Financeiro -- o mesmo defeito do `h1` literal que ele achou em
           06/11. -->
      <div class="painel__identidade">
        <h1 class="painel__titulo">{{ tituloDoPainel }}</h1>
        <AjudaDaTela>
          Os cards deste painel em colunas, pelas <strong>etapas
          nossas</strong> — as que a Movisat definiu, e não as situações do
          Harmonit. <strong>Arraste o card</strong> para mudar de etapa: isso
          grava no nosso banco e registra quem fez. Clique nele para abrir a
          ficha, os recados e o checklist.
        </AjudaDaTela>
      </div>
      <div class="painel__medidas">
        <!-- 🔵 *"faltam recursos no topo da aba1 tbm"* (25/11): a busca e o
             ordenador que a Operação tem. ⚠️ UMA caixa para todos os campos:
             quem procura tem um número ou um nome na mão e não quer decidir
             em qual caixa ele vai. -->
        <label class="controles__busca">
          <span class="so-leitor">
            Procurar por cliente, OS, termo, placa, formulário ou tipo
          </span>
          <input v-model="busca" type="search"
                 placeholder="cliente, OS, termo ou placa" />
        </label>

        <label class="controles__ordem">
          <span class="so-leitor">Ordenar os cards</span>
          <select v-model="ordem">
            <option v-for="(rot, chave) in ROTULO_ORDEM" :key="chave"
                    :value="chave">{{ rot }}</option>
          </select>
        </label>

        <!-- 🚨 Com a busca ativa a pílula diz "x de y": contagem que cai sem
             explicação é a tela mentindo por omissão (`M12`). -->
        <span class="pilula">
          <template v-if="buscando">{{ totalVisivel }} de </template>{{ total }}
          {{ total === 1 && !buscando ? 'card' : 'cards' }}
        </span>
        <button class="botao botao--contorno" type="button"
                :disabled="carregando" @click="carregar">
          <i class="bi bi-arrow-clockwise" aria-hidden="true"></i>
          Atualizar
        </button>
      </div>"""

COLUNA_DE = """            <span class="coluna__nome">{{ coluna.titulo }}</span>
            <span class="coluna__conta"
                  :class="{ 'coluna__conta--zero': !coluna.total }">
              {{ coluna.total }}
            </span>"""

COLUNA_PARA = """            <span class="coluna__nome">{{ coluna.titulo }}</span>
            <!-- ⚠️ Com a busca ativa a conta da coluna é a do que ela MOSTRA,
                 e o total fica ao lado: a soma das colunas tem de fechar com
                 o que a pessoa vê. -->
            <span class="coluna__conta"
                  :class="{ 'coluna__conta--zero': !cardsDa(coluna).length }">
              <template v-if="buscando">{{ cardsDa(coluna).length }}/</template>{{ coluna.total }}
            </span>"""

CARDS_DE = """          <article v-for="card in coluna.cards" :key="card.id" class="card\""""
CARDS_PARA = """          <article v-for="card in cardsDa(coluna)" :key="card.id" class="card\""""

VAZIA_DE = """          <p v-if="!coluna.total" class="nota pequeno">Vazia.</p>"""
VAZIA_PARA = """          <!-- 🚨 COLUNA VAZIA E COLUNA PENEIRADA SÃO COISAS DIFERENTES, e
               dizer "Vazia." quando a busca escondeu tudo é a tela mentindo
               (`M12`): quem leu isso concluiria que não há card nenhum. -->
          <p v-if="!coluna.total" class="nota pequeno">Vazia.</p>
          <p v-else-if="!cardsDa(coluna).length" class="nota pequeno">
            {{ coluna.total }} {{ coluna.total === 1 ? 'card' : 'cards' }},
            nenhum casa com a busca.
          </p>"""

CSS_DE = """.painel__medidas { display: flex; align-items: center; gap: var(--e-2); }"""
CSS_PARA = """.painel__medidas {
  display: flex; align-items: center; gap: var(--e-2); flex-wrap: wrap;
}
/* 🔵 25/11 — a identidade da tela: título e ajuda juntos, como na Operação.
   ⚠️ Nome próprio: `cabecalho__identidade` é `scoped` no `PainelOperacao.vue`
   e copiar o nome de lá daria marcação SEM ESTILO (a armadilha da `.pilula`). */
.painel__identidade {
  display: flex; align-items: center; gap: var(--e-2); min-width: 0;
}
/* Os controles novos, no mesmo desenho dos da aba 2.
   ⚠️ 16px nos campos: abaixo disso o iOS dá zoom ao focar. */
.controles__busca input, .controles__ordem select {
  padding: var(--e-2); border-radius: var(--r-md);
  border: var(--borda-fina) solid var(--borda-forte);
  background: var(--superficie); color: var(--texto);
  font-size: 16px;
}
.controles__busca input { min-width: 220px; }"""

T = [("o import do AjudaDaTela", IMPORT_DE, IMPORT_PARA),
     ("a busca e o ordenador no script", SCRIPT_DE, SCRIPT_PARA),
     ("a identidade e os controles no topo", TOPO_DE, TOPO_PARA),
     ("a conta da coluna", COLUNA_DE, COLUNA_PARA),
     ("os cards peneirados", CARDS_DE, CARDS_PARA),
     ("coluna vazia x peneirada", VAZIA_DE, VAZIA_PARA),
     ("o CSS novo", CSS_DE, CSS_PARA)]


def main() -> int:
    texto = ALVO.read_text(encoding="utf-8")
    ruim = False
    for rotulo, de, _para in T:
        if texto.count(de) != 1:
            print(f"ABORTADO em '{rotulo}': ancora aparece "
                  f"{texto.count(de)} vezes.", file=sys.stderr)
            ruim = True
    if ruim:
        print("NADA FOI GRAVADO.", file=sys.stderr)
        return 1
    novo = texto
    for _r, de, para in T:
        novo = novo.replace(de, para, 1)
    if 'v-for="card in coluna.cards"' in novo:
        print("ABORTADO: sobrou laco sem peneira.", file=sys.stderr)
        return 1
    marca = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    shutil.copy2(ALVO, ALVO.with_suffix(ALVO.suffix + f".bak_{marca}_topo_g2"))
    ALVO.write_text(novo, encoding="utf-8")
    print(f"{len(T)} trocas; linhas {len(texto.splitlines())} -> "
          f"{len(novo.splitlines())}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
