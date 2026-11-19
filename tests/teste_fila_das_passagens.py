# -*- coding: utf-8 -*-
"""O card anda e a escrita vai para fila — 🔵 decisão dele, 18/11.

*"assim op não para de trabalhar e seguimos no background com a OS"*.

🚨 O DEFEITO QUE ISTO CONSERTA, medido na OS 17133 em 18/11. A mesma rota do
Harmonit, na mesma OS, sem nenhuma escrita entre as duas leituras:

    11:42:47  devolveu 251   -> o painel recusou como "alguem mudou no meio"
    11:43:18  devolveu 16488 -> a passagem seguinte funcionou

Das 11:17 às 11:42 ela respondeu **o valor que escrevemos às 09:42**. Sete
recusas, todas falsas, e o operador clicando porque nada acontecia.

🚨 **A DISTINÇÃO QUE FAZ A FILA SER SEGURA, e é o que estes testes guardam:**
o valor que o ERP devolveu é um valor que NÓS já escrevemos nesta OS? Se é
nosso, a leitura dele atrasou → o card anda e a escrita espera. Se nunca
escrevemos, alguém mexeu lá → **recusa**, como sempre, porque o ERP é quem está
certo (foi o caso das OS 17054 e 17114, achado no ensaio a seco do auditor).

🚨 ESCREVE EM `os_passagem`, de produção, com faixa própria (`9974xx`; as reais
vão até 17 mil) e tudo apagado no fim.
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

OS_BASE = 997400
FAIXA = list(range(OS_BASE, OS_BASE + 30))


@pytest.fixture(autouse=True)
def limpo():
    banco.abrir()
    banco.executar("DELETE FROM os_passagem WHERE numero_os = ANY(%s)",
                   (FAIXA,))
    yield
    banco.abrir()
    banco.executar("DELETE FROM os_passagem WHERE numero_os = ANY(%s)",
                   (FAIXA,))


def _moveu(numero_os, de, para, *, ha_segundos=7200):
    banco.executar(
        "INSERT INTO os_passagem (numero_os, de_situacao, para_situacao, ok, em) "
        "VALUES (%s, %s, %s, true, now() - make_interval(secs => %s))",
        (numero_os, de, para, ha_segundos))


def _conflito(de):
    """A resposta da ponte quando a trava do FPSL recusa."""
    return {"ok": False, "gravou": False, "de": de, "conflito": True,
            "causa": "conflito_de_situacao",
            "motivo": f"a OS esta em {de} no Harmonit",
            "frase": f"a OS esta em {de} no Harmonit"}


class TestAtrasoVaiParaAFila:
    def test_valor_QUE_NOS_ESCREVEMOS_faz_o_card_ANDAR(self, monkeypatch):
        """🚨 O caso exato da OS 17133: escrevemos 251 e depois 16488; o ERP
        responde 251, que é NOSSO de antes."""
        _moveu(OS_BASE + 1, 38, 251, ha_segundos=7200)
        _moveu(OS_BASE + 1, 251, 16488, ha_segundos=3600)
        monkeypatch.setattr(passagem.fpsl_ponte, "gravar_situacao_da_os",
                            lambda *a, **k: _conflito(251))
        r = passagem.mover(OS_BASE + 1, 677, atendente_id=None)
        # 🚨 `ok: True` porque o CARD ANDA...
        assert r["ok"] is True, r
        assert r["pendente"] is True
        assert r["causa"] == "leitura_atrasada"
        # ...e `gravou: False` porque a OS NÃO mudou. Card que anda sem dizer
        # isso é tela que mente (`M12`).
        assert r["gravou"] is False
        assert "fila" in r["motivo"]

    def test_entra_na_FILA_como_linha_e_nao_em_memoria(self, monkeypatch):
        """🚨 Reinício não pode perder escrita."""
        _moveu(OS_BASE + 2, 38, 251, ha_segundos=7200)
        _moveu(OS_BASE + 2, 251, 16488, ha_segundos=3600)
        monkeypatch.setattr(passagem.fpsl_ponte, "gravar_situacao_da_os",
                            lambda *a, **k: _conflito(251))
        passagem.mover(OS_BASE + 2, 677, atendente_id=None)
        na_fila = [d for d in passagem.fila() if d["numero_os"] == OS_BASE + 2]
        assert len(na_fila) == 1
        assert na_fila[0]["para_situacao"] == 677

    def test_valor_QUE_NUNCA_ESCREVEMOS_continua_RECUSANDO(self, monkeypatch):
        """🚨 Alguém mexeu na OS dentro do Harmonit, e o ERP é quem está certo.

        ⚠️ Enfileirar aqui escreveria a nossa coluna por cima do trabalho dessa
        pessoa — foi o que o ensaio a seco do auditor achou nas OS 17054 e
        17114, onde o ERP estava em 16490 e nós nunca escrevemos 16490."""
        _moveu(OS_BASE + 3, 251, 16488, ha_segundos=3600)
        monkeypatch.setattr(passagem.fpsl_ponte, "gravar_situacao_da_os",
                            lambda *a, **k: _conflito(16490))
        r = passagem.mover(OS_BASE + 3, 677, atendente_id=None)
        assert r.get("ok") is False
        assert r.get("conflito") is True
        assert r.get("pendente") is None
        assert [d for d in passagem.fila()
                if d["numero_os"] == OS_BASE + 3] == []

    def test_UMA_pendente_por_OS(self, monkeypatch):
        """⚠️ Duas na mesma OS seriam duas verdades sobre em que coluna o card
        está, e a tela teria de escolher uma sem critério. A segunda ATUALIZA o
        destino: o operador acabou de dizer para onde quer o card."""
        _moveu(OS_BASE + 4, 38, 251, ha_segundos=7200)
        _moveu(OS_BASE + 4, 251, 16488, ha_segundos=3600)
        monkeypatch.setattr(passagem.fpsl_ponte, "gravar_situacao_da_os",
                            lambda *a, **k: _conflito(251))
        passagem.mover(OS_BASE + 4, 677, atendente_id=None)
        passagem.mover(OS_BASE + 4, 15747, atendente_id=None)
        na_fila = [d for d in passagem.fila() if d["numero_os"] == OS_BASE + 4]
        assert len(na_fila) == 1, na_fila
        assert na_fila[0]["para_situacao"] == 15747

    def test_a_coluna_do_CARD_sai_da_fila(self, monkeypatch):
        """🚨 É isto que vence o cache do FPSL: sem ele o card voltaria para a
        coluna antiga na próxima abertura do painel, e a pessoa moveria de
        novo — o laço de 7 cliques da 17133."""
        _moveu(OS_BASE + 5, 38, 251, ha_segundos=7200)
        _moveu(OS_BASE + 5, 251, 16488, ha_segundos=3600)
        monkeypatch.setattr(passagem.fpsl_ponte, "gravar_situacao_da_os",
                            lambda *a, **k: _conflito(251))
        passagem.mover(OS_BASE + 5, 677, atendente_id=None)
        mapa = passagem.pendentes_por_os()
        assert mapa[OS_BASE + 5]["para_situacao"] == 677


class TestOEscoamento:
    def _na_fila(self, numero_os, para=677):
        _moveu(numero_os, 38, 251, ha_segundos=7200)
        _moveu(numero_os, 251, 16488, ha_segundos=3600)
        passagem._enfileirar(numero_os, 251, para, None, frase="encenado")

    def test_escrita_ACEITA_sai_da_fila_e_vira_passagem_de_verdade(self):
        self._na_fila(OS_BASE + 6)
        feito = passagem.escoar_fila(gravar=lambda *a, **k: {"ok": True})
        assert feito["resolvidas"] == 1, feito
        assert [d for d in passagem.fila()
                if d["numero_os"] == OS_BASE + 6] == []
        linha = banco.um(
            "SELECT ok, resolvida_em FROM os_passagem WHERE numero_os = %s "
            "  AND para_situacao = 677", (OS_BASE + 6,))
        assert linha["ok"] is True
        assert linha["resolvida_em"] is not None

    def test_UMA_tentativa_por_passada(self):
        """⚠️ Insistir em laço dentro da mesma execução é o *"só cansa a
        req"* dele. Quem dá o ritmo é o cron."""
        chamadas = []
        self._na_fila(OS_BASE + 7)
        passagem.escoar_fila(
            gravar=lambda *a, **k: chamadas.append(a) or {
                "ok": False, "causa": "leitura_falhou",
                "motivo": "pool", "pode_retentar": True})
        assert len(chamadas) == 1, chamadas

    def test_falha_RETENTAVEL_continua_na_fila_e_conta_a_tentativa(self):
        self._na_fila(OS_BASE + 8)
        feito = passagem.escoar_fila(gravar=lambda *a, **k: {
            "ok": False, "causa": "leitura_falhou", "motivo": "pool",
            "pode_retentar": True})
        assert feito["continuam"] == 1, feito
        na_fila = [d for d in passagem.fila() if d["numero_os"] == OS_BASE + 8]
        assert na_fila[0]["tentativas"] == 1

    def test_recusa_de_NEGOCIO_sai_da_fila_sem_ter_gravado(self):
        """🔵 *"só cansa a req"*. ⚠️ E `ok` continua FALSO: saiu da fila não é
        o mesmo que deu certo."""
        self._na_fila(OS_BASE + 9)
        feito = passagem.escoar_fila(gravar=lambda *a, **k: {
            "ok": False, "causa": "recusa_do_erp",
            "motivo": "Produto e obrigatorio", "pode_retentar": False})
        assert feito["desistiu"] == 1, feito
        linha = banco.um(
            "SELECT ok, resolvida_em FROM os_passagem WHERE numero_os = %s "
            "  AND pendente_desde IS NOT NULL", (OS_BASE + 9,))
        assert linha["ok"] is False
        assert linha["resolvida_em"] is not None

    def test_a_fila_escreve_SEM_conferir_antes(self):
        """🚨 A trava compararia com uma `situacao_esperada` que a fila não
        tem, e recusaria a própria correção — seria o conflito falso de novo,
        agora contra nós mesmos."""
        vistos = []
        self._na_fila(OS_BASE + 10)
        passagem.escoar_fila(
            gravar=lambda *a, **k: vistos.append(k) or {"ok": True})
        assert vistos[0].get("conferir_antes") is False


