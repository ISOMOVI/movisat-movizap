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
import { computed } from 'vue'
import { useRouter } from 'vue-router'

import { sessao, sair } from '../estado/sessao.js'

const router = useRouter()

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
  <aside class="menu">
    <div class="menu__marca">
      <img class="menu__logo" src="/movisat-logo.png" alt="Movisat" />
      <b class="menu__nome">MoviZap</b>
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
}

.menu__marca {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: var(--e-1);
  padding: var(--e-2) var(--e-2) var(--e-5);
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

/* Estreitou: vira coluna de ícones. O rodapé CONTINUA — perder o "Sair" numa
   tela menor é o tipo de detalhe que só aparece com o usuário preso dentro. */
@media (max-width: 860px) {
  .menu { width: 62px; padding: var(--e-3) var(--e-2); }
  .menu__nome,
  .menu__titulo,
  .menu__grupo-nome,
  .menu__acao-texto { display: none; }
  .menu__marca { align-items: center; padding-left: 0; padding-right: 0; }
  .menu__logo { height: 22px; }
  .menu__link { justify-content: center; padding: 10px 0; }
  .menu__acao { justify-content: center; }
}
</style>
