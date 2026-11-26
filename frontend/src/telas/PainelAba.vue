<script setup>
/* ============================================================================
   PAINEL DE UMA ABA DE PIPELINE — Pós-venda, e os próximos
   ----------------------------------------------------------------------------
   🔵 Ele, 05/11: *"a aba 'Operação' do Movizap é a mesma lógica para os demais:
   Pós-venda - Abas - Permissão por abas / Aba 1: Treinamentos / Solicitação:
   Agenda* / Treinamento 1: / Treinamento 2: / Entregue: / Aba 2: Pós-venda"*, e
   depois as colunas da segunda: *"Solicitação: Testes: Realizar Pós-venda:
   Pós-venda Realizado:"*.

   🚨 TODAS AS COLUNAS DAQUI SÃO NOSSAS — nenhuma existe no Harmonit, e por isso
   esta tela **nunca** fala com o ERP. É a diferença inteira em relação ao
   painel da Operação, cujas 17 colunas são situações da OS: lá mover escreve
   `situacaoId` no ERP; aqui, só no nosso banco.

   🚨 UMA TELA, DUAS ROTAS: a `PNL_1.2` e a `PNL_1.3` são a MESMA tela com
   `codigo` diferente, porque as colunas vivem no banco (`pipeline_etapa`,
   migração 094) e não no código. Uma tela por aba seria copiar isto por aba.
   ⚠️ Mas a ENTRADA no `telas.py` é uma por aba, e isso não é redundância: a
   permissão é campo da entrada, e ele quer *"a Erika, apenas a aba 3"*.

   🔴 OS CARDS NASCEM VAZIOS, E É ESTADO, NÃO DEFEITO: a origem deles ficou em
   aberto por decisão dele (*"deixe em aberto, depois veremos"*). A tela diz
   isso — quadro vazio que não explica por que está vazio é `M12`.
   ============================================================================ */
import { computed, onMounted, onBeforeUnmount, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { api, ErroDeApi } from '../api/cliente.js'
import BarraDeRolagem from '../componentes/BarraDeRolagem.vue'
import DialogoDeChamado from '../componentes/DialogoDeChamado.vue'
import AjudaDaTela from '../componentes/AjudaDaTela.vue'
import CorpoDoCard from '../componentes/CorpoDoCard.vue'
import RolagemDaBorda from '../componentes/RolagemDaBorda.vue'
import { sessao } from '../estado/sessao.js'

const rota = useRoute()
const quadro = ref(null)
/* 🚨 `rolo`, e nao `quadro`: naquele nome ja mora o JSON do painel.
   Este e o elemento com `overflow-x`, que os dois controles de rolagem
   recebem por `prop` -- a mesma ligacao que a Operacao usa desde
   06/11. */
const rolo = ref(null)
const carregando = ref(true)
const erro = ref('')
const abertas = ref({})
const cardAberto = ref(null)
const erroDeMover = ref('')
const arrastando = ref(null)
const colunaAlvo = ref(null)
let arrastouAgora = 0
const focoAnterior = ref(null)

/* ⚠️ O código da aba vem da ROTA, não de um `prop`: é o que permite uma tela
   servir as duas (e as do Financeiro, quando ele der as colunas). */
const codigo = computed(() => rota.meta?.aba || '')

/* 🔵 11/11: *"deve condizer com o tipo da Aba"*. A ordem das fontes importa: o
   `meta.titulo` da rota é o nome do PAINEL (Pós-venda, Financeiro,
   Contratual), que é o que o cabeçalho quer; o `quadro.titulo` do servidor é o
   nome da ABA aberta, que já aparece na barra de abas logo abaixo. Repetir a
   aba no `h1` diria duas vezes a mesma coisa e deixaria o painel sem nome. */
const tituloDoPainel = computed(
  () => rota.meta?.titulo || quadro.value?.titulo || 'Painel')

const total = computed(() => quadro.value?.total ?? 0)

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
    copia.sort((a, b) => String(a.cliente || '\uffff')
      .localeCompare(String(b.cliente || '\uffff'), 'pt-BR'))
  }
  return copia
}

