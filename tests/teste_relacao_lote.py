"""Marcar o tipo de vários contatos de uma vez — a CAD_1.2 (25/08).

🚨 POR QUE EXISTE. 1.750 dos 1.754 contatos dizem "cliente" porque até a
migração 031 o INSERT do sync gravava essa palavra literal. Corrigir um por
vez são 1.750 idas ao painel -- e sem base honesta o interruptor de automação
por tipo dispara para quem não devia.

🚨 Escreve em `contato`, tabela de PRODUÇÃO. Nome com prefixo `zz`.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, "/home/claude/movizap_painel")
pytest.importorskip("psycopg")

from movizap import banco, cadastro  # noqa: E402

ENV = Path("/home/claude/movizap_painel/.env")
pytestmark = pytest.mark.skipif(
    not ENV.exists() or "MOVIZAP_DB_SENHA" not in ENV.read_text(encoding="utf-8"),
    reason="banco nao configurado no .env")

MARCA = "zz teste lote"


def limpar():
    banco.executar("DELETE FROM contato WHERE nome LIKE %s", (MARCA + "%",))


@pytest.fixture(scope="module", autouse=True)
def pool():
    banco.abrir()
    limpar()
    yield
    limpar()
    banco.fechar()


@pytest.fixture()
def tres():
    limpar()
    ids = []
    for i in range(3):
        ids.append(banco.um(
            """INSERT INTO contato (nome, origem) VALUES (%s, 'movizap')
               RETURNING id""", (f"{MARCA} {i}",))["id"])
    yield ids
    limpar()


def _relacao(contato_id):
    return banco.um("SELECT relacao FROM contato WHERE id = %s",
                    (contato_id,))["relacao"]


class TestOVocabularioEspelhaOBanco:
    def test_sem_identificacao_esta_na_lista(self):
        """🚨 A tupla tinha ficado para trás da migração 029: a rota recusaria,
        com "relação inválida", um valor que o banco aceita. Espelho que não se
        atualiza junto vira mentira."""
        assert "sem_identificacao" in cadastro.RELACOES

    def test_a_tupla_bate_com_o_CHECK_do_banco(self):
        """O contrato é o CHECK; esta lista é só o espelho para a tela e para
        a rota recusar cedo. Divergir é o defeito."""
        bruto = banco.um(
            """SELECT pg_get_constraintdef(oid) AS def FROM pg_constraint
                WHERE conname = 'contato_relacao_check'""")["def"]
        for valor in cadastro.RELACOES:
            assert f"'{valor}'" in bruto, f"{valor} não está no CHECK"


class TestMarcarEmLote:
    def test_marca_os_tres_de_uma_vez(self, tres):
        r = cadastro.definir_relacao_em_lote(tres, "fornecedor")
        assert r["ok"] is True
        assert r["mudados"] == 3
        assert all(_relacao(i) == "fornecedor" for i in tres)

    def test_conta_so_o_que_MUDOU(self, tres):
        """⚠️ Pedir 3 e mudar 0 quer dizer que já estavam assim. Devolver "ok"
        seco esconderia a diferença entre "marquei" e "não precisou"."""
        cadastro.definir_relacao_em_lote(tres, "tecnico")
        segunda = cadastro.definir_relacao_em_lote(tres, "tecnico")
        assert segunda["ok"] is True
        assert segunda["pedidos"] == 3
        assert segunda["mudados"] == 0

    def test_id_que_nao_existe_nao_derruba_o_lote(self, tres):
        r = cadastro.definir_relacao_em_lote(tres + [99999999], "teste")
        assert r["ok"] is True
        assert r["mudados"] == 3
        assert r["pedidos"] == 4

    def test_id_repetido_conta_uma_vez(self, tres):
        r = cadastro.definir_relacao_em_lote(tres + tres, "teste")
        assert r["pedidos"] == 3

    def test_relacao_invalida_e_recusada_antes_do_banco(self, tres):
        r = cadastro.definir_relacao_em_lote(tres, "presidente")
        assert r["ok"] is False
        assert "inválida" in r["motivo"]
        assert all(_relacao(i) == "sem_identificacao" for i in tres)

    def test_lista_vazia_e_recusada(self):
        assert cadastro.definir_relacao_em_lote([], "cliente")["ok"] is False

    def test_lote_acima_do_teto_e_recusado(self, tres):
        """⚠️ O teto não é medo do banco: é que lote sem teto aceita "marcar a
        base inteira" num clique, e não existe desfazer."""
        r = cadastro.definir_relacao_em_lote(
            list(range(1, cadastro.TETO_LOTE + 50)), "cliente")
        assert r["ok"] is False
        assert str(cadastro.TETO_LOTE) in r["motivo"]


class TestONovoNasceSemIdentificacao:
    def test_contato_novo_nasce_sem_identificacao(self, tres):
        """Migração 031: o DEFAULT era 'lead', que é uma AFIRMAÇÃO. Contato
        recém-nascido não sustenta afirmação nenhuma."""
        assert all(_relacao(i) == "sem_identificacao" for i in tres)


class TestFiltrarPorTipo:
    def test_o_filtro_traz_so_o_tipo_pedido(self, tres):
        cadastro.definir_relacao_em_lote(tres[:2], "fornecedor")
        r = cadastro.listar_contatos(busca=MARCA, relacoes=["fornecedor"],
                                     por_pagina=50)
        achados = [i["id"] for i in r["itens"]]
        assert set(achados) == set(tres[:2])

    def test_o_filtro_COMBINA_com_a_busca(self, tres):
        """Procurar "silva" entre os fornecedores é uma pergunta só."""
        cadastro.definir_relacao_em_lote(tres, "fornecedor")
        r = cadastro.listar_contatos(busca="zznaoexisteesse",
                                     relacoes=["fornecedor"], por_pagina=50)
        assert r["itens"] == []

    def test_varios_tipos_somam(self, tres):
        cadastro.definir_relacao_em_lote(tres[:1], "fornecedor")
        cadastro.definir_relacao_em_lote(tres[1:], "tecnico")
        r = cadastro.listar_contatos(busca=MARCA,
                                     relacoes=["fornecedor", "tecnico"],
                                     por_pagina=50)
        assert len(r["itens"]) == 3

    def test_sem_filtro_a_lista_nao_muda(self, tres):
        r = cadastro.listar_contatos(busca=MARCA, relacoes=None, por_pagina=50)
        assert len(r["itens"]) == 3
