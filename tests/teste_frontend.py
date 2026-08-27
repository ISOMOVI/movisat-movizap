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

    def test_o_index_manda_o_navegador_perguntar_antes_de_usar(self):
        """🚨 A TRAVA DE 27/08. O `index.html` saía SEM `Cache-Control`, e sem
        ele o navegador aplica cache heurístico: guarda e serve do disco **sem
        revalidar**. Como o index é quem aponta para o bundle com hash, um
        index velho prende o usuário numa versão antiga inteira -- e a única
        saída vira `Ctrl+Shift+R`, que não é resposta que se dê a usuário.

        ⚠️ MEDE A RESPOSTA, não o fonte. Um `grep` por "no-cache" no `main.py`
        passaria com o cabeçalho num comentário; travas que mediram palavra já
        reprovaram código correto oito vezes neste projeto. Por isso aqui a
        requisição é feita e o cabeçalho é lido dela.

        ⚠️ Cliente próprio, sem `raise_server_exceptions`, para ler o cabeçalho
        bruto como o navegador leria.
        """
        if not main.FRONTEND.exists():
            pytest.skip("frontend/dist ainda não construído")
        r = TestClient(main.app).get("/")
        assert "no-cache" in r.headers.get("cache-control", ""), (
            "o index voltou a ser cacheável sem revalidação -- o usuário vai "
            "ficar preso numa versão antiga e nós vamos achar que é outra coisa")

    def test_o_asset_com_hash_NAO_ganha_no_cache(self, cliente):
        """⚠️ A outra metade, e ela importa: arquivo de /assets tem hash no
        nome, então nome novo é arquivo novo. Cache longo neles é o que faz a
        página abrir rápido -- pôr `no-cache` aqui trocaria um defeito por
        outro, mais silencioso."""
        if not main.FRONTEND.exists():
            pytest.skip("frontend/dist ainda não construído")
        assets = main.FRONTEND / "assets"
        js = next((a for a in assets.glob("index-*.js") if a.is_file()), None)
        if js is None:
            pytest.skip("build sem bundle nomeado com hash")
        r = cliente.get(f"/assets/{js.name}")
        assert r.status_code == 200
        assert "no-cache" not in r.headers.get("cache-control", "")

    def test_caminho_nao_escapa_do_dist(self, cliente):
        if not main.FRONTEND.exists():
            pytest.skip("frontend/dist ainda não construído")
        # Se a trava falhar, isto devolve o .env do projeto.
        r = cliente.get("/../.env")
        assert r.status_code in (200, 404)
        assert "MOVIZAP_JWT_SECRET" not in r.text
        assert "MOVIZAP_ADMIN_SENHA_HASH" not in r.text
