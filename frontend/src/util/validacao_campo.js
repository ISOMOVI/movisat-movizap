/* ============================================================================
   Máscara e conferência de campo — o Bloco 3 do plano de 23/10.
   ----------------------------------------------------------------------------
   🚨 NADA AQUI RECUSA ENVIO. Quem recusa é o servidor
   (`movizap/formularios.py:validar`). O que estas funções produzem é a FRASE
   QUE A PESSOA LÊ e o texto formatado que ela vê. No Bitrix era o contrário --
   toda a validação dos 239 campos no navegador -- e em 22/10 um POST cru com
   `values=[]` criou registro lá dentro.

   🚨 O QUE VAI GRAVADO É LIMPO, NÃO MASCARADO, e isso não é gosto: o servidor
   confere `cnpj` e `cpf` como `double`, e `"123.456.789-01"` não passa por
   `float()` -- a rota responderia *"informe um número"* num CPF correto.
   Então a máscara é só o que se vê (`mascarar`), e o que viaja é o que
   `limpar` devolve.

   ⚠️ A REGRA VEM DO BANCO (`formulario_campo.validacao`), não do tipo do
   Bitrix: 30 dos 239 campos são `double` e são CNPJ, CPF, RG e quantidade. O
   tipo não distingue documento de número, e por isso a coluna existe.
   ============================================================================ */

export const REGRAS = ['cpf', 'cnpj', 'placa', 'telefone', 'email', 'cep']

function digitos(texto) {
  return String(texto ?? '').replace(/\D+/g, '')
}

/* 🚨 O CNPJ PODE TER LETRA DESDE 2026, e isso muda a natureza do campo: são
   **12 posições alfanuméricas** (A–Z e 0–9) e **2 dígitos** de verificação.
   Medido na nossa própria base: `WQ0P6GLD000108` (Pastelaria Velasco) é um
   CNPJ alfanumérico com DV CORRETO, e a primeira versão desta função o
   recusava -- ele colou e o botão Buscar ficou travado. Tratar CNPJ como
   número é a suposição que quebrou. */
function alfanum(texto) {
  return String(texto ?? '').toUpperCase().replace(/[^A-Z0-9]/g, '')
}

/* O valor que VAI GRAVADO, por regra. */
export function limpar(regra, texto) {
  const bruto = String(texto ?? '')
  if (regra === 'cnpj') return alfanum(bruto).slice(0, 14)
  if (regra === 'email') return bruto.trim()
  if (['cpf', 'telefone', 'cep'].includes(regra)) return digitos(bruto)
  /* ⚠️ `placa` NÃO SE LIMPA, e isso foi um defeito meu: o campo do Suporte se
     chama *"Veículo e Placa — um por linha"*, então a pessoa escreve
     `SAVEIRO ABC1234`. Tirar espaço e pontuação viraria `SAVEIROABC1234`, e
     deixar em maiúscula gritaria o nome do veículo. Aqui a regra é só
     MENSAGEM: a conferência procura uma placa dentro do que foi escrito. */
  return bruto
}

/* O valor que a pessoa VÊ. Sempre derivado do limpo — nunca o contrário. */
export function mascarar(regra, texto) {
  const d = digitos(texto)
  if (regra === 'cpf') {
    return d.slice(0, 11)
      .replace(/^(\d{3})(\d)/, '$1.$2')
      .replace(/^(\d{3})\.(\d{3})(\d)/, '$1.$2.$3')
      .replace(/\.(\d{3})(\d{1,2})$/, '.$1-$2')
  }
  /* 🚨 A MÁSCARA DO CNPJ É POSICIONAL, NÃO "DE NÚMERO": com letra no meio,
     regex de `\d` não casa nada e o campo ficava sem pontuação. Os grupos são
     os mesmos de sempre -- 2 . 3 . 3 / 4 - 2 -- só que sobre caracteres
     alfanuméricos. ⚠️ Vale para os dois: `12.345.678/0001-95` e
     `WQ.0P6.GLD/0001-08`. */
  if (regra === 'cnpj') {
    const a = alfanum(texto).slice(0, 14)
    const pedacos = [a.slice(0, 2), a.slice(2, 5), a.slice(5, 8),
                     a.slice(8, 12), a.slice(12, 14)]
    let saida = pedacos[0]
    if (pedacos[1]) saida += `.${pedacos[1]}`
    if (pedacos[2]) saida += `.${pedacos[2]}`
    if (pedacos[3]) saida += `/${pedacos[3]}`
    if (pedacos[4]) saida += `-${pedacos[4]}`
    return saida
  }
  if (regra === 'cep') {
    return d.slice(0, 8).replace(/^(\d{5})(\d)/, '$1-$2')
  }
  if (regra === 'telefone') {
    const n = d.slice(0, 11)
    if (n.length <= 10) {
      return n.replace(/^(\d{2})(\d)/, '($1) $2').replace(/(\d{4})(\d{1,4})$/, '$1-$2')
    }
    return n.replace(/^(\d{2})(\d)/, '($1) $2').replace(/(\d{5})(\d{1,4})$/, '$1-$2')
  }
  return String(texto ?? '')
}

/* 🚨 Dígito verificador de verdade, não contagem de dígitos. Um CPF de 11
   dígitos quaisquer é o erro de digitação mais comum, e é justamente o que
   contar dígitos deixa passar. */
function cpfVale(d) {
  if (d.length !== 11 || /^(\d)\1{10}$/.test(d)) return false
  for (const corte of [9, 10]) {
    let soma = 0
    for (let i = 0; i < corte; i += 1) soma += Number(d[i]) * (corte + 1 - i)
    const resto = (soma * 10) % 11
    if ((resto === 10 ? 0 : resto) !== Number(d[corte])) return false
  }
  return true
}

