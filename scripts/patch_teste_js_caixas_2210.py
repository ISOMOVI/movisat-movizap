"""Testes da tela para as quatro caixas -- anexados ao arquivo do e-mail.

🔵 *"enviadas devem ter seu proprio grupo, igual no Gmail"*.

🚨 O QUE SE DEFENDE AQUI E O FIM DA DUPLICACAO. "Entrada" aparecia nas abas de
caixa E na lista de marcadores, e a tela mandava os dois juntos -- era isso que
escondia 11 enviadas dentro da Lixeira. Teste que so afirmasse "a aba Enviados
existe" deixaria a duplicacao voltar sem ninguem ver.
"""
import sys

ALVO = "frontend/src/email_sumida_2210.teste.js"

NOVO = '''

// ---- as quatro caixas (22/10) --------------------------------------------

describe('Enviados é lugar, não etiqueta', () => {
  it('a aba Enviados está na fileira de caixas', async () => {
    const w = await montar()
    const abas = w.findAll('.caixas--secundaria .caixas__aba').map((n) => n.text())
    expect(abas).toEqual(['Entrada', 'Enviados', 'Arquivadas', 'Lixeira'])
  })

  it('🚨 "Entrada" e "Enviados" NÃO aparecem mais na lista de etiquetas', async () => {
    /* A duplicação era o defeito: dois controles dizendo "onde estou", e a
       tela mandando os dois ao servidor de uma vez. */
    respostas = estadoPadrao([msg()])
    respostas['/api/email/marcadores'] = {
      marcadores: [
        { id: 1, id_externo: 'INBOX', nome: 'INBOX', natureza: 'sistema', quantidade: 9 },
        { id: 2, id_externo: 'SENT', nome: 'SENT', natureza: 'sistema', quantidade: 9 },
        { id: 3, id_externo: 'STARRED', nome: 'STARRED', natureza: 'sistema', quantidade: 2 },
        { id: 4, id_externo: 'Clientes', nome: 'Clientes', natureza: 'usuario', quantidade: 5 },
      ],
    }
    const w = mount(Email)
    await assentar(w)
    const etiquetas = w.findAll('.email__marcador').map((n) => n.text())
    expect(etiquetas.join(' ')).not.toContain('Caixa de entrada')
    expect(etiquetas.join(' ')).not.toContain('Enviados')
    // e as que SÃO etiqueta continuam lá
    expect(etiquetas.join(' ')).toContain('Com estrela')
    expect(etiquetas.join(' ')).toContain('Clientes')
  })

  it('clicar numa caixa manda `caixa=` e NÃO manda etiqueta', async () => {
    /* 🚨 ERA O BUG DAS 11: ir para a Lixeira mantinha `marcador=INBOX`, e a
       Lixeira mostrava só o que tinha o rótulo da Entrada. */
    const w = await montar()
    pedidos.length = 0
    const lixeira = w.findAll('.caixas--secundaria .caixas__aba')
      .find((n) => n.text() === 'Lixeira')
    await lixeira.trigger('click')
    await assentar(w)
    const lista = pedidos.filter((r) => r.startsWith('/api/email/mensagens?'))
    expect(lista.length).toBeGreaterThan(0)
    expect(lista[lista.length - 1]).toContain('caixa=lixeira')
    expect(lista[lista.length - 1]).toContain('marcador=&')
  })

  it('a barra diz o LUGAR, não a etiqueta', async () => {
    /* 🚨 Com o marcador começando em 'INBOX', esta linha escrevia "Caixa de
       entrada" mesmo com a Lixeira aberta -- `M12`, e passou despercebido
       porque os dois controles concordavam por acidente. */
    const w = await montar()
    const lixeira = w.findAll('.caixas--secundaria .caixas__aba')
      .find((n) => n.text() === 'Lixeira')
    await lixeira.trigger('click')
    await assentar(w)
    expect(w.find('.email__barra').text()).toContain('Lixeira')
    expect(w.find('.email__barra').text()).not.toContain('Caixa de entrada')
  })
})
'''

# O duplo de `api.get` precisa guardar as rotas pedidas, para o teste poder
# afirmar o que a tela MANDOU -- e nao so o que ela desenhou.
GET_ANTES = '''    get: (rota) => {
      const chave = Object.keys(respostas)
        .filter((k) => rota.startsWith(k))
        .sort((a, b) => b.length - a.length)[0]
      return Promise.resolve(chave ? respostas[chave] : {})
    },'''

GET_DEPOIS = '''    get: (rota) => {
      /* 🚨 GUARDA A ROTA PEDIDA. Metade do defeito de 22/10 não estava no que
         a tela desenhava, e sim no que ela MANDAVA: `caixa=lixeira` junto com
         `marcador=INBOX`. Sem registrar o pedido, nenhum teste de DOM veria
         isso -- a lista só vinha vazia, e vazio parece "não tem mensagem". */
      pedidos.push(rota)
      const chave = Object.keys(respostas)
        .filter((k) => rota.startsWith(k))
        .sort((a, b) => b.length - a.length)[0]
      return Promise.resolve(chave ? respostas[chave] : {})
    },'''

DECL_ANTES = "let respostas\n"
DECL_DEPOIS = "let respostas\nconst pedidos = []\n"

BEFORE_ANTES = "beforeEach(() => { respostas = estadoPadrao([msg()]) })"
BEFORE_DEPOIS = ("beforeEach(() => { respostas = estadoPadrao([msg()]); "
                 "pedidos.length = 0 })")


def main() -> int:
    texto = open(ALVO, encoding="utf-8").read()
    if "const pedidos" in texto:
        raise SystemExit("ja aplicado")
    for antes, depois, rotulo in (
        (DECL_ANTES, DECL_DEPOIS, "a lista de pedidos"),
        (GET_ANTES, GET_DEPOIS, "o duplo registra a rota"),
        (BEFORE_ANTES, BEFORE_DEPOIS, "limpar os pedidos entre testes"),
    ):
        n = texto.count(antes)
        if n != 1:
            raise SystemExit(f"FALHOU {rotulo}: {n} ocorrencias")
        texto = texto.replace(antes, depois, 1)
        print(f"ok  {rotulo}")
    open(ALVO + ".bak_2026-10-22_caixas", "w", encoding="utf-8").write(
        open(ALVO, encoding="utf-8").read())
    open(ALVO, "w", encoding="utf-8").write(texto.rstrip("\n") + NOVO)
    print("ok  testes das quatro caixas anexados")
    return 0


if __name__ == "__main__":
    sys.exit(main())
