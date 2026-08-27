/**
 * @vitest-environment jsdom
 *
 * O destaque da menção no balão — 27/08.
 *
 * 🚨 O QUE ISTO DEFENDE: o destaque tem de vir de `mencionados`, que está
 * GRAVADO, e nunca de procurar "@" no texto. Caçar arroba acenderia
 * "email@movisat.com.br" e "@10h" como se fossem gente — e erraria em
 * silêncio, que é o defeito que este projeto mais paga.
 *
 * ⚠️ A função é testada isolada, com o mesmo algoritmo do componente: o que
 * importa aqui é a REGRA de quebra, e ela é pura.
 */
import { describe, it, expect } from 'vitest'

/* Mesma lógica de `partesDoTexto` do ChatInterno.vue. */
function partesDoTexto(m) {
  const nomes = (m.mencionados || []).map((p) => p.nome)
    .sort((a, b) => b.length - a.length)
  if (!nomes.length) return [{ texto: m.texto }]
  const partes = []
  let resto = m.texto
  let guarda = 0
  while (resto && guarda++ < 200) {
    let achou = null
    for (const nome of nomes) {
      const i = resto.indexOf('@' + nome)
      if (i !== -1 && (achou === null || i < achou.i)) achou = { i, nome }
    }
    if (!achou) break
    if (achou.i) partes.push({ texto: resto.slice(0, achou.i) })
    partes.push({ texto: '@' + achou.nome, mencao: true, eu: Boolean(m.me_chamou) })
    resto = resto.slice(achou.i + achou.nome.length + 1)
  }
  if (resto) partes.push({ texto: resto })
  return partes
}

const acesas = (partes) => partes.filter((p) => p.mencao).map((p) => p.texto)

describe('o destaque da menção', () => {
  it('acende o nome que está gravado como menção', () => {
    const partes = partesDoTexto({
      texto: '@Erika consegue olhar?',
      mencionados: [{ id: 2, nome: 'Erika' }],
    })
    expect(acesas(partes)).toEqual(['@Erika'])
  })

  it('NÃO acende arroba que não é menção', () => {
    // 🚨 O defeito que isto impede: um e-mail no meio da frase virando pessoa.
    const partes = partesDoTexto({
      texto: 'manda para suporte@movisat.com.br às 10h',
      mencionados: [],
    })
    expect(acesas(partes)).toEqual([])
    expect(partes).toHaveLength(1)
  })

  it('acende só quem foi REALMENTE chamado, mesmo com outra arroba na frase', () => {
    const partes = partesDoTexto({
      texto: '@Erika manda para suporte@movisat.com.br',
      mencionados: [{ id: 2, nome: 'Erika' }],
    })
    expect(acesas(partes)).toEqual(['@Erika'])
  })

  it('acende as duas quando a mensagem chama duas pessoas', () => {
    const partes = partesDoTexto({
      texto: '@Erika e @Claudia, os dois casos',
      mencionados: [{ id: 2, nome: 'Erika' }, { id: 3, nome: 'Claudia' }],
    })
    expect(acesas(partes)).toEqual(['@Erika', '@Claudia'])
  })

  it('o nome MAIS LONGO vence quando um é prefixo do outro', () => {
    // ⚠️ Sem ordenar por tamanho, "@Ana Paula" acenderia só o "@Ana" e
    // deixaria " Paula" solto no texto.
    const partes = partesDoTexto({
      texto: 'oi @Ana Paula tudo bem',
      mencionados: [{ id: 4, nome: 'Ana Paula' }, { id: 5, nome: 'Ana' }],
    })
    expect(acesas(partes)).toEqual(['@Ana Paula'])
  })

  it('o texto sobrevive inteiro à quebra', () => {
    const m = {
      texto: 'antes @Erika meio @Claudia depois',
      mencionados: [{ id: 2, nome: 'Erika' }, { id: 3, nome: 'Claudia' }],
    }
    const inteiro = partesDoTexto(m).map((p) => p.texto).join('')
    expect(inteiro).toBe(m.texto)
  })

  it('a menção A MIM é marcada diferente da menção a outro', () => {
    // Duas intensidades, e a diferença é de significado: menção a outro é
    // informação; menção a mim é chamado.
    const paraMim = partesDoTexto({
      texto: '@Iago olha isso', me_chamou: true,
      mencionados: [{ id: 1, nome: 'Iago' }],
    })
    const paraOutro = partesDoTexto({
      texto: '@Erika olha isso', me_chamou: false,
      mencionados: [{ id: 2, nome: 'Erika' }],
    })
    expect(paraMim.find((p) => p.mencao).eu).toBe(true)
    expect(paraOutro.find((p) => p.mencao).eu).toBe(false)
  })

  it('mensagem sem menção nenhuma volta como uma peça só', () => {
    const partes = partesDoTexto({ texto: 'bom dia', mencionados: [] })
    expect(partes).toEqual([{ texto: 'bom dia' }])
  })

  it('nome gravado que sumiu do texto não quebra nada', () => {
    // A pessoa apagou o "@Erika" à mão depois de escolher. O envio já filtra
    // isso, mas o histórico pode ter casos antigos.
    const partes = partesDoTexto({
      texto: 'deixa pra lá',
      mencionados: [{ id: 2, nome: 'Erika' }],
    })
    expect(partes.map((p) => p.texto).join('')).toBe('deixa pra lá')
    expect(acesas(partes)).toEqual([])
  })
})
