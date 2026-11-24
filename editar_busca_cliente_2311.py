# -*- coding: utf-8 -*-
"""23/11 — o botão *Buscar* do CNPJ deixa de ser regra da tela e passa a ser
dado do formulário (`formulario.busca_cliente`, migração 118).

🔵 Decisão dele, 23/11: **tirar onde não há base**.

🚨 ANTES: `temBusca = ehNovo && campo.validacao === 'cnpj'`. Como
`FORMATO_NOVO = None` põe todos em `novo`, TODO formulário com CNPJ ganhava o
botão -- inclusive os de parceiro técnico, fornecedor e teste gratuito, onde o
`cliente_por_documento` varre a tabela `cliente` e por definição não acha nada.

⚠️ Toca QUATRO arquivos e os quatro andam juntos: backend (serve a coluna),
componente (o contrato do prop), página pública (passa o dado) e a suíte.
"""
import pathlib

ALVOS = {}


def abrir(rel):
    p = pathlib.Path(rel)
    bruto = p.read_bytes()
    ALVOS[rel] = {"p": p, "crlf": b"\r\n" in bruto,
                  "t": bruto.decode("utf-8").replace("\r\n", "\n")}
    return rel


def troca(rel, velho, novo, rotulo):
    d = ALVOS[rel]
    assert velho in d["t"], "NAO ACHOU (%s)" % rotulo
    assert d["t"].count(velho) == 1, "AMBIGUO %dx (%s)" % (
        d["t"].count(velho), rotulo)
    d["t"] = d["t"].replace(velho, novo, 1)
    print("  ok:", rotulo)


# ===========================================================================
# 1. BACKEND — a coluna existe, é escrita pela carga e sai na definição
# ===========================================================================
BK = abrir("movizap/formularios.py")

# 1a. A definição que a internet lê.
troca(BK,
      '''                  formato, etapas
             FROM formulario WHERE slug = %s''',
      '''                  formato, etapas, busca_cliente
             FROM formulario WHERE slug = %s''',
      "1a. definicao() devolve busca_cliente")

# 1b. A assinatura.
troca(BK,
      '''                     titulo: str | None = None, painel: str | None = None,''',
      '''                     titulo: str | None = None, painel: str | None = None,
                     busca_cliente: bool = False,''',
      "1b. gravar_definicao recebe busca_cliente")

# 1c. As colunas do INSERT.
troca(BK,
      '''                                   formato, etapas)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)''',
      '''                                   formato, etapas, busca_cliente)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)''',
      "1c. a coluna entra no INSERT")

# 1d. E no UPDATE do conflito -- REESCRITO, como o painel e o formato.
troca(BK,
      '''                  formato = EXCLUDED.formato, etapas = EXCLUDED.etapas,''',
      '''                  formato = EXCLUDED.formato, etapas = EXCLUDED.etapas,
                  -- 🚨 REESCRITO A CADA CARGA, pela mesma razão do `painel`:
                  -- quem procura cliente é decisão dele e vive no
                  -- `scripts/carregar_formularios.py` (`BUSCA_CLIENTE`).
                  -- Deixar de fora faria a lista divergir do banco em
                  -- silêncio, que é a bomba de 11/11 outra vez.
                  busca_cliente = EXCLUDED.busca_cliente,''',
      "1d. a coluna e reescrita no ON CONFLICT")

# 1e. O valor, no lugar certo da tupla.
troca(BK,
      '''         formato,
         json.dumps(etapas, ensure_ascii=False) if etapas else None))''',
      '''         formato,
         json.dumps(etapas, ensure_ascii=False) if etapas else None,
         bool(busca_cliente)))''',
      "1e. o valor vai no lugar certo da tupla")


# ===========================================================================
# 2. O COMPONENTE — o botão passa a depender de dado, e nasce DESLIGADO
# ===========================================================================
CP = abrir("frontend/src/componentes/CamposDoFormulario.vue")

troca(CP,
      """  formato: { type: String, default: 'classico' },""",
      """  formato: { type: String, default: 'classico' },
  // 🔵 23/11: o botão *Buscar* do CNPJ só onde há base para procurar.
  // ⚠️ `false` POR PADRÃO, de propósito: quem não disser que procura cliente
  // não oferece busca. Oferecer uma busca que nunca acha é pior que não
  // oferecer -- quem vem do `pagamento-tecnicos` clicava e lia "não achou".
  // Quem manda é o banco (`formulario.busca_cliente`, migração 118).
  buscaCliente: { type: Boolean, default: false },""",
      "2a. o prop buscaCliente")

