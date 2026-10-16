"""Bloco 11 na tela: o evento como LINHA, nunca como balao (15/10).

🚨 EVENTO NAO E MENSAGEM, e nao pode parecer uma. Como balao ele entraria no
fio com o mesmo peso do que o cliente escreveu, ganharia menu de editar e
apagar, e a conversa viraria metade conversa e metade log. Como linha discreta
ele se le de relance e se ignora de relance -- que e o uso certo de um log.

Idempotente, ancora contada. Nao faz build.
Uso: ./venv/bin/python scripts/patch_bloco11_frontend.py [--conferir]
"""
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
ALVO = RAIZ / "frontend" / "src" / "telas" / "CaixaDeEntrada.vue"
SO_CONFERIR = "--conferir" in sys.argv

PASSOS: list[tuple[str, str, str]] = []


def passo(nome, velho, novo):
    PASSOS.append((nome, velho, novo))


passo("script: o ícone de cada evento",
      """function hora(iso) {
  return new Date(iso).toLocaleString('pt-BR', { dateStyle: 'short', timeStyle: 'short' })
}""",
      """function hora(iso) {
  return new Date(iso).toLocaleString('pt-BR', { dateStyle: 'short', timeStyle: 'short' })
}

/* ---- EVENTO: o log de ações dentro da conversa (Bloco 11, 15/10) ---------
   🔵 *"log dentro da conversa interno apenas sobre ações de transfernecia,
   inserir pessoas, etc, pode ser em Nota interna do Movizap"*.

   🚨 A lista fechada vive no BANCO (`ck_evento_conhecido`, migração 064). Este
   mapa é só desenho: evento que chegue sem ícone aqui continua aparecendo, com
   um ponto -- a tela não esconde o que não reconhece.

   ⚠️ A FRASE VEM DO SERVIDOR, não daqui. Montá-la no navegador faria o mesmo
   log ter dois textos quando esta tela mudasse, e o histórico não se reescreve
   junto com o frontend. */
const ICONE_EVENTO = {
  assumiu: 'bi-hand-index-thumb',
  entrou: 'bi-box-arrow-in-right',
  convidou: 'bi-person-plus',
  saiu: 'bi-box-arrow-right',
  removeu: 'bi-person-dash',
  devolveu: 'bi-arrow-counterclockwise',
  transferiu: 'bi-arrow-left-right',
  encerrou: 'bi-check2-circle',
  vinculou: 'bi-link-45deg',
  desvinculou: 'bi-x-circle',
  mudou_tipo: 'bi-tag',
  bloqueou: 'bi-slash-circle',
  desbloqueou: 'bi-unlock',
}""")

passo("template: a linha do evento, antes do balão",
      """            <div
              class="balao"
              :class="[`balao--${m.direcao}`, {""",
      """            <!-- ══ EVENTO: LINHA, NÃO BALÃO (Bloco 11, 15/10) ════════════
                 🚨 Como balão, o log entraria no fio com o mesmo peso do que o
                 cliente escreveu e ganharia o menu de editar e apagar --
                 justamente o que um log não pode ter. Como linha discreta ele
                 se lê de relance e se ignora de relance.

                 ⚠️ `data-mensagem` fica: é por ele que `irParaMensagem` rola
                 até uma linha quando a busca casa com o texto dela. -->
            <p v-if="m.evento" class="evento" :data-mensagem="m.id">
              <i class="bi" :class="ICONE_EVENTO[m.evento] || 'bi-dot'"
                 aria-hidden="true"></i>
              <span>
                <strong v-if="m.atendente_nome">{{ m.atendente_nome }}</strong>
                {{ m.conteudo }}
              </span>
              <span class="evento__hora mono">{{ hora(m.criada_em) }}</span>
            </p>

            <div
              v-else
              class="balao"
              :class="[`balao--${m.direcao}`, {""")

passo("estilo: a linha do evento",
      """.diario__marca { flex: none; text-transform: lowercase; }""",
      """.diario__marca { flex: none; text-transform: lowercase; }

/* 🔵 15/10, Bloco 11 — o log de ações.
   ⚠️ SEM os fios de `::before`/`::after` do separador de dia, de propósito:
   separador de dia aparece uma vez por dia, evento aparece várias vezes por
   atendimento. Com dois traços cada, o fio da conversa viraria uma escada. */
.evento {
  display: flex;
  align-items: baseline;
  gap: var(--e-2);
  margin: 2px 0;
  padding: 2px var(--e-2);
  color: var(--texto-apagado);
  font-size: var(--txt-sm);
  line-height: var(--entrelinha-apertada);
}
.evento i { flex: none; }
/* O nome de quem agiu é o que se procura numa linha de log: ganha peso, mas
   não cor -- cor aqui competiria com o balão ao lado. */
.evento strong { font-weight: var(--peso-medio); color: var(--texto-fraco); }
.evento__hora { margin-left: auto; flex: none; font-size: var(--txt-xs); }
@media (max-width: 860px) {
  /* No celular a hora completa empurra o texto para duas linhas; ali o que
     importa é o que aconteceu. */
  .evento__hora { display: none; }
}""")


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


aplicar()
