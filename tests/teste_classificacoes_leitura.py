"""Quem atende LÊ as classificações -- 23/09.

🔴 O DEFEITO (desde 07/08, achado na verificação de 23/09): `GET
/api/classificacoes` exigia `CFG_4.1`. A Caixa pede essa rota junto com
`/api/times`, e o 403 derrubava as duas: o atendente abria "Transferir" com
a lista de times VAZIA -- nenhuma conversa tinha time -- e "Concluir" sem
classificação. Medido: 20 respostas 403 em 12 horas.

O que este teste prende, com um atendente de verdade (perfil `atendimento`):
  - a LEITURA passa;
  - as INATIVAS continuam só da configuração;
  - CRIAR continua negado -- só a leitura abriu.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, "/home/claude/movizap_painel")
pytest.importorskip("psycopg")

from fastapi.testclient import TestClient  # noqa: E402

from movizap import auth, banco, main  # noqa: E402

ENV = Path("/home/claude/movizap_painel/.env")
pytestmark = pytest.mark.skipif(
    not ENV.exists() or "MOVIZAP_DB_SENHA" not in ENV.read_text(encoding="utf-8"),
    reason="banco nao configurado no .env")

LOGIN = "zz_teste_classif_"


def limpar():
    banco.executar("DELETE FROM atendente WHERE login LIKE %s", (LOGIN + "%",))
    banco.executar("DELETE FROM classificacao WHERE nome LIKE %s", ("zz teste classif%",))


@pytest.fixture(scope="module", autouse=True)
def pool():
    banco.abrir()
    limpar()
    banco.executar(
        """INSERT INTO atendente (nome, login, senha_hash, perfil, ativo)
           VALUES ('Teste classif', %s, 'x', 'atendimento', true)""",
        (LOGIN + "atende",))
    # ⚠️ O cadastro real está VAZIO (medido em 23/09: 0 classificações). Sem
    # estas duas o teste das inativas passaria sempre, com lista vazia.
    banco.executar("INSERT INTO classificacao (nome, ativo) VALUES "
                   "('zz teste classif ativa', true), ('zz teste classif inativa', false)")
    yield
    limpar()
    banco.fechar()


def _atendente():
    c = TestClient(main.app)
    c.headers.update({"Authorization": f"Bearer {auth.criar_token(LOGIN + 'atende')}"})
    return c


def _nomes(r):
    return {c["nome"] for c in r.json()}


def test_quem_atende_le_a_lista():
    r = _atendente().get("/api/classificacoes")
    assert r.status_code == 200, r.text
    assert "zz teste classif ativa" in _nomes(r)


def test_as_inativas_continuam_da_configuracao():
    # 🚨 A coluna é `ativo`. A primeira versão deste teste lia `ativa`, que não
    # existe -- e passava sempre. O nome da linha criada é o que prova.
    r = _atendente().get("/api/classificacoes?incluir_inativas=true")
    assert r.status_code == 200
    assert "zz teste classif inativa" not in _nomes(r), "atendente recebeu classificação inativa"
    assert "zz teste classif ativa" in _nomes(r)


def test_criar_continua_negado():
    r = _atendente().post("/api/classificacoes", json={"nome": "zz não pode"})
    assert r.status_code == 403
