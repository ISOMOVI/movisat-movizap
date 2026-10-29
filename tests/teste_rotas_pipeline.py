"""As rotas do pipeline da operação POR HTTP — Blocos A e B (29/10).

🚨 ESTE ARQUIVO NASCEU DE UMA AUDITORIA DELE, no mesmo dia da entrega:
*"auditou e validou o entregue? as rotas?"*. A resposta era **não**: das 4
rotas que entraram hoje, **3 não tinham teste HTTP nenhum** — enquanto 58
arquivos desta suíte usam `TestClient`.

⚠️ É O MESMO ACHADO DA AUDITORIA DE 22/10, sete dias depois: *"as 10 rotas
novas sem teste HTTP"*. Testar a função não é testar a rota: a permissão, o
código de estado, a validação do parâmetro e a serialização só existem no
caminho HTTP.

O que estas travas guardam, e por quê:

  · 🚨 **a data matriz é do OWNER** — `PNL_1.1` abre o painel para a operação
    inteira, e mover a data muda o que **todos** veem. Quem tem a aba e não é
    owner leva **403**;
  · 🚨 **a rota pública de envio ABRE A OS**, e a falha dela **não derruba o
    envio**: o cliente já leu "recebemos", e um ERP fora do ar não pode virar
    chamado perdido. Isto é o coração do Bloco A e não tinha nenhum teste de
    ponta a ponta;
  · o interruptor `so_abertas` atravessa a rota até a ponte;
  · parâmetro torto é **recusado**, não interpretado.

⚠️ A PONTE É TROCADA POR DUBLÊ em tudo: nenhum teste desta casa cria OS no ERP.
"""
import json
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, "/home/claude/movizap_painel")
sys.path.insert(0, "/home/claude/movizap_painel/scripts")
pytest.importorskip("psycopg")

from fastapi.testclient import TestClient  # noqa: E402

import carregar_formularios as carregador  # noqa: E402
from movizap import (auth, banco, chamado_os, formularios, main,  # noqa: E402
                     paineis, passagem)
from movizap.config import settings  # noqa: E402

RAIZ = Path("/home/claude/movizap_painel")
MAPA = json.loads((RAIZ / "dados" / "formularios_bitrix" / "mapa_bruto.json")
                  .read_text(encoding="utf-8"))

CODIGO = "ZZ_TESTE_ROTA_PIPE"
SLUG = "zz-teste-rota-pipe"
BITRIX_SUPORTE = "32"


@pytest.fixture(scope="module", autouse=True)
def pool():
    banco.abrir()
    yield


@pytest.fixture(scope="module")
def cliente():
    """🚨 ESCOPO DE MODULO, e nao de funcao como nas outras suites: o
    `ciclo_de_vida` do app cria objetos de asyncio no startup, e um SEGUNDO
    `TestClient` sobre o MESMO objeto `app` tenta reusa-los num loop novo --
    `Event is bound to a different event loop`. Medido hoje: os testes passam
    um por um e tres falham no arquivo inteiro.

    ⚠️ O preco e que o estado do processo (o contador do `ratelimit`) atravessa
    os testes deste arquivo, e e por isso que o envio monkeypatcha
    `exige_desafio` em vez de contar com o contador zerado.
    """
    with TestClient(main.app) as c:
        yield c


@pytest.fixture
def token():
    """O token do owner."""
    return auth.criar_token(settings.admin_login)


