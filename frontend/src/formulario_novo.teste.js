/*
 * @vitest-environment jsdom
 *
 * ⚠️ O ambiente e declarado NO ARQUIVO, como nas outras suites de tela: o
 * `vite.config.js` deixa o global em `node`, que e mais rapido para os testes
 * que so leem codigo. Montar componente exige DOM.
 */

/* ============================================================================
   O FORMATO NOVO do formulário público — máscara, repetidor e etapa (29/10)
   ----------------------------------------------------------------------------
   🔵 Pedido dele sobre o Suporte: *"ajuste ele no novo formato 'etapas, logo,
   cor, placas, etc'"*. O desenho é o de 23/10 (blocos 1, 3, 5 e 6).

   🚨 O QUE ESTE ARQUIVO PROVA, E O QUE ELE NÃO PROVA. Prova que a tela
   formata, avisa e repete linha. **Não prova que o envio é aceito** -- isso é
   do servidor, e está em `tests/teste_formato_novo.py`, inclusive o teste de
   que um CPF MASCARADO é recusado. Cobrir a recusa aqui daria a impressão de
   que o navegador decide algo.

   🚨 E PROVA O CLÁSSICO TAMBÉM: os 14 formulários que seguem em `classico`
   não podem ganhar botão nenhum por efeito colateral. O último `describe` é
   essa guarda.
   ============================================================================ */
import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'

import {
  conferir, limpar, mascarar, placaVale, problemas,
} from './util/validacao_campo.js'
import CamposDoFormulario from './componentes/CamposDoFormulario.vue'

function campo(nome, tipo, extra = {}) {
  return {
    nome, tipo, rotulo: `Rotulo de ${nome}`, obrigatorio: false,
    multiplo: false, visivel: true, opcoes: [], ajuda: null,
    validacao: null, ...extra,
  }
}

describe('a máscara é só o que se vê, e o limpo é o que vai gravado', () => {
  it('CPF, CNPJ, CEP e telefone ganham a pontuação na tela', () => {
    expect(mascarar('cpf', '11144477735')).toBe('111.444.777-35')
    expect(mascarar('cnpj', '12345678000195')).toBe('12.345.678/0001-95')
    expect(mascarar('cep', '19013180')).toBe('19013-180')
    expect(mascarar('telefone', '18998116168')).toBe('(18) 99811-6168')
    expect(mascarar('telefone', '1833334444')).toBe('(18) 3333-4444')
  })

  it('a máscara não trava quem está no meio da digitação', () => {
    expect(mascarar('cpf', '111')).toBe('111')
    expect(mascarar('cpf', '1114')).toBe('111.4')
    expect(mascarar('cnpj', '12345')).toBe('12.345')
  })

  /* 🚨 ESTE É O PAR DO TESTE DO SERVIDOR: `cpf` é `double` lá, e
     `"111.444.777-35"` não passa por `float()`. Se `limpar` deixar de limpar,
     a rota recusa um CPF correto. */
  it('o que vai gravado é a forma canônica — e a placa fica como foi escrita', () => {
    expect(limpar('cpf', '111.444.777-35')).toBe('11144477735')
    expect(limpar('cnpj', '12.345.678/0001-95')).toBe('12345678000195')
    expect(limpar('telefone', '(18) 99811-6168')).toBe('18998116168')
    /* 🚨 `placa` NÃO se limpa: o campo é *"Veículo e Placa — um por linha"*, e
       `SAVEIRO ABC1234` é resposta certa. Limpar viraria `SAVEIROABC1234`. */
    expect(limpar('placa', 'Saveiro abc-1d23')).toBe('Saveiro abc-1d23')
  })

  /* 🔵 Achado DELE, colando na tela: *"tentei colar WQ0P6GLD000108, deve
     permitir todos os formatos para CNPJ bem como alfanuméricos"* e *"podem
     colar somente numero ou . e - e / tbm"*. */
  it('🚨 CNPJ ALFANUMÉRICO: todos os formatos de colagem dão o mesmo valor', () => {
    const formas = ['WQ0P6GLD000108', 'WQ.0P6.GLD/0001-08', 'wq0p6gld000108',
                    'WQ 0P6 GLD 0001-08']
    for (const forma of formas) {
      expect(limpar('cnpj', forma)).toBe('WQ0P6GLD000108')
      /* E é CNPJ VÁLIDO -- é o da Pastelaria Velasco, na nossa base, com DV
         conferido pela regra nova (ASCII menos 48). */
      expect(conferir('cnpj', forma)).toBe('')
    }
  })

  it('a máscara do CNPJ é posicional, então funciona com letra no meio', () => {
    expect(mascarar('cnpj', 'WQ0P6GLD000108')).toBe('WQ.0P6.GLD/0001-08')
    expect(mascarar('cnpj', '12345678000195')).toBe('12.345.678/0001-95')
    expect(mascarar('cnpj', 'WQ0P6')).toBe('WQ.0P6')
  })
})

