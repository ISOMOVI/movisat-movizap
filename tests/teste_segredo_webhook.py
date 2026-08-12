"""O segredo do webhook: aceitação durante rotação, e o log que o vazava.

Contexto de 12/08. O segredo vive no CAMINHO da URL -- é assim que o Evolution
autentica --, e o uvicorn registra a linha de requisição de toda chamada:
**2.527 vezes em 24 h** no journal, em texto puro, rotacionado e guardado em
disco. Não era vazamento pontual, era contínuo.

Duas coisas nasceram daí e estão presas aqui:
  · aceitar dois segredos, para a rotação não ter janela de 404;
  · filtrar a linha de acesso ANTES de ela ser escrita.
"""
import logging

import pytest

from movizap.config import settings
from movizap.main import MascararSegredoDoCaminho, _segredo_de_webhook_vale


class TestDoisSegredosDuranteARotacao:
    """🚨 Segredo errado devolve 404, e o Evolution trata 404 como falha.

    Sem os dois válidos, trocar o valor e reiniciar recusaria todo evento
    entre o restart e o reapontamento das instâncias.
    """

    def test_o_segredo_em_vigor_vale(self, monkeypatch):
        monkeypatch.setattr(settings, "webhook_segredo", "aaa", raising=False)
        monkeypatch.setattr(settings, "webhook_segredo_anterior", "", raising=False)
        assert _segredo_de_webhook_vale("aaa") is True

    def test_o_anterior_vale_enquanto_estiver_configurado(self, monkeypatch):
        monkeypatch.setattr(settings, "webhook_segredo", "novo", raising=False)
        monkeypatch.setattr(settings, "webhook_segredo_anterior", "velho",
                            raising=False)
        assert _segredo_de_webhook_vale("novo") is True
        assert _segredo_de_webhook_vale("velho") is True

    def test_fechada_a_rotacao_o_anterior_MORRE(self, monkeypatch):
        """O passo `--fechar` tem de ter efeito de verdade."""
        monkeypatch.setattr(settings, "webhook_segredo", "novo", raising=False)
        monkeypatch.setattr(settings, "webhook_segredo_anterior", "", raising=False)
        assert _segredo_de_webhook_vale("velho") is False

    def test_qualquer_outro_e_recusado(self, monkeypatch):
        monkeypatch.setattr(settings, "webhook_segredo", "aaa", raising=False)
        monkeypatch.setattr(settings, "webhook_segredo_anterior", "bbb",
                            raising=False)
        assert _segredo_de_webhook_vale("ccc") is False

    def test_segredo_VAZIO_nunca_abre_o_endpoint(self, monkeypatch):
        """⚠️ `.env` sem a chave não pode virar endpoint público sem senha.

        Com string vazia dos dois lados, `compare_digest("", "")` é True --
        por isso a checagem de truthy vem antes, e este teste a prende.
        """
        monkeypatch.setattr(settings, "webhook_segredo", "", raising=False)
        monkeypatch.setattr(settings, "webhook_segredo_anterior", "", raising=False)
        assert _segredo_de_webhook_vale("") is False
        assert _segredo_de_webhook_vale("qualquer") is False


class TestOLogNaoEscreveOSegredo:
    """🚨 O vazamento não era do shell: era do log de acesso, 2.527x/dia."""

    def _registro(self, caminho):
        return logging.LogRecord(
            name="uvicorn.access", level=logging.INFO, pathname="", lineno=0,
            msg='%s - "%s %s HTTP/%s" %d',
            args=("172.18.0.3:0", "POST", caminho, "1.1", 200),
            exc_info=None)

    def test_o_segredo_some_da_linha(self):
        filtro = MascararSegredoDoCaminho()
        r = self._registro("/api/webhook/evolution/SEGREDO-DE-VERDADE-43-CHARS")
        filtro.filter(r)
        escrito = r.getMessage()
        assert "SEGREDO-DE-VERDADE" not in escrito
        assert "/api/webhook/evolution/<segredo>" in escrito

    def test_o_filtro_nao_descarta_a_linha(self):
        """Mascarar não é silenciar: o acesso continua registrado."""
        filtro = MascararSegredoDoCaminho()
        assert filtro.filter(self._registro("/api/webhook/evolution/x")) is True

    def test_outras_rotas_ficam_intactas(self):
        filtro = MascararSegredoDoCaminho()
        r = self._registro("/api/conversas?busca=boleto")
        filtro.filter(r)
        assert "/api/conversas?busca=boleto" in r.getMessage()

    def test_registro_sem_args_nao_quebra(self):
        """⚠️ Nem todo record do logger tem args em tupla -- um `filter` que
        estoura derruba o log inteiro, e log que morre é pior que log sujo."""
        filtro = MascararSegredoDoCaminho()
        r = logging.LogRecord(name="uvicorn.access", level=logging.INFO,
                              pathname="", lineno=0, msg="mensagem simples",
                              args=None, exc_info=None)
        assert filtro.filter(r) is True
        assert r.getMessage() == "mensagem simples"

    def test_o_filtro_esta_LIGADO_no_logger_do_uvicorn(self):
        """Escrever o filtro e não o registrar seria a verificação que mente."""
        filtros = logging.getLogger("uvicorn.access").filters
        assert any(isinstance(f, MascararSegredoDoCaminho) for f in filtros), (
            "o filtro existe mas não está ligado -- o segredo continua indo "
            "para o journal")


class TestOEstadoRealDoEnv:
    def test_nao_ha_rotacao_esquecida_pela_metade(self):
        """⚠️ `_ANTERIOR` é temporário. Esquecido no `.env`, mantém vivo um
        segredo que já foi considerado vazado -- que é o oposto de rotacionar.
        """
        assert not settings.webhook_segredo_anterior, (
            "MOVIZAP_WEBHOOK_SEGREDO_ANTERIOR ficou no .env: rode "
            "scripts/rotacionar_webhook.py --fechar e reinicie")

    def test_o_segredo_em_vigor_tem_tamanho_de_segredo(self):
        if not settings.webhook_segredo:
            pytest.skip("sem segredo configurado")
        assert len(settings.webhook_segredo) >= 32
