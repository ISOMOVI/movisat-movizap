# -*- coding: utf-8 -*-
"""A trava de 1 minuto entre passagens do mesmo card — 🔵 decisão dele, 18/11.

🔵 *"vamos pensar em travas de 1 minuto para poder mexer o card, com mensagem
na tela, assim evitamos gravação e movimentação rápida"*. E as duas escolhas
dele: **no servidor** (não só na tela, para valer por F5, outra aba, outro
operador) e **por OS** (o que assenta é a OS, não a pessoa).

⚠️ **O QUE ESTA TRAVA NÃO RESOLVE, e fica dito para não se perder:** as duas
passagens da OS 17133, em 18/11, foram **6m35s** uma da outra, e o atraso de
leitura do Harmonit foi de **≈1h54**. Ela não teria evitado aquilo. Quem
conserta a 17133 é a causa `leitura_atrasada` e a fila. Esta trava evita o
duplo clique e a corrida no instante da escrita, que são reais e são outro
problema.

🚨 ESCREVE EM `os_passagem`, QUE É TABELA DE PRODUÇÃO, como o resto da suíte —
com faixa própria de OS (`9972xx`, e as reais vão até 17 mil) e tudo apagado no
fim.

🚨 **E NÃO EXERCITA O CAMINHO DE SUCESSO DO `mover()`.** Medido em 18/11:
**nenhum** teste desta suíte chama `passagem.mover()` de verdade — todas as
referências são `inspect.getsource`. O caminho de sucesso dispara checklist,
aviso ao cliente e pipeline, e inventar um cenário para tudo isso só para
provar a trava seria construir um teste maior que o assunto. Então aqui se
prova: a **decisão** (`_passagem_recente`), a **recusa inteira pelo `mover`**
(que devolve antes de tocar em qualquer um deles) e a **ordem** no código.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, "/home/claude/movizap_painel")
pytest.importorskip("psycopg")

from movizap import banco, passagem  # noqa: E402

ENV = Path("/home/claude/movizap_painel/.env")
pytestmark = pytest.mark.skipif(
    not ENV.exists() or "MOVIZAP_DB_SENHA" not in ENV.read_text(encoding="utf-8"),
    reason="banco nao configurado no .env")

# OS de verdade vão até 17 mil; esta faixa não casa com nenhuma.
OS_BASE = 997200
FAIXA = list(range(OS_BASE, OS_BASE + 20))


@pytest.fixture(autouse=True)
def limpo():
    banco.abrir()
    banco.executar("DELETE FROM os_passagem WHERE numero_os = ANY(%s)",
                   (FAIXA,))
    yield
    banco.abrir()
    banco.executar("DELETE FROM os_passagem WHERE numero_os = ANY(%s)",
                   (FAIXA,))


def _passagem(numero_os, *, ha_segundos, ok=True, de=251, para=16488):
    """Uma passagem já gravada, com a idade que o teste quiser.

    🚨 A idade sai do BANCO (`now() - interval`), não da hora do processo: `em`
    é `timestamptz`, e comparar com Python é o caminho curto para o vermelho
    intermitente de fuso que custou uma sessão em 11/11.
    """
    return banco.um(
        "INSERT INTO os_passagem "
        "  (numero_os, de_situacao, para_situacao, ok, em) "
        "VALUES (%s, %s, %s, %s, now() - make_interval(secs => %s)) "
        "RETURNING id",
        (numero_os, de, para, ok, ha_segundos))["id"]


class TestADecisao:
    """`_passagem_recente`: quantos segundos ainda faltam, ou `None`."""

    def test_sem_passagem_nenhuma_pode_mover(self):
        assert passagem._passagem_recente(OS_BASE + 1) is None

    def test_passagem_de_3_SEGUNDOS_trava(self):
        _passagem(OS_BASE + 2, ha_segundos=3)
        falta = passagem._passagem_recente(OS_BASE + 2)
        assert falta is not None
        assert 50 <= falta <= 60, falta

    def test_passagem_de_61_SEGUNDOS_nao_trava(self):
        _passagem(OS_BASE + 3, ha_segundos=61)
        assert passagem._passagem_recente(OS_BASE + 3) is None

    def test_na_BORDA_nunca_devolve_zero(self):
        """⚠️ 0 diria "pode mover" numa resposta que recusa — a tela mostraria
        "espere 0s" e o operador clicaria de novo no mesmo instante."""
        _passagem(OS_BASE + 4, ha_segundos=passagem.SEGUNDOS_ENTRE_PASSAGENS - 1)
        falta = passagem._passagem_recente(OS_BASE + 4)
        assert falta is None or falta >= 1

    def test_passagem_RECUSADA_nao_trava(self):
        """⚠️ Recusa não assenta nada no ERP. Travar o operador por causa de
        uma tentativa que não escreveu seria castigá-lo pelo defeito do
        Harmonit — e é exatamente o que ele vinha sofrendo na 17133, onde
        clicou 7 vezes porque nada acontecia."""
        _passagem(OS_BASE + 5, ha_segundos=2, ok=False)
        assert passagem._passagem_recente(OS_BASE + 5) is None

    def test_a_trava_e_POR_OS(self):
        """🔵 Escolha dele. Duas OS não se travam entre si."""
        _passagem(OS_BASE + 6, ha_segundos=2)
        assert passagem._passagem_recente(OS_BASE + 6) is not None
        assert passagem._passagem_recente(OS_BASE + 7) is None


class TestARecusaDoMover:
    """A recusa inteira, pelo `mover()` — ela devolve antes de tocar na ponte."""

    def test_recusa_com_causa_e_FRASE_QUE_DIZ_QUANTO_FALTA(self, monkeypatch):
        def nao_deveria(*a, **k):
            raise AssertionError("chamou a ponte dentro da janela de 60s")

        monkeypatch.setattr(passagem.fpsl_ponte, "gravar_situacao_da_os",
                            nao_deveria)
        _passagem(OS_BASE + 8, ha_segundos=5)
        r = passagem.mover(OS_BASE + 8, 677, atendente_id=None)
        assert r["ok"] is False
        assert r["gravou"] is False
        assert r["causa"] == "passagem_muito_recente"
        assert 1 <= r["espere_segundos"] <= 60
        # 🚨 Botão cinza e calado é tela que mente (`M12`): a frase diz o que
        # está acontecendo e quanto falta.
        assert "acabou de ser movida" in r["motivo"]
        assert "Espere" in r["motivo"]
        assert "Harmonit" in r["motivo"]

    def test_a_recusa_NAO_GRAVA_passagem(self, monkeypatch):
        """⚠️ Nada foi tentado no ERP: registrar uma passagem que não aconteceu
        encheria a linha do tempo da OS de ruído — é a mesma regra que já vale
        para o conflito de concorrência."""
        monkeypatch.setattr(passagem.fpsl_ponte, "gravar_situacao_da_os",
                            lambda *a, **k: pytest.fail("chamou a ponte"))
        _passagem(OS_BASE + 9, ha_segundos=5)
        passagem.mover(OS_BASE + 9, 677, atendente_id=None)
        quantas = banco.um(
            "SELECT COUNT(*) AS n FROM os_passagem WHERE numero_os = %s",
            (OS_BASE + 9,))["n"]
        assert quantas == 1, "a recusa gravou uma passagem"

    def test_a_trava_vem_ANTES_da_validacao_da_situacao(self, monkeypatch):
        """🚨 Situação inválida **e** passagem recente: o que se diz é a trava.

        Um `DadoInvalido` aqui esconderia o motivo verdadeiro de o card não ter
        andado, e o operador iria conferir a coluna em vez de esperar."""
        monkeypatch.setattr(passagem.fpsl_ponte, "gravar_situacao_da_os",
                            lambda *a, **k: pytest.fail("chamou a ponte"))
        _passagem(OS_BASE + 10, ha_segundos=1)
        r = passagem.mover(OS_BASE + 10, 999999, atendente_id=None)
        assert r["causa"] == "passagem_muito_recente"


class TestOsSessentaSegundos:
    """⚠️ 60 é número DELE. Não se muda sem a palavra dele."""

    def test_e_UMA_constante_e_a_frase_usa_ELA(self):
        """Espalhado em dois lugares, um muda e o outro não — e a frase
        passaria a prometer um prazo diferente do que a trava aplica."""
        import inspect
        assert passagem.SEGUNDOS_ENTRE_PASSAGENS == 60
        corpo = inspect.getsource(passagem._passagem_recente)
        assert "60" not in corpo, "numero cru dentro da decisao"
        fonte = inspect.getsource(passagem.mover)
        assert "SEGUNDOS_ENTRE_PASSAGENS" in fonte

    def test_a_trava_esta_no_SERVIDOR_e_nao_so_na_tela(self):
        """🔵 Escolha dele: *"no servidor, e a tela explica"*. A tela pode
        desabilitar o arrastar, mas F5 e outra aba contornariam — então a
        recusa tem de existir aqui."""
        import inspect
        fonte = inspect.getsource(passagem.mover)
        assert "_passagem_recente" in fonte
        assert fonte.index("_passagem_recente") < fonte.index("fpsl_ponte")
