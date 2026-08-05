"""Testes da CFG_1.1 -- canais.

O que se protege aqui:
  - estado do Evolution virando um valor que o CHECK do banco recusa;
  - Evolution fora do ar virando "desconectado" na tela (mentira que manda o
    atendente ler um QR que nao vai aparecer);
  - historico enchendo de linhas iguais e afogando a pergunta "quando mudou?";
  - rota de canal aberta a quem nao tem a tela.
"""
import sys

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, "/home/claude/movizap_painel")
from movizap import auth, banco, canais, evolution, main  # noqa: E402
from movizap.config import settings  # noqa: E402


@pytest.fixture(scope="module", autouse=True)
def pool():
    """🚨 Sem isto todo teste que toca o banco devolve 500.

    `TestClient(app)` FORA de um `with` nao executa o lifespan, entao
    `banco.abrir()` nunca roda e `banco.cursor()` levanta RuntimeError -- que
    o FastAPI transforma em 500. O sintoma (500) fica bem longe da causa
    (pool fechado), e foi assim que estes testes falharam da primeira vez.
    """
    banco.abrir()
    yield
    banco.fechar()


@pytest.fixture
def cliente():
    # `with` para o lifespan rodar tambem no caminho HTTP
    with TestClient(main.app) as c:
        yield c


@pytest.fixture
def token():
    return auth.criar_token(settings.admin_login)


class TestTraducaoDeEstado:
    """🚨 `canal_evento.estado` tem CHECK no banco. Estado que o Evolution
    inventar e nos gravarmos cru estoura no INSERT, longe da causa."""

    @pytest.mark.parametrize("bruto,nosso", [
        ("open", "conectado"),
        ("connecting", "pareando"),
        ("close", "desconectado"),
        ("refused", "caiu"),
    ])
    def test_mapeia_o_vocabulario_do_evolution(self, bruto, nosso):
        assert canais.traduzir(bruto) == nosso

    def test_estado_desconhecido_vira_desconectado_e_nao_estoura(self):
        # versao nova do Evolution pode inventar estado; o CHECK do banco nao
        assert canais.traduzir("algo_que_nao_existe") == "desconectado"
        assert canais.traduzir("") == "desconectado"

    def test_todo_valor_traduzido_passa_no_check_do_banco(self):
        permitidos = {"desconectado", "aguardando_qr", "pareando", "conectado", "caiu"}
        for bruto in list(canais.DE_EVOLUTION) + ["", "xyz"]:
            assert canais.traduzir(bruto) in permitidos


class TestHistoricoSoGravaMudanca:
    def test_mesmo_estado_duas_vezes_grava_uma(self):
        canal = banco.um("SELECT id FROM canal WHERE instancia='atendimento'")
        if not canal:
            pytest.skip("canal de atendimento nao cadastrado")
        cid = canal["id"]
        antes = banco.um("SELECT COUNT(*) AS n FROM canal_evento WHERE canal_id=%s",
                         (cid,))["n"]
        atual = banco.um("SELECT estado FROM canal_evento WHERE canal_id=%s "
                         "ORDER BY em DESC LIMIT 1", (cid,))["estado"]

        assert canais.registrar_evento(cid, atual) is False
        depois = banco.um("SELECT COUNT(*) AS n FROM canal_evento WHERE canal_id=%s",
                          (cid,))["n"]
        assert depois == antes, "gravou linha igual e afogou o historico"


class TestEvolutionForaDoAr:
    """Dizer 'desconectado' quando o Evolution caiu manda o atendente ler um
    QR que nunca vai aparecer."""

    def test_falha_vira_indisponivel_e_nao_desconectado(self, monkeypatch):
        def explodir(_):
            raise evolution.ErroEvolution("Evolution nao respondeu.", 0)
        monkeypatch.setattr(evolution, "estado", explodir)

        lista = canais.listar()
        if not lista:
            pytest.skip("sem canal cadastrado")
        c = lista[0]
        assert c["estado"] == "indisponivel"
        assert c["erro"]

    def test_erro_carrega_o_status_para_a_rota_decidir(self):
        e = evolution.ErroEvolution("x", 502)
        assert e.status == 502
        assert evolution.ErroEvolution("y").status == 0


class TestSettingsDaFase1:
    """Decididas no escopo: grupo e Fase 3, historico vem da ficha, e quem
    marca lido e o atendente."""

    def test_os_tres_valores_que_o_escopo_fixa(self):
        s = evolution.SETTINGS_PADRAO
        assert s["groupsIgnore"] is True
        assert s["syncFullHistory"] is False
        assert s["readMessages"] is False


class TestPermissaoNaRota:
    def test_sem_token_nao_lista_canal(self, cliente):
        assert cliente.get("/api/canais").status_code == 401

    def test_sem_token_nao_pede_qr(self, cliente):
        # 🚨 pedir QR muda estado no Evolution: nao pode ser rota aberta
        assert cliente.post("/api/canais/1/conectar").status_code == 401

    def test_sem_token_nao_desconecta(self, cliente):
        assert cliente.post("/api/canais/1/desconectar").status_code == 401

    def test_com_token_lista(self, cliente, token):
        r = cliente.get("/api/canais", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_canal_inexistente_da_404(self, cliente, token):
        r = cliente.get("/api/canais/99999/eventos",
                        headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 404


class TestNadaDeSegredoNaResposta:
    def test_a_chave_do_evolution_nunca_sai_pela_api(self, cliente, token):
        r = cliente.get("/api/canais", headers={"Authorization": f"Bearer {token}"})
        corpo = r.text.lower()
        assert "apikey" not in corpo
        if settings.evolution_api_key:
            assert settings.evolution_api_key.lower() not in corpo

    def test_a_dsn_segura_nao_tem_a_senha(self):
        seguro = settings.dsn_seguro()
        assert settings.db_nome in seguro
        if settings.db_senha:
            assert settings.db_senha not in seguro
