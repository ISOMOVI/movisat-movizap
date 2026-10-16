/**
 * @vitest-environment node
 *
 * Bloco 11 — o log de ações dentro da conversa, na tela (15/10).
 *
 * 🚨 GUARDA DE TEXTO, não de comportamento: `jsdom` não faz layout e isto não
 * clica em nada. O que estes testes impedem é a VOLTA de três decisões:
 *   · evento é LINHA, não balão -- como balão ele entraria no fio com o peso
 *     do que o cliente escreveu e ganharia o menu de editar e apagar, que é
 *     exatamente o que um log não pode ter;
 *   · a FRASE vem do servidor, nunca montada aqui -- senão o mesmo log passa a
 *     ter dois textos quando esta tela mudar, e o histórico não se reescreve
 *     junto com o frontend;
 *   · evento que a tela não reconhece ainda APARECE, com um ponto no lugar do
 *     ícone: tela que esconde o que não entende é tela que mente por omissão.
 */
import { describe, it, expect } from 'vitest'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

const caixa = readFileSync(
  fileURLToPath(new URL('./telas/CaixaDeEntrada.vue', import.meta.url)), 'utf8')

/* 🚨 Corta o ELEMENTO do evento, e não um punhado de caracteres a esmo: a
   primeira versão deste arquivo fatiava 600 caracteres e alcançava o balão
   logo abaixo, acusando o evento de ter classe de balão. Conferência que
   falha por recorte mal feito é pior que conferência nenhuma -- ela convida a
   "consertar" o que está certo. */
const linhaDoEvento = (() => {
  const ini = caixa.indexOf('<p v-if="m.evento"')
  return ini < 0 ? '' : caixa.slice(ini, caixa.indexOf('</p>', ini) + 4)
})()

describe('o evento é uma linha, não um balão', () => {
  it('o ramo do evento vem ANTES do balão, e o balão virou v-else', () => {
    const evento = caixa.indexOf('<p v-if="m.evento" class="evento"')
    const balao = caixa.indexOf('v-else\n              class="balao"')
    expect(evento).toBeGreaterThan(-1)
    expect(balao).toBeGreaterThan(-1)
    expect(evento).toBeLessThan(balao)
  })

  it('a linha do evento não tem classe de balão', () => {
    expect(linhaDoEvento).not.toContain('balao')
  })

  it('mas continua alcançável pela busca da conversa', () => {
    /* `data-mensagem` é por onde `irParaMensagem` rola até ela. */
    expect(linhaDoEvento).toContain(':data-mensagem="m.id"')
  })

  it('o texto vem do servidor, e não é montado na tela', () => {
    /* Se a tela montasse a frase, haveria um mapa de evento → frase aqui. */
    expect(linhaDoEvento).toContain('{{ m.conteudo }}')
    expect(caixa).not.toContain('FRASE_EVENTO')
  })

  it('e diz quem fez, quando o servidor sabe', () => {
    expect(linhaDoEvento).toContain('m.atendente_nome')
  })

  it('evento desconhecido aparece com um ponto, em vez de desaparecer', () => {
    expect(caixa).toContain("ICONE_EVENTO[m.evento] || 'bi-dot'")
  })

  it('o mapa de ícones cobre os treze eventos do banco', () => {
    /* A lista fechada vive no CHECK `ck_evento_conhecido` (migração 064);
       aqui é só desenho, mas desenho faltando vira ponto genérico. */
    for (const e of ['assumiu', 'entrou', 'convidou', 'saiu', 'removeu',
      'devolveu', 'transferiu', 'encerrou', 'vinculou', 'desvinculou',
      'mudou_tipo', 'bloqueou', 'desbloqueou']) {
      expect(caixa).toMatch(new RegExp(`\\n  ${e}: 'bi-`))
    }
  })

  it('a linha do evento não ganha os fios do separador de dia', () => {
    /* Separador de dia aparece uma vez por dia; evento, várias vezes por
       atendimento. Com dois traços cada, o fio viraria uma escada. */
    const css = caixa.slice(caixa.indexOf('.evento {')).slice(0, 700)
    expect(css).not.toContain('::before')
  })
})
