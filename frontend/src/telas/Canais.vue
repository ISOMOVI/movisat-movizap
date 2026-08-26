<script setup>
/* ============================================================================
   CFG_1.1 — Canais
   ----------------------------------------------------------------------------
   Onde o WhatsApp é pareado, e onde se vê o que está conectado.

   🚨 O QR do Baileys expira em ~60 s. A tela conta o tempo e pede outro
   sozinha: pedir F5 para renovar QR é o tipo de detalhe que faz a pessoa
   desistir no meio do pareamento.

   ⚠️ Enquanto o QR está na tela, o estado é consultado a cada 3 s. É o
   Evolution que diz quando conectou -- não há como o navegador saber.
   ============================================================================ */
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'

import { api, ErroDeApi } from '../api/cliente.js'

const canais = ref([])
const carregando = ref(true)
const erro = ref('')

const qr = ref(null)          // { base64, codigo, pareamento }
const qrCanalId = ref(null)
const qrSegundos = ref(0)
const ocupado = ref(false)
const aviso = ref('')

const SEGUNDOS_QR = 60
let relogio = null
let sondagem = null

const canalDoQr = computed(
  () => canais.value.find((c) => c.id === qrCanalId.value) || null,
)

const ROTULO = {
  conectado: { texto: 'conectado', cor: 'ok' },
  pareando: { texto: 'pareando', cor: 'aviso' },
  aguardando_qr: { texto: 'aguardando QR', cor: 'aviso' },
  desconectado: { texto: 'desconectado', cor: '' },
  caiu: { texto: 'caiu', cor: 'erro' },
  indisponivel: { texto: 'Evolution fora do ar', cor: 'erro' },
  desconhecido: { texto: 'desconhecido', cor: '' },
}

async function carregar(silencioso = false) {
  if (!silencioso) carregando.value = true
  try {
    canais.value = await api.get('/api/canais')
    erro.value = ''
  } catch (e) {
    erro.value = e instanceof ErroDeApi ? e.message : 'Falha ao ler os canais.'
  } finally {
    carregando.value = false
  }
}

async function pedirQr(canal) {
  ocupado.value = true
  aviso.value = ''
  try {
    qr.value = await api.post(`/api/canais/${canal.id}/conectar`)
    qrCanalId.value = canal.id
    qrSegundos.value = SEGUNDOS_QR
    iniciarSondagem()
  } catch (e) {
    aviso.value = e instanceof ErroDeApi ? e.message : 'Não foi possível pedir o QR.'
    fecharQr()
  } finally {
    ocupado.value = false
  }
}

function fecharQr() {
  qr.value = null
  qrCanalId.value = null
  qrSegundos.value = 0
  pararSondagem()
}

function iniciarSondagem() {
  pararSondagem()
  // Só o Evolution sabe quando o celular leu o QR. 3s é curto o bastante
  // para parecer imediato e longo o bastante para não martelar a API.
  sondagem = setInterval(async () => {
    await carregar(true)
    const c = canalDoQr.value
    if (c && c.estado === 'conectado') {
      await confirmar(c)
    }
  }, 3000)
}

function pararSondagem() {
  if (sondagem) clearInterval(sondagem)
  sondagem = null
}

async function confirmar(canal) {
  pararSondagem()
  try {
    const r = await api.post(`/api/canais/${canal.id}/confirmar`)
    const aplicadas = Object.entries(r.settings || {})
      .filter(([, v]) => v === true)
      .map(([k]) => k)
    aviso.value = `Conectado. Settings aplicadas: ${aplicadas.join(', ') || '—'}.`
  } catch (e) {
    aviso.value = e instanceof ErroDeApi
      ? `Conectou, mas as settings falharam: ${e.message}`
      : 'Conectou, mas as settings falharam.'
  }
  fecharQr()
  await carregar(true)
}

async function desconectar(canal) {
  if (!window.confirm(
    `Desconectar "${canal.nome}"?\n\n`
    + 'O número para de receber mensagem até alguém ler um QR novo.')) return
  ocupado.value = true
  try {
    await api.post(`/api/canais/${canal.id}/desconectar`)
    aviso.value = 'Canal desconectado.'
    await carregar(true)
  } catch (e) {
    aviso.value = e instanceof ErroDeApi ? e.message : 'Falha ao desconectar.'
  } finally {
    ocupado.value = false
  }
}

