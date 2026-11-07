# -*- coding: utf-8 -*-
r"""A ESTRUTURA da rolagem no painel da Operação — lida do template (06/11).

🔵 Ele: *"pode ligar a rolagem horizontal via mouse sobreposto"*.

🚨 **O DEFEITO QUE SÓ ESTA TRAVA PEGA.** A faixa chama `preventDefault` no
`dragover` — é o preço de o arraste poder rolar —, e isso a torna uma área que
**aceita soltar**. Se ela estivesse DENTRO de uma `.coluna`, um `drop` sobre ela
subiria por **borbulhamento** até o `soltarNaColuna` daquela coluna e o card
mudaria de lugar **sozinho**, sem ninguém pedir. O teste do componente não pode
ver isso: o componente não sabe onde foi montado.

⚠️ **ESTE ARQUIVO LÊ O TEMPLATE, e é de propósito.** A estrutura mora no
`.vue`, e nenhuma suíte de componente a alcança. É o mesmo princípio do
`conferir_css_publicado.mjs`: regra que vive na forma do arquivo precisa de
alguém que leia o arquivo.

Roda:  venv/bin/python -m pytest tests/teste_estrutura_rolagem.py
"""
import pathlib
import re

RAIZ = pathlib.Path(__file__).resolve().parent.parent
TELA = RAIZ / "frontend/src/telas/PainelOperacao.vue"


def fonte() -> str:
    return TELA.read_text(encoding="utf-8")


def teste_a_tela_existe_e_tem_o_quadro():
    """Se o caminho mudar, tudo aqui passaria vazio."""
    t = fonte()
    assert '<div ref="rolo" class="quadro">' in t


def teste_a_faixa_esta_FORA_das_colunas():
    """🚨 A trava do borbulhamento. A `RolagemDaBorda` tem de aparecer ANTES do
    `<div ref="rolo" class="quadro">` -- irmã dele, dentro do casco, e nunca
    dentro de uma `<section class="coluna">`."""
    t = fonte()
    faixa = t.index("<RolagemDaBorda")
    quadro = t.index('<div ref="rolo" class="quadro">')
    assert faixa < quadro, "a faixa está dentro do quadro"
    # ⚠️ E nenhuma `<section class="coluna"` abriu antes dela.
    assert 'class="coluna"' not in t[:faixa]


def teste_a_faixa_mora_no_casco_relativo():
    """Sem um ancestral `position: relative`, a faixa `absolute` se penduraria
    no casco do painel inteiro e cobriria o menu."""
    t = fonte()
    casco = t.index('<div class="quadro__casco">')
    faixa = t.index("<RolagemDaBorda")
    quadro = t.index('<div ref="rolo" class="quadro">')
    assert casco < faixa < quadro
    assert re.search(r"\.quadro__casco\s*\{[^}]*position:\s*relative", t)


def teste_a_barra_fica_FORA_do_casco():
    """⚠️ A barra é `sticky` em relação ao `.painel__conteudo`. Dentro do casco
    ela ficaria na mesma camada das faixas, e a ordem das duas passaria a
    depender da ordem de escrita."""
    t = fonte()
    barra = t.index("<BarraDeRolagem")
    casco = t.index('<div class="quadro__casco">')
    assert barra < casco


def teste_o_rolo_e_o_UNICO_com_overflow_x():
    """🚨 Dois `overflow-x` empilhados dariam duas barras e a faixa rolaria o
    elemento errado. Foi o defeito de 05/11 no modal (duas rolagens, e eu dizia
    ter tirado uma)."""
    t = fonte()
    assert len(re.findall(r"overflow-x:\s*auto", t)) == 1


def teste_os_dois_controles_recebem_o_MESMO_rolo():
    """⚠️ Controles apontando para elementos diferentes é tela que mente: a
    barra mostraria uma posição e a faixa andaria outra."""
    t = fonte()
    for tag in ("<BarraDeRolagem", "<RolagemDaBorda"):
        i = t.index(tag)
        trecho = t[i:i + 200]
        assert ':rolo="rolo"' in trecho, tag


def teste_a_referencia_do_rolo_e_declarada_uma_vez():
    t = fonte()
    assert t.count("const rolo = ref(null)") == 1
    assert t.count('ref="rolo"') == 1
