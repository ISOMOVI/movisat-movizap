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

      <div v-if="googleDisponivel" class="cartao entrada__cartao entrada__google">
        <button class="botao botao--contorno entrada__google-botao" type="button" @click="entrarComGoogle">
          <i class="bi bi-google" aria-hidden="true"></i>
          Entrar com Google
        </button>
        <p class="apagado pequeno">Contas @movisat.com.br já cadastradas no painel.</p>
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

.entrada__google {
  display: flex;
  flex-direction: column;
  gap: var(--e-2);
  align-items: center;
  margin-bottom: var(--e-3);
}
.entrada__google-botao {
  width: 100%;
  min-height: var(--altura-toque);
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