/* 🚨 A CONTA DIZ O QUE A BUSCA ESCONDEU (`M12`): dizer "7 cards" com 2 à
   vista é a tela mentindo por omissão -- foi assim que o corte de data da aba
   2 pareceu defeito em 19/11. */
const totalVisivel = computed(() => (quadro.value?.colunas || [])
  .reduce((soma, c) => soma + (c.cards || []).filter(casa).length, 0))
const buscando = computed(() => !!busca.value.trim())

/* 🔵 AS ABAS DENTRO DA TELA -- correcao dele em 05/11: *"so aba principal
   no menu. As demais sao dentro dela ja"*.

   🚨 06/11, A LISTA PASSOU A SAIR DO PAINEL, e e conserto de um defeito meu
   que ELE achou: *"os itens do pos venda estao aparecendo dentro do financeiro
   e contratual. qual a dificuldade em mante-los separados?"*. Antes era uma
   constante `AS_ABAS = [PNL_1.2, PNL_1.3]` escrita aqui, filtrada so por
   PERMISSAO -- e eu reusei esta tela nos dois paineis novos. Quem e owner tem
   as duas abas do Pos-venda, entao a tira delas aparecia dentro do Financeiro
   e do Contratual. ⚠️ Nao era permissao errada: era a lista nao ter dono.

   🔵 E ele fechou o desenho no mesmo minuto: *"o financeiro tera suas
   proprias abas, mas por agora so 1, o mesmo para o contratual, so o pos
   venda ja temos as duas pipelines em abas"*. Com a lista vindo do painel, a
   segunda aba do Financeiro vai aparecer SOZINHA no dia em que ele a criar --
   nenhuma linha daqui muda.

   ⚠️ DUAS FONTES, cada uma com o que e dela: o SERVIDOR diz quais abas sao
   deste painel e como se chamam (`painel_aba`, que e onde moram
   "Treinamentos" e "Pos-venda" -- no registro as duas telas se chamam as duas
   "Pos-venda"); o `sessao.telas` da a ROTA e, de graca, a permissao: aba que
   a pessoa nao alcanca nao esta nessa lista e cai fora sem segunda regua. */
const abasVisiveis = computed(() => {
  const doPainel = quadro.value?.abas || []
  const porCodigo = new Map(sessao.telas.map((t) => [t.codigo, t]))
  return doPainel
    .filter((a) => porCodigo.has(a.codigo_tela))
    .map((a) => ({ codigo: a.codigo_tela, titulo: a.titulo,
                   rota: porCodigo.get(a.codigo_tela).rota }))
})

function dataCurta(iso) {
  if (!iso) return '—'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return '—'
  const mesmoAno = d.getFullYear() === new Date().getFullYear()
  return d.toLocaleDateString('pt-BR', mesmoAno
    ? { day: '2-digit', month: '2-digit' }
    : { day: '2-digit', month: '2-digit', year: '2-digit' })
}

/* A cor é da COLUNA, e não do card: o card já está nela, e dentro dela todos
   teriam a mesma cor — foi a régua que o painel da Operação adotou em 05/11. */
const CORES = ['#2563EB', '#7C3AED', '#0891B2', '#059669', '#D97706', '#DB2777']
const corDaEtapa = (i) => CORES[i % CORES.length]

async function carregar() {
  carregando.value = true
  erro.value = ''
  try {
    quadro.value = await api.get(`/api/paineis/aba/${codigo.value}`)
    for (const coluna of quadro.value.colunas) {
      if (abertas.value[coluna.chave] === undefined) {
        abertas.value[coluna.chave] = true
      }
    }
    /* 🚨 O CARD ABERTO É RECARREGADO DO QUADRO NOVO, e não mantido: o
       `cardAberto` ficaria apontando para um retrato velho — com a etapa
       antiga escrita na tela. É o mesmo cuidado do `moverDoModal` da
       Operação. */
    if (cardAberto.value) {
      const vivo = quadro.value.colunas
        .flatMap((c) => c.cards)
        .find((c) => c.id === cardAberto.value.id)
      cardAberto.value = vivo || null
    }
  } catch (e) {
    erro.value = e instanceof ErroDeApi
      ? e.message : 'Não deu para abrir este painel agora.'
  } finally {
    carregando.value = false
  }
}

