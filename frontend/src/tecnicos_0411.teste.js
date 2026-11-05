/**
 * @vitest-environment jsdom
 *
 * Técnicos (TEC_1.1, 04/11): a LISTA e a FICHA, que são duas telas.
 *
 * 🚨 SUÍTE VERDE NÃO PROVA QUE A TELA ABRE (`M9`). O que estes testes provam, e
 * nenhum teste de backend alcança:
 *
 *   1. a lista NÃO desenha a ficha — ele recusou o empilhamento (*"cria uma
 *      pagina em cima da atual. fica feio"*), e o botão agora leva para outra
 *      tela e chama **Ficha**;
 *   2. a ficha tem **seta de voltar**, e ela volta em vez de recarregar;
 *   3. quem não tem a `TEC_1.2` não vê botão de gravar, e a tela DIZ o que
 *      acontece — sem citar quem decidiu;
 *   4. "não oferece" é texto e **zero continua zero**;
 *   5. o dinheiro é desenhado como VEIO, e `199,90` volta como `19990`;
 *   6. o bloco do Harmonit saiu: no lugar há o **acesso**, estático, e falha da
 *      ponte não é lida como "sem acesso";
 *   7. o CEP tem as **três** respostas separadas.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'

const { sessao, navegacao } = vi.hoisted(() => ({
  sessao: { nome: 'Fulano de Tal', telas: [], owner: false },
  /* ⚠️ `vi.hoisted` porque `vi.mock` é içado para o topo: um `const` normal
     estoura com "Cannot access before initialization", e o erro aparece
     apontando para a primeira linha do .vue, longe da causa. */
  navegacao: { empurrados: [], voltou: 0, params: { contatoId: '101' }, query: {} },
}))

let respostas
let gets
let puts
let falhas

vi.mock('./api/cliente.js', () => ({
  api: {
    get: (rota) => {
      gets.push(rota)
      if (falhas.some((f) => rota.startsWith(f))) return Promise.reject(new Error('503'))
      const chave = Object.keys(respostas)
        .filter((k) => rota.startsWith(k))
        .sort((a, b) => b.length - a.length)[0]
      return Promise.resolve(chave ? respostas[chave] : {})
    },
    post: (rota, corpo) => { puts.push([rota, corpo]); return Promise.resolve(respostas['/api/tecnicos/101'] || {}) },
    put: (rota, corpo) => { puts.push([rota, corpo]); return Promise.resolve({}) },
    del: () => Promise.resolve({}),
  },
  pedirBlob: () => Promise.resolve(new Blob([''])),
  definirToken: () => {},
  temToken: () => true,
  quandoPerderSessao: () => {},
  ErroDeApi: class ErroDeApi extends Error {},
}))

vi.mock('vue-router', () => ({
  useRoute: () => ({ params: navegacao.params, query: navegacao.query }),
  useRouter: () => ({
    push: (destino) => navegacao.empurrados.push(destino),
    back: () => { navegacao.voltou += 1 },
    replace: () => {},
  }),
  RouterLink: { template: '<a><slot /></a>' },
}))

vi.mock('./estado/sessao.js', () => ({ sessao, sair: () => {} }))

import Tecnicos from './telas/Tecnicos.vue'
import FichaDoTecnico from './telas/FichaDoTecnico.vue'

const LISTA = {
  total: 2, pagina: 1, paginas: 1, por_pagina: 50, sem_ficha: 1,
  busca: { tipo: 'vazio' },
  itens: [
    {
      contato_id: 101, nome: '+5518999990001', ativo: true,
      harmonit_tecnico_id: 47, harmonit_tecnico_nome: 'Caio da Silva',
      telefone: '+5518999990001', tem_ficha: true, estado: 'credenciado',
      nome_fantasia: 'Rastreadores Prudente', razao_social: null,
      cnpj: '12345678000195', cidade: 'Presidente Prudente', uf: 'SP',
      km_valor_centavos: 150, km_valor_texto: '1,50',
      servicos_com_preco: 2, atualizado_em: '2026-11-04T09:00:00-03:00',
    },
    {
      contato_id: 102, nome: 'Adão Oliveira', ativo: true,
      harmonit_tecnico_id: null, harmonit_tecnico_nome: null,
      telefone: null, tem_ficha: false, estado: null,
      nome_fantasia: null, razao_social: null, cnpj: null,
      cidade: null, uf: null, km_valor_centavos: null, km_valor_texto: null,
      servicos_com_preco: 0, atualizado_em: null,
    },
  ],
}

