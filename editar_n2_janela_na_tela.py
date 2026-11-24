# -*- coding: utf-8 -*-
"""N2.3, lado tela: o compromisso passa a DIZER a janela, nas TRÊS telas.

🔵 ELE, 23/11: *"os agendamentos... continuam não sendo escritos nas OS"*.

🚨 A escrita estava completa (medido: start/end no ERP, técnico 14262). O que a
tela mostrava era *"usuário 14262 — compromisso 969544"*: sem nome e sem data.
Com o resumo consertado, o nome já vem; aqui entra a JANELA.

⚠️ SÃO TRÊS CÓPIAS do mesmo bloco, com indentação diferente, e as três têm de
mudar junto: `DialogoDeChamado` (o card do chamado), `PainelOperacao` e
`PainelServicoDosTecnicos`. Consertar uma só repetiria o *"nasceu duas vezes"*.
A FORMATAÇÃO não se repete: ela vem pronta do backend (`janela`).
"""
import pathlib

MARCA = "{{ a.nome || `usuário ${a.usuario_id}` }} —"
SEGUNDA = "compromisso {{ a.agendamento_id }}"

ARQUIVOS = [
    "frontend/src/componentes/DialogoDeChamado.vue",
    "frontend/src/telas/PainelOperacao.vue",
    "frontend/src/telas/PainelServicoDosTecnicos.vue",
]

for rel in ARQUIVOS:
    p = pathlib.Path(rel)
    bruto = p.read_bytes()
    crlf = b"\r\n" in bruto
    t = bruto.decode("utf-8").replace("\r\n", "\n")
    linhas = t.split("\n")

    achados = [i for i, l in enumerate(linhas) if MARCA in l]
    assert len(achados) == 1, "%s: %d ocorrencias da marca" % (rel, len(achados))
    i = achados[0]
    assert SEGUNDA in linhas[i + 1], (
        "%s: a linha seguinte nao e a do compromisso: %r" % (rel, linhas[i + 1]))

    # A indentação é a do próprio arquivo -- os três têm recuos diferentes, e
    # recuo errado num `.vue` não quebra nada e fica feio para sempre.
    recuo = linhas[i + 1][:len(linhas[i + 1]) - len(linhas[i + 1].lstrip())]

    # 🚨 A JANELA ANTES DO ID, e é decisão de leitura: a pessoa olha para saber
    # QUANDO o técnico vai, não para decorar o número do compromisso. O id
    # continua ali porque é o que se usa para conferir no ERP.
    # ⚠️ `v-if` na janela, não texto fixo: compromisso sem `agendamentoOS` é
    # caso real, e ali não há data para mostrar -- inventar seria tela que
    # mente.
    linhas[i + 1] = (
        recuo + '<template v-if="a.janela">{{ a.janela }} · </template>'
        + SEGUNDA)

    t = "\n".join(linhas)
    saida = t.replace("\n", "\r\n") if crlf else t
    p.write_bytes(saida.encode("utf-8"))
    print("  ok: %s (linha %d)" % (rel, i + 2))


# ---------------------------------------------------------------------------
# A trava de tela
# ---------------------------------------------------------------------------
q = pathlib.Path("frontend/src/os_no_card_da_aba_1911.teste.js")
bq = q.read_bytes()
crlf = b"\r\n" in bq
u = bq.decode("utf-8").replace("\r\n", "\n")

VELHO = """  it('acende o Agendamento quando há compromisso', async () => {
    estado.os = { ...A_OS, tem_agendamento: true,
                  agendamentos: [{ agendamento_id: 930447, nome: 'Franck',
                                   usuario_id: 7493 }] }
    const tela = await montar(cardDeOS())
    const abas = tela.findAll('.temas__aba')
    expect(abas[abas.length - 1].attributes('disabled')).toBeUndefined()
  })"""

NOVO = """  it('acende o Agendamento quando há compromisso', async () => {
    estado.os = { ...A_OS, tem_agendamento: true,
                  agendamentos: [{ agendamento_id: 930447, nome: 'Franck',
                                   usuario_id: 7493 }] }
    const tela = await montar(cardDeOS())
    const abas = tela.findAll('.temas__aba')
    expect(abas[abas.length - 1].attributes('disabled')).toBeUndefined()
  })

  /* 🔵 23/11, DELE: *"os agendamentos feitos por aqui no Movizap, continuam
     não sendo escritos nas OS, precisamos de um definitivo para isso!"*

     🚨 A MEDIÇÃO CONTRADISSE O SINTOMA: a escrita estava completa (ERP com
     `start 23/11 16:00` e `end 18:00`, técnico 14262). O que esta tela
     mostrava era *"usuário 14262 — compromisso 969544"* — sem nome e sem
     data. Concluir "não foi escrito" era a leitura certa do que a tela
     mostrava: tela que mente por omissão (`M12`).

     ⚠️ A janela vem PRONTA do backend (`janela`), porque o mesmo bloco é
     desenhado em três telas e formatar em três lugares é o gêmeo nascendo
     outra vez. */
  it('🔵 o compromisso diz QUEM e QUANDO, não só o número', async () => {
    estado.os = { ...A_OS, tem_agendamento: true,
                  agendamentos: [{ agendamento_id: 969544, nome: 'Franck',
                                   usuario_id: 14262,
                                   janela: '23/11/2026 16:00 às 18:00' }] }
    const tela = await montar(cardDeOS())
    const abas = tela.findAll('.temas__aba')
    await abas[abas.length - 1].trigger('click')
    const texto = tela.text()
    expect(texto).toContain('Franck')
    expect(texto).toContain('23/11/2026 16:00 às 18:00')
    /* O id continua: é por ele que se confere no ERP. */
    expect(texto).toContain('969544')
    /* 🚨 E o "usuário 14262" NÃO aparece mais: era o sintoma. */
    expect(texto).not.toContain('usuário 14262')
  })

  it('⚠️ compromisso sem janela não inventa data', async () => {
    estado.os = { ...A_OS, tem_agendamento: true,
                  agendamentos: [{ agendamento_id: 969544, nome: 'Franck',
                                   usuario_id: 14262, janela: null }] }
    const tela = await montar(cardDeOS())
    const abas = tela.findAll('.temas__aba')
    await abas[abas.length - 1].trigger('click')
    expect(tela.text()).toContain('969544')
    expect(tela.text()).not.toContain('null')
  })"""

assert VELHO in u, "NAO ACHOU o teste do Agendamento"
assert u.count(VELHO) == 1
u = u.replace(VELHO, NOVO, 1)
print("  ok: as 2 travas de tela")

saida = u.replace("\n", "\r\n") if crlf else u
q.write_bytes(saida.encode("utf-8"))
print("gravado:", q, len(saida), "bytes")
