# -*- coding: utf-8 -*-
"""Tarefa 2.3, as travas: remover por item nas colunas 3, 4 e 5."""
import pathlib

q = pathlib.Path("frontend/src/aba2_card_aberto_2311.teste.js")
bq = q.read_bytes()
CRLF = b"\r\n" in bq
u = bq.decode("utf-8").replace("\r\n", "\n")

VELHO = """    /* ⚠️ Nas colunas 2 a 5 NÃO há filtro de período: o lote já foi fechado. */
    expect(d.findAll('input[type="date"]')).toHaveLength(0)
  })
})"""

NOVO = """    /* ⚠️ Nas colunas 2 a 5 NÃO há filtro de período: o lote já foi fechado. */
    expect(d.findAll('input[type="date"]')).toHaveLength(0)
  })

  /* ========================================================================
     TAREFA 2.3 — 🔵 *"é possível clicar em remover, onde o item de pagamento
     será removido e devolvido ao card na coluna de Movimentação abrindo um
     campo de justificativa"*.

     📏 MEDIDO EM 23/11: a rota `/devolver` existia nos dois lados e o serviço
     já aceitava de qualquer coluna que não a 1 — e o botão existia SÓ dentro
     do diálogo de conferência, que abre da coluna 2. Nas colunas 3, 4 e 5 não
     havia como remover um item.
     ======================================================================== */
  it('🔵 2.3: o item do lote tem Remover, e ele abre a justificativa',
     async () => {
    const tela = await abrirATela()
    const card = tela.findAll('article.card')
      .find((a) => a.text().includes('lote 7'))
    await card.find('button.card__abrir').trigger('click')
    await flushPromises()
    const d = dialogo(tela)
    const remover = d.findAll('button').find((b) => b.text() === 'Remover')
    expect(remover, 'o item da Validação tem de ter Remover').toBeTruthy()
    await remover.trigger('click')
    await flushPromises()
    /* 🚨 O MESMO diálogo de justificativa da conferência, não um segundo. */
    const just = tela.findAll('.modal')
      .find((m) => m.text().includes('Por que está removendo?'))
    expect(just, 'o campo de justificativa tem de abrir').toBeTruthy()
    expect(just.text()).toContain('volta para a Movimentação em laranja')
    /* ⚠️ E sem justificativa o botão do diálogo fica travado: devolver calado
       deixaria o artefato laranja e ninguém saberia por quê. */
    const confirmar = just.findAll('button').find((b) => b.text() === 'Remover')
    expect(confirmar.attributes('disabled')).toBeDefined()
    await just.find('input.campo').setValue('zz OS voltou para agendar')
    await flushPromises()
    expect(just.findAll('button').find((b) => b.text() === 'Remover')
      .attributes('disabled')).toBeUndefined()
  })

  it('⚠️ 2.3: na coluna 1 NÃO há Remover — o item já está lá', async () => {
    const tela = await abrirATela()
    const d = await abrirOCard(tela, 'Franck')
    expect(d.findAll('button').filter((b) => b.text() === 'Remover'))
      .toHaveLength(0)
  })

  /* 🚨 A CONSEQUÊNCIA, e é o que a tela tem de dizer: na coluna 4 o arquivo do
     Procfy já foi montado com o item dentro, e na 5 já foi enviado. Mesma
     frase das outras colunas seria a tela escondendo o que muda (`M12`). */
  it('🚨 2.3: remover da Procfy avisa que o arquivo já foi montado',
     async () => {
    const q = quadro()
    q.colunas[3].total = 1
    q.colunas[3].cards = [{ tecnico_id: 55, tecnico_nome: 'Franck',
                            lote_id: 9, pode_preparar: true,
                            artefatos: [artefato(301, 17124,
                                                 '16/11/2026 15:35:00')] }]
    estado.quadro = q
    const tela = mount(PainelServicoDosTecnicos, { attachTo: document.body })
    await flushPromises()
    await flushPromises()
    const card = tela.findAll('article.card')
      .find((a) => a.text().includes('lote 9'))
    await card.find('button.card__abrir').trigger('click')
    await flushPromises()
    await dialogo(tela).findAll('button')
      .find((b) => b.text() === 'Remover').trigger('click')
    await flushPromises()
    const just = tela.findAll('.modal')
      .find((m) => m.text().includes('Por que está removendo?'))
    expect(just.text()).toContain('arquivo deste lote já foi montado')
  })
})"""

assert VELHO in u, "NAO ACHOU o fim do describe do lote"
assert u.count(VELHO) == 1
u = u.replace(VELHO, NOVO, 1)
print("  ok: as 3 travas da 2.3")

saida = u.replace("\n", "\r\n") if CRLF else u
q.write_bytes(saida.encode("utf-8"))
print("gravado:", q, len(saida), "bytes")
