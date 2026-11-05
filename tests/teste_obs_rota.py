# -*- coding: utf-8 -*-
r"""As ROTAS das observações do card — o que a suíte não alcançava (05/11).

🚨 ESTE ARQUIVO NASCE DE UM DEFEITO QUE ELE VIU NA TELA: *"as observações não
estão abrindo e precisa funcionar, bem como anexar imagens e textos"*. Eram
três defeitos, e dois deles passavam porque **nada exercitava estas rotas**:

  1. `GET /api/paineis/operacao/ficha` **não tinha teste nenhum** — e no
     frontend ela é *mockada*, com o mock **assumindo** que o campo se chama
     `observacoes`. Nada provava que a rota o devolve com esse nome.
  2. `GET /api/paineis/operacao/anexo/{id}` nunca era exercida por cliente
     HTTP, então o **401** que todo clique levava nunca aparecia: a tela usava
     um `<a href>` puro contra uma rota `Bearer`, e navegação de link não manda
     cabeçalho `Authorization`.

⚠️ O terceiro defeito (o modal ficar atrás do card) é de EMPILHAMENTO e não é
alcançável aqui nem no jsdom — quem o prende é
`frontend/scripts/conferir_css_publicado.mjs`, que lê o CSS publicado.

🚨 E NADA AQUI FALA COM O HARMONIT: a ponte é trocada por dublê. O ponto de
metade destes testes é justamente **o que acontece quando o ERP cai**.

Roda:  venv/bin/python -m pytest tests/teste_obs_rota.py
"""
import pathlib
import sys

import pytest
from fastapi.testclient import TestClient

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from movizap import auth, banco, main, passagem  # noqa: E402

# 🚨 A OS DE TESTE É UM NÚMERO QUE NÃO EXISTE NO ERP, de propósito: nada aqui
# chega ao Harmonit (a ponte é dublada), e um número real arriscaria alguém
# copiar daqui para um script que escreve — foi o que aconteceu em 29/10, com a
# OS 17056 nascendo no cliente errado.
OS_TESTE = 999001


@pytest.fixture
def limpo(cliente):
    """Apaga so o que este arquivo cria, antes e depois.
    ⚠️ Depende do `cliente` porque o banco e aberto pelo lifespan do app."""
    def _apagar():
        banco.executar("DELETE FROM os_observacao WHERE numero_os = %s",
                       (OS_TESTE,))
    _apagar()
    yield
    _apagar()


@pytest.fixture(scope="module")
def cliente():
    """🚨 ESCOPO DE MODULO, e nao de funcao -- e a casa ja pagou por isto:
    o `ciclo_de_vida` do app cria objetos de asyncio no startup, e um SEGUNDO
    `TestClient` sobre o MESMO `app` tenta reusa-los num loop novo, dando
    `Event is bound to a different event loop`. O `teste_rotas_pipeline` tem o
    mesmo comentario, e eu repeti o erro antes de ler.
    ⚠️ E o `banco.abrir()` vem do lifespan do app -- abri-lo tambem numa
    fixture propria era a outra metade do mesmo conflito.
    """
    with TestClient(main.app) as c:
        yield c


@pytest.fixture(scope="module")
def cab(cliente):
    """⚠️ O token do OWNER: `PNL_1.1` e tela dele. Nada e escrito no ERP.
    ⚠️ Depende do `cliente` so para garantir que o app ja subiu e o banco
    esta aberto."""
    linha = banco.um("SELECT login FROM atendente WHERE owner AND ativo LIMIT 1")
    assert linha, "nao ha owner ativo para autenticar o teste"
    return {"Authorization": f"Bearer {auth.criar_token(linha['login'])}"}


# ============================================================================
# A rota própria — a que não depende do Harmonit
# ============================================================================
class TestARotaPropria:
    """🚨 ELA EXISTE PORQUE AS OBSERVAÇÕES DEPENDIAM DO ERP, e não deviam."""

    def test_devolve_as_observacoes_sem_tocar_a_ponte(self, cliente, cab,
                                                      limpo, monkeypatch):
        chamadas = []

        def nao_deveria(*a, **k):
            chamadas.append(a)
            raise AssertionError("esta rota NÃO pode falar com o Harmonit")

        monkeypatch.setattr(main.fpsl_ponte, "ficha_da_os", nao_deveria)
        passagem.observar(OS_TESTE, "zz recado de teste", atendente_id=None)

        r = cliente.get(
            f"/api/paineis/operacao/observacoes?numero_os={OS_TESTE}",
            headers=cab)
        assert r.status_code == 200, r.text
        corpo = r.json()
        assert corpo["numero_os"] == OS_TESTE
        assert [o["texto"] for o in corpo["observacoes"]] == ["zz recado de teste"]
        # 🚨 A prova: nenhuma ida à ponte.
        assert chamadas == []

    def test_cada_recado_vem_com_a_lista_de_anexos(self, cliente, cab, limpo):
        """⚠️ Lista vazia é resposta, não ausência de campo: a tela faz
        `recado.anexos && recado.anexos.length` e um campo ausente a faria
        depender de `undefined`."""
        passagem.observar(OS_TESTE, "zz sem anexo", atendente_id=None)
        r = cliente.get(
            f"/api/paineis/operacao/observacoes?numero_os={OS_TESTE}",
            headers=cab)
        assert r.json()["observacoes"][0]["anexos"] == []

    def test_o_caminho_de_disco_NAO_sai_na_resposta(self, cliente, cab, limpo):
        """🚨 O que identifica o anexo é o ID. O `caminho` é de dentro."""
        passagem.observar(OS_TESTE, "zz", atendente_id=None)
        r = cliente.get(
            f"/api/paineis/operacao/observacoes?numero_os={OS_TESTE}",
            headers=cab)
        assert "caminho" not in r.text
        assert "/home/claude" not in r.text

    def test_sem_recado_devolve_lista_vazia_e_200(self, cliente, cab, limpo):
        """⚠️ 200 com lista vazia, nunca 404: "esta OS não tem recado" é
        resposta, e 404 faria a tela dizer que a OS não existe."""
        r = cliente.get(
            f"/api/paineis/operacao/observacoes?numero_os={OS_TESTE}",
            headers=cab)
        assert r.status_code == 200
        assert r.json()["observacoes"] == []

    def test_sem_sessao_nao_passa(self, cliente):
        assert cliente.get(
            f"/api/paineis/operacao/observacoes?numero_os={OS_TESTE}"
        ).status_code in (401, 403)

    @pytest.mark.parametrize("torto", ["0", "-1", "abc", ""])
    def test_numero_torto_e_recusado(self, cliente, cab, torto):
        r = cliente.get(
            f"/api/paineis/operacao/observacoes?numero_os={torto}", headers=cab)
        assert r.status_code == 422