def _valores_bons(d: dict) -> dict:
    """Valores que a validacao do servidor ACEITA, campo por campo.

    🚨 ISTO NASCEU DE UM PULO: a primeira versao enchia tudo com `"x"` e os
    dois testes mais importantes do Bloco A ficavam em `skip` -- com o placar
    verde. Teste que pula e teste que nao existe, e e o segundo pulo silencioso
    que esta frente me custa no mesmo dia.

    ⚠️ Campo de lista vai pela OPCAO, documento vai com digito verificador real
    (o CNPJ da Velasco, alfanumerico, que foi ele quem achou), e a pergunta
    PF/PJ decide quais campos a regra condicional mostra -- entao o valor dela
    nao e escolha livre: `1756` e Pessoa Juridica, e e o que faz `empresa` e
    `cnpj` serem visiveis e `cpf` nao.
    """
    saida: dict = {}
    visiveis = None
    for campo in d["campos"]:
        if campo["tipo"] == "file":
            continue
        nome, regra = campo["nome"], campo.get("validacao")
        if campo["tipo"] == "list":
            opcoes = campo.get("opcoes") or []
            if not opcoes:
                continue
            # A pergunta PF/PJ: Pessoa Juridica, para `empresa` e `cnpj`
            # entrarem na conta (sao eles que resolvem o cliente).
            escolha = next((o["value"] for o in opcoes
                            if str(o["value"]) == "1756"), opcoes[0]["value"])
            saida[nome] = str(escolha)
        elif regra == "cnpj":
            saida[nome] = "WQ0P6GLD000108"
        elif regra == "cpf":
            saida[nome] = "11144477735"
        elif regra == "email":
            saida[nome] = "zz@teste.com.br"
        elif regra == "telefone":
            saida[nome] = "18998116168"
        elif regra == "placa":
            continue
        else:
            saida[nome] = "zz teste"

    # 🚨 O servidor APAGA do registro o campo escondido por regra, e a
    # validacao so cobra o que esta VISIVEL. Mandar o `cpf` junto com o `cnpj`
    # nao e erro -- e o `visiveis` que decide. Deixa-se os dois: o caminho real
    # tambem manda o que a tela tinha.
    del visiveis
    return saida


def _abertura_valida() -> str:
    """Uma abertura com idade suficiente, assinada como a de verdade.

    ⚠️ Copiada da suite de rotas de 22/10 pelo mesmo motivo: sem isto o teste
    dormiria 3 s por envio, e o que se prova e a conferencia, nao o relogio.
    """
    velho = int(time.time()) - formularios.SEGUNDOS_MINIMOS - 1
    return formularios._assinar(f"a{velho}")


def _apagar():
    banco.executar(
        """DELETE FROM solicitacao_os
            WHERE solicitacao_id IN (
                SELECT s.id FROM formulario_solicitacao s
                  JOIN formulario f ON f.id = s.formulario_id
                 WHERE f.codigo = %s)""", (CODIGO,))
    banco.executar(
        """DELETE FROM formulario_solicitacao
            WHERE formulario_id IN (SELECT id FROM formulario
                                     WHERE codigo = %s)""", (CODIGO,))
    banco.executar("DELETE FROM formulario WHERE codigo = %s", (CODIGO,))


@pytest.fixture
def formulario():
    """Um Suporte de teste no painel da Operação, que ABRE OS.

    ⚠️ Nasce com as `validacoes` e os `ajustes` do próprio carregador: sem eles
    nenhum campo tem `validacao` nem `fonte`, e metade das travas mediria o
    formulário errado. Foi um defeito da minha suíte de hoje.
    """
    _apagar()
    formularios.gravar_definicao(
        MAPA[BITRIX_SUPORTE], codigo=CODIGO, slug=SLUG, setor="Teste",
        titulo="zz Teste rota pipeline", painel="operacao", formato="novo",
        etapas=carregador.ETAPAS["SUPORTE"],
        validacoes=carregador.VALIDACOES["SUPORTE"],
        ajustes=carregador.AJUSTES["SUPORTE"])
    # 🚨 O FORMULARIO NASCE DESLIGADO, e isso e o desenho desta casa (o
    # interruptor e dele). A rota publica usa `definicao(slug)` com
    # `so_ativo=True`, entao sem este `UPDATE` o envio responde **404
    # "Formulario nao encontrado"** -- e foi exatamente o que aconteceu aqui.
    banco.executar("UPDATE formulario SET ativo = true WHERE codigo = %s",
                   (CODIGO,))
    chamado_os.PROBLEMA_POR_FORMULARIO[SLUG] = 12760
    yield formularios.definicao(SLUG, so_ativo=False)
    chamado_os.PROBLEMA_POR_FORMULARIO.pop(SLUG, None)
    _apagar()


