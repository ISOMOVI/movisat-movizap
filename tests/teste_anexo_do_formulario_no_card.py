# -*- coding: utf-8 -*-
r"""O ANEXO DO FORMULÁRIO CHEGA AO CARD — 27/11.

🔵 Ele, 27/11: *"pode colocar o campo de OBS nas mesmas regras dos demais
paineis - com anexo, historico"* · *"quem ve usa tudo"* · *"pode subir tudo"*.

🚨 **O DEFEITO, PROVADO EM DADO REAL.** `paineis._card_do_chamado` devolvia
`"anexos": 0` **fixo**, enquanto os dois construtores de card mais antigos
contam de `formulario_arquivo`. 📏 O card **4360** (Contratual) tem **1** anexo
de formulário e o card dizia **0**; o **4134** tem **2**. Resultado: nos quatro
painéis que usam o `quadro_da_aba` — Compras incluída — a pílula *"N anexo(s)"*
**nunca aparecia**, e o orçamento que o cliente anexou ficava invisível no
quadro.

🚨 **E A SEGUNDA METADE: a porta trancada.** A rota que serve o arquivo exigia
`FRM_1.1`, que é **owner**. Mostrar o anexo no card com aquele link daria 403 a
quem tem o painel — *"tela certa, permissão de outro"*. A decisão dele resolve:
*"quem vê usa tudo"*. Agora a rota aceita **ou** `FRM_1.1` **ou** a tela da aba
do card daquela solicitação, e quem tinha acesso não perdeu nada.

⚠️ Nada aqui escreve. Todos leem o estado.

Roda:  venv/bin/python -m pytest tests/teste_anexo_do_formulario_no_card.py
"""
import pathlib
import sys

import pytest

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

pytest.importorskip("psycopg")

from fastapi.testclient import TestClient  # noqa: E402

from movizap import auth, banco, paineis, telas  # noqa: E402
from movizap import main  # noqa: E402
from movizap.config import settings  # noqa: E402

ENV = RAIZ / ".env"
pytestmark = pytest.mark.skipif(
    not ENV.exists() or "MOVIZAP_DB_SENHA" not in ENV.read_text(encoding="utf-8"),
    reason="banco nao configurado no .env")

BAIXAR = "/api/solicitacoes/{}/arquivo/{}"


@pytest.fixture(scope="module", autouse=True)
def pool():
    banco.abrir()
    yield


@pytest.fixture(scope="module")
def cliente():
    with TestClient(main.app) as c:
        yield c


@pytest.fixture(scope="module")
def cab():
    return {"Authorization":
            f"Bearer {auth.criar_token(settings.admin_login)}"}


@pytest.fixture(scope="module")
def card_com_anexo():
    """Um card de solicitação cuja solicitação TEM anexo de formulário.

    🚨 Medido, nunca escrito à mão: id fixo envelheceria, e um `skip` honesto
    é melhor que uma trava que mede o card errado.
    """
    linha = banco.um(
        """SELECT c.id AS card_id, c.solicitacao_id, c.etapa_id,
                  a.codigo_tela,
                  (SELECT count(*) FROM formulario_arquivo x
                    WHERE x.solicitacao_id = c.solicitacao_id) AS anexos,
                  (SELECT min(x.id) FROM formulario_arquivo x
                    WHERE x.solicitacao_id = c.solicitacao_id) AS arquivo_id
             FROM pipeline_card c
             JOIN painel_aba a ON a.id = c.aba_id
            WHERE c.solicitacao_id IS NOT NULL
              AND c.numero_os IS NULL
              AND EXISTS (SELECT 1 FROM formulario_arquivo x
                           WHERE x.solicitacao_id = c.solicitacao_id)
            ORDER BY c.id DESC LIMIT 1""")
    if not linha:
        pytest.skip("nenhum card de solicitacao com anexo de formulario")
    return linha


@pytest.fixture
def quem_pode(monkeypatch):
    """Troca o oráculo da permissão e grava o que foi perguntado."""
    estado = {"perguntados": [], "permitidas": set()}

    def _pode(usuario, codigo):
        estado["perguntados"].append(codigo)
        return codigo in estado["permitidas"]

    monkeypatch.setattr(telas, "pode_acessar", _pode)
    return estado


