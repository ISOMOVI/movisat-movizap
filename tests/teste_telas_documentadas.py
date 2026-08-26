"""O registro de telas e a doc não podem divergir.

🚨 ESCRITO PORQUE O DOC ATRASOU E NINGUÉM PERCEBEU. Ele perguntou em 26/08 se a
documentação das telas estava em dia. O **registro** estava (as 20 telas do
`movizap/telas.py` aparecem no `docs/03`); o **conteúdo** não: o
`docs/06_Conteudo_das_Telas.md` ainda afirmava *"encaminhar arquivo ainda não"*
depois de o encaminhar arquivo existir, e nada no placar acusava.

⚠️ É A MESMA DÍVIDA QUE `teste_modelo_documentado.py` já prende do outro lado:
lá, migração que cria coluna tem de aparecer no `docs/02`. Aqui, tela que
existe tem de aparecer no `docs/06`. Doc que descreve o sistema é parte do
sistema; se ninguém a mede, ela mente em silêncio.

🚨 ESTE TESTE MEDE LIGAÇÃO, NÃO PALAVRA. Ele não procura frases nem tenta
adivinhar se a descrição está certa -- isso nenhum teste faz. Ele mede o que é
verificável: **o código da tela aparece no documento**, e **todo arquivo de
tela tem um código no registro**. O resto é leitura humana.
"""
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, "/home/claude/movizap_painel")

from movizap import telas  # noqa: E402

RAIZ = Path("/home/claude/movizap_painel")
DOC_REGISTRO = RAIZ / "docs/03_Registro_Telas.md"
DOC_CONTEUDO = RAIZ / "docs/06_Conteudo_das_Telas.md"
TELAS_VUE = RAIZ / "frontend/src/telas"

# Telas do esqueleto do frontend, sem código porque não são telas do produto:
# não entram no menu, não têm permissão e não há o que documentar nelas.
SEM_CODIGO = {"Login.vue", "NaoEncontrada.vue", "SemPermissao.vue"}

# 🚨 RESERVADAS: existem no registro para o código não ser reaproveitado, e
# NÃO existem como tela. Cobrar seção de conteúdo delas obrigaria a escrever
# documentação de algo que ninguém pode abrir -- que é a outra forma de o doc
# mentir. Quando uma delas nascer, sai daqui e o teste passa a cobrar.
RESERVADAS = {"CFG_2.2", "ATD_2.1", "REL_1.1"}


def _codigos():
    return [t["codigo"] for t in telas.TELAS if t.get("codigo")]


def test_existe_registro_para_conferir():
    """Se o import quebrar, o teste passaria vazio e não protegeria nada."""
    assert len(_codigos()) >= 15


@pytest.mark.parametrize("codigo", _codigos())
def test_a_tela_aparece_no_registro_documentado(codigo):
    assert codigo in DOC_REGISTRO.read_text(encoding="utf-8"), (
        f"{codigo} está em movizap/telas.py e não no docs/03. "
        f"Tela nova mexe em TRÊS lugares: registro, roteador e doc.")


@pytest.mark.parametrize("codigo", [c for c in _codigos() if c not in RESERVADAS])
def test_a_tela_tem_conteudo_documentado(codigo):
    """🚨 O que esta tela FAZ tem de estar escrito em algum lugar."""
    assert codigo in DOC_CONTEUDO.read_text(encoding="utf-8"), (
        f"{codigo} existe e o docs/06 não a menciona. Documente antes de "
        f"seguir -- o documento é o que sobra quando ninguém lembra.")


def test_todo_arquivo_de_tela_tem_codigo_no_registro():
    """⚠️ O CAMINHO INVERSO. O de cima pega tela registrada e não documentada;
    este pega tela que EXISTE no frontend e não está registrada -- que é como
    uma tela passa a rodar sem permissão própria e sem aparecer no menu."""
    codigos = set(_codigos())
    orfas = []
    for arquivo in sorted(TELAS_VUE.glob("*.vue")):
        if arquivo.name in SEM_CODIGO:
            continue
        fonte = arquivo.read_text(encoding="utf-8")
        # Mede a OCORRÊNCIA DO CÓDIGO no arquivo (no comentário de cabeçalho ou
        # no chip da tela). Não é a ligação ideal, mas é a que existe: o
        # roteador liga rota↔componente, e a rota já é conferida no registro.
        if not any(re.search(rf"\b{re.escape(c)}\b", fonte) for c in codigos):
            orfas.append(arquivo.name)
    assert orfas == [], (
        f"telas sem código do registro: {orfas}. Tela sem código não tem "
        f"permissão própria e não aparece no menu.")
