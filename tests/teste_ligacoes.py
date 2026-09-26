"""Ligações do MicroSIP — o backup na VPS (Plano 5, 25/09).

🚨 Escreve em `atendente`, `agente_ligacao`, `ligacao` e `ligacao_gravacao`,
tabelas de PRODUÇÃO, e grava arquivos numa pasta TEMPORÁRIA (nunca na de
verdade). Ramais `99xxx` e login `zz_teste_lig_`; tudo apagado no fim.
"""
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi import HTTPException

sys.path.insert(0, "/home/claude/movizap_painel")
pytest.importorskip("psycopg")

from movizap import banco, ligacoes, operacao  # noqa: E402
from movizap.operacao import DadoInvalido  # noqa: E402

ENV = Path("/home/claude/movizap_painel/.env")
pytestmark = pytest.mark.skipif(
    not ENV.exists() or "MOVIZAP_DB_SENHA" not in ENV.read_text(encoding="utf-8"),
    reason="banco nao configurado no .env")

LOGIN = "zz_teste_lig_"
_mp3_seq = [0]


def mp3():
    """Um MP3 falso ÚNICO por chamada (cabeçalho igual ao das gravações reais).
    A gravação é única pelo hash: conteúdo repetido entre testes faria um
    achar o arquivo do outro."""
    _mp3_seq[0] += 1
    return b"\xff\xe2\x48\xc4" + _mp3_seq[0].to_bytes(8, "big") + b"\x00" * 500


def limpar():
    banco.executar("""DELETE FROM ligacao_gravacao WHERE ligacao_id IN
        (SELECT id FROM ligacao WHERE ramal LIKE '99%%')""")
    banco.executar("DELETE FROM ligacao WHERE ramal LIKE '99%%'")
    banco.executar("DELETE FROM agente_ligacao WHERE ramal LIKE '99%%'")
    banco.executar("DELETE FROM atendente WHERE login LIKE %s", (LOGIN + "%",))


@pytest.fixture(scope="module", autouse=True)
def pool():
    banco.abrir()
    limpar()
    yield
    limpar()
    banco.fechar()


@pytest.fixture(autouse=True)
def pasta_temporaria(monkeypatch):
    with tempfile.TemporaryDirectory() as d:
        monkeypatch.setattr(ligacoes, "RAIZ", Path(d))
        yield Path(d)


_seq = [0]


def agente():
    _seq[0] += 1
    a = operacao.criar_atendente(f"Zz Lig {_seq[0]}", f"{LOGIN}{_seq[0]}",
                                 f"{LOGIN}{_seq[0]}@teste.invalid")
    chave = ligacoes.gerar_chave(a["id"], f"99{_seq[0]:03d}")
    return chave, ligacoes.agente_da_chave(chave)


def dados(call_id="c1", sentido="feita", numero="+5518998116168", **extra):
    base = {"call_id": call_id, "sentido": sentido, "numero": numero,
            "inicio": datetime.now(timezone.utc).isoformat(), "duracao_s": 12}
    base.update(extra)
    return base


def test_a_chave_nao_fica_guardada_e_revogada_nao_entra():
    chave, ag = agente()
    assert banco.um("SELECT count(*) n FROM agente_ligacao WHERE chave_sha256 = %s",
                    (chave,))["n"] == 0, "a chave em claro não pode estar no banco"
    ligacoes.gerar_chave(ag["atendente_id"], ag["ramal"])  # nova chave revoga a antiga
    with pytest.raises(ligacoes.ChaveInvalida):
        ligacoes.agente_da_chave(chave)