# ============================================================================
# A ficha — o teste que faltava, e o nome do campo
# ============================================================================
class TestAFichaEOCampo:

    def test_a_ficha_devolve_o_campo_chamado_observacoes(self, cliente, cab,
                                                         limpo, monkeypatch):
        """🚨 ERA UMA SUPOSIÇÃO: no frontend esta rota é mockada, e o mock
        *assume* que o campo se chama `observacoes`. Se a rota o renomeasse, a
        suíte continuaria verde e a tela ficaria vazia."""
        monkeypatch.setattr(main.fpsl_ponte, "ficha_da_os",
                            lambda numero_os: {"numero_os": numero_os,
                                               "descricao": "zz"})
        passagem.observar(OS_TESTE, "zz da ficha", atendente_id=None)
        r = cliente.get(f"/api/paineis/operacao/ficha?numero_os={OS_TESTE}",
                        headers=cab)
        assert r.status_code == 200, r.text
        corpo = r.json()
        assert "observacoes" in corpo, "o nome do campo mudou e a tela quebraria"
        assert corpo["observacoes"][0]["texto"] == "zz da ficha"
        assert corpo["observacoes"][0]["anexos"] == []

    def test_ponte_caida_vira_502_e_NAO_ficha_vazia(self, cliente, cab,
                                                    monkeypatch):
        """🚨 Ficha vazia é indistinguível de OS sem dados."""
        def estourar(numero_os):
            raise RuntimeError("zz ponte fora do ar")

        monkeypatch.setattr(main.fpsl_ponte, "ficha_da_os", estourar)
        r = cliente.get(f"/api/paineis/operacao/ficha?numero_os={OS_TESTE}",
                        headers=cab)
        assert r.status_code == 502
        assert "Harmonit" in r.json()["detail"]

    def test_as_duas_rotas_leem_O_MESMO(self, cliente, cab, limpo, monkeypatch):
        """⚠️ Duas leituras do mesmo dado em dois lugares divergiriam na
        primeira mudança — por isso as duas rotas usam o mesmo leitor."""
        monkeypatch.setattr(main.fpsl_ponte, "ficha_da_os",
                            lambda numero_os: {"numero_os": numero_os})
        passagem.observar(OS_TESTE, "zz igual", atendente_id=None)
        da_ficha = cliente.get(
            f"/api/paineis/operacao/ficha?numero_os={OS_TESTE}",
            headers=cab).json()["observacoes"]
        da_rota = cliente.get(
            f"/api/paineis/operacao/observacoes?numero_os={OS_TESTE}",
            headers=cab).json()["observacoes"]
        assert [o["texto"] for o in da_ficha] == [o["texto"] for o in da_rota]


# ============================================================================
# O anexo — o 401 que ninguém via
# ============================================================================
class TestODownloadDoAnexo:
    """🚨 A tela usava `<a href>` contra esta rota, e **navegação de link não
    manda cabeçalho `Authorization`** — todo clique era 401. O arquivo subia e
    nunca voltava, e `os_observacao_arquivo` tinha ZERO linhas, então ninguém
    chegou a notar."""

    def test_sem_cabecalho_e_401(self, cliente):
        """É exatamente o que o `<a href>` produzia."""
        assert cliente.get(
            "/api/paineis/operacao/anexo/999999").status_code in (401, 403)

    def test_com_cabecalho_e_anexo_inexistente_e_404(self, cliente, cab):
        """⚠️ A prova de que a autenticação não é o que barra quem tem sessão:
        com o cabeçalho, a resposta passa a falar do ARQUIVO, não da sessão."""
        r = cliente.get("/api/paineis/operacao/anexo/999999", headers=cab)
        assert r.status_code in (404, 410), r.text
        assert r.status_code != 401