describe('a conferência diz a frase, e aceita os dois padrões de placa', () => {
  it('dígito verificador de verdade, não contagem de dígitos', () => {
    expect(conferir('cpf', '111.444.777-35')).toBe('')
    expect(conferir('cpf', '111.444.777-36')).toContain('CPF inválido')
    // 11 dígitos iguais tem dígito verificador "correto" na conta ingênua.
    expect(conferir('cpf', '111.111.111-11')).toContain('CPF inválido')
    expect(conferir('cnpj', '12.345.678/0001-95')).toBe('')
    expect(conferir('cnpj', '12.345.678/0001-96')).toContain('CNPJ inválido')
    expect(conferir('cnpj', 'WQ0P6GLD000109')).toContain('CNPJ inválido')
    /* ⚠️ A frase não manda conferir "os números": num CNPJ com letra isso
       mandaria a pessoa procurar erro onde não há. */
    expect(conferir('cnpj', 'WQ0P6GLD000109')).not.toContain('números')
    // Repetição total continua fora: passaria no módulo 11.
    expect(conferir('cnpj', '00000000000000')).toContain('CNPJ inválido')
  })

  it('placa antiga E Mercosul valem — recusar a antiga tiraria a frota da rua', () => {
    expect(placaVale('ABC1234')).toBe(true)
    expect(placaVale('ABC1D23')).toBe(true)
    expect(placaVale('AB12345')).toBe(false)
    expect(conferir('placa', 'ABC1234')).toBe('')
    expect(conferir('placa', 'ABC12')).toContain('Informe a placa')
    /* ⚠️ A placa é PROCURADA dentro do texto: o campo pede veículo E placa. */
    expect(conferir('placa', 'Saveiro ABC1234')).toBe('')
    expect(conferir('placa', 'SAVEIRO BRANCA')).toContain('Informe a placa')
  })

  it('telefone é 10 ou 11 dígitos, e o campo vazio NÃO é erro aqui', () => {
    expect(conferir('telefone', '(18) 99811-6168')).toBe('')
    expect(conferir('telefone', '(18) 9981')).toContain('10 ou 11')
    // ⚠️ O obrigatório é outra conversa, e é do servidor.
    expect(conferir('cpf', '')).toBe('')
    expect(conferir('placa', '   ')).toBe('')
  })
})

describe('problemas() — a mesma conta que a tela mostra e o trilho segura', () => {
  it('cobra o obrigatório vazio e a máscara errada', () => {
    const campos = [
      campo('a', 'string', { obrigatorio: true }),
      campo('b', 'double', { validacao: 'cpf' }),
    ]
    const fora = problemas(campos, { b: '11144477736' }, null)
    expect(fora.map((f) => f.nome).sort()).toEqual(['a', 'b'])
  })

  it('pergunta ESCONDIDA não cobra nada — ela não foi feita', () => {
    const campos = [campo('oculto', 'double', { obrigatorio: true, visivel: false })]
    expect(problemas(campos, {}, new Set())).toEqual([])
    expect(problemas(campos, {}, new Set(['oculto']))).toHaveLength(1)
  })

  it('no repetidor, uma linha errada basta para avisar', () => {
    const campos = [campo('placas', 'string', { multiplo: true, validacao: 'placa' })]
    expect(problemas(campos, { placas: ['ABC1234', 'ABC1D23'] }, null)).toEqual([])
    expect(problemas(campos, { placas: ['ABC1234', 'XX'] }, null)).toHaveLength(1)
    expect(problemas(campos, { placas: ['Saveiro ABC1234'] }, null)).toEqual([])
    // ⚠️ Linha em branco não é linha errada: quem clicou no `+` e desistiu
    // não leva aviso.
    expect(problemas(campos, { placas: ['ABC1234', ''] }, null)).toEqual([])
  })
})

