<script setup>
/* ============================================================================
   O CORPO DO CARD — um só, para a Operação e para as abas de pipeline
   ----------------------------------------------------------------------------
   🚨 ESTE ARQUIVO NASCEU DE UMA PERGUNTA DELE EM 18/11: *"Então pq os cards
   informam que não vem de OS no painel?"* — e a resposta medida foi que havia
   **dois desenhos para a mesma caixa**.

   📏 Os 8 cards do Financeiro naquele dia eram **todos OS** (17120, 17119,
   17122, 17127, 17125, 17129, 17134, 17136), nenhum vindo de formulário: a
   `formulario_solicitacao` não tinha uma linha dos 4 formulários que apontam a
   etapa 875. Quem os trouxe foi `recebe_situacao = 15746`.

   E ainda assim o card do Financeiro:
     · recebia a borda `.card__abrir--chamado`, cujo comentário dizia, com
       estas palavras, *"o card de CHAMADO é visivelmente outro: ele não é uma
       OS"*;
     · desenhava **6** campos, quando o servidor já mandava mais de 20.

   🚨 O PIOR ERA A SEGUNDA PARTE. `_card_do_chamado` já devolvia `tipo_nome`,
   `status_str`, `placas`, `tecnicos`, `termo`, `prioridade`, `visto_em`,
   `etapa_desde`, `prazo` e `finalizada` -- tudo isso entrou em 12/11 a pedido
   dele (*"nos cards do financeiro, faltam informações sobre o tipo do termo,
   número do termo"* / *"igual da OP"*). O backend ganhou os campos, a tela das
   abas nunca os mostrou, e **nenhuma suíte reclamou**: `M12` por omissão.

   ⚠️ A CAUSA ERA ESTRUTURAL, não esquecimento: dois `<article>` em dois
   arquivos. Enquanto forem dois, o próximo campo vai entrar num e faltar no
   outro. Este componente é o conserto da causa.

   🔵 *"Faltam recursos do card do suporte da mesma etapa 1, devem ter os
   mesmos itens. Os cards do financeiro estão crus e fora do padrão."*

   🚨 E A REGRA QUE ESTE COMPONENTE SEGUE: **o que a OS tem aparece quando há
   OS; o que o chamado tem aparece quando há chamado.** Um card, dois conjuntos
   de campos, **zero campos inventados** -- nulo continua querendo dizer "não
   medido", nunca zero.
   ============================================================================ */
import { computed } from 'vue'

const props = defineProps({
  card: { type: Object, required: true },
  /* ⚠️ Os selos de pendência e da trava de 60s são da Operação: só lá o mover
     escreve no ERP. Nas abas o mover grava no nosso banco, então não existe
     escrita pendente -- e mostrar o selo ali seria inventar um estado. */
  mostrarPendencia: { type: Boolean, default: false },
  segundosDeEspera: { type: Number, default: 0 },
})

defineEmits(['abrir'])

const PARADO_DEMAIS_DIAS = 3
const PRIORIDADE_NORMAL = 382

const ROTULO_ESTADO = {
  nova: 'Nova', em_andamento: 'Em andamento', concluida: 'Concluída',
}

/* 🚨 A PERGUNTA QUE O DEFEITO DE 18/11 EXIGIU: este card é de OS?
   ⚠️ A resposta é `numero_os` **ou** `numero_ordem`, e os dois existem por
   motivos diferentes. Na Operação a OS vem em `numero_ordem`; nas abas vem em
   `numero_os`, e `numero_ordem` fica NULO de propósito -- é esse nulo que
   mantém o card sem arrasto para o ERP numa aba cujo mover grava só no nosso
   banco. Quem decide a aparência é ter OS; quem decide o GESTO continua sendo
   o nulo, e ele não é tocado aqui. */
const temOS = computed(
  () => !!(props.card.numero_os || props.card.numero_ordem))

const numeroDaOS = computed(
  () => props.card.numero_ordem || props.card.numero_os || props.card.os_id)

function dataCurta(iso) {
  if (!iso) return '—'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return '—'
  const mesmoAno = d.getFullYear() === new Date().getFullYear()
  return d.toLocaleDateString('pt-BR', mesmoAno
    ? { day: '2-digit', month: '2-digit' }
    : { day: '2-digit', month: '2-digit', year: 'numeric' })
}

function quando(iso) {
  if (!iso) return '—'
  return new Date(iso).toLocaleString('pt-BR',
                                      { dateStyle: 'short', timeStyle: 'short' })
}