const FICHA = {
  contato: {
    contato_id: 101, id: 101, nome: '+5518999990001', relacao: 'tecnico',
    ativo: true, harmonit_tecnico_id: 47, harmonit_tecnico_nome: 'Caio da Silva',
    harmonit_vinculo_origem: 'manual', telefones: [], papeis: [],
  },
  ficha: {
    contato_id: 101, estado: 'credenciado', nome_fantasia: 'Rastreadores Prudente',
    cnpj: '12345678000195', cidade: 'Presidente Prudente', uf: 'SP',
    logradouro: 'Rua Teste', numero: '100', bairro: 'Centro', cep: '19010000',
    complemento: null, razao_social: null, telefone_fixo: null, email_geral: null,
    responsavel_nome: null, responsavel_sobrenome: null, cpf: null,
    responsavel_celular: null, responsavel_email: null,
    pagamento_forma: 'pix', pagamento_dados: 'chave: 18999990001',
    ponto_fixo: null, vai_ao_cliente: true, area_cobertura: 'até 50 km',
    cobra_deslocamento: true, km_valor_centavos: 150, km_valor_texto: '1,50',
    observacao: null, solicitacao_id: null,
  },
  precos: [
    { servico_id: 1, nome: 'Instalação', ordem: 1, custo_centavos: 18000, custo_texto: '180,00' },
    { servico_id: 2, nome: 'Retirada', ordem: 2, custo_centavos: 0, custo_texto: '0,00' },
    { servico_id: 5, nome: 'Substituição Retirada', ordem: 5, custo_centavos: null, custo_texto: null },
    { servico_id: 6, nome: 'Substituição Instalação', ordem: 6, custo_centavos: null, custo_texto: null },
  ],
  solicitacao: null,
}

const ACESSO = {
  harmonit_tecnico_id: 47, harmonit_tecnico_nome: 'Caio da Silva',
  harmonit_vinculo_origem: 'manual', email: '18999990001@movisat.com.br',
}

function montarLista() {
  return mount(Tecnicos, { global: { stubs: { AjudaDaTela: true } } })
}

function montarFicha() {
  return mount(FichaDoTecnico, { global: { stubs: { AjudaDaTela: true } } })
}

async function assentar(tela) {
  for (let i = 0; i < 8; i += 1) await tela.vm.$nextTick()
}

beforeEach(() => {
  gets = []
  puts = []
  falhas = []
  sessao.telas = []
  sessao.owner = false
  navegacao.empurrados = []
  navegacao.voltou = 0
  navegacao.params = { contatoId: '101' }
  navegacao.query = {}
  respostas = {
    '/api/tecnicos?': LISTA,
    '/api/tecnicos/servicos': { servicos: [] },
    '/api/tecnicos/candidatos': { formulario: { codigo: 'CREDENCIAMENTO' }, itens: [] },
    '/api/tecnicos/101': FICHA,
    '/api/contatos/101/tecnico-harmonit': ACESSO,
    '/api/cep/19010000': {
      achado: true, logradouro: 'Rua do CEP', bairro: 'Jardim',
      cidade: 'Presidente Prudente', uf: 'SP',
    },
  }
  window.history.pushState({}, '', '/tecnicos/ficha/101')
})

describe('a lista', () => {
  it('abre e mostra os dois, com ficha e sem ficha', async () => {
    const tela = montarLista()
    await assentar(tela)
    const texto = tela.text()
    expect(texto).toContain('Rastreadores Prudente')
    expect(texto).toContain('Adão Oliveira')
    expect(texto).toContain('sem ficha')
  })

  it('🔵 o botão chama FICHA, e não "abrir"', async () => {
    const tela = montarLista()
    await assentar(tela)
    const rotulos = tela.findAll('button').map((b) => b.text())
    expect(rotulos.filter((r) => r === 'Ficha').length).toBe(2)
    expect(rotulos).not.toContain('Abrir')
  })

  it('🚨 a lista NÃO desenha a ficha: ela NAVEGA', async () => {
    const tela = montarLista()
    await assentar(tela)
    await tela.findAll('button').find((b) => b.text() === 'Ficha').trigger('click')
    await assentar(tela)
    /* O empilhamento que ele recusou morreria aqui: nenhum bloco da ficha
       aparece nesta tela, e o destino é outra rota. */
    expect(tela.text()).not.toContain('Tabela de preço')
    expect(tela.text()).not.toContain('Endereço fixo')
    expect(navegacao.empurrados).toEqual([
      { path: '/tecnicos/ficha/101', query: {} },
    ])
  })

  it('o credenciamento recebido leva a solicitação na query', async () => {
    sessao.telas = [{ codigo: 'TEC_1.2' }]
    respostas['/api/tecnicos/candidatos'] = {
      formulario: { codigo: 'CREDENCIAMENTO' },
      itens: [{
        id: 9001, criada_em: '2026-11-04T08:00:00-03:00', contato_id: 102,
        valores: {}, resumo: { empresa: 'Zz Candidata Ltda', cnpj: '9', cidade: 'X' },
      }],
    }
    const tela = montarLista()
    await assentar(tela)
    await tela.findAll('button').find((b) => b.text() === 'Conferir e credenciar')
      .trigger('click')
    await assentar(tela)
    expect(navegacao.empurrados).toEqual([
      { path: '/tecnicos/ficha/102', query: { solicitacao: '9001' } },
    ])
    expect(puts.length).toBe(0)       // conferir não grava
  })

  it('🚨 sem a chave, não há botão de criar — e a tela diz o que acontece',
     async () => {
    const tela = montarLista()
    await assentar(tela)
    expect(tela.findAll('button').map((b) => b.text())).not.toContain('Novo técnico')
    const texto = tela.text()
    expect(texto).toContain('não é possível por aqui')
    expect(texto.toLowerCase()).not.toContain('owner')
    expect(texto.toLowerCase()).not.toContain('admin')
  })

  it('diz quantos ainda não têm ficha', async () => {
    const tela = montarLista()
    await assentar(tela)
    expect(tela.text()).toContain('ainda sem ficha')
  })
})

