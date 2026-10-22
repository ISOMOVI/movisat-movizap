/* ============================================================================
   Regra condicional do formulário — o ESPELHO do servidor.
   ----------------------------------------------------------------------------
   🚨 A MESMA REGRA É AVALIADA NOS DOIS LADOS, e a estrutura é uma só (a do
   Bitrix, como veio). Aqui ela serve para MOSTRAR e ESCONDER enquanto a pessoa
   preenche; no servidor (`movizap/formularios.py:visiveis`) ela decide quem é
   obrigatório e descarta o valor de campo escondido. Quem manda é o servidor
   -- esta cópia é conforto de quem preenche, nunca autoridade.

   🚨 E É POR ISSO QUE OS CASOS SÃO COMPARTILHADOS: as duas suítes leem
   `tests/casos_regras_formulario.json`. Em 22/10 um `WHERE` de e-mail copiado
   em dois lugares divergiu no mesmo dia -- um selo mostrava 61 onde a verdade
   era 5. Duas implementações da mesma regra só convivem com um conjunto de
   casos em comum.

   ⚠️ CONDIÇÃO EM CAMPO ESCONDIDO NÃO VALE: as regras se encadeiam (A mostra B,
   B mostra C), então o valor de um campo que a pessoa nunca viu não pode
   mandar em nada. Por isso a conta repete até parar de mudar.
   ============================================================================ */

function respostas(valor) {
  if (Array.isArray(valor)) {
    return valor.map((v) => String(v)).filter((v) => v.trim() !== '')
  }
  if (valor === null || valor === undefined) return []
  const texto = String(valor)
  return texto.trim() === '' ? [] : [texto]
}

export function condicaoBate(condicao, valores) {
  const atuais = respostas((valores || {})[condicao?.target])
  if (condicao?.operation === 'any') return atuais.length > 0
  if (condicao?.operation === '=') return atuais.includes(String(condicao.value))
  /* ⚠️ Operação que não conhecemos não mostra nem esconde: o campo fica como
     nasceu. É a mesma escolha do servidor -- uma regra nova do Bitrix não pode
     deixar o formulário em branco na cara do cliente. */
  return false
}

export function visiveis(definicao, valores) {
  const campos = definicao?.campos || []
  const regras = definicao?.regras || []
  const todos = new Set(campos.map((c) => c.nome))
  const base = new Set(campos.filter((c) => c.visivel).map((c) => c.nome))
  let vis = new Set(base)

  for (let volta = 0; volta < regras.length + 2; volta += 1) {
    const novo = new Set(base)
    for (const regra of regras) {
      for (const item of regra?.lista || []) {
        const alvo = item?.action?.target
        if (!todos.has(alvo)) continue
        if (!vis.has(item?.condition?.target)) continue
        if (!condicaoBate(item.condition, valores)) continue
        if (item.action.type === 'show') novo.add(alvo)
        else if (item.action.type === 'hide') novo.delete(alvo)
      }
    }
    const igual = novo.size === vis.size && [...novo].every((n) => vis.has(n))
    vis = novo
    if (igual) break
  }
  return vis
}