def test_ligacao_com_gravacao_devolve_o_hash_do_que_esta_no_disco(pasta_temporaria):
    _, ag = agente()
    arquivo = mp3()
    r = ligacoes.registrar(ag, dados(), arquivo, "20260925-101500-x.mp3", "PC-TESTE")
    import hashlib
    assert r["gravacao_nova"] and r["arquivo_sha256"] == hashlib.sha256(arquivo).hexdigest()
    arquivos = list(pasta_temporaria.rglob("*.mp3"))
    assert len(arquivos) == 1 and arquivos[0].read_bytes() == arquivo
    linha = banco.um("SELECT telefone_e164, pc FROM ligacao WHERE id = %s", (r["ligacao_id"],))
    assert linha["telefone_e164"] == "+5518998116168" and linha["pc"] == "PC-TESTE"


def test_reenviar_nao_duplica_nada():
    """🚨 O agente reenvia à vontade (PC que volta da rede, passada repetida)."""
    _, ag = agente()
    arquivo = mp3()
    a = ligacoes.registrar(ag, dados("c9"), arquivo, "a.mp3")
    b = ligacoes.registrar(ag, dados("c9"), arquivo, "a.mp3")
    assert a["ligacao_id"] == b["ligacao_id"] and b["ligacao_nova"] is False
    assert b["gravacao_nova"] is False and b["arquivo_sha256"] == a["arquivo_sha256"]
    assert banco.um("SELECT count(*) n FROM ligacao_gravacao WHERE ligacao_id = %s",
                    (a["ligacao_id"],))["n"] == 1


def test_uma_ligacao_com_duas_gravacoes():
    """Medido em 10/08 13:27 e 18/09 17:34: a gravação recomeça e o MicroSIP
    abre outro arquivo."""
    _, ag = agente()
    a = ligacoes.registrar(ag, dados("c2"), mp3(), "parte1.mp3")
    b = ligacoes.registrar(ag, dados("c2"), mp3(), "parte2.mp3")
    assert a["ligacao_id"] == b["ligacao_id"] and b["gravacao_nova"] is True
    assert banco.um("SELECT count(*) n FROM ligacao_gravacao WHERE ligacao_id = %s",
                    (a["ligacao_id"],))["n"] == 2


def test_perdida_sem_gravacao_e_ramal_interno_sem_e164():
    _, ag = agente()
    r = ligacoes.registrar(ag, dados("c3", "perdida", "3407"))
    assert "arquivo_sha256" not in r
    assert banco.um("SELECT telefone_e164 FROM ligacao WHERE id = %s",
                    (r["ligacao_id"],))["telefone_e164"] is None


def test_recusa_o_que_nao_e_mp3_e_dados_ruins():
    _, ag = agente()
    with pytest.raises(DadoInvalido, match="MP3"):
        ligacoes.registrar(ag, dados("c4"), b"%PDF-1.4 ...", "x.pdf")
    with pytest.raises(DadoInvalido, match="Sentido"):
        ligacoes.registrar(ag, dados("c5", "sei-la"))
    with pytest.raises(DadoInvalido, match="fuso"):
        ligacoes.registrar(ag, dados("c6", inicio="2026-09-25T10:00:00"))


def test_batimento_e_o_alerta_de_mudo():
    """🔵 *"se ficar mais 1 dia sem comunicar com VPS, tenhamos um alerta"*."""
    _, ag = agente()
    ligacoes.batimento(ag, "PC-TESTE", "0.2", 0, None)
    assert ag["ramal"] not in [m["ramal"] for m in ligacoes.agentes_mudos()]
    banco.executar("UPDATE agente_ligacao SET ultimo_contato_em = now() - interval '25 hours' "
                   "WHERE id = %s", (ag["id"],))
    mudos = {m["ramal"]: m for m in ligacoes.agentes_mudos()}
    assert ag["ramal"] in mudos and mudos[ag["ramal"]]["ultimo_pc"] == "PC-TESTE"


def test_a_rota_recusa_sem_chave():
    from starlette.requests import Request
    from movizap import main
    pedido = Request({"type": "http", "headers": []})
    with pytest.raises(HTTPException) as e:
        main._agente(pedido)
    assert e.value.status_code == 401
