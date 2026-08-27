<script setup>
/* ============================================================================
   CAD_1.1 — Clientes
   ----------------------------------------------------------------------------
   A primeira tela onde os 1.050 clientes lidos do Harmonit ficam visíveis para
   uma pessoa.

   🚨 A busca entende telefone. `18 99811-6168`, `(18) 9811-6168` e
   `5518998116168` acham a mesma pessoa -- e a tela DIZ o que entendeu. Quando
   alguém procura um número e não acha, a diferença entre "não existe" e
   "procurei pelo nome" é a diferença entre desistir e corrigir a digitação.

   ⚠️ Cliente com origem `movizap` é cadastro nosso e o sync nunca encosta.
   A tela marca isso, porque é a diferença entre "posso editar aqui" e "vai
   voltar como estava na próxima sincronização".
   ============================================================================ */
import { ref, computed, watch, onMounted } from 'vue'

import { api, ErroDeApi } from '../api/cliente.js'
import AjudaDaTela from '../componentes/AjudaDaTela.vue'

const busca = ref('')
const pagina = ref(1)
const apenasAtivos = ref(false)
const dados = ref(null)
const carregando = ref(true)
const erro = ref('')

const selecionado = ref(null)
const carregandoDetalhe = ref(false)

let debounce = null

const itens = computed(() => dados.value?.itens || [])
const interpretacao = computed(() => dados.value?.busca || { tipo: 'vazio' })
const total = computed(() => dados.value?.total ?? 0)
const paginas = computed(() => dados.value?.paginas ?? 1)

async function carregar() {
  carregando.value = true
  try {
    const p = new URLSearchParams({
      busca: busca.value,
      pagina: String(pagina.value),
      apenas_ativos: String(apenasAtivos.value),
    })
    dados.value = await api.get(`/api/clientes?${p}`)
    erro.value = ''
  } catch (e) {
    erro.value = e instanceof ErroDeApi ? e.message : 'Falha ao ler os clientes.'
  } finally {
    carregando.value = false
  }
}

async function abrir(item) {
  carregandoDetalhe.value = true
  selecionado.value = { id: item.id, nome: item.nome }
  try {
    selecionado.value = await api.get(`/api/clientes/${item.id}`)
  } catch (e) {
    erro.value = e instanceof ErroDeApi ? e.message : 'Falha ao abrir o cliente.'
    selecionado.value = null
  } finally {
    carregandoDetalhe.value = false
  }
}

// Digitar não dispara uma requisição por tecla.
watch(busca, () => {
  clearTimeout(debounce)
  debounce = setTimeout(() => {
    pagina.value = 1
    carregar()
  }, 300)
})

watch([pagina, apenasAtivos], carregar)

/* "há 3 min", "há 2 h", "há 4 d". Data absoluta obriga quem lê a calcular, e
   nesta ficha o que importa é se foi ontem ou no ano passado. */
function quando(iso) {
  if (!iso) return '—'
  const min = Math.round((Date.now() - new Date(iso)) / 60000)
  if (min < 60) return `há ${min} min`
  if (min < 1440) return `há ${Math.round(min / 60)} h`
  return `há ${Math.round(min / 1440)} d`
}

function numero(n) {
  return (n ?? 0).toLocaleString('pt-BR')
}

function documento(d) {
  if (!d) return '—'
  const so = d.replace(/\D/g, '')
  if (so.length === 11 && so === d)
    return `${so.slice(0, 3)}.${so.slice(3, 6)}.${so.slice(6, 9)}-${so.slice(9)}`
  if (so.length === 14 && so === d)
    return `${so.slice(0, 2)}.${so.slice(2, 5)}.${so.slice(5, 8)}/${so.slice(8, 12)}-${so.slice(12)}`
  return d   // CNPJ alfanumérico fica como veio — mascarar inventaria formato
}

function telefoneBonito(e164) {
  const m = /^\+55(\d{2})(\d{4,5})(\d{4})$/.exec(e164 || '')
  return m ? `(${m[1]}) ${m[2]}-${m[3]}` : e164 || '—'
}

onMounted(carregar)
</script>