/* 🚨 LIGAR A IA É UM ATO, E A TELA TRATA COMO ATO. A confirmação diz o que vai
   acontecer com o cliente do outro lado, não "tem certeza?" — e diz também o
   que NÃO vai: ela não responde nada que tenha chegado antes deste clique.
   Decisão do usuário em 06/08: "ninguém liga por acidente". */
async function alternarIa(canal) {
  const ligando = !canal.ia_ligada
  const pergunta = ligando
    ? `Ligar a IA em "${canal.nome}"?\n\n`
      + 'A partir de agora ela responde sozinha a quem escrever — nos tipos de '
      + 'contato que estiverem ligados na CFG_5.1.\n\n'
      + 'Ela NÃO responde nada que já esteja na caixa: só o que chegar depois '
      + 'deste momento.'
    : `Desligar a IA em "${canal.nome}"?\n\n`
      + 'As conversas que ela estava atendendo ficam onde estão, esperando gente.'
  if (!window.confirm(pergunta)) return
  ocupado.value = true
  try {
    await api.put(`/api/canais/${canal.id}/ia`, { ligada: ligando })
    aviso.value = ligando
      ? 'IA ligada. Ela atende o que chegar a partir de agora.'
      : 'IA desligada.'
    /* Relê em vez de confiar no 200: o que vale é o que o banco gravou. */
    await carregar(true)
  } catch (e) {
    aviso.value = e instanceof ErroDeApi ? e.message : 'Falha ao mudar a IA.'
    await carregar(true)
  } finally {
    ocupado.value = false
  }
}

const historico = ref({ canalId: null, linhas: [] })

async function verHistorico(canal) {
  if (historico.value.canalId === canal.id) {
    historico.value = { canalId: null, linhas: [] }
    return
  }
  try {
    historico.value = {
      canalId: canal.id,
      linhas: await api.get(`/api/canais/${canal.id}/eventos`),
    }
  } catch {
    aviso.value = 'Falha ao ler o histórico.'
  }
}

function quando(iso) {
  return iso ? new Date(iso).toLocaleString('pt-BR') : '—'
}

function desde(iso) {
  if (!iso) return '—'
  const seg = Math.floor((Date.now() - new Date(iso)) / 1000)
  const d = Math.floor(seg / 86400)
  const h = Math.floor((seg % 86400) / 3600)
  const m = Math.floor((seg % 3600) / 60)
  if (d) return `${d} d ${h} h`
  if (h) return `${h} h ${m} min`
  return `${m} min`
}

onMounted(() => {
  carregar()
  relogio = setInterval(() => {
    if (qrSegundos.value > 0) {
      qrSegundos.value -= 1
      // Expirou: pede outro sozinha, sem F5.
      if (qrSegundos.value === 0 && canalDoQr.value) pedirQr(canalDoQr.value)
    }
  }, 1000)
})

onBeforeUnmount(() => {
  if (relogio) clearInterval(relogio)
  pararSondagem()
})
</script>

