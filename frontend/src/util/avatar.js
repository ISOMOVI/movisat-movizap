/* ============================================================================
   Avatar por iniciais — usado na caixa de entrada, no e-mail e no chat interno
   ----------------------------------------------------------------------------
   🚨 NASCEU COMO CÓPIA E VIROU MÓDULO. As duas funções viviam dentro de
   `Email.vue`; quando a caixa de entrada precisou das mesmas, copiar teria
   criado duas versões da mesma regra -- e cópia não fica igual sozinha. É a
   lição do `_condicao_busca`, que existia em dois lugares e passou a procurar
   em campos diferentes sem ninguém notar.

   ⚠️ SEM FOTO, DE PROPÓSITO. Não temos foto de contato, e avatar genérico
   (o boneco cinza) é ruído: ocupa o mesmo espaço e não distingue ninguém.
   Inicial com cor estável distingue à distância, que é o que a lista precisa.
   ============================================================================ */

/* Duas letras no máximo: "Pastelaria Velasco" vira PV, "Iago" vira I. */
export function iniciais(nome) {
  const base = (nome || '?').trim()
  const partes = base
    .replace(/[<>"]/g, '')
    .split(/[\s@._-]+/)
    .filter(Boolean)
  return ((partes[0]?.[0] || '?') + (partes[1]?.[0] || '')).toUpperCase()
}

/* 🚨 A COR É DERIVADA DO NOME, NÃO SORTEADA. Precisa ser a MESMA toda vez que
   a lista recarrega -- a cada 8 segundos, aqui. Cor que muda sozinha destrói
   a única coisa que o avatar oferece: reconhecer a conversa sem ler. */
export function corDaInicial(chave) {
  const base = String(chave || '?')
  let soma = 0
  for (const c of base) soma += c.charCodeAt(0)
  /* Saturação e luminosidade fixas: o texto por cima é sempre branco, e é
     isto que garante contraste legível em qualquer matiz sorteado. */
  return `hsl(${soma % 360} 45% 42%)`
}