# ============================================================================
# PUT /api/paineis/operacao/desde — a data matriz é do OWNER (D9)
# ============================================================================
class TestADataMatriz:
    def test_sem_token_nao_passa(self, cliente):
        r = cliente.put("/api/paineis/operacao/desde",
                        json={"desde": "2026-10-20"})
        assert r.status_code in (401, 403)

    def test_o_owner_grava_e_a_leitura_confirma(self, cliente, token):
        """A prova é RELER o estado, nunca o retorno da escrita."""
        anterior = paineis.data_matriz()
        try:
            r = cliente.put("/api/paineis/operacao/desde",
                            json={"desde": "2026-10-20"},
                            headers={"Authorization": f"Bearer {token}"})
            assert r.status_code == 200, r.text
            assert paineis.data_matriz() == "2026-10-20"
            # 🚨 E o quadro passa a DIZER a data nova -- é o que a tela mostra.
            q = cliente.get("/api/paineis/operacao",
                            headers={"Authorization": f"Bearer {token}"})
            assert q.json()["desde"] == "2026-10-20"
        finally:
            paineis.definir_data_matriz(anterior)

    @pytest.mark.parametrize("torta", ["24/10/2026", "2026-13-01", "ontem", ""])
    def test_data_torta_e_recusada(self, cliente, token, torta):
        """⚠️ Um `desde` torto faria a ponte recusar com 422 e a tela abrir
        vazia -- sem dizer por quê."""
        antes = paineis.data_matriz()
        r = cliente.put("/api/paineis/operacao/desde", json={"desde": torta},
                        headers={"Authorization": f"Bearer {token}"})
        assert r.status_code in (400, 422), r.text
        assert paineis.data_matriz() == antes

    def test_quem_nao_e_owner_leva_403(self):
        """🚨 A PERMISSÃO DA TELA NÃO BASTA, e é o ponto desta rota: `PNL_1.1`
        abre o painel para a operação inteira, e mover a data matriz muda o que
        TODOS veem. Mesma régua do carimbo do nome (05/10).

        ⚠️ Chama a FUNÇÃO da rota com um usuário não-owner, porque a dependência
        de sessão já está montada no app e trocá-la aqui não a alcançaria. O
        que se mede é a guarda do owner, que é a linha que esta rota acrescenta
        à permissão da tela.
        """
        from fastapi import HTTPException

        antes = paineis.data_matriz()
        with pytest.raises(HTTPException) as e:
            main.definir_desde_do_painel(
                dados=main.DataMatrizDoPainel(desde="2026-10-20"),
                usuario={"owner": False, "login": "zz", "nome": "zz"})
        assert e.value.status_code == 403
        assert "owner" in str(e.value.detail)
        # 🚨 E não gravou nada: recusa que grava é pior que recusa nenhuma.
        assert paineis.data_matriz() == antes