describe('o repetidor `+` (Bloco 1) — o dado que se perdia em silêncio', () => {
  const placas = campo('placas', 'string', { multiplo: true, validacao: 'placa' })

  it('desenha uma linha, e o `+` acrescenta outra', async () => {
    const valores = {}
    const tela = mount(CamposDoFormulario, {
      props: { campos: [placas], regras: [], valores, formato: 'novo' },
    })
    expect(tela.findAll('.linha')).toHaveLength(1)

    await tela.find('.campo__adicionar').trigger('click')
    expect(tela.findAll('.linha')).toHaveLength(2)
  })

  it('o valor digitado vira LISTA, e já limpo', async () => {
    const valores = {}
    const tela = mount(CamposDoFormulario, {
      props: { campos: [placas], regras: [], valores, formato: 'novo' },
    })
    await tela.find('.linha input').setValue('Saveiro abc-1d23')
    // Fica como foi escrita -- a placa é conferida, não reescrita.
    expect(valores.placas).toEqual(['Saveiro abc-1d23'])
  })

  it('tirar a ÚLTIMA linha é desabilitado — o campo ficaria sem onde escrever', async () => {
    const valores = { placas: ['ABC1234'] }
    const tela = mount(CamposDoFormulario, {
      props: { campos: [placas], regras: [], valores, formato: 'novo' },
    })
    expect(tela.find('.linha__tirar').attributes('disabled')).toBeDefined()

    await tela.find('.campo__adicionar').trigger('click')
    expect(tela.find('.linha__tirar').attributes('disabled')).toBeUndefined()
    await tela.findAll('.linha__tirar')[1].trigger('click')
    expect(tela.findAll('.linha')).toHaveLength(1)
  })

  it('o aviso só aparece DEPOIS de sair do campo', async () => {
    const valores = {}
    const tela = mount(CamposDoFormulario, {
      props: { campos: [placas], regras: [], valores, formato: 'novo' },
    })
    await tela.find('.linha input').setValue('XX')
    // 🟡 Campo que fica vermelho na terceira tecla é hostil.
    expect(tela.find('.campo__frase').exists()).toBe(false)
    await tela.find('.linha input').trigger('blur')
    expect(tela.find('.campo__frase').text()).toContain('Informe a placa')
  })

  it('arquivo múltiplo aceita vários no mesmo campo', () => {
    const tela = mount(CamposDoFormulario, {
      props: {
        campos: [campo('anexos', 'file', { multiplo: true })],
        regras: [], valores: {}, formato: 'novo',
      },
    })
    expect(tela.find('input[type="file"]').attributes('multiple')).toBeDefined()
  })
})

describe('as etapas pedem UM pedaço da definição por vez', () => {
  const campos = [
    campo('a', 'string'), campo('b', 'string'), campo('c', 'string'),
  ]

  it('`somente` desenha só os campos daquela etapa, na ordem pedida', () => {
    const tela = mount(CamposDoFormulario, {
      props: { campos, regras: [], valores: {}, formato: 'novo', somente: ['c', 'a'] },
    })
    const rotulos = tela.findAll('.campo__rotulo').map((s) => s.text())
    expect(rotulos).toEqual(['Rotulo de c', 'Rotulo de a'])
  })

  it('sem `somente`, desenha todos — é o rolo único', () => {
    const tela = mount(CamposDoFormulario, {
      props: { campos, regras: [], valores: {}, formato: 'novo' },
    })
    expect(tela.findAll('.campo__rotulo')).toHaveLength(3)
  })
})

describe('🚨 o CLÁSSICO não muda — os outros 14 estão no ar', () => {
  it('sem formato, campo múltiplo NÃO ganha repetidor nem máscara', async () => {
    const valores = {}
    const tela = mount(CamposDoFormulario, {
      props: {
        campos: [campo('placas', 'string', { multiplo: true, validacao: 'placa' })],
        regras: [], valores,
      },
    })
    expect(tela.find('.campo__adicionar').exists()).toBe(false)
    expect(tela.findAll('.linha')).toHaveLength(0)

    // E o valor segue string única, como as solicitações antigas gravaram.
    await tela.find('input').setValue('abc-1d23')
    expect(valores.placas).toBe('abc-1d23')
  })

  it('sem formato, arquivo não vira múltiplo', () => {
    const tela = mount(CamposDoFormulario, {
      props: {
        campos: [campo('anexos', 'file', { multiplo: true })],
        regras: [], valores: {},
      },
    })
    expect(tela.find('input[type="file"]').attributes('multiple')).toBeUndefined()
  })
})

