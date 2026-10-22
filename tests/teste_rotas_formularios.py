"""As ROTAS dos formulários e do painel — o que a auditoria de 22/10 achou.

🚨 POR QUE ESTE ARQUIVO EXISTE. Ele perguntou *"quer documentar e auditar os
feitos?"*, e a auditoria mediu três coisas:

  1. **as dez rotas que entraram hoje não tinham teste HTTP nenhum** -- e 17
     arquivos desta suíte usam `TestClient`. A rota pública de envio é a
     superfície mais exposta do projeto (qualquer um na internet a alcança) e
     estava provada só por `curl` meu, à mão;
  2. `formularios.listar_solicitacoes` e `formularios.lista_para_o_painel` --
     o que a FRM_1.1 mostra na lista e no cabeçalho -- não eram chamadas por
     teste nenhum;
  3. `registrar_envio`, `desafio_sempre` e a desduplicação de `nome_legivel`
     também não.

⚠️ É a mesma lição de 21/10, quando a auditoria dele achou três módulos em
produção sem teste Python: **prova ao vivo não substitui teste**. O `curl` que
eu rodei provou o dia; só o teste prova a semana que vem.

🚨 ESCREVE EM TABELAS DE PRODUÇÃO, como o resto da suíte: o formulário de
teste tem código `ZZ_TESTE_ROTA` e é apagado no fim, e as solicitações que o
POST público cria saem com ele.

⚠️ E NÃO TOCA NA `config`: `desafio_sempre` é lido com o banco dobrado, nunca
escrito -- foi um teste meu escrevendo em `config` que desligou a distribuição
de produção por nove minutos em 19/10.

🚨 **E ESTE ARQUIVO JÁ ERROU UMA VEZ, NA PRIMEIRA VERSÃO:** ele passou na
primeira rodada e reprovou na segunda. Cada envio bom chama
`registrar_envio`, que conta no **SQLite do `ratelimit`** -- e esse contador
**sobrevive ao processo e ao restart**, de propósito. Em duas rodadas os
envios de teste passaram de 5 na mesma hora e a rota passou a exigir a conta
de somar, então todo teste seguinte recebia *"Responda a conta para enviar"*
no lugar da frase esperada.

**Remédio:** a fixture `contador_limpo` apaga os eventos da chave deste
cliente (`formulario|testclient`) antes e depois de cada teste. ⚠️ Ela mexe só
nessa chave: o contador dos IPs de verdade é de produção e não se toca. E o
caminho do desafio continua exercitado -- há dois testes que o forçam.
"""
import json
import sys
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, "/home/claude/movizap_painel")
pytest.importorskip("psycopg")

from movizap import auth, banco, formularios, main, paineis  # noqa: E402
from movizap.config import settings  # noqa: E402

RAIZ = Path("/home/claude/movizap_painel")
MAPA = json.loads((RAIZ / "dados" / "formularios_bitrix" / "mapa_bruto.json")
                  .read_text(encoding="utf-8"))

CODIGO = "ZZ_TESTE_ROTA"
SLUG = "zz-teste-rota"


@pytest.fixture(scope="module", autouse=True)
def pool():
    banco.abrir()
    yield


@pytest.fixture(autouse=True)
def contador_limpo():
    """🚨 O contador de envios por IP vive num SQLite que sobrevive ao
    processo. Sem isto, a 6ª requisição desta suíte passa a exigir a conta de
    somar e todo teste seguinte reprova com a frase errada -- foi o que
    aconteceu na segunda rodada.

    ⚠️ Apaga SÓ a chave do `TestClient`. O contador dos IPs reais é de
    produção.
    """
    import sqlite3
    from movizap import ratelimit

    def zerar():
        try:
            with sqlite3.connect(ratelimit.ARQUIVO) as conn:
                conn.execute("DELETE FROM eventos WHERE chave = ?",
                             ("formulario|testclient",))
        except sqlite3.Error:
            pass   # contador fora do ar não reprova teste nenhum

    zerar()
    yield
    zerar()


@pytest.fixture
def cliente():
    # `with` para o lifespan rodar também no caminho HTTP (ver teste_canais).
    with TestClient(main.app) as c:
        yield c


@pytest.fixture
def token():
    """O login do .env é o do OWNER -- é o que dá para exercitar rota de
    owner. ⚠️ Testar a RECUSA de quem não é owner se faz no registro de telas
    (`tests/teste_paineis.py`), sem criar conta de mentira."""
    return auth.criar_token(settings.admin_login)


