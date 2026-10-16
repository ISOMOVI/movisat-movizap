"""Bloco 8 no navegador: a sessao do dia, o rascunho morrendo com ela e o 401
que deixava a pessoa numa tela morta (15/10).

Idempotente, com ancora contada. Nao faz build.
Uso: ./venv/bin/python scripts/patch_bloco8_frontend.py [--conferir]
"""
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent / "frontend" / "src"
SO_CONFERIR = "--conferir" in sys.argv

PASSOS: list[tuple[str, str, str, str]] = []


def passo(rel, nome, velho, novo):
    PASSOS.append((rel, nome, velho, novo))


# ============================================================== sessao.js
passo("estado/sessao.js", "a hora em que a sessao do dia termina",
      """  /** epoch ms do início da sessão, para a duração na barra de status */
  iniciadaEm: Number(localStorage.getItem(CHAVE_INICIO)) || 0,""",
      """  /** epoch ms do início da sessão, para a duração na barra de status */
  iniciadaEm: Number(localStorage.getItem(CHAVE_INICIO)) || 0,
  /* 🔵 15/10 — A SESSÃO É DO DIA. ISO da hora em que este token morre, dito
     pelo backend (que é quem decide), nunca calculado aqui: duas contas da
     mesma regra divergem no primeiro feriado de fuso. */
  expiraEm: '',""")

passo("estado/sessao.js", "o motivo da saida, para o Login poder dizer",
      """export const autenticado = computed(() => Boolean(sessao.usuario))""",
      """export const autenticado = computed(() => Boolean(sessao.usuario))

/* 🚨 POR QUE A PESSOA FOI PARAR NO LOGIN. Até hoje o 401 limpava a sessão e
   NÃO navegava: quem ficasse com a tela aberta na virada do dia continuava
   olhando uma Caixa de entrada sem casca, que não respondia mais nada, até
   tentar navegar. Era defeito já existente, e com um login por dia ele
   passaria a aparecer TODA madrugada. */
export const motivoDaSaida = ref('')""")

passo("estado/sessao.js", "o import do ref",
      """import { reactive, computed } from 'vue'""",
      """import { reactive, computed, ref } from 'vue'""")

passo("estado/sessao.js", "limpar(): o rascunho morre com a sessao",
      """function limpar() {
  sessao.usuario = null
  sessao.telas = []
  sessao.iniciadaEm = 0
  localStorage.removeItem(CHAVE_INICIO)
  definirToken('')
}""",
      """function limpar() {
  sessao.usuario = null
  sessao.telas = []
  sessao.iniciadaEm = 0
  sessao.expiraEm = ''
  localStorage.removeItem(CHAVE_INICIO)
  apagarRascunhos()
  definirToken('')
}

/* 🔵 15/10, decisão dele: *"o login vale até a virada do dia; o rascunho
   morre com ele"*. É aqui que isso acontece de fato -- este `limpar()` roda
   no logout E na queda de sessão, então dentro do dia o rascunho fica e na
   virada ele vai embora junto.

   ⚠️ Em try/catch e varrendo as chaves ao contrário: remover dentro de um
   laço crescente pula item, porque o índice do `localStorage` reindexa. */
const PREFIXO_RASCUNHO = 'movizap.rascunho.'

function apagarRascunhos() {
  try {
    for (let i = localStorage.length - 1; i >= 0; i--) {
      const chave = localStorage.key(i)
      if (chave && chave.startsWith(PREFIXO_RASCUNHO)) localStorage.removeItem(chave)
    }
  } catch { /* sem storage: não havia rascunho para apagar */ }
}""")

passo("estado/sessao.js", "entrar(): guarda a hora do fim e limpa o motivo",
      """  const r = await api.post('/api/sessao/login', { login, senha })
  definirToken(r.token)
  sessao.iniciadaEm = Date.now()""",
      """  const r = await api.post('/api/sessao/login', { login, senha })
  definirToken(r.token)
  motivoDaSaida.value = ''
  sessao.expiraEm = r.expira_em || ''
  sessao.iniciadaEm = Date.now()""")

passo("estado/sessao.js", "carregarEu(): a hora do fim vale depois do F5 e no Google",
      """  sessao.telas = eu.telas || []
  return eu
}""",
      """  sessao.telas = eu.telas || []
  /* Vem daqui também, e não só da resposta do login: um F5 não refaz o
     login, e quem entra pelo Google nem passa pela rota de senha. */
  sessao.expiraEm = eu.sessao_expira_em || ''
  return eu
}""")

passo("estado/sessao.js", "sair() nao e queda: o motivo fica vazio",
      """export function sair() {
  limpar()
}""",
      """export function sair() {
  // Sair por vontade própria não precisa de explicação na tela de login.
  motivoDaSaida.value = ''
  limpar()
}""")

passo("estado/sessao.js", "a queda de sessao diz o que houve",
      """// 401 em qualquer requisição derruba a sessão aqui, num lugar só.
quandoPerderSessao(limpar)""",
      """// 401 em qualquer requisição derruba a sessão aqui, num lugar só.
quandoPerderSessao(() => {
  // A frase é do fim do DIA porque é esse o fim normal agora. Um 401 por
  // outro motivo (chave rotacionada, conta desativada) cai na mesma tela, e
  // "entre de novo" continua sendo a ação certa.
  motivoDaSaida.value = 'Sua sessão do dia terminou. Entre de novo.'
  limpar()
})""")

# ================================================================= App.vue
passo("App.vue", "sessao perdida leva ao Login, em vez de tela morta",
      """import { computed } from 'vue'
import { useRoute } from 'vue-router'""",
      """import { computed, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'""")

