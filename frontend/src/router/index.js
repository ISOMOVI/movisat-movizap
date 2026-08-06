/* ============================================================================
   Rotas do MoviZap.
   ----------------------------------------------------------------------------
   Toda rota de tela carrega `meta.codigo` — o mesmo código imutável do
   `movizap/telas.py`. É ele que a barra de status exibe e que a guarda usa.

   ⚠️ Rota sem `meta.codigo` não é tela: ou é pública (login), ou é auxiliar
   (sem permissão, não encontrada). Uma tela nova só entra aqui DEPOIS de
   existir no registro do backend — senão a guarda a barra na hora.

   As rotas listadas são as telas de FASE 1, e são exatamente as mesmas do
   `movizap/telas.py`. As reservadas (ATD_3.1, ATD_4.1, CFG_2.2, REL_1.1) não
   têm rota de propósito: o código está ocupado, a tela não existe.

   🚨 REGISTRO E ROTEADOR TÊM QUE ANDAR JUNTOS. O menu é gerado do registro do
   backend, então uma tela registrada lá e ausente daqui aparece no menu e
   leva para "não encontrada" -- e ninguém descobre até alguém clicar.
   Aconteceu em 06/08 com a ATD_5.1. O `teste_telas.py` agora compara os dois
   lados e reprova a divergência.
   ============================================================================ */
import { createRouter, createWebHistory } from 'vue-router'

import { sessao, autenticado, codigosPermitidos, restaurar } from '../estado/sessao.js'
import { temToken } from '../api/cliente.js'

import Login from '../telas/Login.vue'
import Canais from '../telas/Canais.vue'
import Sincronizacao from '../telas/Sincronizacao.vue'
import RegistroDeTelas from '../telas/RegistroDeTelas.vue'
import EmConstrucao from '../telas/EmConstrucao.vue'
import SemPermissao from '../telas/SemPermissao.vue'
import NaoEncontrada from '../telas/NaoEncontrada.vue'

/** Atalho: tela de fase 1 ainda sem implementação, mas já com código e barra. */
const emObra = (codigo, titulo, oQueVemAqui) => ({
  component: EmConstrucao,
  meta: { codigo, titulo },
  props: { codigo, titulo, oQueVemAqui },
})

const rotas = [
  {
    path: '/login',
    name: 'login',
    component: Login,
    meta: { publica: true, titulo: 'Entrar' },
  },

  // ---- ATD: atendimento ----
  {
    path: '/atendimento',
    name: 'ATD_1.1',
    ...emObra('ATD_1.1', 'Caixa de entrada',
      'A lista de conversas por canal e por time, com a conversa aberta ao lado.'),
  },
  {
    // antes de /atendimento/:id — senão "fila" vira um id
    path: '/atendimento/fila',
    name: 'ATD_1.3',
    ...emObra('ATD_1.3', 'Fila',
      'As conversas que a IA transferiu e ainda esperam um atendente assumir.'),
  },
  {
    // antes de /atendimento/:id, pela mesma razão que a fila
    path: '/atendimento/historico',
    name: 'ATD_5.1',
    ...emObra('ATD_5.1', 'Histórico',
      'As conversas já encerradas, pesquisáveis pelo telefone do cliente.'),
  },
  {
    path: '/atendimento/:id',
    name: 'ATD_1.2',
    ...emObra('ATD_1.2', 'Conversa',
      'A conversa, com a ficha do cliente ao lado — o motivo de o Chatwoot sair.'),
  },

  // ---- CAD: cadastro ----
  {
    path: '/cadastro/clientes',
    name: 'CAD_1.1',
    ...emObra('CAD_1.1', 'Clientes',
      'Clientes sincronizados do Harmonit ou criados aqui. Depende do banco.'),
  },
  {
    path: '/cadastro/contatos',
    name: 'CAD_1.2',
    ...emObra('CAD_1.2', 'Contatos',
      'Pessoas, telefones em E.164 com o bruto preservado, e seus papéis.'),
  },
  {
    path: '/cadastro/atendentes',
    name: 'CAD_2.1',
    ...emObra('CAD_2.1', 'Atendentes',
      'Contas do painel. Hoje existe um usuário só, vindo do .env.'),
  },
  {
    path: '/cadastro/times',
    name: 'CAD_2.2',
    ...emObra('CAD_2.2', 'Times',
      'Os times que recebem transferência da IA e entre atendentes.'),
  },

  // ---- CFG: configuração ----
  {
    path: '/config/canais',
    name: 'CFG_1.1',
    component: Canais,
    meta: { codigo: 'CFG_1.1', titulo: 'Canais' },
  },
  {
    path: '/config/ia/prompt',
    name: 'CFG_2.1',
    ...emObra('CFG_2.1', 'IA — prompt',
      'As versões do prompt. A conversa grava qual versão a atendeu.'),
  },
  {
    path: '/config/sync',
    name: 'CFG_3.1',
    component: Sincronizacao,
    meta: { codigo: 'CFG_3.1', titulo: 'Sincronização' },
  },
  {
    path: '/config/classificacoes',
    name: 'CFG_4.1',
    ...emObra('CFG_4.1', 'Classificações',
      'Os motivos de fechamento. É o que alimenta analytics na Fase 2.'),
  },
  {
    path: '/config/telas',
    name: 'CFG_9.1',
    component: RegistroDeTelas,
    meta: { codigo: 'CFG_9.1', titulo: 'Registro de telas' },
  },

  // ---- auxiliares ----
  {
    path: '/sem-permissao',
    name: 'sem-permissao',
    component: SemPermissao,
    meta: { titulo: 'Sem permissão' },
  },
  {
    path: '/',
    name: 'raiz',
    // sem tela própria: manda para a primeira tela que ESTE usuário enxerga
    redirect: () => ({ path: sessao.telas[0]?.rota || '/atendimento' }),
  },
  {
    path: '/:qualquer(.*)*',
    name: 'nao-encontrada',
    component: NaoEncontrada,
    meta: { titulo: 'Não encontrada' },
  },
]

export const router = createRouter({
  history: createWebHistory(),
  routes: rotas,
  scrollBehavior: () => ({ top: 0 }),
})

router.beforeEach(async (para) => {
  if (para.meta.publica) {
    // já logado não fica olhando a tela de login
    return autenticado.value ? { path: '/' } : true
  }

  // Recarregou a página com token guardado: recuperar quem é antes de decidir.
  if (!autenticado.value && temToken()) {
    await restaurar()
  }

  if (!autenticado.value) {
    return { name: 'login', query: para.fullPath === '/' ? {} : { destino: para.fullPath } }
  }

  const codigo = para.meta.codigo
  if (codigo && !codigosPermitidos.value.has(codigo)) {
    // O backend não listou esta tela para este usuário. Negar aqui é cortesia:
    // a barreira que vale é a rota do backend, que checa de novo.
    return { name: 'sem-permissao', query: { codigo } }
  }

  return true
})