@pytest.fixture
def formulario(request):
    """Um formulário de teste. `request.param` liga (True) ou não."""
    ligado = getattr(request, "param", True)

    def apagar():
        banco.executar(
            """DELETE FROM formulario_solicitacao
                WHERE formulario_id IN (SELECT id FROM formulario
                                         WHERE codigo = %s)""", (CODIGO,))
        banco.executar("DELETE FROM formulario WHERE codigo = %s", (CODIGO,))

    apagar()
    formularios.gravar_definicao(MAPA["70"], codigo=CODIGO, slug=SLUG,
                                 setor="Teste", titulo="zz Teste de rota",
                                 painel="operacao")
    if ligado:
        banco.executar("UPDATE formulario SET ativo = true WHERE codigo = %s",
                       (CODIGO,))
    yield formularios.definicao(SLUG, so_ativo=False)
    apagar()


def abertura_valida():
    """Uma abertura com idade suficiente, assinada como a de verdade.

    ⚠️ Sem isto o teste teria de DORMIR 3 s por envio. Assinar um carimbo
    antigo exercita o mesmo caminho -- o que se prova é a conferência, não o
    relógio.
    """
    velho = int(time.time()) - formularios.SEGUNDOS_MINIMOS - 1
    return formularios._assinar(f"a{velho}")


def valores_bons(d):
    nota = next(c for c in d["campos"] if c["tipo"] == "list")
    return {
        "CONTACT_NAME": "zz Rota",
        "CONTACT_LAST_NAME": "zz Teste",
        nota["nome"]: str(nota["opcoes"][0]["value"]),
    }


# ============================================================================
# As três rotas públicas
# ============================================================================
class TestFormularioPublico:
    def test_a_definicao_sai_sem_token(self, cliente, formulario):
        r = cliente.get(f"/api/publico/formulario/{SLUG}")
        assert r.status_code == 200
        assert len(r.json()["campos"]) == 5

    def test_o_que_e_interno_NAO_sai(self, cliente, formulario):
        """🚨 `nosso_nome`, `problema_id` e o id do Bitrix são nomes internos e
        números de catálogo. O que não sai não vaza."""
        corpo = r"{}".format(cliente.get(f"/api/publico/formulario/{SLUG}").text)
        for interno in ("nosso_nome", "problema_id", "bitrix_id", "bitrix_sec",
                        "gera_os", "ativo"):
            assert interno not in corpo, interno

    def test_a_definicao_traz_a_abertura_assinada(self, cliente, formulario):
        """O carimbo de "abriu agora" é o que mede o tempo de preenchimento."""
        assert "." in cliente.get(f"/api/publico/formulario/{SLUG}").json()["abertura"]

    @pytest.mark.parametrize("formulario", [False], indirect=True)
    def test_formulario_desligado_responde_404(self, cliente, formulario):
        """🚨 A MESMA resposta de slug inexistente, de propósito: um 404 que
        distingue os dois conta ao mundo quais formulários a casa tem."""
        assert cliente.get(f"/api/publico/formulario/{SLUG}").status_code == 404
        assert cliente.get("/api/publico/formulario/nao-existe").status_code == 404

    @pytest.mark.parametrize("formulario", [False], indirect=True)
    def test_envio_para_formulario_desligado_tambem_e_404(self, cliente, formulario):
        r = cliente.post(f"/api/publico/formulario/{SLUG}",
                         data={"valores": "{}", "abertura": abertura_valida()})
        assert r.status_code == 404


