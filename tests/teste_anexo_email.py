"""Anexo de e-mail recebido — baixar sob demanda, sem guardar.

Até 12/08 a tela dizia "tem anexo" e não deixava abrir: **48 dos 226 e-mails**,
e quem precisava do boleto ia no Gmail. Os bytes continuam no Google (guardar
custaria ~360 MB/ano para duplicar o que já está lá); o que faltava era o
caminho para buscar no clique.

🚨 O GOOGLE NÃO É CHAMADO NESTES TESTES. `gmail.anexo` faz uma requisição HTTP
de verdade; aqui só se exercita a parte que decide -- índice, mensagem, base64
-- com o transporte dublado. Chamar o Gmail a cada execução queimaria cota e
deixaria a suíte dependente de rede.
"""
import base64
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, "/home/claude/movizap_painel")
pytest.importorskip("psycopg")

from movizap import banco, gmail  # noqa: E402

ENV = Path("/home/claude/movizap_painel/.env")
pytestmark = pytest.mark.skipif(
    not ENV.exists() or "MOVIZAP_DB_SENHA" not in ENV.read_text(encoding="utf-8"),
    reason="banco nao configurado no .env")

EXTERNO = "zz_teste_anexo_msg"
PDF = b"%PDF-1.4 conteudo de teste"


def limpar():
    banco.executar("DELETE FROM email_mensagem WHERE id_externo = %s", (EXTERNO,))


@pytest.fixture(scope="module", autouse=True)
def pool():
    banco.abrir()
    limpar()
    yield
    limpar()
    banco.fechar()


@pytest.fixture()
def mensagem():
    """Uma mensagem com dois anexos: um com id no Gmail, outro sem.

    ⚠️ Usa a PRIMEIRA conta de e-mail que existir. Se não houver, pula -- não
    inventa linha em `email_conta`, que carrega refresh_token.
    """
    limpar()
    conta = banco.um("SELECT id FROM email_conta ORDER BY id LIMIT 1")
    if not conta:
        pytest.skip("nenhuma conta de e-mail cadastrada")
    anexos = [
        {"nome": "boleto.pdf", "mime": "application/pdf",
         "tamanho": len(PDF), "id_externo": "ANEXO_COM_ID"},
        {"nome": "assinatura.png", "mime": "image/png",
         "tamanho": 300, "id_externo": None},
    ]
    mid = banco.um(
        """INSERT INTO email_mensagem
               (conta_id, id_externo, remetente, assunto, enviado_em,
                tem_anexo, anexos)
           VALUES (%s, %s, 'cliente@exemplo.com', 'com anexo', now(), true, %s)
           RETURNING id""",
        (conta["id"], EXTERNO, json.dumps(anexos)))["id"]
    yield mid
    limpar()


class TestEscolhaDoAnexo:
    def test_indice_fora_da_lista(self, mensagem):
        r = gmail.anexo(mensagem, 9)
        assert r["ok"] is False
        assert "não encontrado" in r["motivo"]

    def test_indice_negativo(self, mensagem):
        assert gmail.anexo(mensagem, -1)["ok"] is False

    def test_mensagem_inexistente(self):
        r = gmail.anexo(-1, 0)
        assert r["ok"] is False
        assert "Mensagem não encontrada" in r["motivo"]

    def test_anexo_SEM_id_no_gmail_e_explicado(self, mensagem):
        """⚠️ Anexo pequeno vem embutido no corpo da parte e o Gmail não dá
        `attachmentId`. Não temos os bytes -- e a tela precisa dizer isso em
        vez de mostrar erro genérico."""
        r = gmail.anexo(mensagem, 1)
        assert r["ok"] is False
        assert "Gmail" in r["motivo"]

    def test_o_id_vem_da_LISTA_GUARDADA_e_nao_de_quem_pede(self, mensagem,
                                                           monkeypatch):
        """🚨 Quem pede escolhe uma POSIÇÃO; o `attachmentId` sai do que NÓS
        gravamos. Sem isso, passar um id qualquer buscaria anexo de outra
        mensagem."""
        pedidos = []

        def fingir(cliente, caminho, **p):
            pedidos.append(caminho)
            return {"data": base64.urlsafe_b64encode(PDF).decode()}

        monkeypatch.setattr(gmail, "_token_de_acesso", lambda c: "tok")
        monkeypatch.setattr(gmail, "_pedir", fingir)
        gmail.anexo(mensagem, 0)
        assert pedidos and pedidos[0].endswith("/attachments/ANEXO_COM_ID")


