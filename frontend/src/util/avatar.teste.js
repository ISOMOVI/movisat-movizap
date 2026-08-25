/* ============================================================================
   util/avatar.js — as duas funções do avatar por iniciais
   ----------------------------------------------------------------------------
   🚨 ESTE ARQUIVO FALTAVA, E A FALTA ERA MINHA. Criei `avatar.js` em 25/08 com
   lógica de verdade e não escrevi teste -- num projeto que TEM runner
   (`npm test`) e que já testa o `destaque.js`, no mesmo diretório. Achado na
   auditoria do próprio dia.

   ⚠️ A propriedade que mais importa aqui não é a cor ser bonita: é ser
   ESTÁVEL. A caixa de entrada recarrega a cada 8 segundos, e cor que muda
   sozinha destrói a única coisa que o avatar oferece -- reconhecer a conversa
   sem ler.
   ============================================================================ */
import { describe, expect, it } from 'vitest'

import { corDaInicial, iniciais } from './avatar.js'

describe('iniciais', () => {
  it('pega a primeira letra de dois nomes', () => {
    expect(iniciais('Pastelaria Velasco')).toBe('PV')
  })

  it('com um nome só, devolve uma letra', () => {
    expect(iniciais('Iago')).toBe('I')
  })

  it('sobe para maiúscula', () => {
    expect(iniciais('karla financeiro')).toBe('KF')
  })

  it('parte por ponto, arroba, hífen e sublinhado — serve e-mail também', () => {
    expect(iniciais('suporte.tecnico@movisat.com.br')).toBe('ST')
    expect(iniciais('maria-clara')).toBe('MC')
  })

  it('ignora aspas e sinais que vêm de cabeçalho de e-mail', () => {
    expect(iniciais('"Karla Financeiro" <karla@x.com>')).toBe('KF')
  })

  /* 🚨 NOME AUSENTE É CASO NORMAL, NÃO EXCEÇÃO: 64% das conversas não têm
     cadastro, e a lista desenha o avatar assim mesmo. Estourar aqui derrubaria
     a caixa de entrada inteira. */
  it('sem nome, devolve interrogação em vez de estourar', () => {
    expect(iniciais('')).toBe('?')
    expect(iniciais(null)).toBe('?')
    expect(iniciais(undefined)).toBe('?')
  })

  it('espaço extra não vira inicial vazia', () => {
    expect(iniciais('  Rodrigo   Alves  ')).toBe('RA')
  })

  it('nunca passa de duas letras', () => {
    expect(iniciais('Comercial Interno Externo Movisat').length).toBe(2)
  })
})

describe('corDaInicial', () => {
  /* 🚨 A GARANTIA CENTRAL. A lista recarrega a cada 8 s: se a cor mudasse
     entre uma carga e outra, o avatar deixaria de identificar qualquer coisa. */
  it('a mesma chave dá sempre a mesma cor', () => {
    const uma = corDaInicial('Pastelaria Velasco')
    for (let i = 0; i < 50; i += 1) {
      expect(corDaInicial('Pastelaria Velasco')).toBe(uma)
    }
  })

  it('chaves diferentes tendem a cores diferentes', () => {
    expect(corDaInicial('Karla')).not.toBe(corDaInicial('Erika'))
  })

  it('devolve hsl com matiz dentro da volta', () => {
    const achado = /^hsl\((\d+) 45% 42%\)$/.exec(corDaInicial('qualquer'))
    expect(achado).not.toBeNull()
    expect(Number(achado[1])).toBeGreaterThanOrEqual(0)
    expect(Number(achado[1])).toBeLessThan(360)
  })

  /* ⚠️ Saturação e luminosidade FIXAS: o texto por cima é sempre branco, e é
     isso que garante contraste legível em qualquer matiz. Se um dia alguém
     sortear também esses dois, o branco some no amarelo claro. */
  it('mantém saturação e luminosidade fixas em qualquer chave', () => {
    for (const chave of ['a', 'Movisat', '5518998116168', '', 'ç']) {
      expect(corDaInicial(chave)).toMatch(/ 45% 42%\)$/)
    }
  })

  it('chave ausente não estoura', () => {
    expect(() => corDaInicial(null)).not.toThrow()
    expect(() => corDaInicial(undefined)).not.toThrow()
  })
})
