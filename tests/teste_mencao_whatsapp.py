"""Menção em grupo do WhatsApp — 27/08.

Pedido do usuário: *"interessante e pode ser, tanto no interno quanto no do
whatsa"*. Esta é a metade do WhatsApp.

🚨 O QUE ISTO DEFENDE, E POR QUE É DELICADO. Menção só existe em GRUPO: numa
conversa direta o WhatsApp ignora `mentioned`, e mandar assim mesmo seria a
tela prometer o que o outro lado não faz — "parâmetro aceito e ignorado", que
este projeto cataloga como o pior defeito.

🚨 E O `@lid`. Desde que o WhatsApp passou a usar LID nos grupos,
`mensagem.remetente_jid` guarda `...@lid`. Medido em 27/08: **todos** os
remetentes de grupo da base. `@lid` não é telefone e não vira um sozinho — só
o Evolution liga os dois, e é por isso que `quem_da_para_chamar` consulta ele.

⚠️ Escreve em tabelas de PRODUÇÃO com DDD inexistente, e apaga o que criou.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, "/home/claude/movizap_painel")
pytest.importorskip("psycopg")

from movizap import banco, conversas, evolution  # noqa: E402

ENV = Path("/home/claude/movizap_painel/.env")
pytestmark = pytest.mark.skipif(
    not ENV.exists() or "MOVIZAP_DB_SENHA" not in ENV.read_text(encoding="utf-8"),
    reason="banco nao configurado no .env")

PREFIXO = "+559995558%"
FONE = "+5599955580001"
JID = "999999999999999@g.us"


def limpar():
    banco.executar(
        """DELETE FROM mensagem WHERE conversa_id IN
           (SELECT id FROM conversa WHERE telefone_e164 LIKE %s OR grupo_jid = %s)""",
        (PREFIXO, JID))
    banco.executar(
        "DELETE FROM conversa WHERE telefone_e164 LIKE %s OR grupo_jid = %s",
        (PREFIXO, JID))


@pytest.fixture(scope="module", autouse=True)
def pool():
    banco.abrir()
    limpar()
    yield
    limpar()
    banco.fechar()


@pytest.fixture()
def canal():
    limpar()
    linha = banco.um("SELECT id FROM canal WHERE tipo = 'atendimento' AND ativo "
                     "ORDER BY id LIMIT 1")
    if not linha:
        pytest.skip("sem canal de atendimento ativo")
    yield linha["id"]
    limpar()


@pytest.fixture()
def enviado(monkeypatch):
    """Guarda o corpo que teria ido para o Evolution. Nada sai da máquina."""
    saiu = []

    def falso(instancia, destino, texto, citando=None, mencionados=None):
        saiu.append({"destino": destino, "texto": texto,
                     "mencionados": mencionados})
        return {"id_externo": f"zz-men-{len(saiu)}", "status": "PENDING",
                "bruto": {}}

    monkeypatch.setattr(evolution, "enviar_texto", falso)
    return saiu


def _grupo(canal_id):
    with banco.cursor() as cur:
        return conversas.garantir_conversa(cur, canal_id, None, grupo_jid=JID,
                                           grupo_nome="zz grupo da menção")


def _direta(canal_id):
    with banco.cursor() as cur:
        return conversas.garantir_conversa(cur, canal_id, FONE)


class TestSoEmGrupo:
    def test_em_grupo_a_mencao_vai_no_envio(self, canal, enviado):
        cid = _grupo(canal)
        r = conversas.responder(cid, "@Erika olha isso", None,
                                mencionados=["5519974140416@s.whatsapp.net"])
        assert r["ok"] is True, r.get("motivo")
        assert enviado[-1]["mencionados"] == ["5519974140416@s.whatsapp.net"]

    def test_em_conversa_DIRETA_a_mencao_NAO_vai(self, canal, enviado):
        """🚨 O WhatsApp ignora `mentioned` fora de grupo. Mandar assim mesmo
        seria a tela prometer o que o outro lado não faz."""
        cid = _direta(canal)
        r = conversas.responder(cid, "@alguém", None,
                                mencionados=["5519974140416@s.whatsapp.net"])
        assert r["ok"] is True
        assert enviado[-1]["mencionados"] is None

    def test_sem_mencao_o_envio_continua_igual(self, canal, enviado):
        cid = _grupo(canal)
        conversas.responder(cid, "oi grupo", None)
        assert enviado[-1]["mencionados"] is None

    def test_lista_vazia_nao_vira_campo_vazio_no_corpo(self, canal, enviado):
        """⚠️ `mentioned: []` não é o mesmo que campo ausente para uma API
        que não documenta o caso. Ausente é o que sempre funcionou."""
        cid = _grupo(canal)
        conversas.responder(cid, "oi", None, mencionados=[])
        assert enviado[-1]["mencionados"] is None

    def test_a_mensagem_e_gravada_igual_com_ou_sem_mencao(self, canal, enviado):
        cid = _grupo(canal)
        conversas.responder(cid, "com menção", None,
                            mencionados=["5519974140416@s.whatsapp.net"])
        ultima = banco.um(
            "SELECT conteudo FROM mensagem WHERE conversa_id = %s "
            "ORDER BY id DESC LIMIT 1", (cid,))
        assert ultima["conteudo"] == "com menção"


class TestQuemDaParaChamar:
    def test_conversa_direta_nao_oferece_ninguem(self, canal):
        """Vazio não é erro: é a tela não oferecendo o `@` onde ele não faz
        nada."""
        assert conversas.quem_da_para_chamar(_direta(canal)) == []

    def test_conversa_que_nao_existe_devolve_vazio_sem_estourar(self):
        assert conversas.quem_da_para_chamar(-1) == []

    def test_em_grupo_pergunta_ao_EVOLUTION_e_usa_o_telefone(self, canal, monkeypatch):
        """🚨 O `@lid` do participante não é telefone. Quem liga os dois é o
        Evolution — esta função não pode inventar o vínculo."""
        cid = _grupo(canal)
        monkeypatch.setattr(evolution, "participantes_do_grupo",
                            lambda i, j: [
                                {"lid": "111@lid", "jid": "5519974140416@s.whatsapp.net",
                                 "nome": "Do perfil", "admin": False},
                            ])
        pessoas = conversas.quem_da_para_chamar(cid)
        assert len(pessoas) == 1
        assert pessoas[0]["jid"] == "5519974140416@s.whatsapp.net"

    def test_o_nome_de_QUEM_JA_FALOU_vence_o_nome_do_perfil(self, canal, monkeypatch):
        """⚠️ O nome que o atendente reconhece é o que ele já viu no balão
        desta conversa, não o que a pessoa pôs no perfil do WhatsApp."""
        cid = _grupo(canal)
        banco.executar(
            """INSERT INTO mensagem (conversa_id, direcao, autor, tipo, conteudo,
                                     remetente_jid, remetente_nome, criada_em)
               VALUES (%s, 'entrada', 'cliente', 'texto', 'oi', %s, %s, now())""",
            (cid, "111@lid", "Como aparece no balão"))
        monkeypatch.setattr(evolution, "participantes_do_grupo",
                            lambda i, j: [
                                {"lid": "111@lid", "jid": "+5599955589999",
                                 "nome": "Do perfil", "admin": False},
                            ])
        assert conversas.quem_da_para_chamar(cid)[0]["nome"] == "Como aparece no balão"

    def test_sem_nome_nenhum_entra_o_TELEFONE_e_nunca_o_lid(self, canal, monkeypatch):
        """🚨 `1387...@lid` não diz nada a ninguém: escolher por ele seria
        escolher às cegas."""
        cid = _grupo(canal)
        # ⚠️ DDD INEXISTENTE DE PROPOSITO. A primeira versao usou um numero
        # real e o teste reprovou mostrando "Leonardo Teixeira..." -- o codigo
        # tinha acertado (achou no cadastro) e o TESTE e que dependia de dado
        # de producao. E a armadilha ja catalogada: teste nao depende de dado
        # que outro sistema pode criar.
        monkeypatch.setattr(evolution, "participantes_do_grupo",
                            lambda i, j: [
                                {"lid": "222@lid", "jid": "559995558777@s.whatsapp.net",
                                 "nome": None, "admin": False},
                            ])
        nome = conversas.quem_da_para_chamar(cid)[0]["nome"]
        assert "@lid" not in nome
        assert "9995558777" in nome.replace("+", "")

    def test_evolution_sem_participantes_devolve_vazio(self, canal, monkeypatch):
        cid = _grupo(canal)
        monkeypatch.setattr(evolution, "participantes_do_grupo", lambda i, j: [])
        assert conversas.quem_da_para_chamar(cid) == []
