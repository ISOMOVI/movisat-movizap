/* ============================================================================
   As variáveis das mensagens rápidas (25/09, Plano 3)
   ----------------------------------------------------------------------------
   🔵 *"na criação da mensagem, pode ter 3 campos de auto preenchimento, como
   {cliente}; {Nome contato} e {Saudação de Horário}"* -- e, confirmado por
   ele: `{cliente}` é a EMPRESA (o cadastro vinculado), `{contato}` é a PESSOA.

   🟡 Preenchidas NA TELA, ao inserir, com os dados da conversa aberta: o texto
   vai para o campo e a pessoa ainda edita antes de enviar. Variável sem dado
   (conversa sem cadastro) fica em branco e volta em `faltando`, para a tela
   avisar -- nada é enviado sozinho.

   Função pura: testada sem navegador.
   ============================================================================ */

export const VARIAVEIS = [
  { chave: '{cliente}', rotulo: 'Cliente', ajuda: 'a empresa do cadastro' },
  { chave: '{contato}', rotulo: 'Nome do contato', ajuda: 'a pessoa que escreve' },
  { chave: '{saudacao}', rotulo: 'Saudação do horário', ajuda: 'Bom dia, Boa tarde, Boa noite' },
]

/* 🟡 Cortes às 12h e às 18h, no relógio de quem está atendendo. */
export function saudacao(agora = new Date()) {
  const h = agora.getHours()
  if (h < 12) return 'Bom dia'
  if (h < 18) return 'Boa tarde'
  return 'Boa noite'
}

/**
 * @param {string} texto
 * @param {{cliente?: string|null, contato?: string|null}} dados
 * @returns {{texto: string, faltando: string[]}}
 */
export function aplicarVariaveis(texto, dados = {}, agora = new Date()) {
  const valores = {
    '{cliente}': dados.cliente || '',
    '{contato}': dados.contato || '',
    '{saudacao}': saudacao(agora),
  }
  const faltando = []
  let saida = texto || ''
  for (const [chave, valor] of Object.entries(valores)) {
    if (!saida.includes(chave)) continue
    if (!valor) faltando.push(chave)
    saida = saida.split(chave).join(valor)
  }
  if (faltando.length) {
    // A lacuna não pode deixar "Olá , tudo bem?": arruma o espaço que sobrou.
    saida = saida.replace(/[ \t]{2,}/g, ' ').replace(/ ([,.!?;:])/g, '$1')
  }
  return { texto: saida, faltando }
}

export const rotuloDe = (chave) => VARIAVEIS.find((v) => v.chave === chave)?.rotulo || chave
