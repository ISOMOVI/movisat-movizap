<script setup>
/* ============================================================================
   Menu lateral.
   ----------------------------------------------------------------------------
   🚨 O menu é DESENHADO, não decidido. Título, rota e ícone vêm de
   /api/telas — este componente não tem uma linha de "se for admin, mostra".
   Acrescentar uma tela é mexer em `movizap/telas.py`; aqui não se toca.

   O agrupamento por módulo sai do prefixo do código (ATD_, CAD_, CFG_), que
   é imutável por regra do registro. É apresentação, não permissão.
   ============================================================================ */
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import { sessao, sair } from '../estado/sessao.js'
import { api } from '../api/cliente.js'

const router = useRouter()

// 🔵 Erika pediu o selo de mensagem nova (15/09) -- a API já existia
// (`/api/chat/nao-lidas`, "o selo do menu" na própria docstring) e nada a
// chamava: mensagem no chat interno só se descobria abrindo a tela.
const naoLidas = ref(0)

/* 🟡 S11, feito em 15/09: `/api/chat/mencoes` tem conta SEPARADA de propósito
   ("40 não lidas num grupo é rotina; UMA em que te chamaram pelo nome não
   pode esperar") e não tinha um único chamador -- o `@` de 27/08 estava pela
   metade. Um selo só, que MUDA DE COR quando há menção: dois badges no mesmo
   item de menu brigariam por 18px e nenhum dos dois seria legível. */
const mencoes = ref(0)
let timerNaoLidas = null

async function atualizarNaoLidas() {
  // Só chama quem tem a tela -- caso contrário é 403 certo, todo intervalo.
  if (!sessao.telas.some((t) => t.codigo === 'ATD_6.1')) return
  try {
    const [r, m] = await Promise.all([
      api.get('/api/chat/nao-lidas'),
      api.get('/api/chat/mencoes'),
    ])
    naoLidas.value = r.nao_lidas || 0
    mencoes.value = (m || []).reduce((soma, s) => soma + Number(s.quantas || 0), 0)
  } catch {
    // silencioso -- selo é conveniência, não pode gerar erro na tela toda
  }
}

onMounted(() => {
  atualizarNaoLidas()
  timerNaoLidas = setInterval(atualizarNaoLidas, 15000)
})

onUnmounted(() => clearInterval(timerNaoLidas))

// 🔵 Rodrigo pediu (15/09): botão sanduíche -- aberto mostra tudo, fechado só
// ícone. Passar o mouse no fechado abre, mas sem fixar; só o botão fixa.
const CHAVE_COLAPSADO = 'movizap_menu_colapsado'

function lerColapsadoSalvo() {
  try {
    return localStorage.getItem(CHAVE_COLAPSADO) === '1'
  } catch {
    return false // sem localStorage (aba anônima, storage bloqueado): abre.
  }
}

const colapsado = ref(lerColapsadoSalvo())
const emHover = ref(false)

function alternarColapso() {
  colapsado.value = !colapsado.value
  try {
    localStorage.setItem(CHAVE_COLAPSADO, colapsado.value ? '1' : '0')
  } catch {
    // Não lembra na próxima visita -- não é motivo pra travar o clique.
  }
}

// O grid do App.vue é `auto 1fr`: a coluna do menu segue a largura real do
// `.menu`, então mudar a classe aqui já empurra o conteúdo sozinho -- não
// precisa de posição fixa nem de tocar em nenhum outro componente.
const visualCompacto = computed(() => colapsado.value && !emHover.value)

const NOME_DO_MODULO = {
  ATD: 'Atendimento',
  CAD: 'Cadastro',
  CFG: 'Configuração',
  REL: 'Relatórios',
}

/** Agrupa preservando a ordem em que o backend mandou. */
const grupos = computed(() => {
  const porModulo = new Map()
  for (const tela of sessao.telas) {
    // rota com parâmetro (/atendimento/{id}) não é item de menu: só se chega
    // nela a partir de outra tela.
    if (tela.rota.includes('{')) continue
    // 🚨 TELA QUE É ABA DE OUTRA NÃO É ITEM DE MENU (27/08). As seis telas de
    // configuração continuam existindo, com rota e permissão próprias -- elas
    // só deixaram de ocupar seis linhas do menu, que é o que fazia o usuário
    // ter de adivinhar em qual delas estava cada interruptor.
    //
    // ⚠️ APRESENTAÇÃO, NÃO PERMISSÃO. Elas continuam vindo em `sessao.telas`,
    // e têm de continuar: é essa lista que a guarda de rota usa para saber o
    // que este usuário pode abrir.
    if (tela.aba_de) continue
    const modulo = tela.codigo.split('_')[0]
    if (!porModulo.has(modulo)) porModulo.set(modulo, [])
    porModulo.get(modulo).push(tela)
  }
  return [...porModulo].map(([modulo, telas]) => ({
    modulo,
    nome: NOME_DO_MODULO[modulo] || modulo,
    telas,
  }))
})

