# -*- coding: utf-8 -*-
r"""O ANEXO DO COMPROVANTE DA ABA 2 — as duas rotas novas, 25/11.

🔵 Dele, 18/11: *"haverá campo para que em cada 1 dos artefatos de pagamento
seja inserido anexo que comprove o pagamento"*; 🔵 24/11: **anexo completo, não
só PDF**.

🚨 **POR HTTP, NÃO POR FUNÇÃO** (`feedback_rota_nova_pede_teste_http`): rota
nova pede pedido de verdade. Foi a ORDEM de registro que fez a `PNL_1.6` sumir
em 19/11 — invisível na leitura do arquivo, e só um pedido a prova. Estas duas
têm quatro segmentos, então o curinga `/api/paineis/{painel}` não as alcança; o
que as mata é o `{caminho:path}` da SPA, e é isso que a primeira trava mede.

🚨 **NADA AQUI FALA COM O POSTGRES DE PRODUÇÃO NEM COM O FPSL.** Medido em
19/11: a suíte escrevia no banco de verdade. O dublê está na **borda** — a
consulta (`banco`) e a ponte (`fpsl_ponte`) —, nunca em cima da regra que se
quer medir: a conferência pelo quadro, a recusa por extensão, o 410 e o
`anexo:<id>` são exercitados de verdade.

⚠️ O que este arquivo **não** cobre, e está dito em vez de vendido como verde: o
`INSERT` real na `pagamento_comprovante_arquivo`. Isso se prova com o gesto na
tela e um `SELECT` depois (`M17`, linhas 2 e 5).

Roda:  venv/bin/python -m pytest tests/teste_rota_anexo_do_comprovante.py
"""
import pathlib
import sys

import pytest

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from fastapi.testclient import TestClient  # noqa: E402

from movizap import auth, banco, main, pagamento_anexo  # noqa: E402
from movizap.config import settings  # noqa: E402
from movizap.operacao import DadoInvalido  # noqa: E402

POST = "/api/paineis/servico-dos-tecnicos/anexo/{}"
GET = "/api/paineis/servico-dos-tecnicos/anexo/{}"
SPA = "/{caminho:path}"

ARTEFATO = 4242

QUADRO_DUBLE = {
    "colunas": [
        {"chave": "movimentacao", "titulo": "Movimentação", "cards": [
            {"tecnico_id": 55, "tecnico_nome": "Franck", "artefatos": [
                {"id": ARTEFATO, "numero_os": 17124,
                 "comprovante_arquivo": None}]}]},
        {"chave": "validacao", "titulo": "Validação", "cards": []},
    ],
    "total": 1,
}


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
    return {"Authorization": f"Bearer {auth.criar_token(settings.admin_login)}"}


@pytest.fixture(autouse=True)
def ponte_duble(monkeypatch):
    monkeypatch.setattr(main.fpsl_ponte, "quadro_do_pagamento",
                        lambda: QUADRO_DUBLE)


# ============================================================================
# A ORDEM — a trava que não depende de rede
# ============================================================================
def teste_as_duas_rotas_vem_ANTES_do_curinga_da_spa():
    """🚨 Registrar abaixo do `{caminho:path}` faria o upload cair no index."""
    caminhos = [getattr(r, "path", None) for r in main.app.routes]
    alvo = "/api/paineis/servico-dos-tecnicos/anexo/{artefato_id}"
    baixar = "/api/paineis/servico-dos-tecnicos/anexo/{anexo_id}"
    assert alvo in caminhos, "a rota de anexar sumiu do app"
    assert baixar in caminhos, "a rota de baixar sumiu do app"
    assert SPA in caminhos, "o curinga da SPA mudou de forma; reveja o teste"
    assert caminhos.index(alvo) < caminhos.index(SPA)
    assert caminhos.index(baixar) < caminhos.index(SPA)


def teste_sem_login_nenhuma_das_duas_responde(cliente):
    assert cliente.post(POST.format(ARTEFATO),
                        files={"arquivo": ("zz.pdf", b"x", "application/pdf")}
                        ).status_code == 401
    assert cliente.get(GET.format(1)).status_code == 401


