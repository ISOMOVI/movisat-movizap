/* ============================================================================
   Ponto de entrada da PAGINA PUBLICA do formulario.
   ----------------------------------------------------------------------------
   🚨 BUNDLE SEPARADO DO PAINEL, e e a razao de este arquivo existir: o bundle
   do painel publica sourcemap, e uma rota publica dentro dele entregaria o
   codigo-fonte do painel a qualquer anonimo. Aqui entra o renderizador de
   campos e mais nada -- sem router, sem sessao, sem estado do painel.

   ⚠️ Os tokens de estilo sao OS MESMOS do painel (`src/estilo`): o formulario
   e a cara da casa para quem esta fora dela, e "quase a mesma cor le como
   defeito, nao como escolha".
   ============================================================================ */
import { createApp } from 'vue'

import '../src/estilo/tokens.css'
import '../src/estilo/base.css'
import '../src/estilo/componentes.css'

import FormularioPublico from './FormularioPublico.vue'

createApp(FormularioPublico).mount('#app')
