/**
 * @vitest-environment node
 *
 * Bloco 12 — "visto por" na nota interna, na tela (15/10).
 *
 * 🚨 GUARDA DE TEXTO. O que estes testes impedem é a volta de quatro decisões
 * que custaram discussão:
 *   · o rótulo é "visto por", NUNCA "leu" -- o sistema sabe que a nota esteve
 *     na tela, não que a pessoa leu, e dizer "leu" vira prova de algo que não
 *     se mediu;
 *   · marca quando a nota APARECE, não quando a conversa abre;
 *   · "não havia registro" não é "ninguém viu";
 *   · a data do corte vive no backend, e não repetida aqui.
 */
import { describe, it, expect } from 'vitest'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

const caixa = readFileSync(
  fileURLToPath(new URL('./telas/CaixaDeEntrada.vue', import.meta.url)), 'utf8')

const popover = (() => {
  const ini = caixa.indexOf('class="balao__vistos pequeno"')
  return ini < 0 ? '' : caixa.slice(ini, caixa.indexOf('</p>', ini) + 4)
})()

describe('"visto por" na nota', () => {
  it('o rótulo é "Visto por", e a palavra "leu" não aparece', () => {
    expect(popover).toContain('Visto por')
    expect(popover).not.toMatch(/\bleu\b/i)
    expect(popover).not.toMatch(/\blida\b/i)
  })

  it('o ícone fica junto do carimbo, e só em nota', () => {
    expect(caixa).toContain('class="balao__visto"')
    expect(caixa).toMatch(/v-if="m\.tipo === 'nota'"[\s\S]{0,120}class="balao__visto"/)
  })

  it('marca quando a nota APARECE, por IntersectionObserver', () => {
    /* 🚨 Marcar na abertura da conversa carimbaria nota que está três telas
       acima e que ninguém rolou até ver. */
    expect(caixa).toContain('new IntersectionObserver')
    expect(caixa).toContain('[data-nota]')
    expect(caixa).toContain(':data-nota="m.tipo === \'nota\' && m.leitura_rastreada ? m.id : null"')
  })

  it('manda em lote, com espera, e não uma requisição por nota', () => {
    expect(caixa).toContain('setTimeout(mandarNotasVistas, 1200)')
    expect(caixa).toContain('/notas/vistas')
  })

  it('falhar ao marcar não vira erro na tela', () => {
    /* A pessoa está LENDO e não pediu nada: erro ali seria ruído sobre algo
       que ela não fez. */
    const f = caixa.slice(caixa.indexOf('async function mandarNotasVistas'))
      .slice(0, 700)
    expect(f).toContain('} catch {')
    expect(f).not.toContain('erro.value')
  })

  it('"não havia registro" é diferente de "ninguém viu"', () => {
    expect(popover).toContain('m.leitura_rastreada')
    expect(popover).toContain('Sem registro')
    expect(popover).toContain('Ninguém teve esta nota na tela ainda')
  })

  it('e a data do corte NÃO é repetida na tela', () => {
    /* Ela mora no backend (`LEITURA_DE_NOTA_DESDE`). Repetida aqui, viraria
       uma segunda verdade para divergir no dia em que mudar. */
    expect(popover).not.toMatch(/15\/10|2026-10-15/)
  })

  it('o observador é remontado por conversa e com nota nova', () => {
    /* Elemento novo não nasce observado: sem isto, nota que chega depois da
       abertura nunca seria marcada -- e o recurso pareceria funcionar. */
    expect(caixa).toContain('watch(() => aberta.value?.mensagens?.length')
    expect(caixa).toMatch(/vistoAberto\.value = null\s*\n\s*olharAsNotas\(\)/)
  })

  it('e é soltado ao sair da tela, mandando o que faltou', () => {
    expect(caixa).toContain('pararDeOlharAsNotas()')
    const f = caixa.slice(caixa.indexOf('function pararDeOlharAsNotas'))
      .slice(0, 500)
    expect(f).toContain('disconnect()')
    expect(f).toContain('mandarNotasVistas()')
  })
})