onMounted(carregar)
/* A mesma tela serve as duas abas, então trocar de rota recarrega. */
watch(codigo, (novo) => { if (novo) { abertas.value = {}; carregar() } })

function alternar(coluna) {
  abertas.value[coluna.chave] = !abertas.value[coluna.chave]
}

function abrirCard(card) {
  focoAnterior.value = document.activeElement
  cardAberto.value = card
}
function fecharCard() {
  cardAberto.value = null
  const alvo = focoAnterior.value
  focoAnterior.value = null
  if (alvo && typeof alvo.focus === 'function') alvo.focus()
}
function cliqueNoCard(card) {
  if (Date.now() - arrastouAgora < 400) return
  abrirCard(card)
}

function aoTeclar(evento) {
  if (evento.key !== 'Escape') return
  if (cardAberto.value) fecharCard()
}
onMounted(() => window.addEventListener('keydown', aoTeclar))
onBeforeUnmount(() => window.removeEventListener('keydown', aoTeclar))

function comecarArrasto(card, evento) {
  arrastando.value = card
  arrastouAgora = Date.now()
  if (evento.dataTransfer) {
    evento.dataTransfer.effectAllowed = 'move'
    evento.dataTransfer.setData('text/plain', String(card.id))
  }
}
function terminarArrasto() { arrastando.value = null; colunaAlvo.value = null }
function sobreAColuna(coluna) {
  if (arrastando.value) colunaAlvo.value = coluna.chave
}
function saiuDaColuna(coluna) {
  if (colunaAlvo.value === coluna.chave) colunaAlvo.value = null
}

async function soltarNaColuna(coluna) {
  const card = arrastando.value
  arrastando.value = null
  colunaAlvo.value = null
  arrastouAgora = Date.now()
  if (!card || !coluna.etapa_id) return
  /* ⚠️ Card arquivado não se move: reabrir primeiro é o gesto. Oferecer os
     dois ao mesmo tempo deixaria o estado ambíguo. */
  if (card.desfecho) {
    erroDeMover.value = 'Este card está finalizado. Reabra antes de mover.'
    return
  }
  if (card.etapa_id === coluna.etapa_id) return
  erroDeMover.value = ''
  try {
    await api.post(`/api/paineis/operacao/chamado/${card.id}/mover`,
                   { para_etapa: coluna.etapa_id })
    await carregar()
  } catch (e) {
    erroDeMover.value = e instanceof ErroDeApi
      ? e.message : 'Não deu para mover este card.'
  }
}
</script>