# ============================================================================
# 1 — A PÍLULA: o card conta os anexos do formulário
# ============================================================================
class TestOCardContaOsAnexosDoFormulario:
    def test_o_card_do_quadro_traz_a_contagem_de_verdade(self, card_com_anexo):
        """🚨 VERMELHO ANTES DO CONSERTO: `_card_do_chamado` fixava 0."""
        quadro = paineis.quadro_da_aba(card_com_anexo["codigo_tela"],
                                       so_abertas=False)
        assert quadro, "a aba do card nao montou"
        achado = None
        for coluna in quadro["colunas"]:
            for card in coluna["cards"]:
                if card["id"] == card_com_anexo["card_id"]:
                    achado = card
        if achado is None:
            pytest.skip("o card nao esta no quadro aberto agora")
        assert achado["anexos"] == card_com_anexo["anexos"]
        assert achado["anexos"] > 0

    def test_card_sem_anexo_continua_em_zero(self):
        """⚠️ A OUTRA METADE: a pílula não pode aparecer onde não há anexo --
        `v-if="card.anexos"` esconde o zero, e um 1 inventado poria pílula em
        todo card dos quatro painéis."""
        linha = banco.um(
            """SELECT c.id, a.codigo_tela FROM pipeline_card c
                 JOIN painel_aba a ON a.id = c.aba_id
                WHERE c.solicitacao_id IS NOT NULL AND c.numero_os IS NULL
                  AND NOT EXISTS (SELECT 1 FROM formulario_arquivo x
                                   WHERE x.solicitacao_id = c.solicitacao_id)
                ORDER BY c.id DESC LIMIT 1""")
        if not linha:
            pytest.skip("nenhum card de solicitacao sem anexo")
        quadro = paineis.quadro_da_aba(linha["codigo_tela"], so_abertas=False)
        for coluna in quadro["colunas"]:
            for card in coluna["cards"]:
                if card["id"] == linha["id"]:
                    assert card["anexos"] == 0


# ============================================================================
# 2 — A PORTA: quem vê o card baixa o anexo dele
# ============================================================================
class TestQuemVeOCardBaixaOAnexo:
    def test_a_aba_do_card_abre_o_anexo(self, cliente, cab, quem_pode,
                                        card_com_anexo):
        """🚨 VERMELHO ANTES: a rota exigia `FRM_1.1`, que é owner.

        ⚠️ O que se mede é o PORTÃO. O arquivo pode não estar mais no disco
        (esta pasta não tem backup), e 410 é passar pelo portão — 403 é
        reprovar.
        """
        quem_pode["permitidas"] = {card_com_anexo["codigo_tela"]}
        r = cliente.get(BAIXAR.format(card_com_anexo["solicitacao_id"],
                                      card_com_anexo["arquivo_id"]),
                        headers=cab)
        assert r.status_code != 403, r.text[:300]

    def test_quem_tem_a_FRM_1_1_nao_perdeu_nada(self, cliente, cab, quem_pode,
                                                card_com_anexo):
        """🚨 Mudança de permissão que TIRA acesso de quem tinha é regressão,
        e esta trava é o que impede eu trocar uma porta por outra."""
        quem_pode["permitidas"] = {"FRM_1.1"}
        r = cliente.get(BAIXAR.format(card_com_anexo["solicitacao_id"],
                                      card_com_anexo["arquivo_id"]),
                        headers=cab)
        assert r.status_code != 403, r.text[:300]

    def test_quem_nao_tem_nem_uma_nem_outra_continua_de_fora(
            self, cliente, cab, quem_pode, card_com_anexo):
        """⚠️ *"Quem vê usa tudo"* não é *"qualquer um usa tudo"*."""
        quem_pode["permitidas"] = {"ATD_1.1"}
        r = cliente.get(BAIXAR.format(card_com_anexo["solicitacao_id"],
                                      card_com_anexo["arquivo_id"]),
                        headers=cab)
        assert r.status_code == 403, r.text[:300]

    def test_a_aba_de_OUTRO_painel_nao_abre_este_anexo(
            self, cliente, cab, quem_pode, card_com_anexo):
        outra = ("PNL_1.2" if card_com_anexo["codigo_tela"] != "PNL_1.2"
                 else "PNL_1.5")
        quem_pode["permitidas"] = {outra}
        r = cliente.get(BAIXAR.format(card_com_anexo["solicitacao_id"],
                                      card_com_anexo["arquivo_id"]),
                        headers=cab)
        assert r.status_code == 403, r.text[:300]

    def test_solicitacao_sem_card_fica_so_com_a_FRM_1_1(self, cliente, cab,
                                                        quem_pode):
        """⚠️ Solicitação que nunca virou card não tem aba nenhuma -- e aí a
        única porta continua sendo a da tela de Solicitações. Sem esta trava,
        'não achei aba' poderia virar 'deixa passar'."""
        linha = banco.um(
            """SELECT x.solicitacao_id, x.id AS arquivo_id
                 FROM formulario_arquivo x
                WHERE NOT EXISTS (SELECT 1 FROM pipeline_card c
                                   WHERE c.solicitacao_id = x.solicitacao_id)
                ORDER BY x.id DESC LIMIT 1""")
        if not linha:
            pytest.skip("nenhum anexo de solicitacao sem card")
        quem_pode["permitidas"] = {"PNL_1.5"}
        r = cliente.get(BAIXAR.format(linha["solicitacao_id"],
                                      linha["arquivo_id"]), headers=cab)
        assert r.status_code == 403

        quem_pode["permitidas"] = {"FRM_1.1"}
        r = cliente.get(BAIXAR.format(linha["solicitacao_id"],
                                      linha["arquivo_id"]), headers=cab)
        assert r.status_code != 403
