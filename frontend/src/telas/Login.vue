<script setup>
/* ============================================================================
   Login local + entrada pelo Google (10/08).
   ----------------------------------------------------------------------------
   A mensagem de erro é única de propósito, espelhando o backend: não se diz
   se o que estava errado era o login ou a senha.
   ============================================================================ */
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { entrar } from '../estado/sessao.js'
import { api, definirToken, ErroDeApi } from '../api/cliente.js'

const rota = useRoute()
const router = useRouter()

const login = ref('')
const senha = ref('')
const erro = ref('')
const reqIdDoErro = ref('')
const enviando = ref(false)
const campoLogin = ref(null)   // preenchido pelo ref="campoLogin" do template

const googleDisponivel = ref(false)

onMounted(async () => {
  /* 🚨 O RETORNO DO GOOGLE VEM NO FRAGMENTO (`#t=`), não na query. Fragmento
     não vai ao servidor nem entra no log do nginx. Lido aqui, a barra de
     endereços é limpa em seguida para o token não ficar no histórico. */
  const frag = new URLSearchParams(window.location.hash.slice(1))
  const token = frag.get('t')
  const recusa = frag.get('erro')
  if (token || recusa) {
    history.replaceState(null, '', window.location.pathname)
  }
  if (token) {
    definirToken(token)
    await router.push(rota.query.destino || '/')
    return
  }
  if (recusa) erro.value = recusa

  try {
    const r = await api.get('/api/auth/google/disponivel')
    googleDisponivel.value = Boolean(r.disponivel)
  } catch {
    googleDisponivel.value = false
  }
  campoLogin.value?.focus()
})

function entrarComGoogle() {
  // Navegação de página inteira, não fetch: o Google recusa ser carregado
  // dentro de XHR e precisa da barra de endereços para o consentimento.
  window.location.href = '/api/auth/google/inicio'
}

async function enviar() {
  if (enviando.value) return
  erro.value = ''
  reqIdDoErro.value = ''
  enviando.value = true
  try {
    await entrar(login.value.trim(), senha.value)
    await router.push(rota.query.destino || '/')
  } catch (e) {
    erro.value = e instanceof ErroDeApi ? e.message : 'Não foi possível entrar.'
    reqIdDoErro.value = e instanceof ErroDeApi ? e.reqId : ''
    senha.value = ''
  } finally {
    enviando.value = false
  }
}
</script>

<template>
  <div class="entrada">
    <div class="entrada__caixa">
      <!-- Marca fora do cartão, como no MoviChat -->
      <div class="entrada__marca">
        <img class="entrada__logo" src="/movisat-logo.png" alt="Movisat" />
        <p class="entrada__sub">Painel de comunicação · MoviZap</p>
      </div>

      <div v-if="googleDisponivel" class="entrada__google">
        <button class="entrada__google-botao" type="button" @click="entrarComGoogle">
          <!-- G oficial do Google. Inline porque é a única cor da tela e não
               pode depender de fonte de ícone carregar. -->
          <svg class="entrada__google-g" viewBox="0 0 18 18" aria-hidden="true">
            <path fill="#4285F4" d="M17.64 9.2c0-.64-.06-1.25-.16-1.84H9v3.48h4.84a4.14 4.14 0 0 1-1.8 2.72v2.26h2.91c1.7-1.57 2.69-3.88 2.69-6.62z"/>
            <path fill="#34A853" d="M9 18c2.43 0 4.47-.8 5.96-2.18l-2.91-2.26c-.81.54-1.84.86-3.05.86-2.34 0-4.33-1.58-5.04-3.71H.96v2.33A9 9 0 0 0 9 18z"/>
            <path fill="#FBBC05" d="M3.96 10.71a5.41 5.41 0 0 1 0-3.42V4.96H.96a9 9 0 0 0 0 8.08l3-2.33z"/>
            <path fill="#EA4335" d="M9 3.58c1.32 0 2.5.45 3.44 1.35l2.58-2.59C13.46.89 11.43 0 9 0A9 9 0 0 0 .96 4.96l3 2.33C4.67 5.16 6.66 3.58 9 3.58z"/>
          </svg>
          <span>Entrar com Google</span>
        </button>
        <p class="entrada__google-nota">Contas @movisat.com.br já cadastradas</p>

        <div class="entrada__ou"><span>ou</span></div>
      </div>

      <form class="cartao entrada__cartao" @submit.prevent="enviar">
        <h2 class="entrada__titulo">Acesse sua conta</h2>

        <label class="campo campo--grande">
          <span class="campo__rotulo">Login</span>
          <input
            ref="campoLogin"
            v-model="login"
            class="campo__entrada"
            type="text"
            autocomplete="username"
            autocapitalize="off"
            autocorrect="off"
            spellcheck="false"
            maxlength="64"
            required
          />
        </label>

        <label class="campo campo--grande">
          <span class="campo__rotulo">Senha</span>
          <input
            v-model="senha"
            class="campo__entrada"
            type="password"
            autocomplete="current-password"
            maxlength="256"
            required
          />
        </label>

        <p v-if="erro" class="aviso aviso--erro entrada__erro" role="alert">
          <i class="bi bi-exclamation-octagon aviso__icone" aria-hidden="true"></i>
          <span>
            {{ erro }}
            <span v-if="reqIdDoErro" class="mono pequeno"> (req {{ reqIdDoErro }})</span>
          </span>
        </p>

        <button class="botao botao--primario botao--largo entrada__enviar"
                type="submit" :disabled="enviando">
          <span v-if="enviando" class="girando"></span>
          {{ enviando ? 'Entrando…' : 'Entrar' }}
        </button>

        <!--
          Ainda SEM rota, de propósito: recuperação de senha depende do CRUD
          de usuários (CAD_2.1) e do envio de e-mail. Botão desabilitado com
          o motivo à vista é honesto; link que não faz nada é o contrário.
        -->
        <button class="botao botao--fantasma entrada__esqueci"
                type="button" disabled
                title="Disponível quando o cadastro de atendentes existir (CAD_2.1)">
          Esqueci minha senha
        </button>
      </form>
    </div>
  </div>
