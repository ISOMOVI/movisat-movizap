"""Notificações — 24/09 (rota, preferências e a trava do owner).

🔵 Pedidos dele: notificação só de conversa ASSUMIDA; contador em Minhas e
Time; tom e volume 1-5 por pessoa (sem mudo); o owner liga/desliga por pessoa.
A regra de QUANDO toca é do navegador e é testada em `notificacoes_2409.teste.js`.

🚨 Escreve em `atendente`, `conversa`, `mensagem`, `preferencia_atendente`.
Logins `zz_teste_notif_`, telefones de DDD inexistente; tudo apagado no fim.
"""
import sys
from pathlib import Path

import pytest
from fastapi import HTTPException

sys.path.insert(0, "/home/claude/movizap_painel")
pytest.importorskip("psycopg")

from movizap import banco, main, operacao, preferencia  # noqa: E402

ENV = Path("/home/claude/movizap_painel/.env")
pytestmark = pytest.mark.skipif(
    not ENV.exists() or "MOVIZAP_DB_SENHA" not in ENV.read_text(encoding="utf-8"),
    reason="banco nao configurado no .env")

LOGIN = "zz_teste_notif_"
FONE = "+559995558%"


def limpar():
    ids = "(SELECT id FROM conversa WHERE telefone_e164 LIKE %s)"
    banco.executar(f"DELETE FROM mensagem WHERE conversa_id IN {ids}", (FONE,))
    banco.executar(f"DELETE FROM conversa_leitura WHERE conversa_id IN {ids}", (FONE,))
    banco.executar("DELETE FROM conversa WHERE telefone_e164 LIKE %s", (FONE,))
    banco.executar(
        "DELETE FROM preferencia_atendente WHERE atendente_id IN "
        "(SELECT id FROM atendente WHERE login LIKE %s)", (LOGIN + "%",))
    banco.executar("DELETE FROM atendente WHERE login LIKE %s", (LOGIN + "%",))


@pytest.fixture(scope="module", autouse=True)
def pool():
    banco.abrir()
    limpar()
    yield
    limpar()
    banco.fechar()


_seq = [0]


def pessoa():
    _seq[0] += 1
    return operacao.criar_atendente(f"Zz Notif {_seq[0]}", f"{LOGIN}{_seq[0]}",
                                    f"{LOGIN}{_seq[0]}@teste.invalid")["id"]


def conversa(dono, com_mensagem=True):
    _seq[0] += 1
    canal = banco.um("SELECT id FROM canal WHERE tipo = 'atendimento' AND ativo LIMIT 1")
    if not canal:
        pytest.skip("nenhum canal de atendimento ativo")
    cid = banco.um(
        """INSERT INTO conversa (canal_id, telefone_e164, estado, atendente_id)
           VALUES (%s, %s, %s, %s) RETURNING id""",
        (canal["id"], f"+55999555800{_seq[0]:02d}", "humano" if dono else "nova", dono))["id"]
    if com_mensagem:
        banco.executar(
            """INSERT INTO mensagem (conversa_id, id_externo, direcao, autor, tipo, conteudo, criada_em)
               VALUES (%s, %s, 'entrada', 'cliente', 'texto', 'oi', now())""",
            (cid, f"zz-notif-{_seq[0]}"))
    return cid


def rota_como(monkeypatch, aid):
    monkeypatch.setattr(main, "_atendente_do_usuario", lambda u: aid)
    return main.minhas_notificacoes({"login": "x", "owner": False})


def test_nasce_ligada_com_tom_e_volume_padrao(monkeypatch):
    aid = pessoa()
    r = rota_como(monkeypatch, aid)
    assert r["ativa"] is True and r["tom"] == "classico" and r["volume"] == 3


def test_so_conversa_assumida_entra_em_assumidas(monkeypatch):
    aid = pessoa()
    minha = conversa(aid)
    r = rota_como(monkeypatch, aid)
    assert [c["id"] for c in r["assumidas"]] == [minha]
    assert minha in r["donas"]
    assert r["abas"]["minhas"] >= 1


def test_lida_nao_entra_em_assumidas_mas_continua_minha(monkeypatch):
    aid = pessoa()
    cid = conversa(aid)
    ultima = banco.um("SELECT max(id) AS m FROM mensagem WHERE conversa_id = %s", (cid,))["m"]
    banco.executar(
        """INSERT INTO conversa_leitura (conversa_id, atendente_id, lido_ate)
           VALUES (%s, %s, %s)""", (cid, aid, ultima))
    r = rota_como(monkeypatch, aid)
    assert r["assumidas"] == [] and cid in r["donas"]


def test_volume_vai_de_1_a_5_sem_mudo():
    aid = pessoa()
    assert preferencia.definir_notificacao(aid, "sino", 0)["ok"] is False
    assert preferencia.definir_notificacao(aid, "sino", 6)["ok"] is False
    assert preferencia.definir_notificacao(aid, "xilofone", 3)["ok"] is False
    r = preferencia.definir_notificacao(aid, "sino", 5)
    assert r == {"ok": True, "tom": "sino", "volume": 5}
    assert preferencia.notificacao(aid) == {"tom": "sino", "volume": 5}


def test_desligada_pelo_owner_aparece_na_rota(monkeypatch):
    aid = pessoa()
    banco.executar("UPDATE atendente SET notificacao_ativa = false WHERE id = %s", (aid,))
    assert rota_como(monkeypatch, aid)["ativa"] is False


def test_so_o_owner_liga_e_desliga_a_de_alguem():
    with pytest.raises(HTTPException) as e:
        main._so_owner({"login": "x", "owner": False})
    assert e.value.status_code == 403
    main._so_owner({"login": "x", "owner": True})
