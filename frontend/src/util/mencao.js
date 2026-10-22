/* O destaque da menção no balão do Chat interno.

   🚨 MORA AQUI, E NÃO DENTRO DO `ChatInterno.vue`, DESDE 23/09. O teste
   (`mencao.teste.js`) testava uma CÓPIA desta função, escrita à mão no próprio
   arquivo de teste: se a tela mudasse a regra, as 9 verificações continuariam
   verdes defendendo uma função que ninguém usa. Agora a tela e o teste
   importam a MESMA.

   Quebra o texto do balão em pedaços, acendendo só os nomes que estão
   GRAVADOS como menção (`mencionados`) -- nunca caçando "@" no texto, que
   acenderia "suporte@movisat.com.br" e "@10h" como se fossem gente. */
/* 🚨 SÓ CAMINHO NOSSO, NUNCA URL QUALQUER (21/10). O aviso de menção em
   nota interna carrega `/atendimento/<id>`, e sem isto a pessoa teria de
   copiar o caminho à mão. Acender "http..." qualquer seria outra decisão, com
   outro risco: texto de cliente entra aqui. */
const CAMINHO_DA_CONVERSA = /(\/atendimento\/\d+)/

/* Quebra um pedaço de texto comum nos caminhos de conversa que ele tenha. */
function comLinks(parte) {
  const pedacos = parte.texto.split(CAMINHO_DA_CONVERSA).filter(Boolean)
  if (pedacos.length < 2) {
    return CAMINHO_DA_CONVERSA.test(parte.texto)
      ? [{ ...parte, link: parte.texto }]
      : [parte]
  }
  return pedacos.map((p) => (CAMINHO_DA_CONVERSA.test(p)
    ? { ...parte, texto: p, link: p }
    : { ...parte, texto: p }))
}

export function partesDoTexto(m) {
  const nomes = (m.mencionados || []).map((p) => p.nome)
    .sort((a, b) => b.length - a.length)   // o mais longo primeiro: "Ana Paula" antes de "Ana"
  if (!nomes.length) return comLinks({ texto: m.texto })
  const partes = []
  let resto = m.texto
  let guarda = 0
  while (resto && guarda++ < 200) {
    let achou = null
    for (const nome of nomes) {
      const i = resto.indexOf('@' + nome)
      if (i !== -1 && (achou === null || i < achou.i)) achou = { i, nome }
    }
    if (!achou) break
    if (achou.i) partes.push({ texto: resto.slice(0, achou.i) })
    // ⚠️ `me_chamou` vem do backend. Um nome pode se repetir na frase; o que
    // decide o destaque forte é ter sido EU o chamado, não o texto.
    partes.push({ texto: '@' + achou.nome, mencao: true, eu: Boolean(m.me_chamou) })
    resto = resto.slice(achou.i + achou.nome.length + 1)
  }
  if (resto) partes.push({ texto: resto })
  /* ⚠️ O LINK SÓ VALE FORA DA MENÇÃO: "@Fulano" é nome, não caminho, e
     procurar caminho dentro dele seria procurar onde não pode haver. */
  return partes.flatMap((p) => (p.mencao ? [p] : comLinks(p)))
}
