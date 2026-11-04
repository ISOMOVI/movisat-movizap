/* O card da lista: o selo e a hora na COLUNA DA DIREITA (03/11/2026).
 *
 * 🔵 Pedido dele, com a seta desenhada numa imagem do card:
 * *"consegue puxar essas informações mais pra direita e aumentar os caracteres
 * do nome do contato"*.
 *
 * 🚨 POR QUE ESTE ARQUIVO EXISTE: a mudança é de LAYOUT, e layout não tem
 * asserção de comportamento que o jsdom veja -- ele não calcula largura nem
 * recorte. Então o que dá para prender é a ESTRUTURA: onde cada peça mora e
 * quais regras de CSS seguem de pé. Foi assim que o conserto de 14/10 (nome
 * comprido escondendo o botão "Ficha") ficou preso, e é o mesmo molde.
 *
 * ⚠️ E isto NÃO substitui ele abrir a tela: `M9`. Nenhuma das 620 verificações
 * desta suíte vê a tela, e o recorte de layout é justo o que elas não veem.
 */
import { describe, it, expect } from 'vitest'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

const fonte = readFileSync(
  fileURLToPath(new URL('./telas/CaixaDeEntrada.vue', import.meta.url)), 'utf8')

/* Só o <li> da lista: o cabeçalho da conversa aberta tem peças de nome
   parecido, e medir o arquivo inteiro confundiria os dois. */
const item = fonte.slice(
  fonte.indexOf('<li v-for="c in lista"'),
  fonte.indexOf('</ul>', fonte.indexOf('<li v-for="c in lista"')))

describe('o selo e a hora saíram da linha do nome', () => {
  it('a coluna da direita existe, e o selo e a hora estão nela', () => {
    expect(item).toContain('<div class="conversas__direita">')
    const direita = item.slice(item.indexOf('<div class="conversas__direita">'))
    expect(direita).toContain('conversa__selo')
    expect(direita).toContain('conversa__hora')
  })

  it('🚨 o topo do card NÃO tem mais selo nem hora -- é o pedido em si', () => {
    const topo = item.slice(item.indexOf('<div class="conversa__topo">'),
                            item.indexOf('<!-- ⚠️ Fui CHAMADO'))
    expect(topo).toContain('conversa__quem')
    expect(topo).not.toContain('conversa__selo')
    expect(topo).not.toContain('conversa__hora')
  })

  it('o nome ganha a linha: ele cresce e pode encolher para truncar', () => {
    expect(fonte).toContain('.conversa__topo .conversa__quem { flex: 1 1 auto; min-width: 0; }')
  })
})

describe('a coluna da direita tem largura FIXA', () => {
  /* 🚨 Sem isto o pedido não se cumpre: o botão varia de "Entrar" a
     "Ir para a aberta" (166 das 1.014 linhas em 03/11, 16,4%), e a coluna
     elástica faria o nome mudar de tamanho a cada linha. */
  it('a largura é travada', () => {
    expect(fonte).toMatch(/\.conversas__direita\s*\{[^}]*flex:\s*0 0 100px/)
  })

  it('e o rótulo comprido QUEBRA em vez de alargar a coluna', () => {
    expect(fonte).toMatch(
      /\.conversas__direita \.conversas__assumir\s*\{[^}]*white-space:\s*normal/)
  })

  it('o botão comprido continua existindo -- é ele que a largura precisa aguentar', () => {
    expect(item).toContain('Ir para a aberta')
  })
})

describe('o que a mudança NÃO podia quebrar', () => {
  /* 🚨 A trava de 14/10: a regra de reticências é presa à LISTA, nunca solta --
     solta, ela recortava o botão "Ficha" do cabeçalho da conversa. */
  it('a regra de reticências segue presa à lista', () => {
    expect(fonte).toContain('.conversa__topo .conversa__quem,')
  })

  /* 🚨 Os dois selos são de coisas diferentes (cliente × colega) e a cor é o
     que os distingue num relance. Separá-los na tela mataria a distinção. */
  it('o selo da nota viaja junto com o de mensagem', () => {
    const direita = item.slice(item.indexOf('<div class="conversas__direita">'))
    const meta = direita.slice(direita.indexOf('<div class="conversas__meta">'),
                               direita.indexOf('</div>', direita.indexOf('<div class="conversas__meta">')))
    expect(meta).toContain('conversa__selo--nota')
  })

  it('os dois selos continuam com título — ícone e número sem nome é adivinhação', () => {
    expect(item).toContain('mensagem(ns) que você ainda não viu')
    expect(item).toContain('nota(s) interna(s) que você ainda não viu')
  })

  /* ⚠️ O número da nota vem do Notificador, não da consulta da lista -- que é a
     mais quente do painel e tem ordem posicional de parâmetro. O comentário que
     explica isso se perdeu quando eu movi o bloco, e voltou. Prender o texto é
     o que impede de se perder de novo. */
  it('o porquê de a nota não sair da consulta da lista continua escrito', () => {
    expect(fonte).toContain('ordem posicional de parâmetro')
  })

  /* O card inteiro continua sendo UM botão que abre a conversa. O selo e a hora
     ficaram fora dele de propósito (botão dentro de botão é HTML inválido), e
     isso está dito no código. */
  it('o card continua sendo o botão que abre a conversa', () => {
    expect(item).toContain('class="conversa"')
    expect(item).toContain('@click="abrir(c.id)"')
  })
})
