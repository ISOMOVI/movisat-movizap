"""Testes da fronteira entre a API e o frontend servido pelo FastAPI.

O que se protege aqui:
  - rota de API inexistente devolvendo o index.html com status 200 -- o fetch
    recebe HTML, quebra num JSON.parse e o erro aparece longe da causa;
  - caminho do cliente escapando do `dist` e servindo arquivo do servidor
    ("../../.env" era servido como estático);
  - o contrato de diretório entre `vite.config.js` (outDir) e `main.py`
    (FRONTEND). Divergir derruba o painel SEM derrubar a API: o serviço
    continua `active` e nada acusa.
"""
import pytest
from fastapi.testclient import TestClient

from movizap import main


@pytest.fixture
def cliente():
    return TestClient(main.app)


class TestContratoDeDiretorio:
    def test_frontend_aponta_para_frontend_dist(self):
        # Se alguém mudar o outDir do Vite, este teste é quem avisa.
        assert main.FRONTEND.parts[-2:] == ("frontend", "dist")

    def test_frontend_esta_dentro_da_raiz_do_projeto(self):
        assert main.FRONTEND.is_relative_to(main.RAIZ)


class TestRotaDeApiInexistente:
    """Vale com ou sem build: sem `dist` o catch-all nem existe e o 404 é do
    próprio FastAPI. Com `dist`, quem responde é a guarda do `spa`."""

    def test_api_inexistente_responde_404(self, cliente):
        r = cliente.get("/api/isto-nao-existe")
        assert r.status_code == 404

    def test_api_inexistente_nao_devolve_html(self, cliente):
        r = cliente.get("/api/isto-nao-existe")
        assert "text/html" not in r.headers.get("content-type", "")
        assert not r.text.lstrip().lower().startswith("<!doctype")

    def test_prefixo_api_puro_tambem_e_404(self, cliente):
        r = cliente.get("/api")
        assert r.status_code == 404

    def test_rota_que_apenas_comeca_com_api_nao_e_confundida(self, cliente):
        # "apianos" começa com "api" mas não é o prefixo /api/ -- tem que cair
        # no roteamento do Vue, não virar 404 de API.
        r = cliente.get("/apianos")
        assert r.status_code in (200, 404)
        if main.FRONTEND.exists():
            assert r.status_code == 200


class TestSpaSomenteComBuild:
    """Só faz sentido depois de `npm run build`. Sem `dist`, pula."""

    def test_index_e_servido_na_raiz(self, cliente):
        if not main.FRONTEND.exists():
            pytest.skip("frontend/dist ainda não construído")
        r = cliente.get("/")
        assert r.status_code == 200
        assert "<div id=\"app\">" in r.text

    def test_rota_do_vue_cai_no_index(self, cliente):
        if not main.FRONTEND.exists():
            pytest.skip("frontend/dist ainda não construído")
        r = cliente.get("/config/telas")
        assert r.status_code == 200
        assert "<div id=\"app\">" in r.text

    def test_caminho_nao_escapa_do_dist(self, cliente):
        if not main.FRONTEND.exists():
            pytest.skip("frontend/dist ainda não construído")
        # Se a trava falhar, isto devolve o .env do projeto.
        r = cliente.get("/../.env")
        assert r.status_code in (200, 404)
        assert "MOVIZAP_JWT_SECRET" not in r.text
        assert "MOVIZAP_ADMIN_SENHA_HASH" not in r.text