class TestOsBytes:
    @pytest.fixture()
    def dublado(self, monkeypatch):
        monkeypatch.setattr(gmail, "_token_de_acesso", lambda c: "tok")

    def test_devolve_o_arquivo_com_nome_e_mime(self, mensagem, dublado,
                                               monkeypatch):
        monkeypatch.setattr(gmail, "_pedir", lambda c, p, **k: {
            "data": base64.urlsafe_b64encode(PDF).decode()})
        r = gmail.anexo(mensagem, 0)
        assert r["ok"] is True
        assert r["dados"] == PDF
        assert r["nome"] == "boleto.pdf"
        assert r["mime"] == "application/pdf"

    def test_base64_URL_SAFE_e_sem_padding(self, mensagem, dublado, monkeypatch):
        """🚨 O Gmail devolve base64 url-safe SEM padding. Decodificar com o
        alfabeto padrão devolve bytes corrompidos SEM ERRO -- o arquivo chega
        parecendo defeito do remetente.

        Estes bytes produzem `-` e `_` no alfabeto url-safe (`+` e `/` no
        padrão), então o teste falha se alguém trocar o decodificador.
        """
        bruto = bytes([0xFB, 0xFF, 0xBF, 0x00, 0x10, 0x83])
        cru = base64.urlsafe_b64encode(bruto).decode().rstrip("=")
        assert "-" in cru or "_" in cru, "o caso de teste perdeu a graça"
        monkeypatch.setattr(gmail, "_pedir", lambda c, p, **k: {"data": cru})
        assert gmail.anexo(mensagem, 0)["dados"] == bruto

    def test_resposta_ilegivel_nao_estoura(self, mensagem, dublado, monkeypatch):
        monkeypatch.setattr(gmail, "_pedir",
                            lambda c, p, **k: {"data": "!!!nao é base64!!!"})
        r = gmail.anexo(mensagem, 0)
        assert r["ok"] is False

    def test_NADA_e_gravado_no_banco(self, mensagem, dublado, monkeypatch):
        """A decisão de projeto é não duplicar o que o Google guarda.

        🚨 A PRIMEIRA VERSÃO COMPARAVA `count(*) FROM midia` ANTES E DEPOIS, e
        quebrou na suíte inteira passando sozinha: `midia` é tabela de
        PRODUÇÃO e cresce com mensagem real chegando pelo webhook durante o
        teste. Contador global de tabela viva não isola nada — é a armadilha
        que já está na lista do projeto, e eu a repeti.

        A garantia real é estrutural: o módulo do Gmail não conhece o de
        mídia, então não existe caminho de código para gravar arquivo.
        """
        monkeypatch.setattr(gmail, "_pedir", lambda c, p, **k: {
            "data": base64.urlsafe_b64encode(PDF).decode()})
        gmail.anexo(mensagem, 0)

        guardado = banco.um("SELECT anexos FROM email_mensagem WHERE id = %s",
                            (mensagem,))["anexos"]
        lista = json.loads(guardado) if isinstance(guardado, str) else guardado
        assert all("dados" not in a for a in lista), "gravou bytes no banco"

    def test_o_modulo_do_gmail_NAO_IMPORTA_o_de_midia(self):
        """Sem caminho de código até `midia`, não há como gravar arquivo."""
        import ast
        import inspect

        arvore = ast.parse(inspect.getsource(gmail))
        importados = set()
        for no in ast.walk(arvore):
            if isinstance(no, ast.Import):
                importados |= {a.name.split(".")[0] for a in no.names}
            elif isinstance(no, ast.ImportFrom):
                if no.module:
                    importados.add(no.module.split(".")[0])
                importados |= {a.name for a in no.names}
        assert "midia" not in importados, (
            f"o gmail passou a conhecer o módulo de mídia: {importados}")