<template>
  <div class="tela">
    <header class="tela__cabecalho">
      <div>
        <h1>Clientes</h1>
        <AjudaDaTela>Sincronizados do Harmonit a cada 12 h, ou criados aqui. A busca entende nome, documento e telefone.</AjudaDaTela>
      </div>
      <span class="chip chip--codigo chip--acento">CAD_1.1</span>
    </header>

    <section class="cartao">
      <div class="cartao__corpo cad__filtros">
        <label class="cad__busca">
          <i class="bi bi-search" aria-hidden="true"></i>
          <input
            v-model="busca"
            class="campo"
            type="search"
            placeholder="Nome, CPF/CNPJ ou telefone…"
            aria-label="Buscar cliente"
          />
        </label>

        <label class="linha pequeno">
          <input v-model="apenasAtivos" type="checkbox" />
          só ativos
        </label>
      </div>

      <!-- 🚨 devolver a interpretação: sem isto, "não achei" é ambíguo -->
      <p
        v-if="interpretacao.tipo !== 'vazio'"
        class="aviso"
        :class="interpretacao.tipo === 'telefone' ? 'aviso--info' : 'aviso--info'"
      >
        <i
          class="aviso__icone bi"
          :class="{
            'bi-telephone': interpretacao.tipo === 'telefone',
            'bi-card-text': interpretacao.tipo === 'documento',
            'bi-fonts': interpretacao.tipo === 'nome',
          }"
          aria-hidden="true"
        ></i>
        <span v-if="interpretacao.tipo === 'telefone'">
          Procurando pelo <strong>telefone {{ telefoneBonito(interpretacao.e164) }}</strong>,
          nas duas grafias possíveis.
          <br /><span class="pequeno">
            <code class="mono">{{ interpretacao.variantes.join('  ·  ') }}</code>
            — o Harmonit não garante qual delas gravou.
          </span>
        </span>
        <span v-else-if="interpretacao.tipo === 'documento'">
          Procurando pelo <strong>documento {{ interpretacao.limpo }}</strong>.
        </span>
        <span v-else>
          Procurando por <strong>nome</strong> ou nome fantasia contendo
          “{{ interpretacao.termo }}”.
        </span>
      </p>
    </section>

    <p v-if="erro" class="aviso aviso--erro" role="alert">
      <i class="bi bi-exclamation-octagon aviso__icone" aria-hidden="true"></i>
      <span>{{ erro }}</span>
    </p>

    <p v-if="carregando" class="linha fraco">
      <span class="girando"></span> Consultando…
    </p>

    <div v-else-if="!itens.length" class="vazio">
      <i class="bi bi-inbox vazio__icone" aria-hidden="true"></i>
      <p class="vazio__titulo">Nenhum cliente encontrado</p>
      <p v-if="interpretacao.tipo === 'telefone'">
        Nenhum cadastro tem este número. Ele existe no Harmonit?
      </p>
      <p v-else-if="interpretacao.tipo !== 'vazio'">
        Tente outro termo — ou um telefone, que a busca reconhece.
      </p>
    </div>

    <template v-else>
      <p class="fraco pequeno cad__contagem">
        {{ numero(total) }}
        {{ total === 1 ? 'cliente' : 'clientes' }}
        <span v-if="paginas > 1">· página {{ pagina }} de {{ paginas }}</span>
      </p>

      <div class="tabela--rolavel">
        <table class="tabela">
          <thead>
            <tr>
              <th>Nome</th>
              <th>Documento</th>
              <th>Tipo</th>
              <th class="cad__num">Telefones</th>
              <th>Origem</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="item in itens"
              :key="item.id"
              :class="{ 'cad__inativo': !item.ativo }"
            >
              <td>
                <strong>{{ item.nome }}</strong>
                <br v-if="item.nome_fantasia" />
                <span v-if="item.nome_fantasia" class="pequeno fraco">
                  {{ item.nome_fantasia }}
                </span>
              </td>
              <td class="mono pequeno">{{ documento(item.documento) }}</td>
              <td class="pequeno">{{ item.tipo_pessoa_desc }}</td>
              <td class="cad__num mono">{{ item.telefones }}</td>
              <td>
                <span class="chip" :class="item.origem === 'movizap' ? 'chip--acento' : ''">
                  {{ item.origem }}
                </span>
                <span v-if="!item.ativo" class="chip chip--aviso">inativo</span>
              </td>
              <td>
                <button class="botao botao--fantasma botao--pequeno" @click="abrir(item)">
                  abrir
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <nav v-if="paginas > 1" class="linha cad__paginacao">
        <button
          class="botao botao--contorno botao--pequeno"
          :disabled="pagina <= 1"
          @click="pagina -= 1"
        >
          anterior
        </button>
        <span class="pequeno fraco">{{ pagina }} / {{ paginas }}</span>
        <button
          class="botao botao--contorno botao--pequeno"
          :disabled="pagina >= paginas"
          @click="pagina += 1"
        >
          próxima
        </button>
      </nav>
    </template>

    <!-- ------------------------------------------------------------ detalhe -->
    <section v-if="selecionado" class="cartao cad__detalhe">
      <header class="cartao__cabecalho">
        <span class="linha">
          <i class="bi bi-building" aria-hidden="true"></i>
          {{ selecionado.nome }}
        </span>
        <button class="botao botao--fantasma botao--pequeno" @click="selecionado = null">
          fechar
        </button>
      </header>

      <div class="cartao__corpo">
        <p v-if="carregandoDetalhe" class="linha fraco">
          <span class="girando"></span> Carregando…
        </p>

        <template v-else>
          <dl class="cad__dados">
            <div><dt>Documento</dt><dd class="mono">{{ documento(selecionado.documento) }}</dd></div>
            <div><dt>Tipo</dt><dd>{{ selecionado.tipo_pessoa_desc }}</dd></div>
            <div><dt>E-mail</dt><dd>{{ selecionado.email || '—' }}</dd></div>
            <div><dt>Origem</dt><dd>{{ selecionado.origem }}</dd></div>
            <div><dt>Id no Harmonit</dt><dd class="mono">{{ selecionado.harmonit_id || '—' }}</dd></div>
          </dl>

          <!-- 🚨 O ALCANCE, LOGO NO TOPO. `tem_whatsapp` distingue NULL
               (ninguém verificou) de false (verificado e não tem), e essa
               diferença não aparecia em tela nenhuma: quem abria a ficha não
               sabia se dava para mandar mensagem para aquela empresa. -->
          <div v-if="selecionado.alcance" class="cli__alcance">
            <span class="chip chip--ok">
              {{ selecionado.alcance.com_whatsapp }} com WhatsApp
            </span>
            <span v-if="selecionado.alcance.sem_whatsapp" class="chip">
              {{ selecionado.alcance.sem_whatsapp }} sem
            </span>
            <span v-if="selecionado.alcance.nao_verificados" class="chip chip--aviso">
              {{ selecionado.alcance.nao_verificados }} não verificados
            </span>
          </div>

          <!-- ⚠️ AS ÚLTIMAS CONVERSAS, com o id que abre a tela certa. A ficha
               mostrava dados e acabava ali: quem abria um cliente para saber
               "já falamos com essa empresa?" tinha de ir para a caixa de
               entrada e buscar pelo nome. -->
          <h3 class="cad__subtitulo">Últimas conversas</h3>
          <ul v-if="selecionado.conversas?.length" class="cli__fios">
            <li v-for="c in selecionado.conversas" :key="c.id">
              <button class="cli__fio" type="button"
                      @click="$router.push(`/atendimento/${c.id}`)">
                <span class="cli__fio-quem">{{ c.contato_nome }}</span>
                <span class="apagado pequeno mono">{{ telefoneBonito(c.telefone_e164) }}</span>
                <span v-if="c.estado === 'resolvida'" class="chip chip--ok chip--pequeno">
                  concluída
                </span>
                <span v-else-if="c.atendente_nome" class="chip chip--acento chip--pequeno">
                  {{ c.atendente_nome }}
                </span>
                <span v-else class="chip chip--pequeno">sem dono</span>
                <span class="apagado pequeno">{{ quando(c.ultima_atividade_em) }}</span>
              </button>
            </li>
          </ul>
          <p v-else class="apagado pequeno">
            Nunca conversamos com ninguém desta empresa pelo WhatsApp.
          </p>

          <template v-if="selecionado.emails?.length">
            <h3 class="cad__subtitulo">Últimos e-mails</h3>
            <ul class="cli__fios">
              <li v-for="e in selecionado.emails" :key="e.id">
                <span class="cli__fio">
                  <span class="cli__fio-quem">{{ e.assunto || '(sem assunto)' }}</span>
                  <span class="apagado pequeno">{{ e.remetente }}</span>
                  <span class="apagado pequeno">{{ quando(e.enviado_em) }}</span>
                </span>
              </li>
            </ul>
          </template>

          <h3 class="cad__subtitulo">Contatos</h3>
          <div v-for="c in selecionado.contatos || []" :key="c.id" class="cad__contato">
            <p class="linha">
              <i class="bi bi-person" aria-hidden="true"></i>
              <strong>{{ c.nome }}</strong>
              <span class="chip">{{ c.relacao }}</span>
            </p>
            <ul class="cad__telefones">
              <li v-for="t in c.telefones" :key="t.id" class="linha">
                <span class="mono">{{ telefoneBonito(t.e164) }}</span>
                <span v-if="t.principal" class="chip chip--acento">principal</span>
                <span class="chip">{{ t.origem_campo }}</span>
                <span
                  class="chip"
                  :class="t.tem_whatsapp === true ? 'chip--ok'
                          : t.tem_whatsapp === false ? '' : 'chip--aviso'"
                  :title="t.tem_whatsapp === null
                    ? 'Ninguém verificou ainda. Quem verifica é o Evolution, e ele precisa de um canal conectado.'
                    : ''"
                >
                  {{ t.tem_whatsapp === true ? 'tem WhatsApp'
                     : t.tem_whatsapp === false ? 'sem WhatsApp' : 'não verificado' }}
                </span>
                <span class="pequeno fraco mono">veio como {{ t.bruto }}</span>
                <!-- 🚨 O BOTÃO QUE FAZ A FICHA SERVIR PARA ALGUMA COISA.
                     Falar com este número é a ação óbvia de quem está olhando
                     a ficha, e não havia caminho: era copiar o número e ir
                     procurar na caixa de entrada. Só aparece onde há WhatsApp
                     -- oferecer onde não há seria oferecer erro. -->
                <button
                  v-if="t.tem_whatsapp === true"
                  class="botao botao--pequeno botao--contorno"
                  type="button"
                  @click="$router.push(`/atendimento?numero=${encodeURIComponent(t.e164)}`)"
                >
                  <i class="bi bi-whatsapp" aria-hidden="true"></i> Conversar
                </button>
              </li>
              <li v-if="!c.telefones.length" class="fraco pequeno">
                Nenhum telefone no Harmonit.
              </li>
            </ul>
          </div>
        </template>
      </div>
    </section>
  </div>
