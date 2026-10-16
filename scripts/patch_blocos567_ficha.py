"""Blocos 5, 6 e 7 na Caixa de Entrada: Ligacoes na ficha, Outros contatos e
rascunho por conversa (15/10).

Idempotente, com ancora conferida e contada. Nao faz build e nao reinicia nada.
Uso: ./venv/bin/python scripts/patch_blocos567_ficha.py [--conferir]
"""
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
ALVO = RAIZ / "frontend" / "src" / "telas" / "CaixaDeEntrada.vue"
SO_CONFERIR = "--conferir" in sys.argv

PASSOS: list[tuple[str, str, str]] = []


def passo(nome, velho, novo):
    PASSOS.append((nome, velho, novo))


# =========================================================== 1. script: estado
passo("estado novo (ligacoes, outros contatos, rascunho)",
      """const resposta = ref('')
const enviando = ref(false)
""",
      """const resposta = ref('')
const enviando = ref(false)

/* ---- RASCUNHO POR CONVERSA (Bloco 7, 15/10) ------------------------------
   🔵 Pedido dele nesta rodada: o que foi digitado e nao enviado tem de ficar
   guardado por conversa, e morrer com o login do dia.

   🚨 ISTO CORRIGE UM DEFEITO, nao so acrescenta recurso. `resposta` sobrevivia
   a troca de conversa: quem digitava meia frase para a empresa A, trocava para
   a B e apertava Enter mandava o texto da A para a B. Agora o texto e DAQUELA
   conversa, e so dela.

   ⚠️ `rascunho` aqui e o TEXTO DO COMPOSITOR. Nao confundir com
   `rascunhoNome`, que e o nome do contato sendo editado na ficha (07/10).

   ⚠️ `localStorage` em try/catch, no padrao `movizap.*` do projeto: em janela
   privada, ou com dados do site bloqueados, o acesso ESTOURA -- e perder o
   rascunho e aceitavel, derrubar a tela nao e. */
const PREFIXO_RASCUNHO = 'movizap.rascunho.'
/* Quais conversas tem rascunho guardado, para a lista poder marcar. Vive em
   memoria de proposito: ler o `localStorage` dentro do `v-for` seria uma
   leitura por conversa em cada desenho da lista (sao centenas). */
const comRascunho = ref(new Set())

function chaveRascunho(id) { return PREFIXO_RASCUNHO + id }

function lerRascunho(id) {
  try { return localStorage.getItem(chaveRascunho(id)) || '' } catch { return '' }
}

function apagarRascunho(id = null) {
  const alvo = id ?? aberta.value?.id
  if (!alvo) return
  try { localStorage.removeItem(chaveRascunho(alvo)) } catch { /* sem storage */ }
  if (comRascunho.value.has(alvo)) {
    const s = new Set(comRascunho.value)
    s.delete(alvo)
    comRascunho.value = s
  }
}

/* Guarda o que esta no compositor DA CONVERSA ABERTA AGORA. Chamada ANTES de
   trocar de conversa, ao fechar, e no `beforeunload`. */
function guardarRascunho() {
  const id = aberta.value?.id
  if (!id) return
  const texto = resposta.value
  if (!texto || !texto.trim()) { apagarRascunho(id); return }
  try { localStorage.setItem(chaveRascunho(id), texto) } catch { return }
  if (!comRascunho.value.has(id)) {
    const s = new Set(comRascunho.value)
    s.add(id)
    comRascunho.value = s
  }
}

/* Uma varredura so, no arranque: quais conversas tem rascunho. */
function lerRascunhosGuardados() {
  const achados = new Set()
  try {
    for (let i = 0; i < localStorage.length; i++) {
      const chave = localStorage.key(i)
      if (chave && chave.startsWith(PREFIXO_RASCUNHO)) {
        const id = Number(chave.slice(PREFIXO_RASCUNHO.length))
        if (id) achados.add(id)
      }
    }
  } catch { /* sem storage: a marca simplesmente nao aparece */ }
  comRascunho.value = achados
}

/* ---- LIGACOES DESTA PESSOA (Bloco 5, 15/10) ------------------------------
   🔵 *"aqui na conversa, o modal so trara ultimos 7 dias, para mais dias um
   botao vai levar para a aba Ligacoes"* e *"importante a separacao basica
   entre, feitas, recebidas, etc"*.

   🚨 A ROTA E `ATD_1.2`, a permissao da CONVERSA. Quem atende ve as ligacoes
   do numero que esta atendendo, mesmo sem a aba Ligacoes. */
const ligacoesAbertas = ref(false)
const ligacoesCarregando = ref(false)
const ligacoesDados = ref(null)
const ligacoesErro = ref('')
const tocandoLigacao = ref({ id: null, url: '' })
const SENTIDOS_LIGACAO = [
  ['feita', 'Feitas', 'bi-telephone-outbound'],
  ['recebida', 'Recebidas', 'bi-telephone-inbound'],
  ['perdida', 'Perdidas', 'bi-telephone-x'],
]
/* O salto para a aba so aparece para quem TEM a aba: para os outros seria um
   botao que leva a um 403. */
const vejoAbaLigacoes = computed(() => codigosPermitidos.value.has('LIG_1.1'))

function soltarPlayerLigacao() {
  if (tocandoLigacao.value.url) URL.revokeObjectURL(tocandoLigacao.value.url)
  tocandoLigacao.value = { id: null, url: '' }
}

function fecharLigacoes() {
  soltarPlayerLigacao()
  ligacoesAbertas.value = false
}

async function verLigacoes() {
  if (!aberta.value) return
  ligacoesAbertas.value = true
  ligacoesCarregando.value = true
  ligacoesErro.value = ''
  try {
    ligacoesDados.value = await api.get(`/api/conversas/${aberta.value.id}/ligacoes?dias=7`)
  } catch (e) {
    ligacoesDados.value = null
    ligacoesErro.value = e instanceof ErroDeApi ? e.message : 'Nao consegui ler as ligacoes.'
  } finally {
    ligacoesCarregando.value = false
  }
}

async function tocarLigacao(g) {
  if (tocandoLigacao.value.id === g.id) return soltarPlayerLigacao()
  soltarPlayerLigacao()
  try {
    const blob = await pedirBlob(`/api/ligacoes/gravacao/${g.id}`)
    tocandoLigacao.value = { id: g.id, url: URL.createObjectURL(blob) }
  } catch (e) {
    ligacoesErro.value = e instanceof ErroDeApi ? e.message : 'Nao consegui abrir a gravacao.'
  }
}

async function baixarLigacao(g) {
  try {
    const blob = await pedirBlob(`/api/ligacoes/gravacao/${g.id}`)
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = g.nome || `ligacao-${g.id}.mp3`
    a.click()
    URL.revokeObjectURL(url)
  } catch (e) {
    ligacoesErro.value = e instanceof ErroDeApi ? e.message : 'Nao consegui baixar a gravacao.'
  }
}

function todasAsLigacoes() {
  const numero = aberta.value?.telefone_e164
  fecharLigacoes()
  router.push({ path: '/ligacoes', query: { numero, dias: 30 } })
}

function duracaoLigacao(s) {
  const n = Number(s || 0)
  return `${Math.floor(n / 60)}:${String(n % 60).padStart(2, '0')}`
}

function horaLigacao(iso) {
  if (!iso) return '—'
  return new Date(iso).toLocaleString('pt-BR', {
    day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit',
  })
}

/* ---- OUTROS CONTATOS DA EMPRESA (Bloco 6, 15/10) -------------------------
   🔵 Pedido dele nesta rodada: ver os outros contatos da empresa vinculada,
   com telefone, e poder pular para a conversa de um deles.

   🚨 ROTA IRMA SOB `ATD_1.2`. `/api/clientes/{id}` e `CAD_1.1`, que o perfil
   `atendimento` nao tem desde 10/08: a gaveta tomaria 403 justamente para
   quem atende. */
const outrosAbertos = ref(false)
const outrosCarregando = ref(false)
const outros = ref(null)
const outrosErro = ref('')

function fecharOutros() { outrosAbertos.value = false }

async function verOutrosContatos() {
  if (!aberta.value) return
  outrosAbertos.value = true
  outrosCarregando.value = true
  outrosErro.value = ''
  try {
    outros.value = await api.get(`/api/conversas/${aberta.value.id}/contatos-da-empresa`)
  } catch (e) {
    outros.value = null
    outrosErro.value = e instanceof ErroDeApi ? e.message : 'Nao consegui ler os contatos.'
  } finally {
    outrosCarregando.value = false
  }
}

/* Pular para a conversa de outro numero da mesma empresa.

   🚨 REUSA A RECEITA QUE JA EXISTE (a do `?numero=` que vem da ficha do
   cliente): busca o numero, 1 acerto abre a conversa, 0 acerto abre "Nova
   mensagem" preenchida. Nao existe rota que apenas localize ou crie conversa
   sem enviar, e inventar uma so para este botao seria um segundo caminho de
   conversa nascer. */
async function conversarCom(linha) {
  if (!linha.e164) return
  fecharOutros()
  busca.value = linha.e164
  await carregar()
  if (lista.value.length === 1) {
    await abrir(lista.value[0].id)
  } else if (!lista.value.length) {
    abrirNova()
    novoNumero.value = linha.e164
  }
}
""")