class TestEnvioPublico:
    def test_obrigatorio_e_recusado_na_ROTA(self, cliente, formulario):
        """🚨 O mesmo buraco do Bitrix, agora provado pelo caminho HTTP: lá o
        `values=[]` vazio foi aceito e criou o registro 15620."""
        r = cliente.post(f"/api/publico/formulario/{SLUG}",
                         data={"valores": "{}", "abertura": abertura_valida()})
        assert r.status_code == 400
        assert "Primeiro Nome" in r.json()["detail"]

    def test_envio_bom_grava_e_devolve_o_id(self, cliente, formulario):
        r = cliente.post(f"/api/publico/formulario/{SLUG}",
                         data={"valores": json.dumps(valores_bons(formulario)),
                               "abertura": abertura_valida()})
        assert r.status_code == 201
        ident = r.json()["id"]
        lida = formularios.uma(ident)
        assert lida["estado"] == "nova"
        assert lida["slug"] == SLUG

    def test_isca_responde_sucesso_e_NAO_grava(self, cliente, formulario):
        """🚨 Recusa silenciosa: robô que toma erro aprende a tentar de outro
        jeito. A resposta é a mesma de sempre, e o banco não muda."""
        antes = banco.um("SELECT count(*) AS n FROM formulario_solicitacao")["n"]
        r = cliente.post(f"/api/publico/formulario/{SLUG}",
                         data={"valores": json.dumps(valores_bons(formulario)),
                               "abertura": abertura_valida(), "isca": "robo"})
        assert r.status_code == 201
        assert "id" not in r.json()
        assert banco.um("SELECT count(*) AS n FROM formulario_solicitacao")["n"] == antes

    def test_rapido_demais_e_recusado(self, cliente, formulario):
        r = cliente.post(f"/api/publico/formulario/{SLUG}",
                         data={"valores": json.dumps(valores_bons(formulario)),
                               "abertura": formularios.abertura()})
        assert r.status_code == 400

    def test_sem_abertura_e_recusado(self, cliente, formulario):
        """Quem chama a rota por fora da nossa página não traz o carimbo."""
        r = cliente.post(f"/api/publico/formulario/{SLUG}",
                         data={"valores": json.dumps(valores_bons(formulario))})
        assert r.status_code == 400

    def test_json_quebrado_e_recusado_com_frase_legivel(self, cliente, formulario):
        r = cliente.post(f"/api/publico/formulario/{SLUG}",
                         data={"valores": "isto nao e json",
                               "abertura": abertura_valida()})
        assert r.status_code == 400
        assert "dados" in r.json()["detail"].lower()

    def test_anexo_em_campo_que_nao_aceita_arquivo_e_recusado(self, cliente, formulario):
        """⚠️ Os anexos chegam em duas listas paralelas; o servidor confere o
        par. O CES não tem campo de arquivo nenhum."""
        r = cliente.post(
            f"/api/publico/formulario/{SLUG}",
            data={"valores": json.dumps(valores_bons(formulario)),
                  "abertura": abertura_valida(), "campos": "CONTACT_NAME"},
            files={"arquivos": ("prova.pdf", b"%PDF-", "application/pdf")})
        assert r.status_code == 400
        assert "arquivo" in r.json()["detail"].lower()

    def test_desafio_e_pedido_quando_o_IP_estoura(self, cliente, formulario, monkeypatch):
        """🔵 *"captcha no final"*: só depois de 5 envios do mesmo IP na hora."""
        monkeypatch.setattr(formularios, "exige_desafio", lambda ip: True)
        r = cliente.post(f"/api/publico/formulario/{SLUG}",
                         data={"valores": json.dumps(valores_bons(formulario)),
                               "abertura": abertura_valida()})
        assert r.status_code == 400
        assert "conta" in r.json()["detail"].lower()

    def test_a_conta_certa_deixa_enviar(self, cliente, formulario, monkeypatch):
        import re
        monkeypatch.setattr(formularios, "exige_desafio", lambda ip: True)
        desafio = formularios.novo_desafio()
        certa = sum(int(n) for n in re.findall(r"\d+", desafio["pergunta"]))
        r = cliente.post(f"/api/publico/formulario/{SLUG}",
                         data={"valores": json.dumps(valores_bons(formulario)),
                               "abertura": abertura_valida(),
                               "desafio_token": desafio["token"],
                               "desafio_resposta": str(certa)})
        assert r.status_code == 201

    def test_a_rota_do_desafio_serve_uma_conta(self, cliente):
        r = cliente.get("/api/publico/desafio")
        assert r.status_code == 200
        assert "+" in r.json()["pergunta"]


