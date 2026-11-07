# -*- coding: utf-8 -*-
"""A fixture do `menu_grupos_2110.teste.js` era IRREAL -- conserta ela (06/11).

Ate 06/11 o `MenuLateral` pulava toda tela com `aba_de`, e a fixture podia ter
uma aba ORFA (`CFG_1.1` sem a `CFG_0.1`) sem consequencia. Com o conserto da
porta trancada, aba orfa passa a desenhar o proprio item -- e a fixture virou
uma situacao que o sistema nao produz: a casca `/config` e `atendimento`, entao
quem tem `CFG_1.1` tem sempre a `CFG_0.1` junto.

Conserta a FIXTURE, e nao o codigo -- a regra da casa (`duplo se poe na borda`).
Idempotente.
"""
import pathlib
import sys

ALVO = pathlib.Path("/home/claude/movizap_painel/frontend/src/menu_grupos_2110.teste.js")
texto = ALVO.read_text(encoding="utf-8")

if "a aba não vira item de menu quando a tela-mãe veio junto" in texto:
    sys.exit("ja aplicado -- nada a fazer")

ANTIGA = (
    "  // Aba de outra tela: continua na sessão (a guarda de rota usa), e NÃO vira\n"
    "  // item de menu.\n"
    "  { codigo: 'CFG_1.1', titulo: 'Canais', rota: '/config/canais', "
    "icone: 'bi-plug', aba_de: 'CFG_0.1', grupo: 'Configuração', subgrupo: null },\n"
)
NOVA = (
    "  // A casca do `/config` e a aba dela. 🚨 06/11: AS DUAS, e não só a aba --\n"
    "  // a fixture tinha uma aba ÓRFÃ, que o sistema não produz. A `CFG_0.1` é\n"
    "  // `atendimento`, então quem alcança `CFG_1.1` alcança a casca junto. Com\n"
    "  // o conserto da porta trancada (aba órfã passa a desenhar o próprio\n"
    "  // item), a fixture órfã viraria uma regra de mentira. ⚠️ Fixture irreal\n"
    "  // não se conserta afrouxando o código.\n"
    "  { codigo: 'CFG_0.1', titulo: 'Configurações', rota: '/config', "
    "icone: 'bi-sliders', aba_de: null, grupo: 'Configuração', subgrupo: null },\n"
    "  // Aba de outra tela: continua na sessão (a guarda de rota usa), e NÃO vira\n"
    "  // item de menu -- porque a mãe dela veio junto.\n"
    "  { codigo: 'CFG_1.1', titulo: 'Canais', rota: '/config/canais', "
    "icone: 'bi-plug', aba_de: 'CFG_0.1', grupo: 'Configuração', subgrupo: null },\n"
)
if texto.count(ANTIGA) != 1:
    sys.exit(f"ancora da fixture apareceu {texto.count(ANTIGA)}x")
texto = texto.replace(ANTIGA, NOVA)

ANTIGA_ORDEM = (
    "    expect(nomesDosGrupos(tela)).toEqual(['Início', 'Atendimento', 'Cadastro'])"
)
NOVA_ORDEM = (
    "    expect(nomesDosGrupos(tela)).toEqual(['Início', 'Atendimento', "
    "'Cadastro', 'Configuração'])"
)
if texto.count(ANTIGA_ORDEM) != 1:
    sys.exit("ancora da ordem dos grupos nao bateu")
texto = texto.replace(ANTIGA_ORDEM, NOVA_ORDEM)

ANTIGA_GRUPO = (
    "  it('não desenha grupo sem nenhuma tela visível', () => {\n"
    "    // \"Configuração\" só tem tela-aba: existe na sessão, não vira grupo.\n"
    "    expect(nomesDosGrupos(montar())).not.toContain('Configuração')\n"
    "  })"
)
NOVA_GRUPO = (
    "  it('não desenha grupo sem nenhuma tela visível', () => {\n"
    "    // Grupo cujas telas não chegaram NENHUMA: o menu é construído a\n"
    "    // partir do que veio, nunca de uma lista fixa.\n"
    "    const tela = montar([CATALOGO[1]])\n"
    "    expect(nomesDosGrupos(tela)).toEqual(['Atendimento'])\n"
    "  })\n"
    "\n"
    "  it('a aba não vira item de menu quando a tela-mãe veio junto', () => {\n"
    "    // 🚨 06/11: a regra que sobrou do `if (tela.aba_de) continue`. Com a\n"
    "    // mãe presente -- que é o caso de todas as quinze `CFG_*` --, a aba\n"
    "    // continua escondida, e o item é o da casca.\n"
    "    const tela = montar()\n"
    "    expect(titulosVisiveis(tela)).toContain('Configurações')\n"
    "    expect(titulosVisiveis(tela)).not.toContain('Canais')\n"
    "  })"
)
if texto.count(ANTIGA_GRUPO) != 1:
    sys.exit("ancora do teste de grupo nao bateu")
texto = texto.replace(ANTIGA_GRUPO, NOVA_GRUPO)

ALVO.write_text(texto, encoding="utf-8")
print("menu_grupos_2110.teste.js: fixture realista + a regra que sobrou")
