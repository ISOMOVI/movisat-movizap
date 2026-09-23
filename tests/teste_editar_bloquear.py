"""Editar e apagar o que NÓS mandamos, e bloquear pelo painel -- 23/09.

🔵 As duas perguntas dele que abriram isto:
  - *"essa edição é de remetente enviado pelo Movizap, certo? então eu envio
    por lá e posso editar, certo?"* -- até 23/09, não: o painel só MOSTRAVA
    a edição e a exclusão feitas pelo cliente;
  - *"permitir ler e só bloquear se existir pelo painel tbm"*.

🚨 O WHATSAPP É UM DUBLÊ. `evolution._pedir` é trocado no módulo inteiro:
toda chamada fica registrada em `CHAMADAS` e nenhuma sai para a Evolution.
Bloquear um número de verdade num teste deixaria alguém sem conseguir falar
com a empresa.

⚠️ Telefones de DDD inexistente (+55 99 …) para nunca colidir com número real.
"""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

sys.path.insert(0, "/home/claude/movizap_painel")
pytest.importorskip("psycopg")

from fastapi import HTTPException  # noqa: E402
from movizap import banco, conversas, evolution, main  # noqa: E402

ENV = Path("/home/claude/movizap_painel/.env")
pytestmark = pytest.mark.skipif(
    not ENV.exists() or "MOVIZAP_DB_SENHA" not in ENV.read_text(encoding="utf-8"),
    reason="banco nao configurado no .env")

FONE = "+5599944440001"
LOGIN = "zz_reg_editar_"
CHAMADAS: list[tuple] = []
FALHAR = {"sim": False}


def _duble(metodo, caminho, corpo=None, params=None):
    CHAMADAS.append((metodo, caminho, corpo))
    if FALHAR["sim"]:
        raise evolution.ErroEvolution("recusado pelo dublê", 400)
    return {"ok": True}


def limpar():
    for tabela in ("transferencia", "mensagem"):
        banco.executar(f"DELETE FROM {tabela} WHERE conversa_id IN "
                       "(SELECT id FROM conversa WHERE telefone_e164 = %s)", (FONE,))
    banco.executar("DELETE FROM numero_bloqueado WHERE telefone_e164 = %s", (FONE,))
    banco.executar("DELETE FROM conversa WHERE telefone_e164 = %s", (FONE,))
    banco.executar("DELETE FROM atendente WHERE login LIKE %s", (LOGIN + "%",))


@pytest.fixture(scope="module", autouse=True)
def pool():
    original = evolution._pedir
    evolution._pedir = _duble
    banco.abrir()
    limpar()
    yield
    limpar()
    banco.fechar()
    evolution._pedir = original


@pytest.fixture()
def cena():
    limpar()
    CHAMADAS.clear()
    FALHAR["sim"] = False
    canal = banco.um("SELECT id FROM canal WHERE instancia = 'atendimento'")
    if not canal:
        pytest.skip("canal atendimento não cadastrado")

    def gente(nome):
        return banco.um("""INSERT INTO atendente (nome, login, senha_hash, perfil, ativo)
                           VALUES (%s, %s, 'x', 'atendimento', true) RETURNING id""",
                        (nome, LOGIN + nome))["id"]
    eu, outro = gente("eu"), gente("outro")
    cid = banco.um("""INSERT INTO conversa (canal_id, telefone_e164, estado, atendente_id)
                      VALUES (%s, %s, 'humano', %s) RETURNING id""",
                   (canal["id"], FONE, eu))["id"]

    def msg(direcao="saida", tipo="texto", autor_id=None, idade_min=1, texto="oi"):
        return banco.um(
            """INSERT INTO mensagem (conversa_id, id_externo, direcao, autor, tipo,
                                     conteudo, atendente_id, criada_em)
               VALUES (%s, %s, %s, %s, %s, %s, %s, now() - %s * interval '1 minute')
               RETURNING id""",
            (cid, None if tipo == "nota" else f"{LOGIN}{datetime.now().timestamp()}",
             "interna" if tipo == "nota" else direcao,
             "cliente" if direcao == "entrada" else "atendente",
             tipo, texto, autor_id, idade_min))["id"]
    yield {"eu": eu, "outro": outro, "conversa": cid, "msg": msg}
    limpar()


def _linha(mid):
    return banco.um("SELECT conteudo, conteudo_original, editada_em, apagada_em "
                    "FROM mensagem WHERE id = %s", (mid,))


# ── editar ───────────────────────────────────────────────────────────────────

