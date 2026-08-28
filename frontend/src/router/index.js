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
import Inicio from '../telas/Inicio.vue'
import Email from '../telas/Email.vue'
import Canais from '../telas/Canais.vue'
import Clientes from '../telas/Clientes.vue'
import Contatos from '../telas/Contatos.vue'
import CaixaDeEntrada from '../telas/CaixaDeEntrada.vue'
import Fila from '../telas/Fila.vue'
import Informativos from '../telas/Informativos.vue'
import Historico from '../telas/Historico.vue'
import ChatInterno from '../telas/ChatInterno.vue'
import Atendentes from '../telas/Atendentes.vue'
import Times from '../telas/Times.vue'
import Automacao from '../telas/Automacao.vue'
import Classificacoes from '../telas/Classificacoes.vue'
import IaPrompt from '../telas/IaPrompt.vue'
import Sincronizacao from '../telas/Sincronizacao.vue'
import RegistroDeTelas from '../telas/RegistroDeTelas.vue'
// A casca das abas. As seis telas acima continuam existindo e são montadas
// POR ELA -- os imports ficam porque o `teste_router.py` lê este arquivo e
// porque tirá-los não ganharia nada.
import Configuracoes from '../telas/Configuracoes.vue'
import SemPermissao from '../telas/SemPermissao.vue'
import NaoEncontrada from '../telas/NaoEncontrada.vue'

const rotas = [
  {
    path: '/login',
    name: 'login',
    component: Login,
    meta: { publica: true, titulo: 'Entrar' },
  },

  {
    path: '/inicio',
    name: 'INI_1.1',
    component: Inicio,
    meta: { codigo: 'INI_1.1', titulo: 'Início' },
  },

  {
    path: '/email',
    name: 'EML_1.1',
    component: Email,
    meta: { codigo: 'EML_1.1', titulo: 'E-mail' },
  },

  // ---- ATD: atendimento ----
  {
    path: '/atendimento',
    name: 'ATD_1.1',
    component: CaixaDeEntrada,
    meta: { codigo: 'ATD_1.1', titulo: 'Caixa de entrada', cheio: true },
  },
  {
    // antes de /atendimento/:id — senão "fila" vira um id
    path: '/atendimento/fila',
    name: 'ATD_1.3',
    component: Fila,
    meta: { codigo: 'ATD_1.3', titulo: 'Fila' },
  },
  {
    // antes de /atendimento/:id, pela mesma razão que a fila
    path: '/atendimento/historico',
    name: 'ATD_5.1',
    component: Historico,
    meta: { codigo: 'ATD_5.1', titulo: 'Histórico' },
  },
  {
    // 🚨 Fora de /atendimento de propósito: é conversa entre ATENDENTES, e
    // nada daqui sai para o cliente. Pendurar em /atendimento faria o log
    // misturar "falou com cliente" e "falou com colega".
    path: '/chat',
    name: 'ATD_6.1',
    component: ChatInterno,
    meta: { codigo: 'ATD_6.1', titulo: 'Chat interno' },
  },
  {
    // Mesmo componente da ATD_1.1: a conversa abre AO LADO da lista, como o
    // 06_Conteudo_das_Telas desenha. Esta rota só entra já com uma escolhida.
    path: '/atendimento/:id',
    name: 'ATD_1.2',
    component: CaixaDeEntrada,
    meta: { codigo: 'ATD_1.2', titulo: 'Conversa', cheio: true },
  },

  {
    // 🚨 Subiu para fase 1 em 07/08. É a única tela que alcança cliente de
    // verdade em lote — o canal é irreversível.
    path: '/informativos',
    name: 'ATD_3.1',
    component: Informativos,
    meta: { codigo: 'ATD_3.1', titulo: 'Informativos' },
  },

  // ---- CAD: cadastro ----
  {
    path: '/cadastro/clientes',
    name: 'CAD_1.1',
    component: Clientes,
    meta: { codigo: 'CAD_1.1', titulo: 'Clientes' },
  },
  {
    // As abas CAD_1.2.1/.2/.3 vivem DENTRO desta tela e não têm rota própria.
    // O código delas existe só como âncora de auditoria — ver o registro.
    path: '/cadastro/contatos',
    name: 'CAD_1.2',
    component: Contatos,
    meta: { codigo: 'CAD_1.2', titulo: 'Contatos' },
  },
  {
    path: '/cadastro/atendentes',
    name: 'CAD_2.1',
    component: Atendentes,
    meta: { codigo: 'CAD_2.1', titulo: 'Atendentes' },
  },
  {
    path: '/cadastro/times',
    name: 'CAD_2.2',
    component: Times,
    meta: { codigo: 'CAD_2.2', titulo: 'Times' },
  },

  // ---- CFG: configuração ----
  //
  // 🚨 AS SEIS VIRARAM ABAS DA CFG_0.1 EM 27/08, e todas as sete rotas montam
  // o MESMO componente: a casca lê `meta.codigo` e abre na aba certa. É isso
  // que faz link antigo, favorito e histórico do navegador continuarem
  // funcionando -- e é isso que mantém `meta.codigo` significando a mesma
  // coisa que sempre significou, para a guarda e para a barra de status.
  //
  // 🚨 ROTA LITERAL ANTES DA COM PARÂMETRO continua valendo, e aqui a ordem
  // também importa por outro motivo: `/config` é prefixo de `/config/canais`.
  // Com `path` exato (sem `:qualquer`), o vue-router não confunde -- mas a
  // ordem escrita é a que se lê, então a genérica fica em cima.
  {
    path: '/config',
    name: 'CFG_0.1',
    component: Configuracoes,
    meta: { codigo: 'CFG_0.1', titulo: 'Configurações' },
  },
  {
    path: '/config/canais',
    name: 'CFG_1.1',
    component: Configuracoes,
    meta: { codigo: 'CFG_1.1', titulo: 'Canais' },
  },
  {
    path: '/config/ia/prompt',
    name: 'CFG_2.1',
    component: Configuracoes,
    meta: { codigo: 'CFG_2.1', titulo: 'IA — prompt' },
  },
  {
    path: '/config/sync',
    name: 'CFG_3.1',
    component: Configuracoes,
    meta: { codigo: 'CFG_3.1', titulo: 'Sincronização' },
  },
  {
    path: '/config/classificacoes',
    name: 'CFG_4.1',
    component: Configuracoes,
    meta: { codigo: 'CFG_4.1', titulo: 'Classificações' },
  },
  {
    path: '/config/automacao',
    name: 'CFG_5.1',
    component: Configuracoes,
    meta: { codigo: 'CFG_5.1', titulo: 'Automação por tipo' },
  },
  {
    // ⚠️ Dentro de Configurações por `aba_de` no registro do backend: a
    // rota existe, e é a casca que a monta como aba.
    path: '/config/geral',
    name: 'CFG_7.1',
    component: () => import('../telas/Geral.vue'),
    meta: { codigo: 'CFG_7.1', titulo: 'Geral' },
  },
  {
    path: '/config/atalhos',
    name: 'CFG_6.1',
    component: () => import('../telas/Atalhos.vue'),
    meta: { codigo: 'CFG_6.1', titulo: 'Atalhos de teclado' },
  },
  {
    path: '/config/telas',
    name: 'CFG_9.1',
    component: Configuracoes,
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