# ========================================================= 2. script: abrir()
passo("abrir(): guarda o rascunho da conversa anterior",
      """async function abrir(id) {
  try {
    // Solta o que a conversa anterior segurava ANTES de trocar: o object URL
    // da foto de outro cliente não tem por que continuar vivo.
    soltarMidias()""",
      """async function abrir(id) {
  try {
    /* 🚨 O RASCUNHO DA CONVERSA ANTERIOR É GUARDADO AQUI, ANTES DE TROCAR --
       depois de `aberta.value` mudar não há mais de quem ele é. */
    guardarRascunho()
    // Solta o que a conversa anterior segurava ANTES de trocar: o object URL
    // da foto de outro cliente não tem por que continuar vivo.
    soltarMidias()""")

passo("abrir(): fecha os modais novos na troca",
      """    painelAcao.value = ''
    confirmacao.value = null
    limparPaineis()""",
      """    painelAcao.value = ''
    confirmacao.value = null
    // Os modais novos também não atravessam a troca: o de Ligações mostraria
    // o telefone da conversa anterior, e o player ficaria tocando.
    fecharLigacoes()
    fecharOutros()
    limparPaineis()""")

passo("abrir(): restaura o rascunho desta conversa",
      """    // 🔵 07/10: semeia o rascunho do nome (editável quando o tipo for Lead).
    rascunhoNome.value = aberta.value?.empresa?.contato?.nome || ''""",
      """    /* 🔵 15/10: o compositor passa a nascer com o rascunho DESTA conversa --
       e vazio quando ela não tem nenhum, que é o que mata o vazamento de
       texto de uma conversa para a outra. */
    resposta.value = lerRascunho(id)
    // 🔵 07/10: semeia o rascunho do nome (editável quando o tipo for Lead).
    rascunhoNome.value = aberta.value?.empresa?.contato?.nome || ''""")

