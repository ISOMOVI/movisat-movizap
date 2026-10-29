<script setup>
/* ============================================================================
   PNL_1.1 — Painel da Operação (opção A: kanban pelas situações da OS)
   ----------------------------------------------------------------------------
   🔵 Escolha dele em 22/10, entre três mockups lado a lado: *"vamos de A
   somente para a Operação por enquanto, mas bem documentado para as demais
   futuramente"*. A opção A é a única em que **mover o card É a ação** — e foi
   esse o motivo que ele deu para o painel existir: *"hoje ainda não usamos a
   situação da OS, por isso o painel e consulta para atualizar a situação no
   painel"*.

   🚨 MOVER AINDA NÃO EXISTE. A rota que escreve `situacaoId` no Harmonit é da
   volta seguinte; enquanto não existir, não há `draggable` nenhum, porque
   oferecer o gesto e não gravar é pior que não ter o gesto. ⚠️ Em 29/10 ele
   mandou TIRAR a frase que explicava isso na tela (*"os comentários tbm devem
   sumir dali"*) -- o comportamento não mudou, só o texto saiu.

   🚨 SÃO 17 COLUNAS, E A ORDEM É A DELE (29/10): *"as situações já estão na
   Ordem"*. A ordem é o fluxo da operação, não alfabética nem por id, e ela
   vive numa tupla só, em `movizap/paineis.py`.

   🚨 COLUNA VAZIA NASCE COLAPSADA, com o contador à vista — são 17 colunas, e
   nenhuma tela mostra 17 sem rolar. É o que o kanban do FPSL já faz com a
   coluna "Pago". ⚠️ Nenhuma é fixa agora: as duas que nunca colapsavam ("Sem
   OS" e "Sem situação") SAÍRAM em 29/10 -- *"qualquer aba fora dessas não deve
   estar no painel"*.

   🚨 A COR NUNCA É O ÚNICO PORTADOR: o estado da solicitação vem escrito na
   etiqueta, e a situação vem escrita no card. É a regra do quadro de demandas
   do FPSL -- *"o estado continua legível pela etiqueta"*.
   ============================================================================ */
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import { api, ErroDeApi } from '../api/cliente.js'
import AjudaDaTela from '../componentes/AjudaDaTela.vue'

const router = useRouter()
const quadro = ref(null)
const carregando = ref(true)
const erro = ref('')
const abertas = ref({})


/* 🔵 D9: o interruptor nasce LIGADO -- ver o comentário no `template`. */
const soAbertas = ref(true)

/* Só o dia, sem hora: a data matriz é um corte de calendário. */
function dia(iso) {
  if (!iso) return '—'
  const [a, m, d] = String(iso).split('-')
  return (d && m && a) ? `${d}/${m}/${a}` : iso
}

async function carregar() {
  carregando.value = true
  erro.value = ''
  try {
    quadro.value = await api.get(
      `/api/paineis/operacao?so_abertas=${soAbertas.value ? 1 : 0}`)
    for (const coluna of quadro.value.colunas) {
      /* Vazia nasce fechada; com card, aberta. ⚠️ Nenhuma é fixa desde
         29/10 -- as duas que não eram situação saíram do painel. */
      abertas.value[coluna.chave] = coluna.total > 0
    }
  } catch (e) {
    erro.value = e instanceof ErroDeApi ? e.message : 'Não consegui ler o painel.'
  } finally {
    carregando.value = false
  }
}

function alternar(coluna) {
  abertas.value[coluna.chave] = !abertas.value[coluna.chave]
}

function abrirSolicitacao(card) {
  /* A ficha completa é da FRM_1.1 — o painel não repete a leitura dos 34
     campos do credenciamento. */
  router.push({ path: '/solicitacoes', query: { solicitacao: card.id } })
}

/* 🚨 O QUE NÃO TEM COLUNA, DITO EM UMA LINHA -- e só quando existe.
   Solicitação sem OS (a escrita no Harmonit falhou) ou com situação fora das
   17 não cabe em coluna nenhuma, e sumir da tela é o defeito que esta casa
   chama de `M12`. Com zero, esta linha não aparece: hoje o painel fica limpo,
   que é o que ele pediu em 29/10. */
