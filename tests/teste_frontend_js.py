"""Roda a suíte de JavaScript de dentro do pytest.

🚨 TESTE QUE NINGUÉM RODA É DECORATIVO. O projeto tem UM portão -- `pytest` --
e é ele que roda antes de todo deploy. Um `npm test` que só existe no
`package.json` seria esquecido na primeira semana, e as 26 asserções de
`destaque.teste.js` viveriam de boa vontade.

⚠️ PULA SE NÃO HOUVER NODE, em vez de reprovar. A suíte roda em 14 s e precisa
continuar verde numa máquina sem frontend instalado; travar tudo por falta de
`node_modules` transformaria um teste de apoio em bloqueio.
"""
import shutil
import subprocess
from pathlib import Path

import pytest

FRONTEND = Path(__file__).parent.parent / "frontend"
NODE_MODULES = FRONTEND / "node_modules" / "vitest"

pytestmark = pytest.mark.skipif(
    not shutil.which("npm") or not NODE_MODULES.exists(),
    reason="node/vitest não instalados nesta máquina")


def test_a_suite_de_javascript_passa():
    """`partir` e `marcar` — o destaque da busca, inclusive a parte de XSS."""
    r = subprocess.run(
        ["npm", "test", "--silent"],
        cwd=FRONTEND, capture_output=True, text=True, timeout=300)
    saida = (r.stdout or "") + (r.stderr or "")

    # 🚨 CÓDIGO DE RETORNO NÃO BASTA: o Vitest sai com 0 quando não encontra
    # arquivo nenhum de teste, e um `include` errado transformaria esta suíte
    # em "sucesso" silencioso. A prova é ter rodado teste de verdade.
    assert r.returncode == 0, f"vitest reprovou:\n{saida}"
    assert "Tests" in saida and "passed" in saida, (
        f"o vitest não relatou teste algum -- `include` errado?\n{saida}")
    assert "no test files found" not in saida.lower(), saida


def test_o_include_do_vitest_aponta_para_o_padrao_do_projeto():
    """⚠️ Os testes deste projeto são `*.teste.js`, não `*.test.js`.

    O padrão do Vitest é `*.test.js`/`*.spec.js`. Sem o `include`, ele roda
    ZERO teste e sai com sucesso -- a pior forma de passar.
    """
    config = (FRONTEND / "vite.config.js").read_text(encoding="utf-8")
    assert "*.teste.js" in config, (
        "o include sumiu do vite.config.js; o vitest voltaria a rodar nada")