describe('os três pedidos dele de 29/10 à tarde', () => {
  it('🔵 "Escolha…" não é opção da lista — é o campo esmaecido', () => {
    const lista = campo('tipo', 'list', {
      opcoes: [{ value: '1', label: 'Um' }, { value: '2', label: 'Dois' }],
    })
    const tela = mount(CamposDoFormulario, {
      props: { campos: [lista], regras: [], valores: {}, formato: 'novo' },
    })
    const vazia = tela.find('option[value=""]')
    /* ⚠️ A opção CONTINUA existindo: sem ela o navegador mostraria a primeira
       resposta real como se já estivesse escolhida. O que ela não é mais é
       escolhível nem visível no menu. */
    expect(vazia.exists()).toBe(true)
    expect(vazia.attributes('disabled')).toBeDefined()
    expect(vazia.attributes('hidden')).toBeDefined()
    expect(tela.find('select').classes()).toContain('campo__entrada--esmaecido')
  })

  it('o campo esmaecido deixa de ser esmaecido quando há escolha', () => {
    const lista = campo('tipo', 'list', { opcoes: [{ value: '1', label: 'Um' }] })
    const tela = mount(CamposDoFormulario, {
      props: { campos: [lista], regras: [], valores: { tipo: '1' }, formato: 'novo' },
    })
    expect(tela.find('select').classes()).not.toContain('campo__entrada--esmaecido')
  })

  it('🔵 o botão Buscar só existe no CNPJ, e só com o CNPJ completo', async () => {
    const cnpj = campo('cnpj', 'double', { validacao: 'cnpj' })
    const cpf = campo('cpf', 'double', { validacao: 'cpf' })
    const valores = {}
    const tela = mount(CamposDoFormulario, {
      props: { campos: [cnpj, cpf], regras: [], valores, formato: 'novo' },
    })
    /* 🚨 Um botão só: o CPF não tem para onde preencher. */
    expect(tela.findAll('.campo__buscar')).toHaveLength(1)
    expect(tela.find('.campo__buscar').attributes('disabled')).toBeDefined()

    await tela.findAll('input')[0].setValue('WQ.0P6.GLD/0001-08')
    expect(tela.find('.campo__buscar').attributes('disabled')).toBeUndefined()

    await tela.find('.campo__buscar').trigger('click')
    /* O componente não conhece rota nenhuma: ele pede, a página busca. E o que
       sai é a forma canônica, não o que foi colado. */
    expect(tela.emitted('buscar')[0]).toEqual(['cnpj', 'WQ0P6GLD000108'])
  })

  it('o recado da busca aparece no campo', () => {
    const tela = mount(CamposDoFormulario, {
      props: {
        campos: [campo('cnpj', 'double', { validacao: 'cnpj' })],
        regras: [], valores: {}, formato: 'novo',
        recados: { cnpj: 'Cliente: PIETANZA INDUSTRIA' },
      },
    })
    expect(tela.find('.campo__recado').text()).toContain('PIETANZA')
  })

  /* ⚠️ O "Escolha…" esmaecido vale para OS DOIS formatos -- é correção de
     um defeito de leitura, não recurso do formato novo, e gatear um
     placeholder por formulário não faria sentido. O que é do formato novo é o
     botão Buscar. */
  it('no clássico não há botão de buscar — mas o "Escolha…" também é esmaecido', () => {
    const tela = mount(CamposDoFormulario, {
      props: {
        campos: [campo('cnpj', 'double', { validacao: 'cnpj' }),
                 campo('tipo', 'list', { opcoes: [{ value: '1', label: 'Um' }] })],
        regras: [], valores: {},
      },
    })
    expect(tela.find('.campo__buscar').exists()).toBe(false)
    expect(tela.find('option[value=""]').attributes('hidden')).toBeDefined()
  })
})