class TestEditar:
    def test_edita_a_minha_e_guarda_o_original(self, cena):
        m = cena["msg"](autor_id=cena["eu"], texto="placa ABC1D2")
        r = conversas.editar_enviada(cena["conversa"], m, "placa ABC1D23", cena["eu"])
        assert r["ok"] is True
        metodo, caminho, corpo = CHAMADAS[-1]
        assert (metodo, caminho) == ("POST", "/chat/updateMessage/atendimento")
        assert corpo["text"] == "placa ABC1D23"
        assert corpo["number"] == "5599944440001"
        assert corpo["key"]["fromMe"] is True
        l = _linha(m)
        assert l["conteudo"] == "placa ABC1D23"
        assert l["conteudo_original"] == "placa ABC1D2"
        assert l["editada_em"] is not None

    def test_segunda_edicao_guarda_a_primeira_versao(self, cena):
        m = cena["msg"](autor_id=cena["eu"], texto="v1")
        conversas.editar_enviada(cena["conversa"], m, "v2", cena["eu"])
        conversas.editar_enviada(cena["conversa"], m, "v3", cena["eu"])
        l = _linha(m)
        assert (l["conteudo"], l["conteudo_original"]) == ("v3", "v1")

    @pytest.mark.parametrize("caso", ["de_outro", "nota", "do_cliente", "velha", "igual", "vazia"])
    def test_recusas_nao_chamam_o_whatsapp(self, cena, caso):
        if caso == "de_outro":
            m, texto = cena["msg"](autor_id=cena["outro"]), "x"
        elif caso == "nota":
            m, texto = cena["msg"](tipo="nota", autor_id=cena["eu"]), "x"
        elif caso == "do_cliente":
            m, texto = cena["msg"](direcao="entrada"), "x"
        elif caso == "velha":
            m, texto = cena["msg"](autor_id=cena["eu"], idade_min=20), "x"
        elif caso == "igual":
            m, texto = cena["msg"](autor_id=cena["eu"], texto="igual"), "igual"
        else:
            m, texto = cena["msg"](autor_id=cena["eu"]), "   "
        r = conversas.editar_enviada(cena["conversa"], m, texto, cena["eu"])
        assert r["ok"] is False
        assert CHAMADAS == [], "recusa não pode tocar o WhatsApp"

    def test_whatsapp_recusou_nada_muda(self, cena):
        m = cena["msg"](autor_id=cena["eu"], texto="antes")
        FALHAR["sim"] = True
        r = conversas.editar_enviada(cena["conversa"], m, "depois", cena["eu"])
        assert r["ok"] is False and "recusou" in r["motivo"]
        assert _linha(m)["conteudo"] == "antes"


# ── apagar ───────────────────────────────────────────────────────────────────

class TestApagar:
    def test_apaga_para_todos_e_marca_sem_destruir(self, cena):
        m = cena["msg"](autor_id=cena["eu"], texto="mandei errado")
        r = conversas.apagar_enviada(cena["conversa"], m, cena["eu"])
        assert r["ok"] is True
        metodo, caminho, corpo = CHAMADAS[-1]
        assert (metodo, caminho) == ("DELETE", "/chat/deleteMessageForEveryone/atendimento")
        assert corpo["fromMe"] is True and corpo["id"]
        l = _linha(m)
        assert l["apagada_em"] is not None
        assert l["conteudo"] == "mandei errado", "o registro não se destrói"

    def test_nao_apaga_duas_vezes(self, cena):
        m = cena["msg"](autor_id=cena["eu"])
        conversas.apagar_enviada(cena["conversa"], m, cena["eu"])
        CHAMADAS.clear()
        assert conversas.apagar_enviada(cena["conversa"], m, cena["eu"])["ok"] is False
        assert CHAMADAS == []

    def test_fora_da_janela_de_48h(self, cena):
        m = cena["msg"](autor_id=cena["eu"], idade_min=49 * 60)
        assert conversas.apagar_enviada(cena["conversa"], m, cena["eu"])["ok"] is False
        assert CHAMADAS == []

    def test_so_quem_escreveu(self, cena):
        m = cena["msg"](autor_id=cena["outro"])
        assert conversas.apagar_enviada(cena["conversa"], m, cena["eu"])["ok"] is False
        assert CHAMADAS == []


# ── bloquear ─────────────────────────────────────────────────────────────────