const fora = computed(() => {
  const f = quadro.value?.fora_do_quadro
  if (!f || (!f.sem_os && !f.situacao_fora && !f.os_falhou
             && !f.sem_tentativa)) return ''
  const partes = []
  /* 🚨 "SEM OS" SÃO TRÊS CASOS, E A TELA CHAMAVA TODOS DE FALHA -- achado por
     ele em 29/10, na tela, minutos depois de o painel subir: a solicitação
     544 nunca teve escrita tentada (é de 13:06, e o Bloco A subiu às 15:30),
     e a frase a acusava de erro do Harmonit.

     ⚠️ A ORDEM É DELIBERADA: o caso benigno primeiro, o que pede ação depois,
     e a sobra no fim. E a sobra EXISTE de propósito -- uma linha preparada e
     nunca tentada não cai em nenhuma das duas contas, e deixá-la desaparecer
     entre as frases seria o mesmo defeito outra vez, mais fundo. */
  if (f.sem_tentativa) {
    /* 🔵 Ele, 29/10, lendo "1 chamado sem OS": *"pq deu erro? o que falta?"*.
       NADA havia falhado -- era o chamado dele, enviado antes de a abertura
       automática existir. A frase contava em vez de identificar, e contagem
       sem número não responde "qual?". */
    /* 🚨 O PLURAL NAO PODE DEPENDER DA LISTA DE NUMEROS, e foi o defeito que
       a trava pegou: a frase dizia "1 chamados" quando o numero do chamado nao
       vinha (acontece acima de 5 itens, ou se o servidor nao mandar a lista).
       Um e singular com lista ou sem. */
    const quais = (f.sem_tentativa_quais || []).join(', ')
    const um = f.sem_tentativa === 1
    partes.push(
      (um ? (quais ? `o chamado ${quais} ainda não tem OS`
                   : '1 chamado ainda sem OS')
          : `${f.sem_tentativa} chamados ainda sem OS`
            + (quais ? ` (${quais})` : ''))
      + (um ? ' (foi enviado' : ', enviados')
      + ' antes de a abertura automática entrar)'.slice(um ? 0 : 1))
  }
  if (f.os_falhou) {
    partes.push(`${f.os_falhou} ${f.os_falhou === 1 ? 'OS não abriu' : 'OS não abriram'}`
      + ` em ${f.os_falhou_chamados} ${f.os_falhou_chamados === 1 ? 'chamado' : 'chamados'}`
      + (f.os_falhou_em ? ` (última tentativa ${quando(f.os_falhou_em)})` : ''))
  }
  const explicados = (f.sem_tentativa || 0) + (f.os_falhou_chamados || 0)
  if (f.sem_os > explicados) {
    partes.push(`${f.sem_os - explicados} sem OS e sem motivo registrado`)
  }
  if (f.situacao_fora) {
    /* 🚨 A SITUAÇÃO VEM DO ERP, e dizer isso é o ponto: a OS está em `0` no
       Harmonit, e `0` não é uma das 17. Não é defeito nosso, e a frase antiga
       ("1 com situação fora das 17") fazia parecer que era. */
    const quais = f.fora_quais || []
    partes.push(quais.length
      ? quais.map((o) => `a OS ${o.numero_os} está em situação `
          + `${o.situacao_id} no Harmonit, que não é uma das 17`).join(' · ')
      : `${f.situacao_fora} com situação fora das 17`
        + (f.situacoes.length ? ` (${f.situacoes.join(', ')})` : ''))
  }
  return partes.join(' · ')
})

function quando(iso) {
  if (!iso) return '—'
  return new Date(iso).toLocaleString('pt-BR', { dateStyle: 'short', timeStyle: 'short' })
}

/* ============================================================================
   MOVER O CARD — Bloco D. 🔵 Dele: *"O card pode ser por arrastar"*.
   ----------------------------------------------------------------------------
   🚨 A ORDEM É LIVRE: *"que tal de caminho proibido é esse??"*. Não há mapa de
   transições aqui, nem no servidor, nem no Harmonit.

   🚨 A TRAVA DE CONCORRÊNCIA VAI NO PEDIDO: `situacao_esperada` é a situação
   que ESTE card carregava. Se o ERP já estiver em outra, o servidor recusa e a
   tela recarrega -- em vez de escrever por cima do que outra pessoa fez.

   ⚠️ E O CARD VOLTA SOZINHO quando a escrita falha: o movimento na tela é
   otimista (o card pula de coluna na hora), e o `catch` recarrega o quadro.
   Card que fica na coluna nova com a OS na antiga é a tela mentindo.
   ============================================================================ */