class TestARedFlag:
    def test_pendencia_de_MAIS_DE_UMA_HORA_avisa(self):
        """🔵 1 hora, número dele."""
        _moveu(OS_BASE + 11, 38, 251, ha_segundos=99999)
        _moveu(OS_BASE + 11, 251, 16488, ha_segundos=88888)
        passagem._enfileirar(OS_BASE + 11, 251, 677, None, frase="encenado")
        banco.executar(
            "UPDATE os_passagem SET pendente_desde = now() - interval '2 hours' "
            " WHERE numero_os = %s AND pendente_desde IS NOT NULL",
            (OS_BASE + 11,))
        assert [d for d in passagem.pendentes_para_a_red_flag()
                if d["numero_os"] == OS_BASE + 11]

    def test_pendencia_NOVA_nao_avisa(self):
        """⚠️ O atraso medido na 17133 foi de ≈1h54 e se resolveu sozinho:
        avisar em 2 minutos seria ruído."""
        _moveu(OS_BASE + 12, 38, 251, ha_segundos=99999)
        _moveu(OS_BASE + 12, 251, 16488, ha_segundos=88888)
        passagem._enfileirar(OS_BASE + 12, 251, 677, None, frase="encenado")
        assert [d for d in passagem.pendentes_para_a_red_flag()
                if d["numero_os"] == OS_BASE + 12] == []

    def test_a_MESMA_pendencia_nao_avisa_duas_vezes(self):
        _moveu(OS_BASE + 13, 38, 251, ha_segundos=99999)
        _moveu(OS_BASE + 13, 251, 16488, ha_segundos=88888)
        passagem._enfileirar(OS_BASE + 13, 251, 677, None, frase="encenado")
        banco.executar(
            "UPDATE os_passagem SET pendente_desde = now() - interval '2 hours' "
            " WHERE numero_os = %s AND pendente_desde IS NOT NULL",
            (OS_BASE + 13,))
        quais = [d for d in passagem.pendentes_para_a_red_flag()
                 if d["numero_os"] == OS_BASE + 13]
        passagem.marcar_avisadas([d["id"] for d in quais])
        assert [d for d in passagem.pendentes_para_a_red_flag()
                if d["numero_os"] == OS_BASE + 13] == []

    def test_fila_vazia_NAO_avisa_nada(self):
        """🚨 *"aviso que aparece todo dia vira aviso que ninguém lê"*."""
        assert [d for d in passagem.pendentes_para_a_red_flag()
                if d["numero_os"] in FAIXA] == []

    def test_UMA_HORA_e_numero_dele(self):
        assert passagem.HORAS_PARA_A_RED_FLAG == 1


class TestAsDuasCopiasDaMesmaPergunta:
    def test_ja_escrevemos_PERGUNTA_O_MESMO_nos_dois_modulos(self):
        """🚨 `passagem._ja_escrevemos` e `auditoria_os._ja_escrevemos` fazem a
        mesma pergunta em dois módulos, por causa de ciclo de import. Duas
        cópias são duas chances de divergir — então há esta trava."""
        from movizap import auditoria_os
        _moveu(OS_BASE + 14, 38, 251, ha_segundos=7200)
        _moveu(OS_BASE + 14, 251, 16488, ha_segundos=3600)
        assert (passagem._ja_escrevemos(OS_BASE + 14)
                == auditoria_os._ja_escrevemos(OS_BASE + 14)
                == {251, 16488})