# ================================================= 3. script: Esc e fechamento
passo("fecharComEsc: os dois modais novos",
      """  if (evento.key !== 'Escape') return
  if (confirmacao.value) { confirmacao.value = null; return }""",
      """  if (evento.key !== 'Escape') return
  if (confirmacao.value) { confirmacao.value = null; return }
  // Modal fica ACIMA da gaveta, então Esc fecha o modal primeiro.
  if (ligacoesAbertas.value) { fecharLigacoes(); return }
  if (outrosAbertos.value) { fecharOutros(); return }""")

passo("fecharConversa: guarda o rascunho e fecha os modais",
      """function fecharConversa() {
  soltarMidias()""",
      """function fecharConversa() {
  // O texto não se perde ao fechar a conversa: ele é rascunho dela.
  guardarRascunho()
  fecharLigacoes()
  fecharOutros()
  soltarMidias()""")

# ============================================= 4. script: os 3 pontos de envio
passo("envio de texto: o rascunho morre com o envio",
      """    resposta.value = ''
    citando.value = null
    mencionados.value = []""",
      """    resposta.value = ''
    apagarRascunho()
    citando.value = null
    mencionados.value = []""")

passo("envio de arquivos (sucesso): o rascunho morre",
      """    limparArquivos()
    resposta.value = ''
    recado.value = total > 1""",
      """    limparArquivos()
    resposta.value = ''
    apagarRascunho()
    recado.value = total > 1""")

passo("envio de arquivos (parcial): o rascunho morre do que foi",
      """    if (enviados > 0) {
      resposta.value = ''
      await Promise.all([abrir(aberta.value.id), carregar({ silencioso: true })])
    }""",
      """    if (enviados > 0) {
      resposta.value = ''
      apagarRascunho()
      await Promise.all([abrir(aberta.value.id), carregar({ silencioso: true })])
    }""")