const arrastando = ref(null)
const movendo = ref(null)
const erroDeMover = ref('')

function comecarArrasto(card, evento) {
  if (!quadro.value?.pode_mover) return
  arrastando.value = card
  /* ⚠️ `move` e não `copy`: o cursor tem de dizer que isto MOVE. */
  if (evento.dataTransfer) {
    evento.dataTransfer.effectAllowed = 'move'
    /* Alguns navegadores exigem algum dado para iniciar o arrasto. */
    evento.dataTransfer.setData('text/plain', String(card.numero_ordem || ''))
  }
}

function terminarArrasto() {
  arrastando.value = null
}

async function soltarNaColuna(coluna) {
  const card = arrastando.value
  arrastando.value = null
  if (!card || !quadro.value?.pode_mover) return
  /* Soltar na própria coluna não é movimento. */
  if (card.situacao_id === coluna.situacao_id) return
  await mover(card, coluna.situacao_id)
}

async function mover(card, paraSituacao) {
  erroDeMover.value = ''
  movendo.value = card.numero_ordem
  try {
    const r = await api.post('/api/paineis/operacao/mover', {
      numero_os: card.numero_ordem,
      para_situacao: paraSituacao,
      /* 🚨 A trava de concorrência -- ver o comentário do bloco. */
      situacao_esperada: card.situacao_id,
    })
    if (!r.ok) {
      erroDeMover.value = r.motivo || 'Não consegui mover este card.'
    }
  } catch (e) {
    erroDeMover.value = e instanceof ErroDeApi
      ? e.message : 'Não consegui mover este card.'
  } finally {
    movendo.value = null
    /* 🚨 RECARREGA SEMPRE, deu certo ou não: a verdade é o que o ERP
       confirmou, nunca o que a tela achou que ia acontecer. */
    await carregar()
  }
}

/* 🔵 AS 6 CORES DO CATAVENTO, como código de etapa — do mockup que ele
   aprovou. Ciclam pelas 17 colunas, na ordem do fluxo.

   🚨 A COR NUNCA É O ÚNICO PORTADOR, e é regra desta casa: o nome da etapa e
   o número da situação no Harmonit continuam escritos em cada coluna. Quem não
   distingue as cores perde a decoração, nunca a informação. */
const CORES_DA_ETAPA = [
  '#8CC63F', '#FFC20E', '#F07F13', '#C4203F', '#1B75BB', '#41BFE8',
]

function corDaEtapa(i) {
  return CORES_DA_ETAPA[i % CORES_DA_ETAPA.length]
}

/* "há 2 dias", "hoje" — o que o card do mockup mostra no canto.
   ⚠️ É O TEMPO DESDE A ABERTURA, não o tempo na etapa: o tempo por etapa não
   existe no Harmonit (a linha do tempo registra só o `status`) e é o Bloco C
   desta frente. Escrever "nesta etapa" aqui seria a tela afirmando o que
   ninguém mediu. */
function ha(iso) {
  if (!iso) return ''
  const quandoFoi = new Date(iso)
  if (Number.isNaN(quandoFoi.getTime())) return ''
  const dias = Math.floor((Date.now() - quandoFoi.getTime()) / 86400000)
  if (dias <= 0) return 'hoje'
  if (dias === 1) return 'há 1 dia'
  return `há ${dias} dias`
}

const ROTULO_ESTADO = {
  nova: 'Nova', em_andamento: 'Em andamento', concluida: 'Concluída',
}

onMounted(carregar)
</script>