function ha(iso) {
  if (!iso) return ''
  const quandoFoi = new Date(iso)
  if (Number.isNaN(quandoFoi.getTime())) return ''
  const dias = Math.floor((Date.now() - quandoFoi.getTime()) / 86400000)
  if (dias <= 0) return 'hoje'
  if (dias === 1) return 'há 1 dia'
  return `há ${dias} dias`
}

function duracao(iso) {
  if (!iso) return null
  const t = new Date(iso).getTime()
  if (Number.isNaN(t)) return null
  let seg = Math.max(0, Math.floor((Date.now() - t) / 1000))
  const d = Math.floor(seg / 86400); seg -= d * 86400
  const h = Math.floor(seg / 3600); seg -= h * 3600
  const m = Math.floor(seg / 60)
  if (d) return `${d}d ${h}h`
  if (h) return `${h}h ${m}min`
  return `${m}min`
}

function prazoCurto(prazo) {
  if (!prazo || !prazo.vence_em) return null
  const seg = Math.abs(Math.floor(Number(prazo.segundos_uteis) || 0))
  const h = Math.floor(seg / 3600)
  const m = Math.floor((seg % 3600) / 60)
  const quanto = h ? `${h}h ${m}min` : `${m}min`
  /* ⚠️ "úteis" fica escrito: 7h de prazo numa sexta às 16h não são 7h de
     relógio, e sem a palavra o número parece errado para quem olha o
     reloginho. */
  return prazo.atrasado
    ? `atrasado há ${quanto} úteis`
    : `vence em ${quanto} úteis`
}

function diasNaEtapa(card) {
  /* ⚠️ `etapa_desde` NULO quer dizer "não medido" (a `os_passagem` começou em
     29/10), e não-medido NUNCA acende alerta: seria afirmar um atraso que
     ninguém mediu. */
  if (!card || !card.etapa_desde) return null
  const t = new Date(card.etapa_desde).getTime()
  if (Number.isNaN(t)) return null
  return (Date.now() - t) / 86400000
}

const paradoDemais = computed(() => {
  const d = diasNaEtapa(props.card)
  return d !== null && d >= PARADO_DEMAIS_DIAS
})

const prioridadeDeExcecao = computed(() => {
  /* ⚠️ Prioridade NULA = a varredura ainda não releu esta OS. Nulo não é
     exceção, é ausência de medida. */
  const c = props.card
  return !!(c && c.prioridade) && c.prioridade !== PRIORIDADE_NORMAL
})

const ehExcecao = computed(() => paradoDemais.value || prioridadeDeExcecao.value)

const placas = computed(() => {
  const p = props.card.placas
  return Array.isArray(p) && p.length
    ? p.map((x) => x.placa).filter(Boolean).join(' · ')
    : ''
})

function tituloDaPendencia(card) {
  /* 🚨 O MOTIVO POR EXTENSO no `title`, que é a pendência 4 dele: *"os motivos
     de recusa deve aparecer descritos ao inves de erro generico, para que me
     tragam o problema ja cientes"*. */
  const partes = ['O card já está nesta coluna, e a OS no Harmonit ainda não '
                  + 'confirmou. A escrita está na fila e insiste sozinha.']
  if (card.situacao_do_erp) {
    partes.push('A OS ainda diz: ' + card.situacao_do_erp + '.')
  }
  if (card.pendente_erro) partes.push('Último retorno: ' + card.pendente_erro)
  return partes.join(' ')
}

defineExpose({ ehExcecao, temOS })
</script>

