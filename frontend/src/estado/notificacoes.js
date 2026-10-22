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
  /* 🔵 22/10: os não lidos da ENTRADA do e-mail, para o selo do menu. Mora
     aqui, e não numa chamada do MenuLateral, porque este estado já é
     preenchido de 8 em 8 s em toda tela -- o selo do e-mail e o do WhatsApp
     são o mesmo dado, lido uma vez.

     🚨 DECLARADO AQUI DE PROPÓSITO, mesmo sendo `reactive`. Campo que só
     existe depois da primeira resposta faz o menu desenhar `undefined` no
     primeiro quadro, e deixa o arquivo que É a lista do estado sem dizer que
     ele existe. */
  email_nao_lidos: 0,
  /* 🔵 22/10: as solicitações de formulário ainda `nova`, para o quarto selo
     do menu. Vem da MESMA resposta de 8 em 8 s -- selo que pisca em dois
     relógios mostra soma que não bate com as partes.

     🚨 DECLARADO AQUI, como o do e-mail: campo que só existe depois da
     primeira resposta faz o menu desenhar `undefined` no primeiro quadro. */
  solicitacoes_novas: 0,
  assumidasNaoLidas: 0,
  /* 🔵 25/09: a conversa aberta na Caixa agora. Com a tela à vista, ela não
     toca (`decidirToque`); a Caixa escreve, o Notificador lê. */
  conversaAberta: null,
  /* A permissão do balão do Windows, reativa para o convite e a CFG_11.1
     mudarem juntos quando a pessoa aceita num dos dois. */
  permissaoBalao: 'default',
})