<template>
  <div class="tela">
    <header class="tela__cabecalho">
      <div>
        <h1>Operação</h1>
        <AjudaDaTela>
          As solicitações dos formulários da <strong>Operação</strong> (Suporte,
          Demonstração, Teste gratuito e Credenciamento técnico), em colunas
          nas <strong>17 situações da OS no Harmonit</strong>, na ordem do
          fluxo da operação. A OS nasce junto com o chamado, na primeira
          situação.
        </AjudaDaTela>
      </div>
      <button class="botao botao--contorno" type="button" @click="carregar">Atualizar</button>

        <!-- 🔵 D9 dele: a data matriz. A tela DIZ desde quando está montando,
             porque "o painel está vazio" e "o painel começa em 24/10" são
             respostas diferentes para a mesma tela vazia.
             ⚠️ Mudar a data é do OWNER (a rota recusa com 403), e por isso
             aqui ela é só TEXTO -- botão que o servidor recusa é pior que
             botão nenhum. -->
        <span v-if="quadro" class="painel__desde">
          desde {{ dia(quadro.desde) }}
        </span>

        <!-- 🚨 O INTERRUPTOR DAS FINALIZADAS, e o motivo de ele existir é
             medido: com ele ligado o Financeiro cai de 6 para 2 cards, porque
             OS financeira nasce `Finalizado`. Sem o interruptor, quem procura
             uma OS finalizada concluiria que ela não existe. -->
        <label class="painel__interruptor">
          <input type="checkbox" v-model="soAbertas" @change="carregar">
          <span>só as abertas</span>
        </label>
    </header>

    <p v-if="erro" class="aviso aviso--erro" role="alert">{{ erro }}</p>
    <!-- 🚨 A RECUSA DE MOVER É DITA, e com `alert`: a escrita no ERP não
         aconteceu, e o card já voltou para o lugar. Falha silenciosa aqui
         faria a pessoa pensar que gravou. -->
    <p v-if="erroDeMover" class="aviso aviso--erro" role="alert">
      {{ erroDeMover }}
    </p>
    <p v-if="carregando" class="apagado">Lendo…</p>

    <template v-if="quadro">
      <!-- 🚨 A PONTE CAÍDA É O PRIMEIRO AVISO, acima de todos os outros, e
           com cara de erro: sem ela o quadro mostra só o que o nosso banco
           sabe, e hoje isso são 2 cards em vez de 10. Quadro pequeno sem
           explicação faria o operador concluir que não há trabalho -- e é
           justo nessa hora que há. -->
      <p v-if="quadro && !quadro.ponte_respondeu" class="aviso aviso--erro"
         role="alert">
        <i class="bi bi-plug aviso__icone" aria-hidden="true"></i>
        <span>
          O FPSL não respondeu, então este quadro mostra <strong>só os
          chamados que já têm OS registrada aqui</strong> — as OS abertas
          direto no Harmonit não aparecem agora.
        </span>
      </p>

      <!-- 🚨 CARA DE ATENÇÃO SÓ QUANDO ALGO FALHOU DE VERDADE. Ele leu esta
           linha em 29/10 e perguntou *"pq deu erro?"* -- e nada havia
           falhado: era um chamado aguardando e uma OS que o ERP tem em
           situação 0. O triângulo e o estilo de atenção diziam "problema", e
           a pessoa vai procurar um erro que não existe. Falha de abertura de
           OS é problema; o resto é nota. -->
      <!-- ⚠️ `aviso--fora` existe para quem TESTA poder apontar para ESTA
           linha: a tela tem tres `.aviso` (erro de leitura, ponte caida, e
           esta), e um seletor generico pega a primeira do DOM. -->
      <p v-if="fora" class="aviso aviso--fora"
         :class="quadro.fora_do_quadro.os_falhou ? 'aviso--atencao' : 'aviso--nota'"
         role="status">
        <i class="aviso__icone" aria-hidden="true"
           :class="quadro.fora_do_quadro.os_falhou
                     ? 'bi bi-exclamation-triangle' : 'bi bi-info-circle'"></i>
        <span>{{ fora }} — abra em <strong>Solicitações</strong>.</span>
      </p>

      <!-- 🔵 29/10, ele: *"os comentários tbm devem sumir dali"*. Saíram os
           três textos que ficavam aqui -- o aviso de que mover não existe, a
           lista dos formulários com a contagem de campos, e o cartão de
           "nenhuma solicitação chegou ainda".
           ⚠️ O que saiu é o TEXTO: mover continua não existindo
           (`quadro.pode_mover` segue falso e não há gesto de arrastar), e
           coluna vazia continua colapsada com o contador à vista.
           🚨 E a palavra do atributo de arrastar NÃO SE ESCREVE neste
           comentário: comentário de HTML entra no `html()` renderizado, e a
           trava que garante a ausência do gesto procura exatamente essa
           palavra -- escrevê-la aqui fazia o teste reprovar com a tela
           correta. -->

      <div class="quadro">
        <section
          v-for="(coluna, indice) in quadro.colunas"
          :key="coluna.chave"
          class="coluna"
          :class="{ 'coluna--fechada': !abertas[coluna.chave],
                    'coluna--vazia': !coluna.total }"
          :style="{ borderTopColor: corDaEtapa(indice) }"
          :aria-label="coluna.titulo"
          @dragover.prevent
          @drop.prevent="soltarNaColuna(coluna)"
        >
          <h2 class="coluna__titulo">
            <!-- ⚠️ Toda coluna colapsa desde 29/10: as duas que eram fixas
                 ("Sem OS" e "Sem situacao") sairam do painel. -->
            <button
              class="coluna__botao"
              type="button"
              :aria-expanded="abertas[coluna.chave] ? 'true' : 'false'"
              @click="alternar(coluna)"
            >
              <span class="coluna__nome">{{ coluna.titulo }}</span>
              <!-- 🚨 CHEIO quando tem card, vazado quando não tem: o quadro
                   tem 17 colunas, e a diferença entre "0" e "3" precisa se ver
                   de longe, sem contar casa por casa. -->
              <span class="coluna__conta"
                    :class="{ 'coluna__conta--zero': !coluna.total }">
                {{ coluna.total }}
              </span>
            </button>
          </h2>

          <div v-if="abertas[coluna.chave]" class="coluna__corpo">
            <p v-if="coluna.nota" class="apagado pequeno">{{ coluna.nota }}</p>
            <p v-if="coluna.situacao_id" class="apagado pequeno">
              situação {{ coluna.situacao_id }} no Harmonit
            </p>

            <!-- 🚨 A OS VEM NA FRENTE, e isto mudou com a D8: até 29/10 o card
                 começava pelo nome do formulário, e desde que o card é a OS
                 "de qualquer origem" a maioria não tem formulário nenhum --
                 10 de 10 medidos hoje vêm do ERP. O card começava com um
                 campo vazio. -->
            <article v-for="card in coluna.cards"
                     :key="card.numero_ordem || card.id" class="card"
                     :class="{ 'card--movendo': movendo === card.numero_ordem }"
                     :draggable="quadro.pode_mover && !!card.numero_ordem"
                     @dragstart="comecarArrasto(card, $event)"
                     @dragend="terminarArrasto">
              <button class="card__abrir" type="button"
                      :style="{ borderLeftColor: corDaEtapa(indice) }"
                      @click="abrirSolicitacao(card)">
                <span class="card__topo">
                  <strong class="card__os">OS {{ card.numero_ordem || card.os_id }}</strong>
                  <span v-if="ha(card.criada_em)" class="card__ha">
                    {{ ha(card.criada_em) }}
                  </span>
                </span>

                <span v-if="card.cliente" class="card__cliente">{{ card.cliente }}</span>
                <!-- ⚠️ Cliente sem nome é DITO, não deixado em branco: o
                     `harmonit_id` da OS pode não estar no nosso cadastro. Hoje
                     os 9 clientes das OS estão todos lá, e por isso esta linha
                     não aparece -- mas basta uma OS de cliente novo. -->
                <span v-else class="card__cliente card__cliente--sem">
                  cliente {{ card.cliente_id || '?' }}, fora do nosso cadastro
                </span>

                <span v-if="card.tipo_nome" class="card__tipo">{{ card.tipo_nome }}</span>

                <!-- As placas da OS, que só a ponte sabe. -->
                <span v-if="card.placas && card.placas.length" class="card__dado">
                  {{ card.placas.map((p) => p.placa).join(' · ') }}
                </span>

                <span class="card__pistas">
                  <!-- ⚠️ A situação CRUA fica à vista: `0` é um valor que
                       existe em 129 OS, e o que fazer com ele é decisão dele. -->
                  <span v-if="card.situacao_id !== null" class="pilula">
                    situação {{ card.situacao_id }}
                  </span>
                  <span v-else class="pilula">situação nunca lida</span>

                  <span v-if="card.origem === 'erp'" class="pilula">Harmonit</span>
                  <span v-else-if="card.formulario" class="pilula">{{ card.formulario }}</span>

                  <span v-if="card.estado" class="etiqueta"
                        :class="`etiqueta--${card.estado}`">
                    {{ ROTULO_ESTADO[card.estado] || card.estado }}
                  </span>

                  <span v-if="card.anexos" class="pilula">
                    {{ card.anexos }} anexo(s)
                  </span>

                  <!-- 🚨 FINALIZADA É AVISO, não decoração: ela só aparece com
                       o interruptor desligado, e sem esta marca ficaria
                       indistinguível de uma OS viva na mesma coluna. -->
                  <span v-if="card.finalizada" class="card__alerta">finalizada</span>
                </span>

                <!-- ⚠️ Quando este dado foi lido do ERP. A varredura roda a
                     cada 5 min, e a tela não pode deixar supor que é agora. -->
                <span v-if="card.visto_em" class="card__visto">
                  lido do Harmonit {{ quando(card.visto_em) }}
                </span>
              </button>

              <!-- ⚠️ O MESMO CAMINHO, OUTRO GESTO. Arrastar foi a escolha dele
                   e é o gesto principal; mas arrastar **não é alcançável por
                   teclado**, e sem isto o painel passaria a ter uma ação que
                   só funciona com mouse. São 6 linhas, e é o que faz o recurso
                   existir para quem usa teclado ou leitor de tela. -->
              <label v-if="quadro.pode_mover && card.numero_ordem"
                     class="card__mover">
                <span class="so-leitor">
                  Mover a OS {{ card.numero_ordem }} para outra etapa
                </span>
                <select :value="card.situacao_id"
                        :disabled="movendo === card.numero_ordem"
                        @change="mover(card, Number($event.target.value))">
                  <option v-for="c in quadro.colunas" :key="c.chave"
                          :value="c.situacao_id">{{ c.titulo }}</option>
                </select>
              </label>
            </article>

            <p v-if="!coluna.cards.length" class="apagado pequeno">Vazia.</p>
          </div>
        </section>
      </div>
    </template>
  </div>