# ============================================================================
# As rotas do painel (FRM_1.1) — o que a lista e o cabeçalho mostram
# ============================================================================
class TestRotasDoPainelDeSolicitacoes:
    def test_sem_token_nao_passa(self, cliente):
        for rota in ("/api/formularios", "/api/solicitacoes",
                     "/api/paineis/operacao"):
            assert cliente.get(rota).status_code == 401, rota

    def test_a_lista_de_formularios_conta_as_novas(self, cliente, token, formulario):
        """Fecha o buraco do `lista_para_o_painel`, que a FRM_1.1 usa no
        cabeçalho e que teste nenhum chamava."""
        formularios.registrar(formulario, {"CONTACT_NAME": "zz Rota"})
        r = cliente.get("/api/formularios", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200
        meu = next(f for f in r.json() if f["codigo"] == CODIGO)
        assert meu["novas"] == 1
        assert meu["solicitacoes"] == 1

    def test_a_lista_filtra_por_formulario_e_por_estado(self, cliente, token, formulario):
        """Fecha o buraco do `listar_solicitacoes` com os filtros da tela."""
        ident = formularios.registrar(formulario, {"CONTACT_NAME": "zz Rota"})["id"]
        cab = {"Authorization": f"Bearer {token}"}

        so_meu = cliente.get(f"/api/solicitacoes?formulario={SLUG}", headers=cab).json()
        assert [s["id"] for s in so_meu] == [ident]

        novas = cliente.get(f"/api/solicitacoes?formulario={SLUG}&estado=nova",
                            headers=cab).json()
        assert [s["id"] for s in novas] == [ident]

        formularios.definir_estado(ident, "concluida", None)
        assert cliente.get(f"/api/solicitacoes?formulario={SLUG}&estado=nova",
                           headers=cab).json() == []

    def test_estado_inventado_no_filtro_e_recusado(self, cliente, token):
        r = cliente.get("/api/solicitacoes?estado=arquivada",
                        headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 400

    def test_a_ficha_traz_o_rotulo_e_nao_o_nome_de_origem(self, cliente, token, formulario):
        ident = formularios.registrar(formulario, {"CONTACT_NAME": "zz Rota"})["id"]
        r = cliente.get(f"/api/solicitacoes/{ident}",
                        headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200
        assert r.json()["respostas"][0]["rotulo"] == "Primeiro Nome"

    def test_solicitacao_inexistente_e_404(self, cliente, token):
        r = cliente.get("/api/solicitacoes/99999999",
                        headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 404

    def test_anexo_inexistente_e_404(self, cliente, token, formulario):
        ident = formularios.registrar(formulario, {"CONTACT_NAME": "zz Rota"})["id"]
        r = cliente.get(f"/api/solicitacoes/{ident}/arquivo/99999999",
                        headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 404

    @pytest.mark.parametrize("formulario", [False], indirect=True)
    def test_o_owner_liga_e_desliga_o_formulario(self, cliente, token, formulario):
        cab = {"Authorization": f"Bearer {token}"}
        r = cliente.put(f"/api/formularios/{CODIGO}/ativo", json={"ativo": True},
                        headers=cab)
        assert r.status_code == 200 and r.json()["ativo"] is True
        # 🚨 A prova é RELER o estado, não o retorno da escrita.
        assert cliente.get(f"/api/publico/formulario/{SLUG}").status_code == 200
        cliente.put(f"/api/formularios/{CODIGO}/ativo", json={"ativo": False},
                    headers=cab)
        assert cliente.get(f"/api/publico/formulario/{SLUG}").status_code == 404

    def test_ligar_formulario_que_nao_existe_e_404(self, cliente, token):
        r = cliente.put("/api/formularios/NAO_EXISTE/ativo", json={"ativo": True},
                        headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 404


# ============================================================================
# A rota do painel
# ============================================================================
class TestRotaDoPainel:
    def test_o_painel_da_operacao_responde_com_as_13_colunas(self, cliente, token):
        r = cliente.get("/api/paineis/operacao",
                        headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200
        assert len(r.json()["colunas"]) == len(paineis.SITUACOES) + 2
        assert r.json()["pode_mover"] is False

    @pytest.mark.parametrize("painel", ["pos_venda", "contratual", "financeiro"])
    def test_os_tres_sem_tela_respondem_400_dizendo_o_que_sao(self, cliente, token, painel):
        r = cliente.get(f"/api/paineis/{painel}",
                        headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 400
        assert "ainda não existe" in r.json()["detail"]

    def test_painel_inventado_tambem_e_400(self, cliente, token):
        r = cliente.get("/api/paineis/marketing",
                        headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 400


# ============================================================================
# As três funções que a auditoria achou sem chamada
# ============================================================================
def teste_registrar_envio_conta_por_ip(monkeypatch):
    contados = []
    monkeypatch.setattr(formularios.ratelimit, "registrar_evento", contados.append)
    formularios.registrar_envio("203.0.113.7")
    assert contados == ["formulario|203.0.113.7"]
    # ⚠️ Sem IP não conta nada -- e não estoura.
    formularios.registrar_envio(None)
    assert len(contados) == 1


def teste_desafio_sempre_nasce_desligado(monkeypatch):
    """⚠️ Lido com o banco DOBRADO: este teste não escreve na `config`, e o
    motivo está no cabeçalho do arquivo."""
    monkeypatch.setattr(formularios.banco, "um", lambda *a, **k: None)
    assert formularios.desafio_sempre() is False
    monkeypatch.setattr(formularios.banco, "um", lambda *a, **k: {"valor": "true"})
    assert formularios.desafio_sempre() is True


def teste_nome_legivel_desduplica():
    """Dois campos com o mesmo rótulo não podem virar o mesmo `nosso_nome`:
    a solicitação ficaria ambígua justamente na leitura."""
    usados = set()
    assert formularios.nome_legivel("E-mail", "CONTACT_EMAIL", usados) == "e-mail"
    assert formularios.nome_legivel("E-mail", "COMPANY_EMAIL", usados) == "e-mail-2"
    assert formularios.nome_legivel("", "DEAL_UF_CRM_123", usados) == "deal-uf-crm-123"


def teste_resumo_do_card_pega_as_duas_primeiras_respostas():
    assert paineis._resumo({"a": "um", "b": "dois", "c": "tres"}) == "um · dois"
    # ⚠️ Número não entra no resumo: card não é ficha, e valor solto sem
    # rótulo não diz nada a quem lê.
    assert paineis._resumo({"a": 10, "b": "texto"}) == "texto"
    assert paineis._resumo({}) == ""