class TestBloquear:
    @staticmethod
    def _ids(**kw):
        return {x["id"] for x in conversas.listar(limite=5000, **kw)}

    def test_bloqueia_anota_e_tira_da_lista(self, cena):
        cid = cena["conversa"]
        assert cid in self._ids()
        r = conversas.bloquear(cid, cena["eu"])
        assert r["ok"] is True
        metodo, caminho, corpo = CHAMADAS[-1]
        assert (metodo, caminho) == ("POST", "/chat/updateBlockStatus/atendimento")
        assert corpo == {"number": "5599944440001", "status": "block"}
        assert conversas.bloqueio_ativo(cid)["bloqueado_por"] == cena["eu"]
        assert cid not in self._ids(), "bloqueado continuou nas abas"
        assert cid in self._ids(bloqueados=True), "o filtro Bloqueados não mostra"

    def test_na_busca_aparece_marcado(self, cena):
        conversas.bloquear(cena["conversa"], cena["eu"])
        linha = next(x for x in conversas.listar(limite=5000, busca="99944440001")
                     if x["id"] == cena["conversa"])
        assert linha["bloqueado"] is True

    def test_nao_bloqueia_duas_vezes(self, cena):
        conversas.bloquear(cena["conversa"], cena["eu"])
        CHAMADAS.clear()
        assert conversas.bloquear(cena["conversa"], cena["eu"])["ok"] is False
        assert CHAMADAS == []

    def test_whatsapp_recusou_nada_e_anotado(self, cena):
        FALHAR["sim"] = True
        assert conversas.bloquear(cena["conversa"], cena["eu"])["ok"] is False
        assert conversas.bloqueio_ativo(cena["conversa"]) is None

    def test_bad_request_do_whatsapp_explica_e_nao_anota(self, cena, monkeypatch):
        # 🚨 A PRIMEIRA PROVA REAL (23/09) deu exatamente isto, com o número
        # dele: "Error blocking user / Error: bad-request".
        def recusa(*a, **k):
            raise evolution.ErroEvolution("['Error blocking user', 'Error: bad-request']", 500)
        monkeypatch.setattr(evolution, "_pedir", recusa)
        r = conversas.bloquear(cena["conversa"], cena["eu"])
        assert r["ok"] is False
        assert "LID" in r["motivo"] and "Nada foi bloqueado" in r["motivo"]
        assert conversas.bloqueio_ativo(cena["conversa"]) is None

    def test_grupo_nao_se_bloqueia(self, cena):
        # ⚠️ Conversa de grupo À PARTE: o CHECK `ck_conversa_identidade` exige
        # `tipo = 'grupo'` e telefone vazio, e a limpeza do módulo apaga pelo
        # telefone -- esta é apagada aqui mesmo.
        jid = "120363999999999999@g.us"
        canal = banco.um("SELECT id FROM canal WHERE instancia = 'atendimento'")
        g = banco.um("""INSERT INTO conversa (canal_id, tipo, grupo_jid, estado)
                        VALUES (%s, 'grupo', %s, 'nova') RETURNING id""",
                     (canal["id"], jid))["id"]
        try:
            assert conversas.bloquear(g, cena["eu"])["ok"] is False
            assert CHAMADAS == []
        finally:
            banco.executar("DELETE FROM conversa WHERE id = %s", (g,))

    def test_envio_para_bloqueado_e_recusado_na_rota(self, cena):
        conversas.bloquear(cena["conversa"], cena["eu"])
        with pytest.raises(HTTPException) as e:
            main._recusa_se_bloqueada(cena["conversa"])
        assert e.value.status_code == 409 and "Desbloqueie" in e.value.detail

    def test_desbloquear_volta_para_a_lista_e_guarda_historico(self, cena):
        cid = cena["conversa"]
        conversas.bloquear(cid, cena["eu"])
        r = conversas.desbloquear(cid, cena["outro"])
        assert r["ok"] is True
        assert CHAMADAS[-1][2] == {"number": "5599944440001", "status": "unblock"}
        assert conversas.bloqueio_ativo(cid) is None
        assert cid in self._ids()
        h = banco.um("SELECT bloqueado_por, desbloqueado_por, desbloqueado_em "
                     "FROM numero_bloqueado WHERE telefone_e164 = %s", (FONE,))
        assert (h["bloqueado_por"], h["desbloqueado_por"]) == (cena["eu"], cena["outro"])
        assert h["desbloqueado_em"] is not None

    def test_o_resumo_conta_os_bloqueados(self, cena):
        antes = conversas.resumo()["bloqueados"]
        conversas.bloquear(cena["conversa"], cena["eu"])
        assert conversas.resumo()["bloqueados"] == antes + 1