<template>
  <section class="painel escala-operacao">
    <header class="painel__topo">
      <!-- 🚨 O TÍTULO VEM DA ROTA, NUNCA ESCRITO À MÃO. Este componente serve
           os quatro painéis de aba (Pós-venda, Financeiro, Contratual e os que
           vierem), porque as colunas vivem no banco -- então um título literal
           aqui é o título de UM painel aparecendo em todos. Foi o que
           aconteceu: o Financeiro e o Contratual abriam dizendo "Pós-venda".
           ⚠️ O `meta.titulo` já existia e já estava certo em cada rota. -->
      <!-- 🔵 25/11: A IDENTIDADE E OS CONTROLES, como na Operação desde
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
      </div>
    </header>

    <!-- 🔵 AS ABAS: *"abas de pipeline: Treinamento / Pos venda"*.
         ⚠️ Com uma aba so, a barra nao aparece: uma aba sozinha nao e
         escolha, e desenhar a barra seria enfeite. -->
    <!-- ⚠️ O rotulo do `nav` sai do TITULO DO PAINEL, e nao fixo no
         Pos-venda: com a tela servindo cinco abas de tres paineis, "Abas do
         Pos-venda" seria a tela mentindo para quem usa leitor de tela. -->
    <nav v-if="abasVisiveis.length > 1" class="abas"
         :aria-label="`Abas de ${quadro?.titulo || 'painel'}`">
      <RouterLink v-for="a in abasVisiveis" :key="a.codigo" :to="a.rota"
                  class="abas__item"
                  :class="{ 'abas__item--atual': a.codigo === codigo }"
                  :aria-current="a.codigo === codigo ? 'page' : undefined">
        {{ a.titulo }}
      </RouterLink>
    </nav>

    <p v-if="erro" class="aviso aviso--erro" role="alert">{{ erro }}</p>
    <p v-if="erroDeMover" class="aviso aviso--erro" role="alert">
      {{ erroDeMover }}
    </p>

    <p v-if="carregando && !quadro" class="nota">Abrindo…</p>

    <!-- 🚨 QUADRO VAZIO QUE NÃO DIZ POR QUÊ É `M12`: estas abas nascem sem
         cards porque a ORIGEM deles é decisão dele, e não porque algo falhou.
         ⚠️ Isto é ESTADO, e não texto explicativo: diz o que há, não como
         funciona. -->
    <p v-else-if="quadro && !total" class="nota">
      Nenhum card nesta aba ainda.
    </p>

    <!-- 🔵 11/11, item 1 dele: a rolagem que a Operacao tem desde 06/11
         chega as abas. ⚠️ A barra fica FORA do casco, como na Operacao: dentro
         dele ela entraria na mesma camada das colunas e ficaria por baixo. -->
    <BarraDeRolagem v-if="quadro" :rolo="rolo"
                    :rotulo="`quadro de ${tituloDoPainel}`" />

    <div v-if="quadro" class="painel__casco">
      <RolagemDaBorda :rolo="rolo" rotulo="quadro" />
      <div ref="rolo" class="painel__quadro">
      <div v-for="(coluna, indice) in quadro.colunas" :key="coluna.chave"
           class="coluna"
           :class="{ 'coluna--vazia': !coluna.total,
                     'coluna--alvo': colunaAlvo === coluna.chave }"
           :style="{ borderTopColor: corDaEtapa(indice) }"
           :aria-label="coluna.titulo"
           @dragover.prevent="sobreAColuna(coluna)"
           @dragenter.prevent="sobreAColuna(coluna)"
           @dragleave="saiuDaColuna(coluna)"
           @drop.prevent="soltarNaColuna(coluna)">
        <h2 class="coluna__titulo">
          <button class="coluna__botao" type="button"
                  :aria-expanded="abertas[coluna.chave] ? 'true' : 'false'"
                  @click="alternar(coluna)">
            <span class="coluna__nome">{{ coluna.titulo }}</span>
            <!-- ⚠️ Com a busca ativa a conta da coluna é a do que ela MOSTRA,
                 e o total fica ao lado: a soma das colunas tem de fechar com
                 o que a pessoa vê. -->
            <span class="coluna__conta"
                  :class="{ 'coluna__conta--zero': !cardsDa(coluna).length }">
              <template v-if="buscando">{{ cardsDa(coluna).length }}/</template>{{ coluna.total }}
            </span>
          </button>
        </h2>

        <div v-if="abertas[coluna.chave]" class="coluna__corpo">
          <article v-for="card in cardsDa(coluna)" :key="card.id" class="card"
                   :draggable="!card.desfecho"
                   @dragstart="comecarArrasto(card, $event)"
                   @dragend="terminarArrasto">
            <!-- 🚨 O CORPO DO CARD VEM DO COMPONENTE ÚNICO desde 18/11, e isto
                 nasceu de uma pergunta dele: *"Então pq os cards informam que
                 não vem de OS no painel?"*

                 📏 Os 8 cards do Financeiro eram TODOS OS, e esta tela
                 desenhava 6 campos enquanto o servidor mandava mais de 20 --
                 `tipo_nome`, `termo`, `status_str`, `placas`, `tecnicos`,
                 `prioridade`, `visto_em`, `etapa_desde`, `prazo` entraram em
                 12/11 a pedido dele (*"igual da OP"*) e nunca apareceram aqui.

                 ⚠️ A causa era estrutural: dois `<article>` em dois arquivos.
                 Enquanto fossem dois, o próximo campo entraria num e faltaria
                 no outro. -->
            <!-- 🔵 25/11: a prop é ligada SÓ no Contratual (`PNL_1.5`), porque
                 esta tela serve as quatro abas com um componente só. -->
            <CorpoDoCard :card="card" :termo-primeiro="codigo === 'PNL_1.5'"
                         @abrir="cliqueNoCard" />
          </article>

          <!-- 🚨 COLUNA VAZIA E COLUNA PENEIRADA SÃO COISAS DIFERENTES, e
               dizer "Vazia." quando a busca escondeu tudo é a tela mentindo
               (`M12`): quem leu isso concluiria que não há card nenhum. -->
          <p v-if="!coluna.total" class="nota pequeno">Vazia.</p>
          <p v-else-if="!cardsDa(coluna).length" class="nota pequeno">
            {{ coluna.total }} {{ coluna.total === 1 ? 'card' : 'cards' }},
            nenhum casa com a busca.
          </p>
        </div>
      </div>
      </div>
    </div>

    <!-- 🚨 `:aba` entrou em 23/11 e NÃO é enfeite: esta tela serve QUATRO
         painéis (`PNL_1.2`, `PNL_1.3`, `PNL_1.4`, `PNL_1.5`) com uma única
         passagem de rótulo, e a pergunta nova do "Finalizar" é só da etapa 888
         do Contratual (D1 dele). Sem a aba, o diálogo só veria o número da
         etapa -- e trocar o texto por número solto mudaria as quatro telas no
         dia em que outra aba tivesse uma etapa com o mesmo id. -->
    <DialogoDeChamado v-if="cardAberto" :card="cardAberto"
                      rotulo-finalizar="Finalizar" :aba="codigo"
                      @fechar="fecharCard" @mudou="carregar" />
  </section>