<template>
  <div class="tela">
    <header class="tela__cabecalho">
      <div>
        <h1>Canais</h1>
        <p class="fraco pequeno">
          Conectar e acompanhar os números de WhatsApp. O estado vem do
          Evolution ao vivo — o banco guarda o histórico.
        </p>
      </div>
      <span class="chip chip--codigo chip--acento">CFG_1.1</span>
    </header>

    <p v-if="aviso" class="aviso aviso--info tela__aviso" role="status">
      <i class="bi bi-info-circle aviso__icone" aria-hidden="true"></i>
      <span>{{ aviso }}</span>
    </p>

    <p v-if="carregando" class="linha fraco">
      <span class="girando"></span> Consultando os canais…
    </p>

    <p v-else-if="erro" class="aviso aviso--erro" role="alert">
      <i class="bi bi-exclamation-octagon aviso__icone" aria-hidden="true"></i>
      <span>{{ erro }}</span>
    </p>

    <div v-else-if="!canais.length" class="vazio">
      <i class="bi bi-whatsapp vazio__icone" aria-hidden="true"></i>
      <p class="vazio__titulo">Nenhum canal cadastrado</p>
      <p>O canal nasce por migração, não pela tela.</p>
    </div>

    <template v-else>
      <section v-for="canal in canais" :key="canal.id" class="cartao canal">
        <header class="cartao__cabecalho">
          <span class="linha">
            <i class="bi bi-whatsapp" aria-hidden="true"></i>
            {{ canal.nome }}
          </span>
          <span class="linha">
            <!-- ⚠️ O chip da IA vem ANTES do estado da conexão, e só quando
                 ligada: é a informação mais consequente desta tela. -->
            <span v-if="canal.ia_ligada" class="chip chip--acento">
              <i class="bi bi-robot" aria-hidden="true"></i> IA no ar
            </span>
            <span class="chip" :class="'chip--' + (ROTULO[canal.estado]?.cor || '')">
              <span class="canal__ponto" :class="'canal__ponto--' + canal.estado"></span>
              {{ ROTULO[canal.estado]?.texto || canal.estado }}
            </span>
          </span>
        </header>

        <div class="cartao__corpo">
          <p v-if="canal.erro" class="aviso aviso--erro canal__erro">
            <i class="bi bi-plug aviso__icone" aria-hidden="true"></i>
            <span>
              {{ canal.erro }}
              <br /><span class="pequeno">
                Enquanto o Evolution não responder, não há QR a mostrar — e
                dizer "desconectado" aqui seria mentira.
              </span>
            </span>
          </p>

          <dl class="canal__dados">
            <div><dt>Número</dt><dd class="mono">{{ canal.numero || '— não pareado' }}</dd></div>
            <div><dt>Instância</dt><dd class="mono">{{ canal.instancia }}</dd></div>
            <div><dt>Modo</dt><dd>{{ canal.modo }}</dd></div>
            <div><dt>Pareado em</dt><dd>{{ quando(canal.pareado_em) }}</dd></div>
            <div><dt>Conectado há</dt><dd>{{ canal.estado === 'conectado' ? desde(canal.conectado_desde) : '—' }}</dd></div>
            <div>
              <dt>Quedas (24 h)</dt>
              <dd :class="{ 'canal__alerta': canal.quedas_24h > 3 }">{{ canal.quedas_24h }}</dd>
            </div>
          </dl>

          <div class="linha canal__acoes">
            <button v-if="canal.estado !== 'conectado'"
                    class="botao botao--primario" type="button"
                    :disabled="ocupado || canal.estado === 'indisponivel'"
                    @click="pedirQr(canal)">
              <i class="bi bi-qr-code" aria-hidden="true"></i> Conectar
            </button>

            <button v-else class="botao botao--perigo" type="button"
                    :disabled="ocupado" @click="desconectar(canal)">
              <i class="bi bi-plug" aria-hidden="true"></i> Desconectar
            </button>

            <button class="botao botao--contorno" type="button" @click="verHistorico(canal)">
              <i class="bi bi-clock-history" aria-hidden="true"></i>
              {{ historico.canalId === canal.id ? 'Ocultar' : 'Histórico' }}
            </button>

            <!-- 🚨 O ATO DELIBERADO (docs/04, passo 4 da sequência de
                 ativação). Só no canal de atendimento: o informativo é
                 disparo, e a rota recusa — a tela nem oferece. -->
            <button v-if="canal.tipo === 'atendimento'"
                    class="botao"
                    :class="canal.ia_ligada ? 'botao--perigo' : 'botao--contorno'"
                    type="button" :disabled="ocupado"
                    @click="alternarIa(canal)">
              <i class="bi bi-robot" aria-hidden="true"></i>
              {{ canal.ia_ligada ? 'Desligar IA' : 'Ligar IA' }}
            </button>

            <span class="espaco"></span>

            <button class="botao botao--fantasma" type="button" @click="carregar()">
              <i class="bi bi-arrow-clockwise" aria-hidden="true"></i> Atualizar
            </button>
          </div>

          <div v-if="historico.canalId === canal.id" class="canal__historico">
            <p v-if="!historico.linhas.length" class="apagado pequeno">
              Sem eventos registrados.
            </p>
            <table v-else class="tabela">
              <thead><tr><th>Quando</th><th>Estado</th><th>Motivo</th></tr></thead>
              <tbody>
                <tr v-for="(ev, i) in historico.linhas" :key="i">
                  <td class="mono pequeno">{{ quando(ev.em) }}</td>
                  <td>
                    <span class="chip" :class="'chip--' + (ROTULO[ev.estado]?.cor || '')">
                      {{ ROTULO[ev.estado]?.texto || ev.estado }}
                    </span>
                  </td>
                  <td class="fraco pequeno">{{ ev.motivo || '—' }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </section>
    </template>

    <!-- ---------------- QR ---------------- -->
    <div v-if="qr" class="qr" role="dialog" aria-label="Ler o QR code">
      <div class="cartao qr__caixa">
        <h2>Leia com o WhatsApp</h2>
        <p class="fraco pequeno qr__passos">
          Aparelho → Aparelhos conectados → Conectar um aparelho
        </p>

        <img v-if="qr.base64" class="qr__imagem" :src="qr.base64" alt="QR code para parear" />
        <p v-else class="aviso aviso--atencao">
          O Evolution não devolveu a imagem do QR.
        </p>

        <p v-if="qr.pareamento" class="qr__codigo">
          ou use o código <b class="mono">{{ qr.pareamento }}</b>
        </p>

        <p class="qr__tempo" :class="{ 'qr__tempo--fim': qrSegundos <= 10 }">
          Expira em {{ qrSegundos }} s — a tela pede outro sozinha.
        </p>

        <button class="botao botao--contorno botao--largo" type="button" @click="fecharQr">
          Cancelar
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.tela { max-width: 860px; }
.tela__cabecalho {
  display: flex; align-items: flex-start; justify-content: space-between;
  gap: var(--e-4); flex-wrap: wrap; margin-bottom: var(--e-5);
}
.tela__cabecalho p { max-width: var(--largura-texto); margin-top: var(--e-1); }
.tela__aviso { margin-bottom: var(--e-4); }

.canal { margin-bottom: var(--e-5); }
.canal__erro { margin-bottom: var(--e-4); }

.canal__ponto {
  width: 8px; height: 8px; border-radius: var(--r-full);
  display: inline-block; margin-right: 2px; background: var(--texto-apagado);
}
.canal__ponto--conectado { background: var(--ok); }
.canal__ponto--pareando,
.canal__ponto--aguardando_qr { background: var(--aviso); }
.canal__ponto--caiu,
.canal__ponto--indisponivel { background: var(--erro); }

.canal__dados {
  display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
  gap: var(--e-4); margin: 0 0 var(--e-5);
}
.canal__dados dt {
  font-size: var(--txt-xs); text-transform: uppercase; letter-spacing: .05em;
  color: var(--texto-apagado); margin-bottom: 2px;
}
.canal__dados dd { margin: 0; }
.canal__alerta { color: var(--erro); font-weight: var(--peso-forte); }

.canal__acoes { flex-wrap: wrap; }
.canal__historico {
  margin-top: var(--e-5); padding-top: var(--e-4);
  border-top: var(--borda-fina) solid var(--borda);
}

.qr {
  position: fixed; inset: 0; z-index: var(--z-modal);
  display: grid; place-items: center;
  padding: var(--e-4);
  background: rgba(15, 23, 42, .62);
}
.qr__caixa {
  width: 100%; max-width: 360px; padding: var(--e-6);
  text-align: center; box-shadow: var(--sombra-2);
}
.qr__passos { margin: var(--e-2) 0 var(--e-5); }
.qr__imagem {
  width: 260px; height: 260px; max-width: 100%;
  background: #fff; border-radius: var(--r-md); padding: var(--e-2);
}
.qr__codigo { margin-top: var(--e-3); font-size: var(--txt-sm); }
.qr__tempo { margin: var(--e-4) 0; font-size: var(--txt-sm); color: var(--texto-fraco); }
.qr__tempo--fim { color: var(--erro); font-weight: var(--peso-forte); }
</style>
