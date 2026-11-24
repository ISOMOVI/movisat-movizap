# -*- coding: utf-8 -*-
"""Tarefa 2.4, trava de tela: o gesto de excluir o card inteiro."""
import pathlib

q = pathlib.Path("frontend/src/aba2_card_aberto_2311.teste.js")
bq = q.read_bytes()
CRLF = b"\r\n" in bq
u = bq.decode("utf-8").replace("\r\n", "\n")

VELHO = """  it('⚠️ 2.3: na coluna 1 NÃO há Remover — o item já está lá', async () => {"""

NOVO = """  /* ========================================================================
     TAREFA 2.4 — 🔵 *"Excluir o card inteiro devolvendo tudo à coluna 1, com
     justificativa única"*.
     ======================================================================== */
  it('🔵 2.4: excluir o card manda o LOTE e a justificativa única',
     async () => {
    const tela = await abrirATela()
    const card = tela.findAll('article.card')
      .find((a) => a.text().includes('lote 7'))
    await card.find('button.card__abrir').trigger('click')
    await flushPromises()
    const excluir = dialogo(tela).findAll('button')
      .find((b) => b.text() === 'Excluir o card')
    expect(excluir, 'o card do lote tem de ter Excluir o card').toBeTruthy()
    await excluir.trigger('click')
    await flushPromises()
    const just = tela.findAll('.modal')
      .find((m) => m.text().includes('Excluir o card inteiro?'))
    expect(just, 'o diálogo da justificativa única tem de abrir').toBeTruthy()
    /* 🚨 O NÚMERO À VISTA: "todos os itens" sem dizer quantos faria a pessoa
       decidir no escuro. */
    expect(just.text()).toContain('1 item(ns)')
    await just.find('input.campo').setValue('zz lote do técnico errado')
    await flushPromises()
    await just.findAll('button').find((b) => b.text() === 'Excluir o card')
      .trigger('click')
    await flushPromises()
    const pedido = estado.postado.find((p) => p[0].includes('devolver-lote'))
    expect(pedido, 'o POST de devolver-lote não saiu').toBeTruthy()
    expect(pedido[1]).toEqual({ lote_id: 7,
                                justificativa: 'zz lote do técnico errado' })
  })

  it('⚠️ 2.4: na coluna 1 não há card de lote para excluir', async () => {
    const tela = await abrirATela()
    const d = await abrirOCard(tela, 'Franck')
    expect(d.findAll('button').filter((b) => b.text() === 'Excluir o card'))
      .toHaveLength(0)
  })

  it('⚠️ 2.3: na coluna 1 NÃO há Remover — o item já está lá', async () => {"""

assert VELHO in u and u.count(VELHO) == 1
u = u.replace(VELHO, NOVO, 1)
print("  ok: as 2 travas de tela da 2.4")

saida = u.replace("\n", "\r\n") if CRLF else u
q.write_bytes(saida.encode("utf-8"))
print("gravado:", q, len(saida), "bytes")