function encerrar() {
  sair()
  router.push({ name: 'login' })
}
</script>

<template>
  <aside
    class="menu"
    :class="{ 'menu--compacto': visualCompacto }"
    @mouseenter="emHover = true"
    @mouseleave="emHover = false"
  >
    <div class="menu__topo">
      <div class="menu__marca">
        <img class="menu__logo" src="/movisat-logo.png" alt="Movisat" />
        <b class="menu__nome">MoviZap</b>
      </div>
      <button
        class="menu__colapsar"
        type="button"
        @click="alternarColapso"
        :title="colapsado ? 'Fixar menu aberto' : 'Recolher menu'"
      >
        <i class="bi bi-list" aria-hidden="true"></i>
      </button>
    </div>

    <nav class="menu__nav" aria-label="Telas">
      <div v-for="grupo in grupos" :key="grupo.modulo" class="menu__grupo">
        <p class="menu__grupo-nome">{{ grupo.nome }}</p>
        <RouterLink
          v-for="tela in grupo.telas"
          :key="tela.codigo"
          :to="tela.rota"
          class="menu__link"
          active-class="menu__link--ativo"
          :title="tela.codigo"
        >
          <i class="bi" :class="tela.icone" aria-hidden="true"></i>
          <span class="menu__titulo">{{ tela.titulo }}</span>
          <span
            v-if="tela.codigo === 'ATD_6.1' && naoLidas > 0"
            class="menu__selo"
            :class="{ 'menu__selo--mencao': mencoes > 0 }"
            :title="mencoes > 0
              ? `${mencoes} vez(es) em que te chamaram pelo nome, de ${naoLidas} não lida(s)`
              : `${naoLidas} mensagem(ns) nova(s) no chat interno`"
          >{{ naoLidas > 99 ? '99+' : naoLidas }}</span>
        </RouterLink>
      </div>

      <p v-if="!grupos.length" class="menu__vazio">
        Nenhuma tela liberada para esta conta.
      </p>
    </nav>

    <div class="menu__rodape">
      <button class="botao botao--contorno menu__acao" type="button" @click="encerrar">
        <i class="bi bi-box-arrow-left" aria-hidden="true"></i>
        <span class="menu__acao-texto">Sair</span>
      </button>
    </div>
  </aside>
</template>

<style scoped>
/* 🚨 O menu é ESCURO nos dois temas — é a assinatura visual do MoviChat e o
   que mais distingue o painel à primeira vista. Por isso usa os tokens
   --menu-*, que não seguem claro/escuro. */
.menu {
  grid-area: menu;
  display: flex;
  flex-direction: column;
  min-height: 0;
  width: var(--largura-menu);
  padding: var(--e-4) var(--e-3);
  background: var(--menu-fundo);
  color: var(--menu-texto);
  border-right: var(--borda-fina) solid var(--menu-borda);
  /* O grid do App.vue é `auto 1fr` -- a largura real do `.menu` já é a
     largura da coluna, então a transição aqui move o layout inteiro. */
  transition: width .15s ease;
}

.menu__topo {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--e-2);
  padding: 0 var(--e-2);
}

.menu__colapsar {
  flex: none;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border: none;
  border-radius: var(--r-sm);
  background: transparent;
  color: var(--menu-texto);
  cursor: pointer;
  font-size: 16px;
  transition: background var(--tempo-rapido) var(--curva);
}
.menu__colapsar:hover { background: var(--menu-hover); }

.menu__marca {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: var(--e-1);
  padding: var(--e-2) 0 var(--e-5);
  min-width: 0;
}
.menu__logo {
  height: 34px;
  width: auto;
  max-width: 100%;
  /* A logo é escura; no fundo escuro do menu ela precisa inverter. */
  filter: brightness(0) invert(1);
}
.menu__nome {
  font-size: var(--txt-sm);
  font-weight: var(--peso-forte);
  letter-spacing: .08em;
  text-transform: uppercase;
  color: var(--menu-texto);
}

.menu__nav { flex: 1 1 auto; overflow-y: auto; min-height: 0; }

.menu__grupo + .menu__grupo { margin-top: var(--e-4); }
.menu__grupo-nome {
  padding: 0 var(--e-3) var(--e-2);
  font-size: var(--txt-xs);
  font-weight: var(--peso-forte);
  text-transform: uppercase;
  letter-spacing: .06em;
  color: rgba(148, 163, 184, .62);
}