describe('os ajustes de 29/10 na aba 2 e 3', () => {
  it('🔵 o modelo esmaecido do telefone é placeholder, não valor', () => {
    const valores = {}
    const tela = mount(CamposDoFormulario, {
      props: {
        campos: [campo('telefone', 'phone', {
          validacao: 'telefone', fantasma: '(00) 123456789',
        })],
        regras: [], valores, formato: 'novo',
      },
    })
    expect(tela.find('input').attributes('placeholder')).toBe('(00) 123456789')
    /* 🚨 Modelo NÃO é valor: o campo segue vazio, e nada é enviado. */
    expect(valores.telefone).toBeUndefined()
  })

  it('o espaço e o traço do telefone entram sozinhos', async () => {
    const valores = {}
    const tela = mount(CamposDoFormulario, {
      props: {
        campos: [campo('telefone', 'phone', { validacao: 'telefone' })],
        regras: [], valores, formato: 'novo',
      },
    })
    await tela.find('input').setValue('18998116168')
    expect(tela.find('input').element.value).toBe('(18) 99811-6168')
    // ⚠️ E o que vai gravado continua só dígito.
    expect(valores.telefone).toBe('18998116168')
  })

  it('🔵 `linhas` deixa o campo mais alto, mesmo sendo `string`', () => {
    const tela = mount(CamposDoFormulario, {
      props: {
        campos: [campo('detalhe', 'string', { linhas: 6 })],
        regras: [], valores: {}, formato: 'novo',
      },
    })
    const caixa = tela.find('textarea')
    expect(caixa.exists()).toBe(true)
    expect(caixa.attributes('rows')).toBe('6')
  })

  /* 🚨 `linhas` e `fantasma` são DADO do campo, não recurso do formato novo:
     dado nulo não desenha nada. Nos outros 14 as duas colunas estão nulas, e é
     isso que mantém a tela deles igual -- não um `if` no componente. */
  it('sem `linhas` e sem `fantasma`, o campo é o de sempre', () => {
    const tela = mount(CamposDoFormulario, {
      props: {
        campos: [campo('detalhe', 'string')],
        regras: [], valores: {},
      },
    })
    expect(tela.find('textarea').exists()).toBe(false)
    expect(tela.find('input').attributes('placeholder')).toBeUndefined()
  })
})

describe('🔵 a frota do cliente, e o escape de digitar', () => {
  const placaCampo = campo('placas', 'string', {
    multiplo: true, validacao: 'placa', fonte: 'weso_placas',
  })
  const frota = [
    { placa: 'BYL2170', apelido: 'DIEGO COSTA PEGASUS', veiculo: null },
    { placa: 'CLU3E28', apelido: null, veiculo: 'DUCATO' },
  ]

  it('sem frota carregada, o campo é o repetidor de sempre', () => {
    const tela = mount(CamposDoFormulario, {
      props: { campos: [placaCampo], regras: [], valores: {}, formato: 'novo' },
    })
    expect(tela.findAll('input[type="checkbox"]')).toHaveLength(0)
    expect(tela.findAll('.linha')).toHaveLength(1)
  })

  it('com frota, marca o veículo e grava a placa', async () => {
    const valores = {}
    const tela = mount(CamposDoFormulario, {
      props: {
        campos: [placaCampo], regras: [], valores, formato: 'novo',
        sugestoes: { placas: frota },
      },
    })
    expect(tela.findAll('input[type="checkbox"]')).toHaveLength(2)
    /* ⚠️ O apelido aparece; faltando ele, o modelo entra no lugar. */
    expect(tela.text()).toContain('DIEGO COSTA PEGASUS')
    expect(tela.text()).toContain('DUCATO')

    await tela.findAll('input[type="checkbox"]')[0].setValue(true)
    expect(valores.placas).toEqual(['BYL2170'])
    await tela.findAll('input[type="checkbox"]')[1].setValue(true)
    expect(valores.placas).toEqual(['BYL2170', 'CLU3E28'])
    // Desmarcar tira só aquela.
    await tela.findAll('input[type="checkbox"]')[0].setValue(false)
    expect(valores.placas).toEqual(['CLU3E28'])
  })

  it('🔵 "Meu veículo não está na lista" abre a digitação, e a lista fica', async () => {
    const valores = {}
    const tela = mount(CamposDoFormulario, {
      props: {
        campos: [placaCampo], regras: [], valores, formato: 'novo',
        sugestoes: { placas: frota },
      },
    })
    const botao = tela.findAll('button').find(
      (b) => b.text().includes('não está na lista'))
    expect(botao).toBeTruthy()

    await botao.trigger('click')
    expect(tela.findAll('.linha')).toHaveLength(1)
    // 🚨 A lista NÃO desaparece: sugerir e digitar convivem.
    expect(tela.findAll('input[type="checkbox"]')).toHaveLength(2)

    await tela.find('.linha input').setValue('XYZ1234 reboque')
    expect(valores.placas).toEqual(['XYZ1234 reboque'])
  })

  it('🚨 marcar e desmarcar NÃO embaralha o que foi digitado', async () => {
    const valores = { placas: ['BYL2170', 'XYZ1234 reboque'] }
    const tela = mount(CamposDoFormulario, {
      props: {
        campos: [placaCampo], regras: [], valores, formato: 'novo',
        sugestoes: { placas: frota },
      },
    })
    // A digitada aparece como linha; a da frota, como marcada.
    expect(tela.findAll('.linha')).toHaveLength(1)
    expect(tela.find('.linha input').element.value).toBe('XYZ1234 reboque')

    await tela.findAll('input[type="checkbox"]')[1].setValue(true)
    expect(valores.placas).toEqual(['BYL2170', 'XYZ1234 reboque', 'CLU3E28'])
    // A linha digitada continua sendo a mesma, e no mesmo lugar.
    expect(tela.find('.linha input').element.value).toBe('XYZ1234 reboque')

    await tela.find('.linha input').setValue('XYZ1234 carreta')
    expect(valores.placas).toEqual(['BYL2170', 'XYZ1234 carreta', 'CLU3E28'])
  })
})