</template>

<style scoped>
.entrada {
  display: grid;
  place-items: center;
  min-height: 100%;
  padding: var(--e-5);
  background: var(--fundo);
}

/* ---- entrada pelo Google -------------------------------------------------
   É o caminho principal: o time inteiro entra por aqui, e a senha é a exceção
   do dono. Por isso vem ANTES do formulário, com separador. */
.entrada__google {
  width: 100%;
  max-width: 420px;
  margin: 0 auto var(--e-4);
}

.entrada__google-botao {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--e-2);
  width: 100%;
  /* 🚨 48px e 16px: abaixo disso o iOS dá zoom sozinho ao focar, e o painel
     fica torto. Mesma régua dos campos, definida no padrão visual de 05/08. */
  min-height: 48px;
  font-size: 16px;
  font-weight: 600;
  font-family: var(--fonte);
  color: var(--texto);
  background: var(--superficie);
  border: var(--borda-fina) solid var(--borda-forte);
  border-radius: var(--r-md);
  cursor: pointer;
  box-shadow: var(--sombra-1);
  transition: background .15s, box-shadow .15s, border-color .15s;
}
.entrada__google-botao:hover {
  background: var(--superficie-2);
  border-color: var(--acento-borda);
  box-shadow: var(--sombra-2);
}
.entrada__google-botao:focus-visible {
  outline: none;
  box-shadow: var(--foco);
}
.entrada__google-botao:active {
  background: var(--superficie-3);
  box-shadow: none;
}

.entrada__google-g {
  width: 20px;
  height: 20px;
  flex: none;
}

.entrada__google-nota {
  margin: var(--e-2) 0 0;
  text-align: center;
  font-size: var(--txt-sm);
  color: var(--texto-apagado);
}

/* Separador com a palavra no meio: duas linhas e um respiro, sem imagem. */
.entrada__ou {
  display: flex;
  align-items: center;
  gap: var(--e-3);
  margin-top: var(--e-4);
  color: var(--texto-apagado);
  font-size: var(--txt-sm);
}
.entrada__ou::before,
.entrada__ou::after {
  content: '';
  flex: 1;
  height: 1px;
  background: var(--borda);
}
.entrada__caixa {
  width: 100%;
  max-width: 420px;   /* MoviChat usa 380px; aqui os campos são maiores */
}

.entrada__marca {
  text-align: center;
  margin-bottom: var(--e-6);
}
/* Maior que a do MoviChat (52px), a pedido. */
.entrada__logo {
  height: 76px;
  max-width: 100%;
  object-fit: contain;
}

.entrada__sub {
  margin-top: var(--e-3);
  font-size: var(--txt-sm);
  letter-spacing: .04em;
  color: var(--texto-fraco);
}

.entrada__cartao {
  padding: var(--e-6);
  box-shadow: var(--sombra-2);
}
.entrada__titulo {
  margin-bottom: var(--e-5);
  font-size: var(--txt-lg);
  font-weight: var(--peso-forte);
}

.entrada__erro { margin-bottom: var(--e-4); }
.entrada__enviar { min-height: var(--altura-campo); font-size: var(--txt-lg); }
.entrada__esqueci { width: 100%; margin-top: var(--e-3); font-size: var(--txt-sm); }

/* Tela baixa (celular deitado): encolhe a marca antes de espremer o cartão. */
@media (max-height: 640px) {
  .entrada__logo { height: 46px; }
  .entrada__marca { margin-bottom: var(--e-4); }
  .entrada__cartao { padding: var(--e-4); }
}
</style>