<template>
  <!-- 🚨 `card__abrir--chamado` SÓ PARA CARD SEM OS, e é literalmente o defeito
       que ele achou: 8 cards de OS no Financeiro recebiam a borda cujo
       comentário dizia *"ele não é uma OS"*.
       ⚠️ O comentário mora AQUI e não dentro do `:class`: comentário de bloco
       dentro de expressão de template é erro de sintaxe, e ele derrubou 10
       arquivos de teste de uma vez quando eu o escrevi lá. -->
  <div class="card__abrir"
       :class="{ 'card__abrir--excecao': ehExcecao,
                 'card__abrir--chamado': !temOS,
                 'card__abrir--arquivado': !!card.desfecho }"
       @click="$emit('abrir', card)">

    <!-- 🔵 O SELO DO DESFECHO: *"ele esmaece e fica no fim da fila arquivado
         com status de concluído"*. ⚠️ O esmaecer sozinho não diz QUAL dos dois
         foi — opacidade não é portadora de informação. -->
    <span v-if="card.desfecho" class="card__arquivado">
      <i class="bi bi-archive" aria-hidden="true"></i>
      {{ card.desfecho_rotulo || card.desfecho }}
      <template v-if="card.desfecho_em">
        &middot; {{ dataCurta(card.desfecho_em) }}
      </template>
    </span>

    <!-- 🚨 O SELO DA PENDÊNCIA (migração 115). ⚠️ Só na Operação: nas abas o
         mover grava no nosso banco e não há escrita pendente. -->
    <span v-if="mostrarPendencia && card.passagem_pendente"
          class="card__pendente" :title="tituloDaPendencia(card)">
      <i class="bi bi-hourglass-split" aria-hidden="true"></i>
      ainda não foi para a OS
      <template v-if="card.pendente_tentativas">
        &middot; {{ card.pendente_tentativas }}ª tentativa
      </template>
    </span>

    <!-- 🔵 A TRAVA DE 1 MINUTO (18/11). 🚨 A razão fica ESCRITA, com a
         contagem: card que para de arrastar sem dizer nada faz o operador
         concluir que travou e clicar mais -- o laço de 7 cliques da OS 17133.
         ⚠️ A guarda de verdade está no servidor; isto é a explicação. -->
    <span v-if="segundosDeEspera" class="card__assentando">
      <i class="bi bi-pause-circle" aria-hidden="true"></i>
      acabou de ser movido &middot; espere {{ segundosDeEspera }}s
    </span>

    <!-- LINHA 1 — O CLIENTE. 🔵 Variante C, escolhida por ele em 05/11.
         🚨 Corta em duas linhas, com o nome inteiro no `title`. -->
    <span class="card__linha">
      <span v-if="card.cliente" class="card__cliente"
            :title="card.cliente">{{ card.cliente }}</span>
      <!-- ⚠️ Cliente sem nome é DITO, não deixado em branco: o `harmonit_id`
           da OS pode não estar no nosso cadastro. -->
      <span v-else class="card__cliente card__cliente--sem">
        cliente {{ card.cliente_id || '?' }}, fora do nosso cadastro
      </span>
      <span v-if="ha(card.criada_em)" class="card__direita">
        {{ ha(card.criada_em) }}
      </span>
    </span>

    <!-- LINHA 2 — os identificadores com que se cruza papel.
         ⚠️ A OS continua sendo o BOTÃO (o alvo de teclado) e o único em cor de
         acento; o TERMO é referência, não ação. -->
    <span class="card__linha">
      <span class="card__ident">
        <!-- ⚠️ CHAMADO NÃO TEM NÚMERO DE OS, e a tela não inventa um: o que
             identifica o chamado é o formulário de onde ele veio. -->
        <button v-if="!temOS" class="card__os" type="button"
                @click.stop="$emit('abrir', card)">
          {{ card.formulario || 'Card ' + card.id }}
        </button>
        <button v-else class="card__os" type="button"
                @click.stop="$emit('abrir', card)">OS {{ numeroDaOS }}</button>
        <!-- ⚠️ OS SEM TERMO É 1 DE CADA 7, e a tela não diz nada: venda,
             cartão RFID e manutenção não nascem de termo. -->
        <span v-if="card.termo" class="card__termo">TERMO {{ card.termo }}</span>
      </span>
      <span v-if="card.tipo_nome || placas"
            class="card__direita card__direita--dado">
        <template v-if="card.tipo_nome">{{ card.tipo_nome }}</template>
        <template v-if="card.tipo_nome && placas"> &middot; </template>
        <template v-if="placas">{{ placas }}</template>
      </span>
    </span>

    <!-- LINHA 3 — os dois tempos. ⚠️ "não medido" quando não há passagem:
         mostrar "0h" seria afirmar o que ninguém mediu. -->
    <span class="card__linha card__dado">
      <span class="card__etapa"
            :class="{ 'card__etapa--parado': paradoDemais }">
        nesta etapa
        <strong>{{ duracao(card.etapa_desde) || 'não medido' }}</strong>
        <template v-if="duracao(card.criada_em)">
          &middot; total {{ duracao(card.criada_em) }}
        </template>
      </span>
    </span>

    <!-- 🔵 O PRAZO, só onde ele existe: hoje é o card de chamado.
         ⚠️ O selo DIZ "atrasado" por extenso, nunca só por cor. -->
    <span v-if="prazoCurto(card.prazo)" class="card__linha card__dado">
      <span class="card__prazo"
            :class="{ 'card__prazo--atrasado': card.prazo.atrasado }">
        <i class="bi bi-hourglass-split" aria-hidden="true"></i>
        {{ prazoCurto(card.prazo) }}
      </span>
    </span>

    <!-- LINHA 4 — os selos à esquerda, a data à direita. -->
    <span class="card__linha">
      <span class="card__pistas">
        <!-- ⚠️ O que distingue é ter vindo de FORMULÁRIO: a origem ERP é a
             maioria, e um selo em quase todo card não distingue nada.
             🚨 A PERGUNTA É `origem !== 'erp'`, NÃO `!temOS` -- e eu errei isto
             primeiro, derrubando dois testes de 22/10 e 05/11. OS nascida de
             formulário TEM OS **e** tem formulário, e o nome do formulário é
             justamente o que ela precisa mostrar. Trocar por `!temOS` escondia
             a origem exatamente no caso em que ela informa algo. -->
        <span v-if="card.origem !== 'erp' && card.formulario"
              class="pilula pilula--origem">{{ card.formulario }}</span>

        <span v-if="card.estado" class="etiqueta"
              :class="`etiqueta--${card.estado}`">
          {{ ROTULO_ESTADO[card.estado] || card.estado }}
        </span>

        <span v-if="card.anexos" class="pilula">{{ card.anexos }} anexo(s)</span>

        <!-- 🔵 *"a prioridade vem escrita porque ela nasce Normal e mudar e
             excecao, e excecao precisa estar visivel sem abrir"*. 🚨 Só a
             exceção aparece: *Normal* em todo card não distinguia nada. -->
        <span v-if="prioridadeDeExcecao" class="pilula pilula--alerta">
          {{ card.prioridade_nome }}
        </span>

        <!-- 🔵 04/11: o selo do checklist. ⚠️ `tem_checklist` e `checklist`
             são coisas diferentes: a etapa pode TER lista e o card ainda não a
             ter aberto. 🚨 Completo fica verde, incompleto âmbar. -->
        <span v-if="card.checklist" class="pilula"
              :class="card.checklist.feitos >= card.checklist.total
                      ? 'pilula--pronto' : 'pilula--alerta'">
          {{ card.checklist.feitos }} de {{ card.checklist.total }}
        </span>
        <span v-else-if="card.tem_checklist" class="pilula">checklist</span>

        <span v-if="card.observacoes" class="pilula">
          {{ card.observacoes }} obs
        </span>

        <!-- 🚨 FINALIZADA É AVISO, não decoração: sem esta marca ficaria
             indistinguível de uma OS viva na mesma coluna. -->
        <span v-if="card.finalizada" class="card__alerta">finalizada</span>
      </span>

      <!-- 🚨 *"PREVISÃO"*, e não *"prazo"*: medido, a OS do Harmonit tem UM
           campo de data (`dataPrevisao`) e não existe campo de prazo. -->
      <span v-if="card.criada_em" class="card__direita">
        previsão {{ dataCurta(card.criada_em) }}
      </span>
    </span>

    <!-- ⚠️ Quando este dado foi lido do ERP. A varredura roda a cada 5 min, e
         a tela não pode deixar supor que é agora.
         🚨 E O CAMPO É `atualizado_em`, NÃO `visto_em` do cache: `visto_em` é
         a PRIMEIRA vez que a OS foi vista e é preservado para sempre. Quem
         escolhe isso é o servidor; aqui só se mostra o que ele mandou. -->
    <span v-if="card.visto_em" class="card__visto">
      lido do Harmonit {{ quando(card.visto_em) }}
    </span>

    <!-- 🔵 O resumo das respostas do formulário, que é o que o card de chamado
         tem e a OS não. ⚠️ Fica no fim: é o campo mais comprido. -->
    <p v-if="card.resumo" class="card__resumo">{{ card.resumo }}</p>
  </div>