</template>

<style scoped>
.tela__cabecalho { display: flex; align-items: flex-start; justify-content: space-between; gap: var(--e-3); margin-bottom: var(--e-4); }
.tela__cabecalho h1 { margin: 0; font-size: var(--txt-xl); }


.quadro { display: flex; gap: var(--e-3); overflow-x: auto; padding-bottom: var(--e-3); align-items: flex-start; }

/* 🔵 A BORDA DE CIMA É A COR DA ETAPA — do mockup. A cor vem do `:style`,
   porque são 17 colunas ciclando 6 cores e isso é dado, não folha de estilo. */
.coluna {
  flex: 0 0 248px;
  background: var(--superficie);
  border: var(--borda-fina) solid var(--borda);
  border-top: 3px solid var(--borda-forte);
  border-radius: var(--r-md);
  transition: box-shadow .15s ease;
}
.coluna:hover { box-shadow: var(--sombra-1); }
/* ⚠️ Coluna sem card fica mais apagada, mas NUNCA escondida: o contador é a
   informação dela. */
.coluna--vazia { background: var(--superficie-2); }

.coluna__nome { line-height: 1.3; }

.painel__desde { font-size: var(--txt-xs); color: var(--texto-fraco); }
/* Nota neutra: informa, nao alarma. Ver o comentario no `template`. */
.aviso--nota {
  background: var(--superficie-2);
  border: var(--borda-fina) solid var(--borda);
  color: var(--texto-fraco);
}
.painel__interruptor {
  display: flex; align-items: center; gap: var(--e-1);
  min-height: var(--altura-toque);
  font-size: var(--txt-xs); color: var(--texto-fraco);
  cursor: pointer;
}
/* 🚨 Colapsada fica ESTREITA, não invisível: o contador continua à vista. */
.coluna--fechada { flex: 0 0 210px; }