/* 🚨 CNPJ ALFANUMÉRICO (vigente desde 2026) — e o numérico é um caso dele.
   As 12 primeiras posições podem ser letra ou dígito; as 2 últimas são SEMPRE
   dígito. O valor de cada caractere na conta é **o código ASCII menos 48**,
   que para `0`–`9` dá o próprio número (então o CNPJ antigo passa pela mesma
   conta) e para `A` dá 17, `B` 18, e assim por diante. Pesos e módulo 11
   seguem os de sempre.

   ⚠️ Conferido na nossa base: `WQ0P6GLD000108` tem DV `08` e esta conta
   devolve `08`. Era o CNPJ que ele colou e que a versão só-numérica recusava. */
function valorDoCaractere(c) {
  return c.charCodeAt(0) - 48
}

function cnpjVale(bruto) {
  const d = alfanum(bruto)
  if (d.length !== 14) return false
  if (!/^[A-Z0-9]{12}\d{2}$/.test(d)) return false
  // ⚠️ Repetição total continua fora: `00000000000000` passaria no módulo 11.
  if (/^(.)\1{13}$/.test(d)) return false

  const pesos = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
  for (const corte of [12, 13]) {
    const usa = pesos.slice(pesos.length - corte)
    let soma = 0
    for (let i = 0; i < corte; i += 1) soma += valorDoCaractere(d[i]) * usa[i]
    const resto = soma % 11
    if ((resto < 2 ? 0 : 11 - resto) !== Number(d[corte])) return false
  }
  return true
}

/* 🚨 OS DOIS PADRÕES, e os dois valem: `ABC1234` (antigo, ainda na rua) e
   `ABC1D23` (Mercosul). Aceitar só o novo recusaria a maior parte da frota. */
const PLACA_ANTIGA = /^[A-Z]{3}\d{4}$/
const PLACA_MERCOSUL = /^[A-Z]{3}\d[A-Z]\d{2}$/

/* ⚠️ PROCURA A PLACA DENTRO DO TEXTO, não exige que o texto SEJA a placa: o
   campo do Suporte pede *"Veículo e Placa"*, então `SAVEIRO ABC1234` é
   resposta certa, não resposta errada. */
export function placaVale(texto) {
  const bruto = String(texto ?? '').toUpperCase()
  return bruto.split(/[^A-Z0-9]+/).some(
    (p) => PLACA_ANTIGA.test(p) || PLACA_MERCOSUL.test(p))
}

/* A frase que a pessoa lê. Vazio = sem nada a dizer.

   ⚠️ CAMPO VAZIO NÃO É ERRO AQUI: o obrigatório é outra conversa (e é do
   servidor). Esta função só fala do que foi escrito. */
export function conferir(regra, texto) {
  const bruto = String(texto ?? '').trim()
  if (!bruto) return ''
  if (regra === 'cpf') {
    return cpfVale(digitos(bruto)) ? '' : 'CPF inválido — confira os números.'
  }
  if (regra === 'cnpj') {
    /* ⚠️ A frase NÃO diz "números": o CNPJ pode ter letra, e mandar conferir
       os números num CNPJ alfanumérico manda a pessoa procurar erro onde não
       há. */
    return cnpjVale(bruto) ? '' : 'CNPJ inválido — confira os 14 caracteres.'
  }
  if (regra === 'placa') {
    return placaVale(bruto) ? '' : 'Informe a placa (ABC1234 ou ABC1D23).'
  }
  if (regra === 'telefone') {
    const n = digitos(bruto).length
    return n === 10 || n === 11 ? '' : 'Telefone com DDD, 10 ou 11 dígitos.'
  }
  if (regra === 'cep') {
    return digitos(bruto).length === 8 ? '' : 'CEP com 8 dígitos.'
  }
  if (regra === 'email') {
    return /^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(bruto) ? '' : 'E-mail incompleto.'
  }
  return ''
}

/* ============================================================================
   Os problemas de um conjunto de campos — usado em DOIS lugares, e é por isso
   que mora aqui.
   ----------------------------------------------------------------------------
   🚨 A TELA MOSTRA e o TRILHO DE ETAPAS SEGURA, e as duas leem esta mesma
   função. Duas contas do mesmo fato divergiriam na primeira mexida -- é a
   lição do `WHERE` copiado em dois lugares que divergiu no mesmo dia (22/10).

   ⚠️ Segurar o *Avançar* não é "validar no navegador no lugar do servidor": o
   envio continua sendo recusado lá, por `formularios.validar`. Aqui é o que
   impede a pessoa de descobrir no fim que faltou algo na etapa 1.

   `dePe` é o conjunto de campos visíveis (regra condicional já aplicada):
   pergunta escondida não cobra nada, porque não foi feita.
   ============================================================================ */
export function problemas(campos, valores, dePe) {
  const fora = []
  for (const campo of campos || []) {
    if (['page', 'layout'].includes(campo.tipo)) continue
    if (dePe && !dePe.has(campo.nome)) continue

    const bruto = valores?.[campo.nome]
    const partes = Array.isArray(bruto) ? bruto : [bruto]
    const preenchidas = partes.filter((v) => String(v ?? '').trim() !== '')

    if (campo.obrigatorio && campo.tipo !== 'file' && preenchidas.length === 0) {
      fora.push({ nome: campo.nome, mensagem: 'Preencha este campo.' })
      continue
    }
    if (!campo.validacao) continue
    for (const valor of preenchidas) {
      const msg = conferir(campo.validacao, valor)
      if (msg) { fora.push({ nome: campo.nome, mensagem: msg }); break }
    }
  }
  return fora
}