# ============================================ 5. script: montagem e desmontagem
passo("onMounted: lê os rascunhos guardados e protege o fechar da aba",
      """  document.addEventListener('keydown', fecharComEsc)""",
      """  document.addEventListener('keydown', fecharComEsc)
  /* 🚨 FECHAR A ABA TAMBÉM TEM DE GUARDAR. Sem isto, o F5 e o fechar levavam
     embora o que estava digitado -- e é justamente aí que a pessoa reclama. */
  window.addEventListener('beforeunload', guardarRascunho)
  lerRascunhosGuardados()""")

passo("onUnmounted: guarda ao sair da tela e solta o player",
      """onUnmounted(() => {
  clearInterval(timer)
  document.removeEventListener('keydown', atalho)
  document.removeEventListener('keydown', fecharComEsc)""",
      """onUnmounted(() => {
  clearInterval(timer)
  // Sair da Caixa de entrada para outra tela não é descartar o que foi
  // digitado: guarda, e solta o áudio que estiver tocando.
  guardarRascunho()
  soltarPlayerLigacao()
  window.removeEventListener('beforeunload', guardarRascunho)
  document.removeEventListener('keydown', atalho)
  document.removeEventListener('keydown', fecharComEsc)""")

# ====================================================== 6. template: os botões
passo("ficha: o botão Ligações",
      """            <!-- Empresas do grupo desta pessoa. Consulta, não escolha: o""",
      """            <!-- 🔵 15/10, Bloco 5: as LIGAÇÕES deste número, últimos 7
                 dias. Modal, e não gaveta: é consulta de um minuto, e a
                 gaveta já é a ficha. -->
            <button
              class="botao botao--pequeno botao--contorno"
              type="button"
              @click="verLigacoes"
            >
              <i class="bi bi-telephone" aria-hidden="true"></i>
              Ligações
            </button>

            <!-- Empresas do grupo desta pessoa. Consulta, não escolha: o""")

passo("ficha: telefone do contato e Outros contatos",
      """                <dd v-else>{{ aberta.empresa.contato.nome }}</dd>""",
      """                <dd v-else>{{ aberta.empresa.contato.nome }}</dd>
                <!-- 🔵 15/10, Bloco 6: o TELEFONE do contato, que este <dl>
                     nunca mostrou, e o caminho para os outros contatos da
                     mesma empresa.
                     ⚠️ `principal` primeiro: é a ordem que o backend devolve
                     (`contato_telefone ORDER BY principal DESC`). -->
                <dd v-if="(aberta.empresa.contato.telefones || []).length"
                    class="gaveta__fones pequeno">
                  <span v-for="t in aberta.empresa.contato.telefones.slice(0, 2)"
                        :key="t.id" class="mono">
                    {{ t.e164 }}
                    <span v-if="t.tem_whatsapp === false"
                          class="chip chip--aviso chip--pequeno">sem WhatsApp</span>
                  </span>
                  <span v-if="aberta.empresa.contato.telefones.length > 2" class="apagado">
                    +{{ aberta.empresa.contato.telefones.length - 2 }}
                  </span>
                </dd>
                <dd>
                  <button
                    class="botao botao--pequeno botao--contorno"
                    type="button"
                    @click="verOutrosContatos"
                  >
                    <i class="bi bi-person-lines-fill" aria-hidden="true"></i>
                    Outros contatos
                  </button>
                </dd>""")

passo("lista: a marca de rascunho",
      """              <div class="conversa__marcas pequeno">
                <span v-if="!c.contato_nome" class="chip chip--aviso chip--pequeno">""",
      """              <div class="conversa__marcas pequeno">
                <!-- 🟡 15/10 (minha): sem esta marca, o texto guardado fica
                     invisível até a pessoa reabrir a conversa -- e rascunho
                     que ninguém vê é rascunho esquecido. -->
                <span v-if="comRascunho.has(c.id)" class="chip chip--pequeno"
                      title="Você tem texto digitado e não enviado nesta conversa">
                  <i class="bi bi-pencil" aria-hidden="true"></i>
                  rascunho
                </span>
                <span v-if="!c.contato_nome" class="chip chip--aviso chip--pequeno">""")