.coluna__titulo { margin: 0; font-size: var(--txt-sm); }
.coluna__botao {
  width: 100%;
  min-height: var(--altura-toque);
  display: flex; align-items: center; justify-content: space-between; gap: var(--e-2);
  padding: var(--e-2) var(--e-3);
  border: 0; border-bottom: var(--borda-fina) solid var(--borda);
  border-radius: var(--r-md) var(--r-md) 0 0;
  background: var(--superficie-2);
  color: var(--texto);
  font-size: var(--txt-sm); font-weight: var(--peso-forte);
  text-align: left;
  cursor: pointer;
}
.coluna__botao--fixo { cursor: default; }
.coluna--sem-os .coluna__botao { background: var(--acento-suave); color: var(--acento); }
.coluna--sem-situacao .coluna__botao { background: var(--aviso-suave); color: var(--aviso); }
/* Cheio = tem card. Ver o comentário no `template`. */
.coluna__conta {
  background: var(--texto);
  color: var(--superficie);
  border: var(--borda-fina) solid var(--texto);
  border-radius: var(--r-full);
  min-width: 22px;
  padding: 0 var(--e-2);
  font-size: var(--txt-xs);
  font-weight: var(--peso-forte);
  text-align: center;
}
.coluna__conta--zero {
  background: var(--superficie);
  color: var(--texto-apagado);
  border-color: var(--borda-forte);
  font-weight: var(--peso-normal);
}
.coluna__corpo { padding: var(--e-3); display: flex; flex-direction: column; gap: var(--e-2); }