describe('🔵 A REGRA DA PLACA: chamado só para placa ativa na WESO', () => {
  /* 🚨 E um erro meu de método, que estes testes impedem de voltar: eu havia
     escrito que a lista "sugere, nunca restringe". Ninguém me disse isso --
     inferi de uma medição minha. A regra do negócio é dele. */
  const placaCampo = campo('placas', 'string', {
    multiplo: true, validacao: 'placa', fonte: 'weso_placas',
  })

  it('ao sair do campo, a tela pede a conferência', async () => {
    const tela = mount(CamposDoFormulario, {
      props: { campos: [placaCampo], regras: [], valores: {}, formato: 'novo' },
    })
    await tela.find('.linha input').setValue('ABC1234')
    // 🟡 Só ao SAIR: pedir a cada tecla gastaria a cota e piscaria aviso.
    expect(tela.emitted('placa')).toBeUndefined()
    await tela.find('.linha input').trigger('blur')
    expect(tela.emitted('placa')[0]).toEqual(['ABC1234'])
  })

  it('campo vazio não pede conferência', async () => {
    const tela = mount(CamposDoFormulario, {
      props: { campos: [placaCampo], regras: [], valores: {}, formato: 'novo' },
    })
    await tela.find('.linha input').trigger('blur')
    expect(tela.emitted('placa')).toBeUndefined()
  })

  it('placa ativa mostra o apelido; inativa, o que fazer', () => {
    const ativa = mount(CamposDoFormulario, {
      props: {
        campos: [placaCampo], regras: [], valores: { placas: ['BYL2170'] },
        formato: 'novo',
        placas: { BYL2170: { conferiu: true, ativa: true, apelido: 'SAVEIRO' } },
      },
    })
    expect(ativa.text()).toContain('SAVEIRO')

    const inativa = mount(CamposDoFormulario, {
      props: {
        campos: [placaCampo], regras: [], valores: { placas: ['ZZZ9999'] },
        formato: 'novo',
        placas: { ZZZ9999: { conferiu: true, ativa: false, apelido: null } },
      },
    })
    expect(inativa.text()).toContain('Sem rastreador ativo')
    expect(inativa.text()).toContain('Movisat')
  })

  it('🚨 "não deu para conferir" NÃO é "inativa"', () => {
    const tela = mount(CamposDoFormulario, {
      props: {
        campos: [placaCampo], regras: [], valores: { placas: ['BYL2170'] },
        formato: 'novo',
        placas: { BYL2170: { conferiu: false } },
      },
    })
    /* ⚠️ Falha nossa não vira acusação ao cliente: a frase diz que pode
       seguir, e o envio passa marcado (migração 081). */
    expect(tela.text()).toContain('pode seguir')
    expect(tela.text()).not.toContain('Sem rastreador ativo')
  })

  it('a placa digitada no campo de frota também é conferida', async () => {
    const tela = mount(CamposDoFormulario, {
      props: {
        campos: [placaCampo], regras: [], valores: {}, formato: 'novo',
        sugestoes: { placas: [{ placa: 'BYL2170', apelido: 'X', veiculo: null }] },
      },
    })
    const botao = tela.findAll('button').find(
      (b) => b.text().includes('não está na lista'))
    await botao.trigger('click')
    await tela.find('.linha input').setValue('AOY4C94')
    await tela.find('.linha input').trigger('blur')
    expect(tela.emitted('placa')[0]).toEqual(['AOY4C94'])
  })
})
