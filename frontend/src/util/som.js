/* ============================================================================
   Os tons da notificação — gerados no navegador, sem arquivo de áudio (24/09)
   ----------------------------------------------------------------------------
   🔵 *"coloque opções de som"* e volume *"com minimo de 1 (1 até 5)"*.

   ⚠️ SEM ARQUIVO DE PROPÓSITO: Web Audio gera o tom na hora. Nada para
   hospedar, nada que o cache sirva velho, e o volume é exato.

   🚨 O NAVEGADOR SÓ DEIXA TOCAR DEPOIS DE UM CLIQUE NA PÁGINA (política de
   autoplay). Logo depois do login isso já aconteceu; depois de um F5, não.
   `somBloqueado` avisa a tela, e o primeiro clique em qualquer lugar libera.
   ============================================================================ */
import { ref } from 'vue'

export const TONS = [
  { valor: 'classico', rotulo: 'Clássico', ajuda: 'dois toques, agudo e grave' },
  { valor: 'suave', rotulo: 'Suave', ajuda: 'um toque baixo e curto' },
  { valor: 'sino', rotulo: 'Sino', ajuda: 'um toque que ecoa' },
  { valor: 'alerta', rotulo: 'Alerta', ajuda: 'três toques rápidos' },
]

// Volume 1..5 -> ganho. Sem zero: quem não deve ouvir é decisão do owner.
const GANHO = [0, 0.08, 0.16, 0.28, 0.42, 0.6]

export const somBloqueado = ref(false)
let contexto = null

function ctx() {
  if (!contexto) {
    const Ctor = window.AudioContext || window.webkitAudioContext
    if (!Ctor) return null
    contexto = new Ctor()
    // O primeiro clique em qualquer lugar destrava o som daqui em diante.
    const destravar = () => {
      contexto.resume().then(() => { somBloqueado.value = contexto.state !== 'running' })
    }
    window.addEventListener('pointerdown', destravar)
    window.addEventListener('keydown', destravar)
  }
  return contexto
}

function nota(c, freq, inicio, duracao, ganho, forma = 'sine') {
  const osc = c.createOscillator()
  const g = c.createGain()
  osc.type = forma
  osc.frequency.value = freq
  const t0 = c.currentTime + inicio
  g.gain.setValueAtTime(0.0001, t0)
  g.gain.exponentialRampToValueAtTime(ganho, t0 + 0.015)
  g.gain.exponentialRampToValueAtTime(0.0001, t0 + duracao)
  osc.connect(g).connect(c.destination)
  osc.start(t0)
  osc.stop(t0 + duracao + 0.02)
}

const DESENHO = {
  classico: (c, g) => { nota(c, 880, 0, 0.14, g); nota(c, 660, 0.16, 0.18, g) },
  suave: (c, g) => { nota(c, 520, 0, 0.28, g * 0.9) },
  sino: (c, g) => { nota(c, 1320, 0, 0.7, g, 'triangle'); nota(c, 1980, 0, 0.35, g * 0.3) },
  alerta: (c, g) => {
    nota(c, 1000, 0, 0.08, g * 0.8, 'square')
    nota(c, 1000, 0.12, 0.08, g * 0.8, 'square')
    nota(c, 1000, 0.24, 0.08, g * 0.8, 'square')
  },
}

/** Toca o tom. Devolve false quando o navegador ainda não deixa tocar. */
export async function tocar(tom = 'classico', volume = 3) {
  const c = ctx()
  if (!c) return false
  if (c.state !== 'running') {
    try { await c.resume() } catch { /* segue: o estado diz o que houve */ }
  }
  if (c.state !== 'running') {
    somBloqueado.value = true
    return false
  }
  somBloqueado.value = false
  const g = GANHO[Math.min(5, Math.max(1, Number(volume) || 3))];
  (DESENHO[tom] || DESENHO.classico)(c, g)
  return true
}
