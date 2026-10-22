<script setup>
/* ============================================================================
   Menu lateral.
   ----------------------------------------------------------------------------
   🚨 O menu é DESENHADO, não decidido. Título, rota e ícone vêm de
   /api/telas — este componente não tem uma linha de "se for admin, mostra".
   Acrescentar uma tela é mexer em `movizap/telas.py`; aqui não se toca.

   🚨 O AGRUPAMENTO DEIXOU DE SAIR DO PREFIXO EM 21/10. Grupo e subgrupo são
   dados da tela (`movizap/telas.py`), porque o código é imutável e deduzir o
   grupo dele impedia pôr "Ligações" dentro de Atendimento. Continua sendo
   apresentação, não permissão.
   ============================================================================ */
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { sessao, sair } from '../estado/sessao.js'
import { notificacoes } from '../estado/notificacoes.js'
import { api } from '../api/cliente.js'

const router = useRouter()
const rota = useRoute()

// 🔵 Erika pediu o selo de mensagem nova (15/09) -- a API já existia
// (`/api/chat/nao-lidas`, "o selo do menu" na própria docstring) e nada a
// chamava: mensagem no chat interno só se descobria abrindo a tela.
const naoLidas = ref(0)

/* 🔵 22/10, pedido dele: o selo do Chat interno passa a ter irmãos -- o do
   WhatsApp (*"conforme notificações da aba 'Minhas'"*) e o do E-mail (não
   lidos), e o cabeçalho de "Atendimento" fechado mostra A SOMA DOS TRÊS.

   🚨 OS DOIS NOVOS NÃO ABREM UM TERCEIRO RITMO. O `Notificador.vue` está
   montado no `App.vue` e já pergunta `/api/eu/notificacoes` de 8 em 8 s em
   TODA tela; o número de "Minhas" e o de e-mail saem de lá, do estado
   reativo, sem uma requisição nova. Selo que pisca em dois relógios
   diferentes (8 s e 15 s) mostraria soma que não bate com as partes por
   alguns segundos, e "a bolinha não pode discordar da aba" é a regra desta
   casa desde 24/09.

   ⚠️ O do Chat interno continua tendo chamada própria porque `nao-lidas` e
   `mencoes` exigem a ATD_6.1 e trazem a conta de menção separada (a que muda
   a COR do selo) -- juntá-los a esta rota é uma limpeza de outro dia. */
const naoLidasWhatsapp = computed(() => notificacoes.abas?.minhas || 0)
const naoLidosEmail = computed(() => notificacoes.email_nao_lidos || 0)

/* A soma que o grupo fechado carrega. Os três, sempre -- inclusive quando um
   deles é zero: é a mesma conta, só sem a parcela. */
const somaDoGrupo = computed(
  () => naoLidasWhatsapp.value + naoLidas.value + naoLidosEmail.value)

/* O selo de um item qualquer. Fora destes três códigos não há selo: devolver
   0 é o que faz o `v-if` do template não desenhar nada. */
function seloDaTela(codigo) {
  if (codigo === 'ATD_1.1') return naoLidasWhatsapp.value
  if (codigo === 'ATD_6.1') return naoLidas.value
  if (codigo === 'EML_1.1') return naoLidosEmail.value
  return 0
}

function textoDoSelo(codigo) {
  if (codigo === 'ATD_1.1') {
    return `${naoLidasWhatsapp.value} conversa(s) sua(s) com mensagem não lida`
  }
  if (codigo === 'EML_1.1') {
    return `${naoLidosEmail.value} e-mail(s) não lido(s) na entrada`
  }
  return mencoes.value > 0
    ? `${mencoes.value} vez(es) em que te chamaram pelo nome, de ${naoLidas.value} não lida(s)`
    : `${naoLidas.value} mensagem(ns) nova(s) no chat interno`
}

/* 🚨 QUANTOS SÃO SÓ 99+ NO DESENHO. O número real vai no `title`, porque
   "99+" no cabeçalho fechado é a única informação que a pessoa tem. */
function curto(n) {
  return n > 99 ? '99+' : String(n)
}

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

/* 🔵 19/10, pedido dele: o menu abre "em grupos e subgrupos", que ficam
   abertos até clicar de novo, e a escolha é lembrada por pessoa. Vários
   grupos podem ficar abertos ao mesmo tempo -- é decisão dele, não economia
   de código: fechar um ao abrir outro esconderia justamente o item de onde a
   pessoa acabou de sair.

   Chave própria, no mesmo desenho (e com o mesmo `try/catch` silencioso) do
   `CHAVE_COLAPSADO` acima: sem localStorage o menu abre e não lembra, que é
   degradar, não quebrar. */