passo("App.vue", "o watch que navega",
      """const rota = useRoute()
const comCasca = computed(() => autenticado.value && !rota.meta.publica)""",
      """const rota = useRoute()
const roteador = useRouter()
const comCasca = computed(() => autenticado.value && !rota.meta.publica)

/* 🚨 QUEM PERDE A SESSÃO VAI PARA O LOGIN, e não para uma tela morta. O 401
   limpa a sessão em `estado/sessao.js`, a casca desaparece -- e a tela de
   dentro continuava desenhada, sem menu e sem responder, até a pessoa tentar
   navegar. Fica AQUI, na casca, porque é o único lugar que vê as duas coisas:
   se ainda estou autenticado e em que rota estou. */
watch(autenticado, (agora) => {
  if (!agora && !rota.meta.publica) {
    roteador.push({ name: 'login', query: { destino: rota.fullPath } })
  }
})""")

passo("App.vue", "o import do autenticado continua um so",
      """import { autenticado } from './estado/sessao.js'""",
      """import { autenticado } from './estado/sessao.js'""")

# ========================================================== BarraStatus.vue
passo("componentes/BarraStatus.vue", "a barra diz a hora em que o dia acaba",
      """const codigo = computed(() => rota.meta.codigo || '—')""",
      """/* 🔵 15/10 — a sessão é DO DIA, então a barra diz a hora em que ela acaba,
   não só quanto tempo faz que começou. "10 horas" não dizia nada a quem
   entrou às 17h. */
const fimDoDia = computed(() => {
  if (!sessao.expiraEm) return ''
  const d = new Date(sessao.expiraEm)
  if (Number.isNaN(d.getTime())) return ''
  return d.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' })
})

/* 🟡 Aviso 15 minutos antes da virada (minha): quem está com a tela aberta
   não pode perder o que digitou sem ter sido avisado. O rascunho sobrevive a
   F5, mas não ao fim da sessão -- é o que ele decidiu. */
const QUASE = 15 * 60 * 1000
const acabando = computed(() => {
  if (!sessao.expiraEm) return false
  const resta = new Date(sessao.expiraEm).getTime() - agora.value.getTime()
  return resta > 0 && resta <= QUASE
})

const codigo = computed(() => rota.meta.codigo || '—')""")

passo("componentes/BarraStatus.vue", "o texto da sessao",
      """    <span class="barra__item barra__item--opcional" title="Tempo desde o início desta sessão">
      <i class="bi bi-hourglass-split" aria-hidden="true"></i>
      sessão {{ duracao }}
    </span>""",
      """    <span class="barra__item barra__item--opcional"
          :class="{ 'barra__item--acabando': acabando }"
          :title="fimDoDia
            ? 'Esta sessão vale até ' + fimDoDia + '. Depois é entrar de novo.'
            : 'Tempo desde o início desta sessão'">
      <i class="bi bi-hourglass-split" aria-hidden="true"></i>
      <template v-if="fimDoDia">sessão do dia · até {{ fimDoDia }}</template>
      <template v-else>sessão {{ duracao }}</template>
    </span>""")

passo("componentes/BarraStatus.vue", "o estilo do aviso",
      """.barra__item--voando { color: var(--texto-fraco); }""",
      """.barra__item--voando { color: var(--texto-fraco); }
/* Só nos últimos 15 minutos do dia: cor de aviso o tempo todo seria ruído. */
.barra__item--acabando { color: var(--aviso, #b45309); font-weight: var(--peso-medio); }""")

# =============================================================== Login.vue
passo("telas/Login.vue", "o import do motivo",
      """import { entrar } from '../estado/sessao.js'""",
      """import { entrar, motivoDaSaida } from '../estado/sessao.js'""")

passo("telas/Login.vue", "o Login diz por que a pessoa voltou para ca",
      """  if (recusa) erro.value = recusa""",
      """  if (recusa) erro.value = recusa
  /* 🚨 QUEM CAIU AQUI POR FIM DE SESSÃO TEM DE LER ISSO. Sem a frase, a
     pessoa que estava trabalhando volta para o login sem explicação e conclui
     que o sistema a derrubou por erro. A recusa do Google ganha a vez: ela é
     sobre a tentativa de agora. */
  if (!erro.value && motivoDaSaida.value) {
    erro.value = motivoDaSaida.value
    motivoDaSaida.value = ''
  }""")


def aplicar():
    por_arquivo: dict[str, str] = {}
    feitos, pulados = [], []
    for rel, nome, velho, novo in PASSOS:
        caminho = RAIZ / rel
        if rel not in por_arquivo:
            por_arquivo[rel] = caminho.read_text(encoding="utf-8")
        texto = por_arquivo[rel]
        if velho == novo:
            continue
        if novo in texto:
            pulados.append(f"{rel}: {nome}")
            continue
        n = texto.count(velho)
        if n != 1:
            raise SystemExit(f"ANCORA {n}x em {rel} '{nome}': {velho[:70]!r}")
        por_arquivo[rel] = texto.replace(velho, novo, 1)
        feitos.append(f"{rel}: {nome}")

    if not SO_CONFERIR:
        for rel, texto in por_arquivo.items():
            (RAIZ / rel).write_text(texto, encoding="utf-8")
    for n in feitos:
        print(f"  {'conferido' if SO_CONFERIR else 'aplicado'}: {n}")
    for n in pulados:
        print(f"  ja aplicado: {n}")
    print(f"{len(feitos)} passo(s), {len(pulados)} ja estavam")


aplicar()