describe('a ficha, em tela própria', () => {
  it('🔵 tem seta de voltar, e ela VOLTA', async () => {
    const tela = montarFicha()
    await assentar(tela)
    const voltar = tela.findAll('button').find((b) => b.text().includes('Voltar'))
    expect(voltar).toBeTruthy()
    await voltar.trigger('click')
    expect(navegacao.voltou).toBe(1)
    expect(navegacao.empurrados.length).toBe(0)
  })

  it('abre pelo id da rota e mostra os blocos', async () => {
    const tela = montarFicha()
    await assentar(tela)
    const texto = tela.text()
    expect(gets).toContain('/api/tecnicos/101')
    for (const bloco of ['Empresa', 'Responsável', 'Endereço fixo',
                         'Dados de pagamento', 'Tabela de preço', 'Deslocamento',
                         'Acesso ao Harmonit', 'Observação']) {
      expect(texto).toContain(bloco)
    }
  })

  it('🚨 o bloco "Técnico no Harmonit" SAIU', async () => {
    const tela = montarFicha()
    await assentar(tela)
    /* Ele disse que não tinha uso dentro da ficha. O que ficou é o acesso. */
    expect(tela.text()).not.toContain('Técnico no Harmonit')
    expect(tela.text()).not.toContain('Procurar no cadastro do Harmonit')
  })

  it('🔵 o acesso mostra o e-mail, estático, e diz que não guarda senha',
     async () => {
    const tela = montarFicha()
    await assentar(tela)
    const texto = tela.text()
    expect(texto).toContain('E-mail de acesso')
    expect(texto).toContain('18999990001@movisat.com.br')
    expect(texto).toContain('A senha não fica guardada aqui')
    /* Nenhum campo editável no bloco: é leitura. */
    expect(tela.findAll('input[disabled]').length).toBeGreaterThan(0)
  })

  it('⚠️ ponte fora do ar NÃO é lido como "sem acesso"', async () => {
    falhas = ['/api/contatos/101/tecnico-harmonit']
    const tela = montarFicha()
    await assentar(tela)
    expect(tela.text()).toContain('não quer dizer que ele esteja sem acesso')
  })

  it('o pagamento vem pela lista, com as três formas dele', async () => {
    const tela = montarFicha()
    await assentar(tela)
    const opcoes = tela.findAll('option').map((o) => o.text())
    expect(opcoes).toContain('PIX')
    expect(opcoes).toContain('TED / depósito em conta')
    expect(opcoes).toContain('Boleto')
    const area = tela.findAll('textarea').map((t) => t.element.value)
    expect(area).toContain('chave: 18999990001')
  })

  it('🔵 "Preenche OS" está junto das perguntas do deslocamento', async () => {
    const tela = montarFicha()
    await assentar(tela)
    expect(tela.text()).toContain('Preenche OS')
    /* As quatro perguntas de sim/não vivem na mesma lista, fora da grade dos
       campos de texto — foi a mistura das duas que quebrou o layout. */
    const perguntas = tela.findAll('.perguntas .pergunta')
    expect(perguntas.length).toBe(4)
    expect(perguntas[3].text()).toContain('Preenche OS')
  })

  it('🚨 "não oferece" é TEXTO, e 0,00 continua zero', async () => {
    const tela = montarFicha()
    await assentar(tela)
    const texto = tela.text()
    expect(texto).toContain('não oferece')
    expect(texto).toContain('0,00')
    expect(texto).toContain('180,00')
    expect(texto).not.toContain('18000')
  })

  it('🚨 salvar manda centavos, e a vírgula não vira outro número', async () => {
    sessao.telas = [{ codigo: 'TEC_1.2' }]
    const tela = montarFicha()
    await assentar(tela)
    const campo = tela.findAll('input').find((i) => i.element.value === '180,00')
    await campo.setValue('199,90')
    await tela.findAll('button').find((b) => b.text() === 'Salvar a ficha')
      .trigger('click')
    await assentar(tela)
    const chamada = puts.find(([rota]) => rota.endsWith('/precos'))
    expect(chamada[1].precos[1]).toBe(19990)
    expect(chamada[1].precos[2]).toBe(0)        // zero continua zero
    expect(chamada[1].precos[5]).toBe(null)     // vazio = não oferece
  })

  it('⚠️ valor impossível não manda NADA — meia ficha salva é pior', async () => {
    sessao.telas = [{ codigo: 'TEC_1.2' }]
    const tela = montarFicha()
    await assentar(tela)
    const campo = tela.findAll('input').find((i) => i.element.value === '180,00')
    await campo.setValue('cento e oitenta')
    await tela.findAll('button').find((b) => b.text() === 'Salvar a ficha')
      .trigger('click')
    await assentar(tela)
    expect(puts.length).toBe(0)
    expect(tela.text()).toContain('não é um número')
  })

  it('🔵 o CEP preenche rua, bairro, cidade e UF — e nunca o número', async () => {
    sessao.telas = [{ codigo: 'TEC_1.2' }]
    const tela = montarFicha()
    await assentar(tela)
    const cep = tela.findAll('input').find((i) => i.element.value === '19010000')
    await cep.trigger('blur')
    await assentar(tela)
    expect(gets).toContain('/api/cep/19010000')
    const valores = tela.findAll('input').map((i) => i.element.value)
    expect(valores).toContain('Rua do CEP')
    expect(valores).toContain('Jardim')
    /* O número continua o que estava: o ViaCEP não sabe o número. */
    expect(valores).toContain('100')
  })

  it('🚨 as TRÊS respostas do CEP são distinguíveis', async () => {
    sessao.telas = [{ codigo: 'TEC_1.2' }]
    respostas['/api/cep/19010000'] = { achado: false, cep: '19010000' }
    let tela = montarFicha()
    await assentar(tela)
    await tela.findAll('input').find((i) => i.element.value === '19010000')
      .trigger('blur')
    await assentar(tela)
    expect(tela.text()).toContain('este CEP não existe')

    falhas = ['/api/cep/']
    tela = montarFicha()
    await assentar(tela)
    await tela.findAll('input').find((i) => i.element.value === '19010000')
      .trigger('blur')
    await assentar(tela)
    expect(tela.text()).toContain('não deu para conferir agora')
  })

  it('sem a chave, a ficha abre e os campos ficam travados', async () => {
    const tela = montarFicha()
    await assentar(tela)
    expect(tela.text()).toContain('aberta para consulta')
    expect(tela.findAll('button').map((b) => b.text()))
      .not.toContain('Salvar a ficha')
    const livres = tela.findAll('input').filter(
      (i) => i.attributes('disabled') === undefined)
    expect(livres.length).toBe(0)
  })

  it('já credenciado não oferece credenciar de novo', async () => {
    sessao.telas = [{ codigo: 'TEC_1.2' }]
    const tela = montarFicha()
    await assentar(tela)
    const rotulos = tela.findAll('button').map((b) => b.text())
    expect(rotulos).toContain('Recusar')
    expect(rotulos).not.toContain('Credenciar')
  })

  it('a solicitação na query preenche a ficha sem gravar', async () => {
    sessao.telas = [{ codigo: 'TEC_1.2' }]
    navegacao.query = { solicitacao: '9001' }
    respostas['/api/tecnicos/da-solicitacao/9001'] = {
      solicitacao_id: 9001, contato_id: 101,
      sugestao: { nome_fantasia: 'Zz Vinda Do Formulario', pagamento_forma: 'ted' },
      precos_respondidos: { 'Remoção': '90' },
      avisos: ['O endereço veio como uma linha só; separe número, bairro e complemento antes de credenciar.'],
    }
    const tela = montarFicha()
    await assentar(tela)
    expect(puts.length).toBe(0)
    const texto = tela.text()
    expect(texto).toContain('Nada foi gravado')
    expect(texto).toContain('Remoção')
    const valores = tela.findAll('input').map((i) => i.element.value)
    expect(valores).toContain('Zz Vinda Do Formulario')
  })
})