# ====================================================== 7. template: os modais
passo("os dois modais novos",
      """    <!-- VINCULAR A UMA EMPRESA — a escolha que morava espremida na gaveta -->""",
      """    <!-- ============ LIGAÇÕES DESTE NÚMERO — 7 dias (Bloco 5, 15/10) ======
         🔵 *"o modal só trará ultimos 7 dias, para mais dias um botão vai
         levar para a aba Ligações"*. -->
    <div v-if="ligacoesAbertas && aberta" class="modal" @click.self="fecharLigacoes">
      <div class="modal__caixa modal__caixa--larga" role="dialog" aria-modal="true"
           aria-label="Ligações deste número">
        <p class="modal__titulo">
          Ligações · últimos 7 dias
          <span class="apagado pequeno mono">{{ aberta.telefone_e164 }}</span>
        </p>

        <p v-if="ligacoesErro" class="aviso aviso--erro pequeno" role="alert">
          {{ ligacoesErro }}
        </p>
        <p v-if="ligacoesCarregando" class="apagado pequeno">consultando…</p>

        <template v-else-if="ligacoesDados">
          <!-- 🚨 A FAIXA QUE IMPEDE A TELA DE MENTIR: "nenhuma ligação" e
               "aquele PC não manda ligação nenhuma" são coisas diferentes, e
               só esta linha distingue as duas. -->
          <p class="apagado pequeno">
            Só aparecem ligações de ramais com o agente instalado:
            <strong>{{ ligacoesDados.cobertura.com_agente }}</strong>
            de {{ ligacoesDados.cobertura.atendentes }} atendentes.
          </p>

          <p v-if="!ligacoesDados.total" class="apagado pequeno">
            Nenhuma ligação com este número nos últimos 7 dias.
          </p>

          <div v-for="[valor, rotulo, icone] in SENTIDOS_LIGACAO" :key="valor">
            <template v-if="ligacoesDados.por_sentido[valor].length">
              <p class="campo__rotulo">
                <i class="bi" :class="icone" aria-hidden="true"></i>
                {{ rotulo }} · {{ ligacoesDados.por_sentido[valor].length }}
              </p>
              <ul class="ligacoes__lista">
                <li v-for="l in ligacoesDados.por_sentido[valor]" :key="l.id"
                    class="ligacoes__item pequeno">
                  <span class="mono">{{ horaLigacao(l.inicio) }}</span>
                  <span class="apagado">{{ duracaoLigacao(l.duracao_s) }}</span>
                  <span>{{ l.atendente || 'ramal ' + l.ramal }}</span>
                  <span v-if="!l.gravacoes.length" class="apagado">sem gravação</span>
                  <span v-for="g in l.gravacoes" :key="g.id" class="ligacoes__grav">
                    <button class="botao botao--pequeno botao--contorno" type="button"
                            @click="tocarLigacao(g)">
                      <i class="bi" aria-hidden="true"
                         :class="tocandoLigacao.id === g.id ? 'bi-stop-fill' : 'bi-play-fill'"></i>
                      {{ tocandoLigacao.id === g.id ? 'Parar' : 'Ouvir' }}
                    </button>
                    <button class="botao botao--pequeno botao--contorno" type="button"
                            @click="baixarLigacao(g)">
                      <i class="bi bi-download" aria-hidden="true"></i>
                    </button>
                    <audio v-if="tocandoLigacao.id === g.id" :src="tocandoLigacao.url"
                           controls autoplay></audio>
                  </span>
                </li>
              </ul>
            </template>
          </div>
        </template>

        <div class="modal__acoes">
          <!-- O salto só existe para quem tem a aba: para os outros seria um
               botão que termina em 403. -->
          <button v-if="vejoAbaLigacoes" class="botao botao--contorno" type="button"
                  @click="todasAsLigacoes">
            Ver todas na aba Ligações
          </button>
          <button class="botao botao--primario" type="button"
                  @click="fecharLigacoes">Fechar</button>
        </div>
      </div>
    </div>

    <!-- ============ OUTROS CONTATOS DA EMPRESA (Bloco 6, 15/10) ========== -->
    <div v-if="outrosAbertos && aberta" class="modal" @click.self="fecharOutros">
      <div class="modal__caixa modal__caixa--larga" role="dialog" aria-modal="true"
           aria-label="Outros contatos da empresa">
        <p class="modal__titulo">
          Outros contatos
          <span v-if="outros && outros.cliente" class="apagado pequeno">
            {{ outros.cliente.nome }}
          </span>
        </p>

        <p v-if="outrosErro" class="aviso aviso--erro pequeno" role="alert">
          {{ outrosErro }}
        </p>
        <p v-if="outrosCarregando" class="apagado pequeno">consultando…</p>

        <template v-else-if="outros">
          <!-- ⚠️ VAZIO DIZ POR QUÊ. "Número sem cadastro" e "empresa sem
               outro contato" são casos diferentes, e a tela não pode
               devolver a mesma frase para os dois. -->
          <p v-if="outros.motivo === 'sem_cadastro'" class="apagado pequeno">
            Este número não está no cadastro — então não há empresa de onde
            tirar outros contatos. Dá para vincular pela ficha.
          </p>
          <p v-else-if="outros.motivo === 'contato_sem_empresa'" class="apagado pequeno">
            Esta pessoa não está vinculada a nenhuma empresa.
          </p>
          <p v-else-if="outros.contatos.length <= 1" class="apagado pequeno">
            Esta empresa tem só este contato cadastrado.
          </p>

          <ul v-if="outros.contatos.length" class="outros__lista">
            <li v-for="(l, i) in outros.contatos" :key="i" class="outros__item">
              <span class="outros__quem">
                {{ l.nome }}
                <span v-if="l.este_contato" class="chip chip--pequeno">este</span>
                <span v-for="p in l.papeis" :key="p" class="chip chip--pequeno">{{ p }}</span>
              </span>
              <span class="mono pequeno">{{ l.e164 || 'sem telefone' }}</span>
              <span v-if="l.tem_whatsapp === false"
                    class="chip chip--aviso chip--pequeno">sem WhatsApp</span>
              <!-- 🟡 O botão não aparece sem número nem para quem foi
                   conferido e NÃO tem WhatsApp: mandar ali só produz 409.
                   `tem_whatsapp` nulo (nunca conferido) continua tendo botão
                   -- recusar por falta de conferência seria inventar o `false`. -->
              <button
                v-if="l.e164 && l.tem_whatsapp !== false && !l.esta_conversa"
                class="botao botao--pequeno botao--contorno"
                type="button"
                @click="conversarCom(l)"
              >
                <i class="bi bi-chat-dots" aria-hidden="true"></i>
                Mensagem
              </button>
            </li>
          </ul>
        </template>

        <div class="modal__acoes">
          <button class="botao botao--primario" type="button"
                  @click="fecharOutros">Fechar</button>
        </div>
      </div>
    </div>

    <!-- VINCULAR A UMA EMPRESA — a escolha que morava espremida na gaveta -->""")