</template>

<style scoped>
.painel { display: flex; flex-direction: column; gap: var(--e-4); }
.painel__topo {
  display: flex; flex-wrap: wrap; gap: var(--e-3);
  align-items: center; justify-content: space-between;
}
.painel__titulo { margin: 0; font-size: var(--txt-lg); }

/* 🚨 `relative` E A CONDICAO da faixa de rolagem da borda: ela e
   `position: absolute` e, sem um ancestral posicionado, ancoraria no elemento
   que rola -- e aí andaria junto com o conteudo em vez de ficar parada na
   borda. Foi o mesmo cuidado que a Operacao tomou em 06/11. */
.painel__casco { position: relative; }
.painel__medidas {
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
.controles__busca input { min-width: 220px; }

/* ⚠️ A ABA ATUAL E MARCADA POR BORDA, e nao so por cor: cor sozinha nao
   carrega informacao, e foi a regua que o item ativo do menu adotou em
   05/11 (barra branca, porque `--acento` sobre o fundo `#04034D` dava
   3,6:1). */
.abas {
  display: flex; gap: var(--e-1); flex-wrap: wrap;
  border-bottom: var(--borda-fina) solid var(--borda);
}
.abas__item {
  padding: var(--e-2) var(--e-3);
  border-bottom: 3px solid transparent;
  color: var(--texto-fraco); text-decoration: none;
  font-size: var(--txt-sm); font-weight: var(--peso-forte);
}
.abas__item:hover { color: var(--texto); background: var(--superficie-2); }
.abas__item--atual {
  color: var(--texto); border-bottom-color: var(--acento);
}

/* 🚨 A COLUNA DE 360px, e são 3 por scroll em 1366px — a medida que ele
   aprovou na Operação em 05/11: *"vendo 3 colunas por scroll esta ok"*. */
.painel__quadro {
  display: flex; gap: var(--e-3);
  overflow-x: auto; padding-bottom: var(--e-2);
  align-items: flex-start;
}
.coluna {
  flex: 0 0 360px;
  background: var(--fundo);
  border: var(--borda-fina) solid var(--borda);
  border-top: 3px solid var(--borda-forte);
  border-radius: var(--r-md);
  padding: var(--e-3);
}
.coluna--alvo { background: var(--superficie-2); }
.coluna--vazia { opacity: .8; }
.coluna__titulo { margin: 0; font-size: var(--txt-sm); }
.coluna__botao {
  width: 100%; display: flex; align-items: center; justify-content: space-between;
  gap: var(--e-2); border: 0; background: transparent; cursor: pointer;
  font: inherit; color: var(--texto); padding: 0 0 var(--e-2);
  text-align: left;
}
.coluna__nome { font-weight: var(--peso-forte); }
.coluna__conta {
  flex: 0 0 auto; min-width: 22px; text-align: center;
  padding: 0 var(--e-1); border-radius: var(--r-full);
  background: var(--acento); color: #FFFFFF;
  font-size: var(--txt-xs); font-weight: var(--peso-forte);
}
.coluna__conta--zero {
  background: transparent; color: var(--texto-fraco);
  border: var(--borda-fina) solid var(--borda-forte);
}
.coluna__corpo { display: flex; flex-direction: column; gap: var(--e-2); }

/* 🚨 A COLUNA RECUA E O CARD É BRANCO: os dois eram `--superficie` na
   Operação até 05/11, e 1px no tom mais claro da paleta era a única separação
   — era isso que fazia as caixas não terem limite. */
.card { border-radius: var(--r-md); }
.card[draggable="true"] { cursor: grab; }
.card[draggable="true"]:active { cursor: grabbing; }
.card__abrir {
  display: flex; flex-direction: column; gap: var(--e-1);
  padding: var(--e-3);
  background: var(--superficie);
  border: var(--borda-fina) solid var(--borda-forte);
  border-radius: var(--r-md);
  box-shadow: var(--sombra-1);
  cursor: pointer;
}
.card__abrir:hover { box-shadow: var(--sombra-2); }
.card__abrir--arquivado { opacity: .62; }
.card__abrir--arquivado:hover { opacity: 1; }

/* ⚠️ O NOME CORTA EM 2 LINHAS e o inteiro fica no `title`: 11 dos 15 nomes de
   cliente do quadro passam de 24 caracteres (mediana 28, o maior 56). */
.card__cliente {
  margin: 0; font-weight: var(--peso-forte); color: var(--texto);
  display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical;
  overflow: hidden;
}
.card__ident {
  display: flex; flex-wrap: wrap; align-items: center; gap: var(--e-2);
  font-size: var(--txt-sm); color: var(--texto-fraco);
}
.card__os {
  border: 0; background: transparent; padding: 0; cursor: pointer;
  font: inherit; font-weight: var(--peso-forte); color: var(--texto);
  text-align: left;
}
.card__os:hover { text-decoration: underline; }
.card__resumo {
  margin: 0; font-size: var(--txt-sm); color: var(--texto-fraco);
  display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical;
  overflow: hidden;
}
.card__arquivado {
  display: inline-flex; align-items: center; gap: var(--e-1);
  align-self: flex-start;
  padding: 1px var(--e-2);
  border: var(--borda-fina) solid var(--borda-forte);
  border-radius: var(--r-full);
  background: var(--superficie-2);
  font-size: var(--txt-xs); font-weight: var(--peso-forte);
  color: var(--texto-fraco);
}
.pilula {
  display: inline-flex; align-items: center; gap: var(--e-1);
  align-self: flex-start;
  padding: 1px var(--e-2); border-radius: var(--r-full);
  background: var(--superficie-2); color: var(--texto-fraco);
  font-size: var(--txt-xs); font-weight: var(--peso-forte);
}
.nota { color: var(--texto-fraco); }
.pequeno { font-size: var(--txt-sm); }
</style>