# ============================================================================
# ANEXAR — o artefato é conferido PELO QUADRO antes de gravar
# ============================================================================
def teste_anexa_e_devolve_o_id_e_a_referencia(cliente, cab, monkeypatch):
    visto = {}

    def duble(artefato_id, nome, dados, mime=None, por=None):
        visto.update(artefato_id=artefato_id, nome=nome, bytes=len(dados),
                     mime=mime, por=por)
        return {"id": 91, "artefato_id": artefato_id, "nome_original": nome,
                "bytes": len(dados), "mime": mime}

    monkeypatch.setattr(main.pagamento_anexo, "guardar", duble)
    r = cliente.post(POST.format(ARTEFATO), headers=cab,
                     files={"arquivo": ("recibo do franck.pdf", b"%PDF-1.4 zz",
                                        "application/pdf")})
    assert r.status_code == 201, r.text
    corpo = r.json()
    # 🚨 A TELA RECEBE UM ID, NUNCA UM CAMINHO.
    assert corpo["id"] == 91
    assert "caminho" not in corpo
    # 🚨 É esta string que vai para o `comprovante_arquivo` do FPSL — e ela é a
    # ponte inteira do anexo: nenhum byte atravessa.
    assert corpo["referencia"] == "anexo:91"
    assert visto["artefato_id"] == ARTEFATO
    assert visto["nome"] == "recibo do franck.pdf"
    assert visto["bytes"] == len(b"%PDF-1.4 zz")
    assert visto["por"], "o nome de quem anexou não foi adiante"


def teste_artefato_fora_do_quadro_e_404_E_NAO_GRAVA(cliente, cab, monkeypatch):
    """🚨 Não há FK: o artefato vive no SQLite do FPSL. Se esta recusa cair,
    um id digitado na URL grava comprovante em artefato que a tela não mostra."""
    chamou = []
    monkeypatch.setattr(main.pagamento_anexo, "guardar",
                        lambda *a, **k: chamou.append(1))
    r = cliente.post(POST.format(999999), headers=cab,
                     files={"arquivo": ("zz.pdf", b"zz", "application/pdf")})
    assert r.status_code == 404, r.text
    assert "não está no quadro" in r.json()["detail"]
    assert chamou == [], "gravou anexo de artefato que não está no quadro"


def teste_fpsl_fora_do_ar_e_502_E_NAO_GRAVA(cliente, cab, monkeypatch):
    """⚠️ 502, não 404: dizer "não está no quadro" quando o quadro não pôde
    ser lido mandaria o operador procurar defeito no lugar errado."""
    chamou = []

    def caiu():
        raise main.fpsl_ponte.FpslIndisponivel("zz o FPSL não respondeu")

    monkeypatch.setattr(main.fpsl_ponte, "quadro_do_pagamento", caiu)
    monkeypatch.setattr(main.pagamento_anexo, "guardar",
                        lambda *a, **k: chamou.append(1))
    r = cliente.post(POST.format(ARTEFATO), headers=cab,
                     files={"arquivo": ("zz.pdf", b"zz", "application/pdf")})
    assert r.status_code == 502, r.text
    assert chamou == []


# ============================================================================
# BAIXAR — 404, 410 e o arquivo
# ============================================================================
def teste_anexo_inexistente_e_404(cliente, cab, monkeypatch):
    monkeypatch.setattr(main.pagamento_anexo, "anexo", lambda _id: None)
    assert cliente.get(GET.format(7), headers=cab).status_code == 404


def teste_arquivo_que_sumiu_do_disco_e_410_com_a_frase(cliente, cab,
                                                       monkeypatch, tmp_path):
    """🚨 410, NÃO 500 — esta pasta não tem backup: a linha sobrevive ao
    arquivo, e a tela precisa dizer isso em vez de estourar."""
    monkeypatch.setattr(main.pagamento_anexo, "anexo", lambda _id: {
        "id": 7, "artefato_id": ARTEFATO, "nome_original": "zz.pdf",
        "caminho": str(tmp_path / "que-ninguem-gravou.pdf"),
        "bytes": 3, "mime": "application/pdf"})
    r = cliente.get(GET.format(7), headers=cab)
    assert r.status_code == 410, r.text
    assert "não está mais no disco" in r.json()["detail"]
    assert "backup" in r.json()["detail"]


def teste_baixa_com_o_nome_original(cliente, cab, monkeypatch, tmp_path):
    arquivo = tmp_path / "sorteado.bin"
    arquivo.write_bytes(b"%PDF-1.4 zz comprovante")
    monkeypatch.setattr(main.pagamento_anexo, "anexo", lambda _id: {
        "id": 7, "artefato_id": ARTEFATO, "nome_original": "recibo 17124.pdf",
        "caminho": str(arquivo), "bytes": arquivo.stat().st_size,
        "mime": "application/pdf"})
    r = cliente.get(GET.format(7), headers=cab)
    assert r.status_code == 200, r.text
    assert r.content == b"%PDF-1.4 zz comprovante"
    # ⚠️ O nome que a pessoa subiu é o nome que ela baixa — o nome no disco é
    # sorteado de propósito.
    # 🚨 O cabeçalho vem PERCENT-ENCODED (`filename*=utf-8''recibo%2017124.pdf`,
    # RFC 5987), e procurar o nome cru nele dava vermelho num comportamento
    # CERTO. Compara-se o valor decodificado.
    from urllib.parse import unquote
    assert "recibo 17124.pdf" in unquote(r.headers["content-disposition"])


