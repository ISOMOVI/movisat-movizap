"""O registro do backend e o roteador do frontend não podem divergir.

🚨 Por que este arquivo existe. O menu do MoviZap é gerado do
`movizap/telas.py`. O frontend desenha o que vem, sem reclamar. Então uma tela
registrada no backend e ausente do roteador **aparece no menu e leva para "não
encontrada"** -- e ninguém descobre até alguém clicar.

Foi o que aconteceu em 2026-08-06: a `ATD_5.1` entrou no registro, no doc e no
`telas.py` no mesmo commit, como a regra manda, e mesmo assim ficou de fora do
roteador. Os 191 testes passaram. O doc do próprio registro avisa sobre essa
falha e não havia nada verificando.

O teste lê o `router/index.js` como texto de propósito: montar Node no meio da
suíte Python seria caro e frágil, e o que importa aqui é a LISTA de códigos e
rotas -- que é justamente o que dá para ler sem interpretar JavaScript.
"""
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, "/home/claude/movizap_painel")

from movizap import telas  # noqa: E402

ROUTER = Path("/home/claude/movizap_painel/frontend/src/router/index.js")

pytestmark = pytest.mark.skipif(
    not ROUTER.exists(), reason="frontend não está neste checkout")


def _rotas_do_router() -> dict[str, str]:
    """{codigo: path} lido do roteador. Só as rotas que têm código de tela."""
    texto = ROUTER.read_text(encoding="utf-8")
    # Cada bloco de rota tem `path: '...'` seguido de `name: 'CODIGO'`.
    achados = re.findall(
        r"path:\s*'([^']+)'\s*,\s*\n\s*name:\s*'([A-Z]{3}_[0-9.]+)'", texto)
    return {codigo: caminho for caminho, codigo in achados}


def _codigos_ativos() -> set[str]:
    return {t["codigo"] for t in telas.ativas()}


class TestRegistroERoteadorAndamJuntos:
    def test_toda_tela_registrada_tem_rota_no_frontend(self):
        faltando = _codigos_ativos() - set(_rotas_do_router())
        assert not faltando, (
            f"{sorted(faltando)} está no registro do backend e NÃO tem rota no "
            f"frontend. O menu é gerado do registro, então essas telas aparecem "
            f"e levam para 'não encontrada'."
        )

    def test_toda_rota_do_frontend_existe_no_registro(self):
        sobrando = set(_rotas_do_router()) - {t["codigo"] for t in telas.TELAS}
        assert not sobrando, (
            f"{sorted(sobrando)} tem rota no frontend e não existe no registro. "
            f"Rota sem código registrado não sobe -- ver docs/03_Registro_Telas.md."
        )

    def test_o_caminho_e_o_mesmo_dos_dois_lados(self):
        """Rota mudou de um lado e não do outro é pior que faltar: o menu leva
        ao lugar errado e nada acusa."""
        router = _rotas_do_router()
        divergentes = []
        for tela in telas.ativas():
            caminho_backend = tela["rota"]
            caminho_frontend = router.get(tela["codigo"])
            if caminho_frontend is None:
                continue  # já coberto pelo teste acima
            # `/atendimento/{id}` no backend é `/atendimento/:id` no vue-router
            normalizado = re.sub(r"\{(\w+)\}", r":\1", caminho_backend)
            if normalizado != caminho_frontend:
                divergentes.append(
                    (tela["codigo"], caminho_backend, caminho_frontend))
        assert not divergentes, f"caminhos divergentes: {divergentes}"

    def test_reservada_de_fase_futura_nao_tem_rota(self):
        """Código ocupado não é tela. Dar rota a uma reservada é entregar
        antes da hora e sem querer."""
        futuras = {t["codigo"] for t in telas.TELAS if t["fase"] > telas.FASE_ATUAL}
        com_rota = futuras & set(_rotas_do_router())
        assert not com_rota, f"reservadas com rota no frontend: {sorted(com_rota)}"

    def test_o_leitor_do_router_realmente_leu_alguma_coisa(self):
        """🚨 Se a regex parar de casar, todos os testes acima passam vazios.

        É a armadilha do valor constante da metodologia §6, na forma de
        conjunto vazio: nada falha, e nada foi verificado.
        """
        rotas = _rotas_do_router()
        assert len(rotas) >= 10, (
            f"o leitor achou só {len(rotas)} rotas no router -- a regex "
            f"provavelmente quebrou, e os outros testes deste arquivo estão "
            f"passando sem verificar nada"
        )