</template>

<style scoped>
.cad__filtros {
  display: flex;
  gap: var(--e-4);
  align-items: center;
  flex-wrap: wrap;
}

.cad__busca {
  display: flex;
  align-items: center;
  gap: var(--e-2);
  flex: 1 1 18rem;
}

.cad__busca .campo {
  flex: 1;
}

.cad__contagem {
  margin: var(--e-3) 0;
}

.cad__num {
  text-align: right;
  font-variant-numeric: tabular-nums;
}

.cad__inativo {
  opacity: 0.62;
}

.cad__paginacao {
  gap: var(--e-3);
  margin-top: var(--e-4);
  align-items: center;
}

.cli__alcance { display: flex; gap: var(--e-1); flex-wrap: wrap; margin-bottom: var(--e-3); }

.cli__fios { list-style: none; margin: 0 0 var(--e-3); padding: 0; }
.cli__fio {
  display: flex;
  align-items: center;
  gap: var(--e-2);
  width: 100%;
  padding: var(--e-2);
  border: 0;
  border-bottom: var(--borda-fina) solid var(--borda);
  background: none;
  text-align: left;
  font-family: var(--fonte);
  font-size: var(--txt-sm);
}
button.cli__fio { cursor: pointer; }
button.cli__fio:hover { background: var(--superficie-2); }
.cli__fio-quem {
  flex: 1 1 auto;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--texto);
}

.cad__detalhe {
  margin-top: var(--e-5);
}

.cad__dados {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(11rem, 1fr));
  gap: var(--e-4);
  margin: 0 0 var(--e-5);
}

.cad__dados dt {
  font-size: var(--txt-xs);
  color: var(--texto-fraco);
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.cad__dados dd {
  margin: 0;
}

.cad__subtitulo {
  font-size: var(--txt-md);
  margin: 0 0 var(--e-3);
}

.cad__contato {
  border-top: var(--borda-fina);
  padding-top: var(--e-3);
  margin-top: var(--e-3);
}

.cad__telefones {
  list-style: none;
  padding: 0;
  margin: var(--e-2) 0 0;
  display: flex;
  flex-direction: column;
  gap: var(--e-2);
}

.cad__telefones li {
  flex-wrap: wrap;
  gap: var(--e-2);
}
</style>