.menu__link {
  display: flex;
  align-items: center;
  gap: var(--e-3);
  min-height: var(--altura-toque);
  padding: 8px var(--e-3);
  border-radius: var(--r-sm);
  color: var(--menu-texto);
  font-size: var(--txt-md);
  text-decoration: none;
  transition: background var(--tempo-rapido) var(--curva),
              color var(--tempo-rapido) var(--curva);
}
.menu__link:hover {
  background: var(--menu-hover);
  color: var(--menu-texto-forte);
  text-decoration: none;
}
.menu__link--ativo {
  background: var(--acento);
  color: #fff;
  font-weight: var(--peso-forte);
}
.menu__link .bi { font-size: 15px; flex: none; width: 18px; text-align: center; }
.menu__titulo { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

.menu__selo {
  flex: none;
  margin-left: auto;
  min-width: 18px;
  height: 18px;
  padding: 0 5px;
  border-radius: 999px;
  background: var(--acento);
  color: #fff;
  font-size: 11px;
  font-weight: var(--peso-forte);
  line-height: 18px;
  text-align: center;
}
/* Ativo já usa o acento como fundo do link inteiro -- o selo muda de cor
   pra não desaparecer contra o próprio fundo. */
.menu__link--ativo .menu__selo { background: rgba(255, 255, 255, .3); }

/* Menção pesa mais que mensagem nova: o selo troca de cor em vez de ganhar
   um segundo badge ao lado (S11). */
.menu__selo--mencao { background: var(--erro); }
.menu__link--ativo .menu__selo--mencao { background: rgba(255, 255, 255, .45); }

.menu__vazio {
  padding: var(--e-4) var(--e-3);
  font-size: var(--txt-sm);
  color: rgba(148, 163, 184, .62);
}

.menu__rodape {
  flex: none;
  display: flex;
  flex-direction: column;
  gap: var(--e-2);
  margin-top: var(--e-4);
  padding-top: var(--e-3);
  border-top: var(--borda-fina) solid var(--menu-borda);
}
/* Os botões do rodapé vivem no fundo escuro: não podem herdar o botão claro. */
.menu__acao {
  justify-content: flex-start;
  min-height: var(--altura-toque);
  font-size: var(--txt-sm);
  background: transparent;
  border-color: var(--menu-borda);
  color: var(--menu-texto);
}
.menu__acao:hover:not(:disabled) {
  background: var(--menu-hover);
  border-color: rgba(255, 255, 255, .22);
  color: var(--menu-texto-forte);
}

/* Recolhido pelo botão (15/09, pedido do Rodrigo) -- mesmo visual do modo
   estreito de tela, só que por escolha da pessoa, e revertido ao passar o
   mouse (ver `visualCompacto` no script: hover tira esta classe sem mexer
   no que está fixado). Regras repetidas do `@media` abaixo de propósito --
   uma é presença de tela, a outra é escolha de quem usa; são independentes
   e não dá pra expressar as duas com um seletor só. */
.menu--compacto { width: 62px; padding: var(--e-3) var(--e-2); }
.menu--compacto .menu__nome,
.menu--compacto .menu__titulo,
.menu--compacto .menu__grupo-nome,
.menu--compacto .menu__acao-texto { display: none; }
.menu--compacto .menu__topo { flex-direction: column; align-items: center; gap: var(--e-2); padding: 0; }
.menu--compacto .menu__marca { align-items: center; padding: 0; }
.menu--compacto .menu__logo { height: 22px; }
.menu--compacto .menu__link { justify-content: center; padding: 10px 0; position: relative; }
.menu--compacto .menu__acao { justify-content: center; }
.menu--compacto .menu__selo { position: absolute; top: 2px; right: 6px; margin-left: 0; }

/* Estreitou: vira coluna de ícones. O rodapé CONTINUA — perder o "Sair" numa
   tela menor é o tipo de detalhe que só aparece com o usuário preso dentro. */
@media (max-width: 860px) {
  .menu { width: 62px; padding: var(--e-3) var(--e-2); }
  .menu__nome,
  .menu__titulo,
  .menu__grupo-nome,
  .menu__acao-texto { display: none; }
  .menu__topo { flex-direction: column; align-items: center; gap: var(--e-2); padding: 0; }
  .menu__marca { align-items: center; padding-left: 0; padding-right: 0; }
  .menu__logo { height: 22px; }
  .menu__link { justify-content: center; padding: 10px 0; position: relative; }
  .menu__acao { justify-content: center; }
  /* Compacto some com o título, não com o selo -- vira badge no canto do
     ícone, senão a mensagem nova fica invisível justo em quem recolheu o
     menu (S1 da rodada anterior). */
  .menu__selo {
    position: absolute;
    top: 2px;
    right: 6px;
    margin-left: 0;
  }
}
</style>