# =============================================================== 8. o estilo
passo("estilo dos dois modais",
      """.modal__caixa--larga { max-width: 560px; }""",
      """.modal__caixa--larga { max-width: 560px; }

/* Ligações e Outros contatos: linha por item, sem tabela. São listas curtas
   (7 dias, um punhado de contatos) e tabela aqui só acrescentaria moldura. */
.ligacoes__lista,
.outros__lista { list-style: none; margin: 0 0 var(--e-3); padding: 0; }
.ligacoes__item,
.outros__item {
  display: flex;
  align-items: center;
  gap: var(--e-2);
  flex-wrap: wrap;
  padding: 4px 0;
  border-bottom: var(--borda-fina) solid var(--borda);
}
.ligacoes__grav { display: inline-flex; align-items: center; gap: 4px; }
.ligacoes__item audio { max-width: 200px; height: 30px; }
.outros__quem { display: inline-flex; align-items: center; gap: 4px; flex: 1; min-width: 40%; }
.gaveta__fones { display: flex; align-items: center; gap: var(--e-2); flex-wrap: wrap; }""")


def aplicar():
    texto = ALVO.read_text(encoding="utf-8")
    feitos, pulados = [], []
    for nome, velho, novo in PASSOS:
        if novo in texto:
            pulados.append(nome)
            continue
        n = texto.count(velho)
        if n != 1:
            raise SystemExit(f"ANCORA {n}x em '{nome}': {velho[:70]!r}")
        texto = texto.replace(velho, novo, 1)
        feitos.append(nome)
    if not SO_CONFERIR and feitos:
        ALVO.write_text(texto, encoding="utf-8")
    for n in feitos:
        print(f"  {'conferido' if SO_CONFERIR else 'aplicado'}: {n}")
    for n in pulados:
        print(f"  ja aplicado: {n}")
    print(f"{len(feitos)} passo(s), {len(pulados)} ja estavam")


aplicar()