.card { display: block; }
/* 🔵 O gesto dele. ⚠️ `grab` no card inteiro, e `grabbing` enquanto arrasta. */
.card[draggable="true"] { cursor: grab; }
.card[draggable="true"]:active { cursor: grabbing; }
/* Enquanto a escrita no ERP não voltou, o card fica apagado e o select
   desabilitado -- dois cliques seguidos seriam duas escritas. */
.card--movendo { opacity: .55; pointer-events: none; }
.card__mover { display: block; margin-top: var(--e-1); }
.card__mover select {
  width: 100%;
  min-height: var(--altura-toque);
  padding: var(--e-1) var(--e-2);
  border: var(--borda-fina) solid var(--borda);
  border-radius: var(--r-sm, 6px);
  background: var(--superficie);
  color: var(--texto-fraco);
  font-size: var(--txt-xs);
}
.card__abrir {
  width: 100%;
  min-height: var(--altura-toque);
  display: flex; flex-direction: column; gap: 2px;
  padding: var(--e-3);
  text-align: left;
  background: var(--superficie);
  border: var(--borda-fina) solid var(--borda);
  border-left: 3px solid var(--acento);
  border-radius: var(--r-md);
  color: var(--texto);
  cursor: pointer;
}
/* 🔵 O EFEITO QUE ELE PEDIU: o card levanta e ganha sombra na passagem.
   ⚠️ `prefers-reduced-motion` desliga o movimento e mantém a sombra -- quem
   pediu menos movimento no sistema continua vendo que o card responde. */
.card__abrir { transition: box-shadow .15s ease, transform .15s ease, border-color .15s ease; }
.card__abrir:hover {
  background: var(--superficie-2);
  box-shadow: var(--sombra-1);
  transform: translateY(-1px);
}
.card__abrir:active { transform: translateY(0); }
@media (prefers-reduced-motion: reduce) {
  .card__abrir, .coluna { transition: none; }
  .card__abrir:hover { transform: none; }
}

.card__topo { display: flex; align-items: baseline; justify-content: space-between; gap: var(--e-2); }
.card__os { font-size: var(--txt-md); }
.card__ha { font-size: var(--txt-xs); color: var(--texto-fraco); }
.card__cliente { font-size: var(--txt-sm); font-weight: var(--peso-forte); }
.card__cliente--sem { font-weight: var(--peso-normal); color: var(--texto-fraco); font-style: italic; }
.card__tipo { font-size: var(--txt-xs); color: var(--texto-fraco); }
.card__dado {
  align-self: flex-start;
  font-size: var(--txt-xs);
  background: var(--superficie-3, var(--superficie-2));
  border-radius: var(--r-sm, 6px);
  padding: 2px var(--e-1);
}
.card__pistas { display: flex; flex-wrap: wrap; gap: var(--e-1); align-items: center; margin-top: var(--e-1); }
.card__visto { font-size: var(--txt-xs); color: var(--texto-apagado); }
/* 🚨 Aviso, não decoração: ver o comentário no `template`. */
.card__alerta { font-size: var(--txt-xs); color: var(--erro); font-weight: var(--peso-forte); }

.pilula {
  font-size: var(--txt-xs);
  color: var(--texto-fraco);
  border: var(--borda-fina) solid var(--borda);
  border-radius: var(--r-full);
  padding: 0 var(--e-2);
}

.etiqueta { padding: 0 var(--e-2); border-radius: var(--r-full); font-size: var(--txt-xs); border: var(--borda-fina) solid var(--borda); }
.etiqueta--nova { background: var(--acento-suave); border-color: var(--acento-borda); color: var(--acento); }
.etiqueta--em_andamento { background: var(--aviso-suave); border-color: var(--aviso); color: var(--aviso); }
.etiqueta--concluida { background: var(--ok-suave); border-color: var(--ok-borda); color: var(--ok); }
</style>