const CHAVE_GRUPOS = 'movizap_menu_grupos'

function lerGruposSalvos() {
  try {
    const cru = localStorage.getItem(CHAVE_GRUPOS)
    return cru ? new Set(JSON.parse(cru)) : null
  } catch {
    return null // storage bloqueado ou JSON estragado: cai no padrão.
  }
}

const fechados = ref(new Set())
const salvoCarregado = ref(false)

/** 🚨 Guarda-se o que está FECHADO, não o que está aberto.

    Grupo novo (e a tela Agendamentos vem aí) nasce ABERTO para quem já tem
    escolha gravada. Se a lista fosse de abertos, toda entrega nova nasceria
    escondida para quem usa o painel há mais tempo -- e ninguém descobriria,
    porque para mim, de conta limpa, apareceria. */
function carregarUmaVez() {
  if (salvoCarregado.value) return
  const salvo = lerGruposSalvos()
  if (salvo) fechados.value = salvo
  salvoCarregado.value = true
}
carregarUmaVez()

function gravarFechados() {
  try {
    localStorage.setItem(CHAVE_GRUPOS, JSON.stringify([...fechados.value]))
  } catch {
    // Não lembra na próxima visita -- não é motivo pra travar o clique.
  }
}

/** O grupo da tela aberta agora -- ele NASCE ABERTO, mesmo se estiver na
    lista de fechados: menu que esconde o item em que a pessoa está é o
    mesmo defeito do rótulo que mente. */
const grupoDaTelaAtual = computed(() => {
  const codigo = rota?.meta?.codigo
  if (!codigo) return null
  const tela = sessao.telas.find((t) => t.codigo === codigo)
  return tela ? tela.grupo : null
})

function estaAberto(nome) {
  if (nome === grupoDaTelaAtual.value) return true
  return !fechados.value.has(nome)
}

function alternarGrupo(nome) {
  const proximo = new Set(fechados.value)
  if (proximo.has(nome)) proximo.delete(nome)
  else proximo.add(nome)
  fechados.value = proximo
  gravarFechados()
}

/* 🚨 NO MENU COMPACTO NÃO EXISTE ACORDEÃO. O nome do grupo some por CSS
   (`.menu--compacto .menu__grupo-nome`), e sem ele não há onde clicar para
   reabrir: um grupo fechado sumiria sem volta. Compacto mostra tudo. */
function mostrarItens(nome) {
  return visualCompacto.value || estaAberto(nome)
}

/* 🟡 Defeito que o acordeão CRIA, e que o acordeão tem de resolver: com o
   grupo fechado, o selo de mensagem nova do chat interno some junto com o
   item -- e o selo existe exatamente para quem não está olhando a tela. O
   cabeçalho fechado passa a carregá-lo. */
/* 🔵 22/10: era só o Chat interno; passou a ser qualquer um dos três que
   têm selo. O grupo fechado some com o item E com o aviso dele, e o aviso é
   justamente para quem não está olhando -- valia para o chat em 21/10 e vale
   igual para o WhatsApp e para o e-mail agora. */
const CODIGOS_COM_SELO = ['ATD_1.1', 'ATD_6.1', 'EML_1.1']

function temSelo(grupo) {
  return grupo.subgrupos.some(
    (s) => s.telas.some((t) => CODIGOS_COM_SELO.includes(t.codigo)))
}

/** Agrupa em dois níveis, preservando a ordem em que o backend mandou.

    🚨 GRUPO SEM NENHUMA TELA VISÍVEL NÃO É DESENHADO -- e é isso que deixa
    "Painéis › Operacional" existir no registro sem mentir na tela. Vale
    igual para permissão: quem não tem nenhuma tela do grupo não vê o grupo,
    porque ele é construído a partir das telas que chegaram, nunca de uma
    lista fixa aqui. */
