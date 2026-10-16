"""O teste de frontend acompanha o desenho A da ficha (15/10).

A guarda que existia ("a ficha passou a mostrar o telefone do contato") era
verdadeira as 14h e virou falsa as 15h, quando ele viu o numero repetido tres
vezes e escolheu o desenho A. Ela nao se apaga: passa a guardar o CONTRARIO,
que e a decisao nova -- o telefone uma vez so.
"""
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
ALVO = RAIZ / "frontend" / "src" / "ficha_1510.teste.js"
texto = ALVO.read_text(encoding="utf-8")

VELHO = """  it('a ficha passou a mostrar o telefone do contato', () => {
    expect(caixa).toContain('gaveta__fones')
    expect(caixa).toContain('aberta.empresa.contato.telefones')
  })
})"""

NOVO = """  it('o botão Contatos só existe havendo empresa', () => {
    /* Sem empresa o modal só teria "este número não está no cadastro", que a
       própria ficha já diz em âmbar -- botão que só sabe dar a notícia ruim. */
    expect(caixa).toMatch(
      /v-if="aberta\\.empresa && aberta\\.empresa\\.cliente && !ehTecnico"/)
  })
})

describe('desenho A da ficha — o que ele escolheu em 15/10', () => {
  /* 🔵 *"essa tela dentro da ficha esta redundante e um pouco feia"* →
     três mockups → *"Tipo A 100%"*. */

  it('o telefone do contato NÃO é mostrado de novo na lista de dados', () => {
    /* 🚨 ERA O DEFEITO QUE ELE VIU: `+5518998116168` no topo, em "Contato"
       (o nome derivado) e na linha de telefones que eu acrescentei no Bloco 6
       -- o mesmo número três vezes na mesma tela. Duas dessas três eram
       minhas, do mesmo dia. */
    expect(caixa).not.toContain('gaveta__fones')
    expect(caixa).not.toContain('aberta.empresa.contato.telefones')
  })

  it('nome derivado do telefone vira "sem nome no cadastro"', () => {
    /* Ausência de dado com cara de dado é tela que mente. */
    expect(caixa).toContain('const contatoSemNome = computed')
    expect(caixa).toContain('sem nome no cadastro')
    expect(caixa).toContain('v-else-if="contatoSemNome"')
  })

  it('e a comparação exige 10 dígitos, para não confundir nome com número', () => {
    expect(caixa).toContain('digitos.length >= 10')
  })

  it('as três consultas dividem UMA linha', () => {
    /* A gaveta é `flex-direction: column`: botão solto nela ganhava uma linha
       inteira, e eram três, numa gaveta com `max-height: 45%`. */
    expect(caixa).toContain('class="gaveta__acoes"')
    expect(caixa).toContain('.gaveta__acoes .botao { flex: 1 1 auto;')
  })

  it('a empresa é um cartão com hierarquia, e não quatro pares iguais', () => {
    expect(caixa).toContain('class="gaveta__cartao"')
    expect(caixa).toContain('class="gaveta__razao"')
    expect(caixa).toContain('class="gaveta__fantasia"')
    /* Os rótulos "Nome fantasia" e "CNPJ/CPF" saíram: o dado fala por si com
       o ícone ao lado. */
    expect(caixa).not.toContain('<dt>Nome fantasia</dt>')
    expect(caixa).not.toContain('<dt>CNPJ/CPF</dt>')
  })

  it('o e-mail quebra em vez de cortar com reticências', () => {
    /* E-mail cortado não dá para copiar, e copiar é o que se faz com ele. */
    expect(caixa).toContain('.gaveta__meta span > :last-child { overflow-wrap: anywhere;')
  })

  it('Desvincular saiu da pilha das consultas', () => {
    /* 🚨 Três botões de ler e um de APAGAR, todos iguais e na mesma pilha. */
    expect(caixa).toContain('class="gaveta__pe"')
    expect(caixa).toMatch(/gaveta__pe[\\s\\S]{0,600}@click="desvincular"/)
  })

  it('o Tipo continua na lista de dados, e não vira chip no topo', () => {
    /* ⚠️ DIVERGÊNCIA DECLARADA do mockup A: lá o Tipo era um chip no topo.
       Para quem tem `podeTrocarTipo` ele é um `<select>` -- um controle, não um
       rótulo --, e chip no topo mais select embaixo recriaria a duplicação que
       este desenho existe para matar. */
    expect(caixa).toContain('<dt>Tipo</dt>')
    expect(caixa).toContain('podeTrocarTipo')
  })
})"""

if "desenho A da ficha" in texto:
    print("ja aplicado")
else:
    assert texto.count(VELHO) == 1, f"ancora {texto.count(VELHO)}x"
    ALVO.write_text(texto.replace(VELHO, NOVO, 1), encoding="utf-8")
    print("aplicado")