</template>

<style scoped>
/* 🚨 TODO O ESTILO DO CARD MORA AQUI, e isto é o ponto do arquivo. Enquanto o
   corpo estava em dois lugares, o estilo também estava -- e foi assim que o
   card do Financeiro ficou com 6 campos enquanto o da Operação tinha 20.

   ⚠️ AS CLASSES SÃO AS MESMAS DE ANTES, de propósito: `conferir_css_publicado.mjs`
   tem 9 conferências que olham nomes, e renomear aqui seria quebrar travas que
   guardam outras coisas. */
.card__abrir {
  display: flex; flex-direction: column; gap: var(--e-1);
  width: 100%; padding: var(--e-2) var(--e-3);
  border: var(--borda-fina) solid var(--borda);
  border-left: 3px solid transparent;
  border-radius: var(--r-md);
  background: var(--superficie);
  text-align: left; cursor: pointer;
}
.card__abrir:hover { background: var(--superficie-2); }

/* 🔵 A EXCEÇÃO, variante C: a única cor do card, e ela nunca está sozinha --
   o tempo da etapa fica âmbar e o selo da prioridade vira sólido. Quem não
   distingue a cor lê o número. */
.card__abrir--excecao { border-left-color: var(--aviso); }

/* 🔵 O card de CHAMADO é visivelmente outro: ele não é uma OS.
   🚨 E DESDE 18/11 ISTO VALE SÓ PARA CARD SEM OS. Antes, todo card de aba
   levava esta borda -- inclusive os 8 do Financeiro, que eram OS. A tela
   afirmava o contrário do que o dado dizia. */