troca(CP,
      """function temBusca(campo) {
  return ehNovo.value && campo.validacao === 'cnpj'
}""",
      """function temBusca(campo) {
  return ehNovo.value && campo.validacao === 'cnpj' && props.buscaCliente
}""",
      "2b. temBusca consulta o dado")

# E o comentário acima da função deixa de dizer só metade da regra.
troca(CP,
      """/* 🔵 O botão *Buscar* do CNPJ -- pedido dele, 29/10. Só no CNPJ: o CPF não tem
   para onde preencher (o nome da pessoa é uma caixa livre, e dividir nome no
   palpite erra sobrenome composto). */""",
      """/* 🔵 O botão *Buscar* do CNPJ -- pedido dele, 29/10. Só no CNPJ: o CPF não tem
   para onde preencher (o nome da pessoa é uma caixa livre, e dividir nome no
   palpite erra sobrenome composto).

   🚨 E SÓ ONDE HÁ BASE PARA PROCURAR (🔵 dele, 23/11). Esta função dizia
   `ehNovo && validacao === 'cnpj'` e isso era regra fixa demais: desde 11/11
   os 16 estão em `novo`, então todo formulário com CNPJ ganhou o botão. O
   `cliente_por_documento` varre a tabela `cliente` -- os clientes NOSSOS --,
   e parceiro técnico, fornecedor ou interessado em teste gratuito não está
   lá. A terceira condição é dado (`formulario.busca_cliente`), não `if` por
   slug: no dia em que ele mudar de ideia é uma linha na carga. */""",
      "2c. o comentario diz a regra inteira")


# ===========================================================================
# 3. A PÁGINA PÚBLICA — passa o dado adiante
# ===========================================================================
PG = abrir("frontend/publico/FormularioPublico.vue")

troca(PG,
      '''        :formato="def.formato"''',
      '''        :formato="def.formato"
        :busca-cliente="def.busca_cliente === true"''',
      "3. a pagina passa busca-cliente")


# ===========================================================================
# 4. A SUÍTE — o contrato novo, e a trava do caso que o defeito criou
# ===========================================================================
TS = abrir("frontend/src/formulario_novo.teste.js")

troca(TS,
      """      props: { campos: [cnpj, cpf], regras: [], valores, formato: 'novo' },""",
      """      props: {
        campos: [cnpj, cpf], regras: [], valores, formato: 'novo',
        // 🔵 23/11: o botão depende de o formulário procurar cliente.
        buscaCliente: true,
      },""",
      "4a. o teste do botao declara que o formulario procura cliente")

troca(TS,
      """  it('o recado da busca aparece no campo', () => {""",
      """  /* 🔵 23/11, DELE: *"ele nao precisa de cpf e cnpj, obviamente pois nao puxa
     de base alguma"* -- e, sobre o botão, **tirar onde não há base**.

     🚨 ESTA TRAVA GUARDA UM DEFEITO QUE ESTEVE NO AR. A regra era
     `ehNovo && validacao === 'cnpj'`, e `FORMATO_NOVO = None` põe os 16 em
     `novo`: o `pagamento-tecnicos` mostrava um botão que varre a tabela
     `cliente` procurando um parceiro técnico, que nunca está lá.

     ⚠️ E o campo CONTINUA INTEIRO -- máscara, validação e tudo. O que sai é a
     busca, não a pergunta. */
  it('🔵 sem base para procurar, o CNPJ não tem botão Buscar', async () => {
    const cnpj = campo('cnpj', 'double', { validacao: 'cnpj' })
    const tela = mount(CamposDoFormulario, {
      props: { campos: [cnpj], regras: [], valores: {}, formato: 'novo' },
    })
    /* O padrão é NÃO procurar: o prop ausente já significa "sem busca". */
    expect(tela.find('.campo__buscar').exists()).toBe(false)
    /* ⚠️ Mas o campo é o mesmo campo: mascarado, e com a frase de erro. */
    await tela.find('input').setValue('123')
    await tela.find('input').trigger('blur')
    expect(tela.find('.campo__frase').exists()).toBe(true)
  })

  it('o recado da busca aparece no campo', () => {""",
      "4b. trava nova: sem base, sem botao")


for rel, d in ALVOS.items():
    saida = d["t"].replace("\n", "\r\n") if d["crlf"] else d["t"]
    d["p"].write_bytes(saida.encode("utf-8"))
    print("gravado:", rel, len(saida), "bytes")