const grupos = computed(() => {
  const porGrupo = new Map()
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
    // ⚠️ Fallback do fallback: backend antigo (ou tela sem grupo) ainda cai
    // no prefixo. O MoviZap serve o `dist` do disco -- tela e backend podem
    // ficar um passo fora de sincronia no meio de uma publicação.
    const nome = tela.grupo || tela.codigo.split('_')[0]
    if (!porGrupo.has(nome)) porGrupo.set(nome, new Map())
    const sub = tela.subgrupo || ''
    const subgrupos = porGrupo.get(nome)
    if (!subgrupos.has(sub)) subgrupos.set(sub, [])
    subgrupos.get(sub).push(tela)
  }
  return [...porGrupo].map(([nome, subgrupos]) => ({
    nome,
    // O subgrupo vazio ('') não desenha rótulo: tela sem subgrupo pendura
    // direto no grupo, como era antes desta entrega. E vem primeiro por
    // ordenação explícita, não por sorte da ordem de inserção.
    subgrupos: [...subgrupos]
      .sort(([a], [b]) => (a === '' ? -1 : b === '' ? 1 : 0))
      .map(([sub, telas]) => ({ nome: sub, telas })),
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
      <div v-for="grupo in grupos" :key="grupo.nome" class="menu__grupo">
        <!-- O nome do grupo era um <p> sem clique até 21/10. Virou botão para
             abrir e fechar; no menu compacto ele some por CSS, e por isso o
             `mostrarItens` ignora o acordeão lá. -->
        <button
          class="menu__grupo-nome"
          type="button"
          :aria-expanded="estaAberto(grupo.nome)"
          :title="estaAberto(grupo.nome) ? 'Fechar grupo' : 'Abrir grupo'"
          @click="alternarGrupo(grupo.nome)"
        >
          <span>{{ grupo.nome }}</span>
          <span
            v-if="!mostrarItens(grupo.nome) && temSelo(grupo) && somaDoGrupo > 0"
            class="menu__selo menu__selo--grupo"
            :class="{ 'menu__selo--mencao': mencoes > 0 }"
            :title="`${somaDoGrupo} não lida(s) neste grupo fechado: `
              + `${naoLidasWhatsapp} no WhatsApp, ${naoLidas} no chat interno, `
              + `${naoLidosEmail} no e-mail`"
          >{{ curto(somaDoGrupo) }}</span>
          <i
            class="bi menu__seta"
            :class="estaAberto(grupo.nome) ? 'bi-chevron-down' : 'bi-chevron-right'"
            aria-hidden="true"
          ></i>
        </button>

        <template v-if="mostrarItens(grupo.nome)">
          <div v-for="sub in grupo.subgrupos" :key="sub.nome" class="menu__sub">
            <p v-if="sub.nome" class="menu__sub-nome">{{ sub.nome }}</p>
            <RouterLink
              v-for="tela in sub.telas"
              :key="tela.codigo"
              :to="tela.rota"
              class="menu__link"
              :class="{ 'menu__link--sub': sub.nome }"
              active-class="menu__link--ativo"
              :title="tela.codigo"
            >
              <i class="bi" :class="tela.icone" aria-hidden="true"></i>
              <span class="menu__titulo">{{ tela.titulo }}</span>
              <span
                v-if="seloDaTela(tela.codigo) > 0"
                class="menu__selo"
                :class="{
                  'menu__selo--mencao': tela.codigo === 'ATD_6.1' && mencoes > 0,
                }"
                :title="textoDoSelo(tela.codigo)"
              >{{ curto(seloDaTela(tela.codigo)) }}</span>
            </RouterLink>
          </div>
        </template>
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
/* Era um <p>; virou botão em 21/10 (acordeão). O reset aqui é o que impede
   o botão de herdar o visual de botão do tema -- o rótulo tem de continuar
   parecendo rótulo, só que clicável. */
.menu__grupo-nome {
  display: flex;
  align-items: center;
  gap: var(--e-2);
  width: 100%;
  padding: 4px var(--e-3) var(--e-2);
  border: none;
  background: transparent;
  font-family: inherit;
  font-size: var(--txt-xs);
  font-weight: var(--peso-forte);
  text-align: left;
  text-transform: uppercase;
  letter-spacing: .06em;
  color: rgba(148, 163, 184, .62);
  cursor: pointer;
  border-radius: var(--r-sm);
  transition: color var(--tempo-rapido) var(--curva);
}
.menu__grupo-nome:hover { color: var(--menu-texto-forte); }
.menu__seta { margin-left: auto; font-size: 10px; flex: none; }
.menu__selo--grupo { margin-left: 0; }

/* O subgrupo só ganha rótulo quando tem nome. Hoje nenhuma tela usa -- a
   estrutura existe porque "Painéis › Operacional" já está declarado no
   registro e nasce vazio por decisão dele. */
.menu__sub-nome {
  padding: var(--e-2) var(--e-3) 4px calc(var(--e-3) + 12px);
  margin: 0;
  font-size: var(--txt-xs);
  letter-spacing: .04em;
  color: rgba(148, 163, 184, .5);
}
.menu__link--sub { padding-left: calc(var(--e-3) + 12px); }

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
.menu--compacto .menu__sub-nome,
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
  .menu__sub-nome,
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
