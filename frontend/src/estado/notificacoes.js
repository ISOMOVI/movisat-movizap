/* ============================================================================
   Estado das notificações — o que o Notificador lê e a Caixa mostra (24/09)
   ----------------------------------------------------------------------------
   Um objeto `reactive`, como `sessao.js`: o Notificador (em toda tela) escreve;
   as abas Minhas e Time da Caixa leem o número daqui, em vez de cada tela
   perguntar ao servidor por conta própria.
   ============================================================================ */
import { reactive } from 'vue'

export const notificacoes = reactive({
  carregado: false,
  ativa: true,
  tom: 'classico',
  volume: 3,
  abas: { minhas: 0, time: 0 },
  assumidasNaoLidas: 0,
  /* 🔵 25/09: a conversa aberta na Caixa agora. Com a tela à vista, ela não
     toca (`decidirToque`); a Caixa escreve, o Notificador lê. */
  conversaAberta: null,
  /* A permissão do balão do Windows, reativa para o convite e a CFG_11.1
     mudarem juntos quando a pessoa aceita num dos dois. */
  permissaoBalao: 'default',
})