# ============================================================================
# A RECUSA ANTES DO DISCO — e esta é a regra, não a borda
# ============================================================================
class TestRecusaAntesDeEscrever:
    """🚨 Extensão, teto e vazio são conferidos ANTES de tocar no disco, para
    não deixar arquivo solto quando a linha não vai existir."""

    def _nada_no_disco(self, monkeypatch, tmp_path):
        monkeypatch.setattr(pagamento_anexo, "PASTA", tmp_path / "pasta")
        monkeypatch.setattr(pagamento_anexo.banco, "um",
                            lambda *a, **k: pytest.fail(
                                "escreveu no banco num arquivo recusado"))
        return tmp_path / "pasta"

    def test_extensao_de_fora_da_lista_branca_e_recusada(self, monkeypatch,
                                                         tmp_path):
        pasta = self._nada_no_disco(monkeypatch, tmp_path)
        with pytest.raises(DadoInvalido) as e:
            pagamento_anexo.guardar(ARTEFATO, "comprovante.exe", b"MZ zz")
        assert ".exe" in str(e.value)
        assert not pasta.exists(), "criou pasta para arquivo recusado"

    def test_arquivo_vazio_e_recusado(self, monkeypatch, tmp_path):
        pasta = self._nada_no_disco(monkeypatch, tmp_path)
        with pytest.raises(DadoInvalido):
            pagamento_anexo.guardar(ARTEFATO, "zz.pdf", b"")
        assert not pasta.exists()

    def test_acima_do_teto_e_recusado(self, monkeypatch, tmp_path):
        pasta = self._nada_no_disco(monkeypatch, tmp_path)
        with pytest.raises(DadoInvalido) as e:
            pagamento_anexo.guardar(ARTEFATO, "zz.pdf",
                                    b"x" * (pagamento_anexo.TETO + 1))
        assert "limite" in str(e.value)
        assert not pasta.exists()

    def test_nao_e_so_pdf(self):
        """🔵 24/11: *"anexo completo — não só PDF"*. A lista é a MESMA da
        observação da Operação, e é importada de lá, não recopiada."""
        from movizap.passagem import EXTENSOES_DA_OBS
        assert pagamento_anexo.EXTENSOES is EXTENSOES_DA_OBS
        for esperada in (".pdf", ".jpg", ".png", ".xlsx", ".csv"):
            assert esperada in pagamento_anexo.EXTENSOES


# ============================================================================
# 403 — a tela move dinheiro, e quem nao tem a `PNL_1.6` nao entra
# ============================================================================
def teste_sem_a_tela_e_403_nas_DUAS_rotas_E_NAO_GRAVA(cliente, cab,
                                                      monkeypatch):
    """🚨 Pedido do plano, e nao e detalhe: a `PNL_1.6` nasce **so owner** e
    estas rotas gravam arquivo e devolvem comprovante de pagamento.

    ⚠️ O dublê e o CATALOGO (`pode_acessar`), que e quem decide permissao --
    a rota, a dependencia `requer_tela` e o 403 rodam de verdade. Um atendente
    de teste exigiria ESCREVER no Postgres de producao, que e a licao de 19/11.
    """
    chamou = []
    monkeypatch.setattr(main.auth.registro_telas, "pode_acessar",
                        lambda usuario, codigo: False)
    monkeypatch.setattr(main.pagamento_anexo, "guardar",
                        lambda *a, **k: chamou.append(1))
    monkeypatch.setattr(main.pagamento_anexo, "anexo",
                        lambda _id: pytest.fail("leu anexo sem a tela"))

    r = cliente.post(POST.format(ARTEFATO), headers=cab,
                     files={"arquivo": ("zz.pdf", b"zz", "application/pdf")})
    assert r.status_code == 403, r.text
    assert "PNL_1.6" in r.json()["detail"]
    assert chamou == [], "gravou anexo para quem nao tem a tela"

    assert cliente.get(GET.format(1), headers=cab).status_code == 403


def teste_a_referencia_e_texto_e_nunca_caminho():
    """🚨 O FPSL guarda `anexo:<id>` no campo de texto que já existe — sem
    migração daquele lado e sem bytes na ponte."""
    assert pagamento_anexo.referencia(91) == "anexo:91"
    assert "/" not in pagamento_anexo.referencia(91)