# ============================================================================
# GET /api/paineis/{painel} — o interruptor e a recusa
# ============================================================================
class TestOQuadro:
    def test_sem_token_nao_passa(self, cliente):
        assert cliente.get("/api/paineis/operacao").status_code in (401, 403)

    def test_o_quadro_responde_com_as_seis_chaves_que_a_tela_le(
            self, cliente, token):
        r = cliente.get("/api/paineis/operacao",
                        headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200, r.text
        q = r.json()
        for chave in ("colunas", "total", "desde", "so_abertas",
                      "ponte_respondeu", "fora_do_quadro", "pode_mover"):
            assert chave in q, chave
        assert len(q["colunas"]) == 17
        # 🚨 ESTA LINHA AFIRMAVA O CONTRARIO HA UMA HORA, e e o segundo teste
        # meu de hoje a guardar a verdade antiga (o primeiro exigia a palavra
        # "Harmonit" numa frase errada). Mover passou a existir no Bloco D:
        # *"O card pode ser por arrastar"*. A verdade do gesto continua sendo
        # este campo -- o que mudou e o valor dele.
        assert q["pode_mover"] is True

    def test_o_interruptor_atravessa_a_rota(self, cliente, token):
        cab = {"Authorization": f"Bearer {token}"}
        assert cliente.get("/api/paineis/operacao?so_abertas=1",
                           headers=cab).json()["so_abertas"] is True
        assert cliente.get("/api/paineis/operacao?so_abertas=0",
                           headers=cab).json()["so_abertas"] is False

    @pytest.mark.parametrize("valor", ["2", "-1", "sim"])
    def test_interruptor_torto_e_recusado(self, cliente, token, valor):
        r = cliente.get(f"/api/paineis/operacao?so_abertas={valor}",
                        headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 422

    def test_os_tres_paineis_sem_tela_recusam_com_frase(self, cliente, token):
        """⚠️ Não é 404: 404 faria parecer erro de digitação. A frase diz que a
        tela ainda não existe."""
        cab = {"Authorization": f"Bearer {token}"}
        for painel in ("pos_venda", "contratual", "financeiro"):
            r = cliente.get(f"/api/paineis/{painel}", headers=cab)
            assert r.status_code == 400, r.text
            assert "ainda não existe" in r.text

    def test_painel_desconhecido_recusa(self, cliente, token):
        r = cliente.get("/api/paineis/marte",
                        headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 400

    def test_a_falha_de_os_contada_e_SO_a_deste_painel(
            self, cliente, token, formulario, monkeypatch):
        """🚨 DEFEITO ACHADO NESTA AUDITORIA: `falhas_em_aberto` não filtrava
        por painel, e a linha de aviso da Operação somava falha de chamado do
        Financeiro e do Contratual. Hoje não há falha na base, então nada se
        via -- era latente."""
        def recusar(**kwargs):
            return {"ok": False, "criada": False, "motivo": "zz teste"}

        monkeypatch.setattr(chamado_os.fpsl_ponte, "criar_os", recusar)
        d = formulario
        sid = formularios.registrar(d, {})["id"]
        chamado_os.abrir(sid, d, {}, cliente_id=68546)

        cab = {"Authorization": f"Bearer {token}"}
        operacao = cliente.get("/api/paineis/operacao",
                               headers=cab).json()["fora_do_quadro"]
        assert operacao["os_falhou"] >= 1
        # 🚨 E a conta da casa inteira é OUTRA função, de propósito.
        assert chamado_os.falhas_em_aberto()["quantas"] >= operacao["os_falhou"]
        assert chamado_os.falhas_em_aberto("contratual")["quantas"] == 0


# ============================================================================
# POST /api/publico/formulario/{slug} — o envio ABRE A OS (Bloco A)
# ============================================================================
class TestOEnvioAbreAOS:
    """🚨 O CORAÇÃO DO BLOCO A, e não tinha nenhum teste de ponta a ponta."""

    def _enviar(self, cliente, d, valores, monkeypatch):
        # ⚠️ A isca, o tempo minimo e o teto por IP sao as camadas entre a
        # internet e a criacao de OS no ERP, e NENHUMA delas e desligada aqui:
        # a abertura e assinada ANTIGA, como a suite de rotas de 22/10 ja faz,
        # porque o que se prova e a conferencia e nao o relogio.
        monkeypatch.setattr(formularios, "exige_desafio", lambda ip: False)
        return cliente.post(
            f"/api/publico/formulario/{d['slug']}",
            data={"valores": json.dumps(valores),
                  "abertura": _abertura_valida()})

    def test_o_envio_cria_a_os_e_a_linha(self, cliente, formulario,
                                         monkeypatch):
        chamadas = []

        def criar(**kwargs):
            chamadas.append(kwargs)
            return {"ok": True, "criada": True, "numero_os": 17200,
                    "os_id": 928000, "situacao_id": 38}

        monkeypatch.setattr(chamado_os.fpsl_ponte, "criar_os", criar)
        monkeypatch.setattr(chamado_os, "cliente_do_chamado",
                            lambda d, v: 68546)

        d = formulario
        r = self._enviar(cliente, d, _valores_bons(d), monkeypatch)
        # 🚨 SEM `skip`: se a validacao recusar, e defeito e tem de ser vermelho.
        assert r.status_code == 201, r.text

        sid = r.json()["id"]
        linhas = chamado_os.da_solicitacao(sid)
        assert len(linhas) == 1
        assert linhas[0]["numero_ordem"] == 17200
        assert len(chamadas) == 1
        # 🔵 3.1: o `tipoId` vem da ORIGEM -- link livre é Demanda Interna.
        assert chamadas[0]["tipo_id"] == 1782

    def test_erp_fora_do_ar_NAO_derruba_o_envio(self, cliente, formulario,
                                                monkeypatch):
        """🚨 A TRAVA MAIS IMPORTANTE DO BLOCO A: o cliente já leu "recebemos",
        e um ERP fora do ar não pode virar chamado perdido. O chamado fica
        gravado, a falha fica ESCRITA e o painel a conta."""
        def estourar(**kwargs):
            raise RuntimeError("o FPSL caiu no meio")

        monkeypatch.setattr(chamado_os.fpsl_ponte, "criar_os", estourar)
        monkeypatch.setattr(chamado_os, "cliente_do_chamado",
                            lambda d, v: 68546)

        d = formulario
        r = self._enviar(cliente, d, _valores_bons(d), monkeypatch)

        # 🚨 O ENVIO DEU 201: o chamado está no banco.
        assert r.status_code == 201, r.text
        assert "Recebemos" in r.json()["mensagem"]
        assert banco.um("SELECT id FROM formulario_solicitacao WHERE id = %s",
                        (r.json()["id"],)) is not None


# ============================================================================
# POST /api/paineis/operacao/mover — Bloco D (29/10)
# ============================================================================
# 🔵 *"deve ter o log de quem faz o que SEMPRE"* · *"pode mover que tiver acesso
# a tela, por enquanto somente owner"* · *"que tal de caminho proibido é
# esse??"* (ordem LIVRE).
#
# 🚨 ENTRA COM TESTE HTTP NA MESMA VOLTA, que foi exatamente o buraco da
# auditoria de hoje: rota de escrita sem teste de rota.
class TestMoverOCard:
    def test_sem_token_nao_passa(self, cliente):
        r = cliente.post("/api/paineis/operacao/mover",
                         json={"numero_os": 1, "para_situacao": 38})
        assert r.status_code in (401, 403)

    def test_situacao_fora_das_17_e_recusada(self, cliente, token):
        """⚠️ Não é "caminho proibido" — é id que não tem coluna, e o card
        desapareceria da tela."""
        r = cliente.post("/api/paineis/operacao/mover",
                         json={"numero_os": 90999, "para_situacao": 99999},
                         headers={"Authorization": f"Bearer {token}"})
        assert r.status_code in (400, 422), r.text
        assert "17" in r.text

    def test_a_ordem_e_LIVRE_entre_as_17(self, cliente, token, monkeypatch):
        """🔵 *"que tal de caminho proibido é esse??"* — nada valida transição.
        Aqui se prova indo da ÚLTIMA etapa para a PRIMEIRA, que seria o pulo
        mais estranho possível."""
        vistos = []

        def gravar(numero_os, situacao_id, situacao_esperada=None,
                   conferir_antes=True):
            vistos.append((numero_os, situacao_id, situacao_esperada))
            return {"ok": True, "gravou": True, "numero_os": numero_os,
                    "de": 16492, "para": situacao_id}

        monkeypatch.setattr(passagem.fpsl_ponte, "gravar_situacao_da_os",
                            gravar)
        r = cliente.post(
            "/api/paineis/operacao/mover",
            json={"numero_os": 90999, "para_situacao": 38,
                  "situacao_esperada": 16492},
            headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200, r.text
        assert r.json()["ok"] is True
        # 🚨 A trava de concorrência atravessou a rota até a ponte.
        assert vistos == [(90999, 38, 16492)]

    def test_O_LOG_SAI_SEMPRE_inclusive_quando_o_ERP_recusa(
            self, cliente, token, monkeypatch):
        """🔵 *"deve ter o log de quem faz o que SEMPRE"*. 🚨 Escrita negada sem
        rastro é o que ninguém descobre depois."""
        def recusar(numero_os, situacao_id, situacao_esperada=None,
                    conferir_antes=True):
            return {"ok": False, "gravou": False, "numero_os": numero_os,
                    "de": 38, "para": situacao_id,
                    "motivo": "o Harmonit recusou"}

        monkeypatch.setattr(passagem.fpsl_ponte, "gravar_situacao_da_os",
                            recusar)
        r = cliente.post(
            "/api/paineis/operacao/mover",
            json={"numero_os": 90998, "para_situacao": 1316,
                  "situacao_esperada": 38},
            headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200, r.text
        assert r.json()["ok"] is False

        linhas = passagem.historico(90998)
        assert len(linhas) == 1
        assert linhas[0]["ok"] is False
        assert "recusou" in linhas[0]["erro"]
        # 🔵 E QUEM fez: é o "quem faz o que".
        assert linhas[0]["quem"]
        banco.executar("DELETE FROM os_passagem WHERE numero_os = %s", (90998,))

    def test_conflito_NAO_vira_passagem(self, cliente, token, monkeypatch):
        """⚠️ Nada foi tentado no ERP, então registrar uma passagem encheria a
        linha do tempo da OS de ruído. A resposta diz o conflito."""
        def conflitar(numero_os, situacao_id, situacao_esperada=None,
                      conferir_antes=True):
            return {"ok": False, "gravou": False, "conflito": True,
                    "numero_os": numero_os, "de": 1316, "para": situacao_id,
                    "motivo": "alguem mudou no meio"}

        monkeypatch.setattr(passagem.fpsl_ponte, "gravar_situacao_da_os",
                            conflitar)
        cliente.post("/api/paineis/operacao/mover",
                     json={"numero_os": 90997, "para_situacao": 890,
                           "situacao_esperada": 38},
                     headers={"Authorization": f"Bearer {token}"})
        assert passagem.historico(90997) == []

    def test_o_log_e_legivel_pela_rota(self, cliente, token, monkeypatch):
        """🔵 Um log que ninguém consegue ler não cumpre *"SEMPRE"*."""
        def gravar(numero_os, situacao_id, situacao_esperada=None,
                   conferir_antes=True):
            return {"ok": True, "gravou": True, "numero_os": numero_os,
                    "de": 38, "para": situacao_id}

        monkeypatch.setattr(passagem.fpsl_ponte, "gravar_situacao_da_os",
                            gravar)
        cab = {"Authorization": f"Bearer {token}"}
        cliente.post("/api/paineis/operacao/mover",
                     json={"numero_os": 90996, "para_situacao": 1316,
                           "situacao_esperada": 38}, headers=cab)
        try:
            uma = cliente.get("/api/paineis/operacao/passagens?numero_os=90996",
                              headers=cab)
            assert uma.status_code == 200, uma.text
            assert uma.json()["passagens"][0]["para_situacao"] == 1316

            todas = cliente.get("/api/paineis/operacao/passagens?dias=1",
                                headers=cab)
            assert any(p["numero_os"] == 90996
                       for p in todas.json()["passagens"])
        finally:
            banco.executar("DELETE FROM os_passagem WHERE numero_os = %s",
                           (90996,))

    def test_pode_mover_virou_verdade_no_quadro(self, cliente, token):
        """⚠️ `pode_mover` é a verdade do gesto, e ela mudou em 29/10."""
        r = cliente.get("/api/paineis/operacao",
                        headers={"Authorization": f"Bearer {token}"})
        assert r.json()["pode_mover"] is True