.card__abrir--chamado { border-left-color: var(--acento); }

/* ⚠️ `opacity` NÃO É O PORTADOR: o selo com o nome do desfecho está no card. */
.card__abrir--arquivado { opacity: .62; }
.card__abrir--arquivado:hover { opacity: 1; }

.card__linha {
  display: flex; align-items: baseline; justify-content: space-between;
  gap: var(--e-2); width: 100%;
}
.card__cliente {
  font-weight: var(--peso-forte); font-size: var(--txt-sm);
  display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical;
  overflow: hidden;
}
.card__cliente--sem { font-weight: var(--peso-normal); color: var(--texto-fraco); }
.card__direita {
  flex: none; font-size: var(--txt-xs); color: var(--texto-fraco);
  white-space: nowrap;
}
.card__direita--dado { color: var(--texto); }
.card__ident { display: flex; align-items: baseline; gap: var(--e-2); min-width: 0; }
.card__os {
  padding: 0; border: 0; background: none; cursor: pointer;
  color: var(--acento); font-weight: var(--peso-forte); font-size: var(--txt-sm);
}
.card__termo { font-size: var(--txt-xs); color: var(--texto-fraco); white-space: nowrap; }
.card__dado { font-size: var(--txt-xs); color: var(--texto-fraco); }
.card__etapa--parado { color: var(--aviso); font-weight: var(--peso-forte); }
.card__prazo { display: inline-flex; align-items: center; gap: var(--e-1); }
.card__prazo--atrasado { color: var(--erro); font-weight: var(--peso-forte); }
.card__pistas { display: flex; flex-wrap: wrap; gap: var(--e-1); min-width: 0; }
.card__alerta {
  font-size: var(--txt-xs); font-weight: var(--peso-forte); color: var(--erro);
}
.card__visto { font-size: var(--txt-xs); color: var(--texto-fraco); }
.card__resumo {
  margin: 0; font-size: var(--txt-xs); color: var(--texto-fraco);
  display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical;
  overflow: hidden;
}
.card__arquivado,
.card__pendente,
.card__assentando {
  display: inline-flex; align-items: center; gap: var(--e-1);
  align-self: flex-start;
  padding: 1px var(--e-2);
  border: var(--borda-fina) solid var(--borda-forte);
  border-radius: var(--r-full);
  font-size: var(--txt-xs); font-weight: var(--peso-forte);
}
.card__arquivado,
.card__assentando { background: var(--superficie-2); color: var(--texto-fraco); }
.card__pendente {
  background: var(--aviso-fundo, var(--superficie-2));
  color: var(--aviso-texto, var(--texto-fraco));
}

/* 🚨 A PÍLULA TEM BASE NO MESMO ESCOPO, e isto é uma das 9 conferências de CSS
   publicado: `.pilula` é `scoped` por componente e NÃO existe em
   `estilo/*.css`. Um componente que a usa sem defini-la aqui desenha um selo
   sem estilo -- e o jsdom, que não faz layout, não pega. */
.pilula {
  display: inline-flex; align-items: center; gap: var(--e-1);
  padding: 1px var(--e-2);
  border: var(--borda-fina) solid var(--borda);
  border-radius: var(--r-full);
  background: var(--superficie-2);
  font-size: var(--txt-xs); color: var(--texto-fraco);
}
.pilula--origem { border-color: var(--acento); color: var(--acento); }
.pilula--alerta {
  border-color: var(--aviso); color: var(--aviso);
  font-weight: var(--peso-forte);
}
.pilula--pronto { border-color: var(--ok); color: var(--ok); }
.etiqueta {
  padding: 1px var(--e-2); border-radius: var(--r-full);
  font-size: var(--txt-xs); background: var(--superficie-2);
}
</style>
