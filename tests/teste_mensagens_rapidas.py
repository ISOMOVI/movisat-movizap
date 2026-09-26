"""Mensagens rápidas — Plano 3 (25/09).

🔵 Decisões dele: Padrões e Formulários (links) de owner e admin; Minhas
notas de cada um; apelido curto; no Chat interno, só Notas e Formulários.

🚨 Escreve em `atendente` e `mensagem_rapida`, tabelas de PRODUÇÃO. Logins
`zz_teste_mr_`, apelidos `zz ` -- tudo apagado no fim.
"""
import sys
from pathlib import Path

import pytest
from fastapi import HTTPException

sys.path.insert(0, "/home/claude/movizap_painel")
pytest.importorskip("psycopg")

from movizap import banco, mensagens_rapidas as mr, operacao  # noqa: E402

ENV = Path("/home/claude/movizap_painel/.env")
pytestmark = pytest.mark.skipif(
    not ENV.exists() or "MOVIZAP_DB_SENHA" not in ENV.read_text(encoding="utf-8"),
    reason="banco nao configurado no .env")

LOGIN = "zz_teste_mr_"
DONO = {"login": "dono", "owner": True, "permissoes": []}
ADMIN = {"login": "adm", "owner": False, "permissoes": ["atendimento", "equipe"]}
QUEM_ATENDE = {"login": "at", "owner": False, "permissoes": ["atendimento"]}


def limpar():
    banco.executar("DELETE FROM mensagem_rapida WHERE apelido LIKE %s", ("zz %",))
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
    return operacao.criar_atendente(f"Zz MR {_seq[0]}", f"{LOGIN}{_seq[0]}",
                                    f"{LOGIN}{_seq[0]}@teste.invalid")["id"]


def apelido():
    _seq[0] += 1
    return f"zz {_seq[0]}"


def test_a_nota_de_um_nao_aparece_para_outro():
    ana, beto = pessoa(), pessoa()
    nota = mr.criar(QUEM_ATENDE, ana, "nota", apelido(), "Obrigado, {contato}!")
    assert nota["id"] in [m["id"] for m in mr.para_usar(ana)["nota"]]
    assert nota["id"] not in [m["id"] for m in mr.para_usar(beto)["nota"]]
    assert nota["id"] not in [m["id"] for m in mr.para_gerir(beto)["nota"]]


def test_quem_atende_nao_cria_padrao_nem_formulario():
    ana = pessoa()
    for tipo, texto in (("padrao", "Bom dia"), ("formulario", "https://x.br")):
        with pytest.raises(HTTPException) as e:
            mr.criar(QUEM_ATENDE, ana, tipo, apelido(), texto)
        assert e.value.status_code == 403
        assert "owner" not in e.value.detail.lower()


def test_admin_e_owner_criam_padrao_e_todos_usam():
    ana = pessoa()
    p = mr.criar(ADMIN, None, "padrao", apelido(), "{saudacao}, {contato}!")
    f = mr.criar(DONO, None, "formulario", apelido(), "https://forms.movisat.com.br/cadastro")
    usar = mr.para_usar(ana)
    assert p["id"] in [m["id"] for m in usar["padrao"]]
    assert f["id"] in [m["id"] for m in usar["formulario"]]


def test_no_chat_interno_so_notas_e_formularios():
    """🔵 *"Minhas notas e Formulários"*."""
    ana = pessoa()
    assert set(mr.para_usar(ana, "interno")) == {"nota", "formulario"}


def test_formulario_tem_de_ser_link():
    with pytest.raises(operacao.DadoInvalido):
        mr.criar(DONO, None, "formulario", apelido(), "preencha a ficha")


def test_apelido_repetido_no_mesmo_tipo_e_recusado():
    nome = apelido()
    mr.criar(DONO, None, "padrao", nome, "a")
    with pytest.raises(operacao.DadoInvalido, match="apelido"):
        mr.criar(DONO, None, "padrao", nome.upper(), "b")


def test_desativada_some_do_botao_mas_fica_na_gestao():
    ana = pessoa()
    nota = mr.criar(QUEM_ATENDE, ana, "nota", apelido(), "texto")
    mr.atualizar(nota["id"], QUEM_ATENDE, ana, nota["apelido"], "texto", ativo=False)
    assert nota["id"] not in [m["id"] for m in mr.para_usar(ana)["nota"]]
    assert nota["id"] in [m["id"] for m in mr.para_gerir(ana)["nota"]]


def test_nao_se_mexe_na_nota_de_outro():
    ana, beto = pessoa(), pessoa()
    nota = mr.criar(QUEM_ATENDE, ana, "nota", apelido(), "minha")
    with pytest.raises(HTTPException) as e:
        mr.apagar(nota["id"], QUEM_ATENDE, beto)
    assert e.value.status_code == 404


def test_o_banco_prende_o_dono_da_nota():
    """`ck_mensagem_rapida_dono`: nota sem dono ou padrão com dono é recusado
    pelo próprio banco, não só pela rota."""
    import psycopg
    with pytest.raises(psycopg.errors.CheckViolation):
        banco.executar("INSERT INTO mensagem_rapida (tipo, apelido, conteudo) "
                       "VALUES ('nota', 'zz sem dono', 'x')")
