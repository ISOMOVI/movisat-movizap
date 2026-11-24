# -*- coding: utf-8 -*-
"""Limpa o [Vue warn] do teste novo da 2.3: faltava o stub do RouterLink."""
import pathlib

q = pathlib.Path("frontend/src/aba2_card_aberto_2311.teste.js")
bruto = q.read_bytes()
CRLF = b"\r\n" in bruto
u = bruto.decode("utf-8").replace("\r\n", "\n")

VELHO = """    const tela = mount(PainelServicoDosTecnicos, { attachTo: document.body })"""
NOVO = """    const tela = mount(PainelServicoDosTecnicos, {
      attachTo: document.body,
      /* ⚠️ O MESMO stub do `abrirATela`: sem ele o Vue avisa
         "Failed to resolve component: RouterLink" e a suite passa verde com
         ruido -- divida para quem vier depois. */
      global: { stubs: { RouterLink: { props: ['to'],
                                       template: '<a :href="to"><slot /></a>' } } },
    })"""

assert VELHO in u, "NAO ACHOU o mount sem stub"
assert u.count(VELHO) == 1
u = u.replace(VELHO, NOVO, 1)
print("  ok: o stub do RouterLink no teste novo")

saida = u.replace("\n", "\r\n") if CRLF else u
q.write_bytes(saida.encode("utf-8"))
print("gravado:", q, len(saida), "bytes")
