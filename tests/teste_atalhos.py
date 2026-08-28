"""Atalhos de teclado por pessoa — CFG_6.1, 28/08.

🚨 O DEFEITO QUE ISTO DEFENDE. Eu pus cinco atalhos na Caixa de entrada como
sugestão minha, e ele perguntou: *"quem pediu esses atalhos? ou eles já são
nativos do WhatsApp?"*. Ninguém pediu, `j`/`k` vêm do Gmail, e o `a` assumia a
conversa SEM PERGUNTAR -- com 380 conversas sem dono e nove pessoas testando.

🚨 DESLIGADO É A AUSÊNCIA. Sem linha em `preferencia_atendente`, os atalhos não
existem. Se ausência significasse "ligado", quem nunca abriu a tela teria o
teclado agindo -- que é o risco que este bloco veio fechar.

⚠️ Escreve na tabela de produção `preferencia_atendente`, e limpa só o que
criou: usa um atendente REAL (o teste não cria gente) e apaga as linhas dele no
fim.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, "/home/claude/movizap_painel")
pytest.importorskip("psycopg")

from movizap import banco, preferencia  # noqa: E402

ENV = Path("/home/claude/movizap_painel/.env")
pytestmark = pytest.mark.skipif(
    not ENV.exists() or "MOVIZAP_DB_SENHA" not in ENV.read_text(encoding="utf-8"),
    reason="banco nao configurado no .env")


def um_atendente() -> int:
    linha = banco.um("SELECT id FROM atendente WHERE ativo ORDER BY id LIMIT 1")
    if not linha:
        pytest.skip("nenhum atendente ativo")
    return linha["id"]


def limpar(atendente_id: int):
    banco.executar("DELETE FROM preferencia_atendente WHERE atendente_id = %s",
                   (atendente_id,))


@pytest.fixture(scope="module", autouse=True)
def pool():
    banco.abrir()
    yield
    banco.fechar()


@pytest.fixture(autouse=True)
def limpo():
    banco.abrir() if False else None
    alvo = um_atendente()
    limpar(alvo)
    yield alvo
    limpar(alvo)


class TestNascemDesligados:

    def test_sem_preferencia_os_atalhos_estao_DESLIGADOS(self, limpo):
        """🚨 O coração do pedido dele. Ausência = desligado."""
        r = preferencia.dos_atalhos(limpo)
        assert r["ligados"] is False

    def test_e_ainda_assim_a_tela_recebe_o_catalogo(self, limpo):
        """Desligado não é vazio: a pessoa precisa VER o que existe para
        decidir se quer."""
        r = preferencia.dos_atalhos(limpo)
        assert len(r["catalogo"]) == 11
        assert r["teclas"]["proxima"] == "j"

    def test_conta_sem_atendente_nao_estoura(self):
        """A tela existe para todo mundo, inclusive conta sem vínculo."""
        r = preferencia.dos_atalhos(None)
        assert r["ligados"] is False
        assert len(r["catalogo"]) == 11


class TestOInterruptor:

    def test_ligar_e_desligar_valem_so_para_essa_pessoa(self, limpo):
        preferencia.ligar_atalhos(limpo, True)
        assert preferencia.dos_atalhos(limpo)["ligados"] is True
        preferencia.ligar_atalhos(limpo, False)
        assert preferencia.dos_atalhos(limpo)["ligados"] is False

    def test_o_catalogo_marca_o_que_age_sem_perguntar(self, limpo):
        """⚠️ A tela avisa ANTES de a pessoa ligar, em vez de ela descobrir
        apertando. `a` assume e `e` arquiva, os dois na hora."""
        perigosos = {a["acao"] for a in preferencia.ATALHOS if a.get("perigo")}
        assert perigosos == {"assumir", "email_arquivar"}
        for acao in perigosos:
            item = next(a for a in preferencia.ATALHOS if a["acao"] == acao)
            assert item.get("aviso"), f"{acao} é perigoso e não explica por quê"


class TestTrocarTecla:

    def test_troca_uma_tecla_e_guarda(self, limpo):
        r = preferencia.definir_teclas(limpo, {"proxima": "n"})
        assert r["ok"] is True
        assert preferencia.dos_atalhos(limpo)["teclas"]["proxima"] == "n"

    def test_o_que_nao_foi_trocado_fica_no_padrao(self, limpo):
        preferencia.definir_teclas(limpo, {"proxima": "n"})
        assert preferencia.dos_atalhos(limpo)["teclas"]["anterior"] == "k"

    def test_duas_acoes_com_a_MESMA_tecla_na_mesma_tela_e_recusa(self, limpo):
        """🚨 Sem isto, `j` para "próxima" e para "assumir" faria a pessoa
        assumir conversa tentando andar na lista, sem saber por quê."""
        r = preferencia.definir_teclas(limpo, {"assumir": "j"})
        assert r["ok"] is False
        assert "duas ações" in r["motivo"]

    def test_a_mesma_tecla_em_TELAS_diferentes_vale(self, limpo):
        """`j` anda na lista nas duas telas: é a mesma ideia, não conflito."""
        r = preferencia.definir_teclas(limpo, {"proxima": "j", "email_proxima": "j"})
        assert r["ok"] is True

    def test_tecla_proibida_e_recusada(self, limpo):
        for ruim in (" ", "Enter", "Escape", "ab", ""):
            r = preferencia.definir_teclas(limpo, {"proxima": ruim})
            assert r["ok"] is False, f"{ruim!r} devia ser recusada"

    def test_acao_desconhecida_e_recusada(self, limpo):
        r = preferencia.definir_teclas(limpo, {"voar": "v"})
        assert r["ok"] is False

    def test_voltar_ao_padrao(self, limpo):
        preferencia.definir_teclas(limpo, {"proxima": "n"})
        preferencia.definir_teclas(limpo, {})
        assert preferencia.dos_atalhos(limpo)["teclas"]["proxima"] == "j"

    def test_chave_estranha_guardada_nao_vira_atalho_fantasma(self, limpo):
        """⚠️ Versão antiga pode ter gravado ação que não existe mais."""
        banco.executar(
            "INSERT INTO preferencia_atendente (atendente_id, chave, valor) "
            "VALUES (%s, %s, %s)",
            (limpo, preferencia.CHAVE_TECLAS, '{"acao_que_sumiu": "z"}'))
        r = preferencia.dos_atalhos(limpo)
        assert "acao_que_sumiu" not in r["teclas"]
        assert r["teclas"]["proxima"] == "j"

    def test_json_ilegivel_cai_no_padrao_sem_estourar(self, limpo):
        banco.executar(
            "INSERT INTO preferencia_atendente (atendente_id, chave, valor) "
            "VALUES (%s, %s, %s)",
            (limpo, preferencia.CHAVE_TECLAS, "isto não é json"))
        r = preferencia.dos_atalhos(limpo)
        assert r["teclas"]["proxima"] == "j"
