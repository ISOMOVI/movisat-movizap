"""O endereço do compromisso (21/10): a linha, a tradução e a ida ao Harmonit.

🚨 Este arquivo também nasceu da auditoria: as três funções de endereço do
`movizap/agendamento.py` entraram em produção sem um teste Python. A escrita
foi provada **ao vivo** na OS 16991 -- prova real, mas que não se repete
sozinha: uma regressão passaria verde.

O que ele guarda:
  · a LINHA do endereço continua sendo o texto da mensagem, montada com o que
    existe e **sem buraco marcado** no meio;
  · 🚨 `logradouro` → `endereco` é a ÚNICA tradução de nome do caminho, e ela
    mora num lugar só;
  · 🚨 SEM RUA NÃO TENTA: mandar CEP sozinho sobrescreveria o endereço que a OS
    já tem por um que não leva ninguém a lugar nenhum;
  · o interruptor desligado não escreve nada e **não** é erro;
  · falha na OS grava o motivo na linha e **não derruba o compromisso**.

⚠️ A ponte com o FPSL é trocada por função nossa: teste que fala com o Harmonit
de verdade escreve em OS de produção.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, "/home/claude/movizap_painel")
pytest.importorskip("psycopg")

from movizap import agendamento, banco, fpsl_ponte  # noqa: E402

ENV = Path("/home/claude/movizap_painel/.env")
pytestmark = pytest.mark.skipif(
    not ENV.exists() or "MOVIZAP_DB_SENHA" not in ENV.read_text(encoding="utf-8"),
    reason="banco nao configurado no .env")

COMPLETO = {"cep": "19013180", "logradouro": "Rua Marcondes Salgado",
            "numero": "26", "bairro": "Centro",
            "cidade": "Presidente Prudente", "uf": "SP",
            "complemento": "sala 2"}


class TesteALinhaQueOClienteLe:
    def teste_monta_na_ordem_com_separadores(self):
        assert agendamento.linha_do_endereco(COMPLETO) == (
            "Rua Marcondes Salgado, 26 · Centro · sala 2 · "
            "Presidente Prudente - SP · CEP 19013180")

    def teste_sem_complemento_nao_deixa_buraco(self):
        """⚠️ Endereço com "—" no meio parece defeito para quem recebe."""
        e = {**COMPLETO, "complemento": None}
        texto = agendamento.linha_do_endereco(e)
        assert "· ·" not in texto
        assert "sala" not in texto

    def teste_so_a_rua_tambem_vale(self):
        assert agendamento.linha_do_endereco(
            {"logradouro": "Rua A"}) == "Rua A"

    def teste_so_cidade_sem_uf_nao_deixa_tracinho_solto(self):
        texto = agendamento.linha_do_endereco(
            {"logradouro": "Rua A", "cidade": "Prudente"})
        assert texto == "Rua A · Prudente"

    def teste_tudo_vazio_e_None_nao_string_vazia(self):
        """🚨 `""` na mensagem imprimiria um segmento em branco."""
        assert agendamento.linha_do_endereco({}) is None
        assert agendamento.linha_do_endereco(
            {"logradouro": "  ", "numero": ""}) is None


class TesteATraducaoParaOHarmonit:
    def teste_logradouro_vira_endereco_e_o_resto_fica(self):
        traduzido = agendamento._endereco_para_a_os(COMPLETO)
        assert traduzido["endereco"] == "Rua Marcondes Salgado"
        assert "logradouro" not in traduzido
        for campo in ("cep", "numero", "bairro", "cidade", "uf", "complemento"):
            assert traduzido[campo] == COMPLETO[campo]

    def teste_nao_inventa_campo_que_nao_veio(self):
        traduzido = agendamento._endereco_para_a_os({"logradouro": "Rua A"})
        assert traduzido["endereco"] == "Rua A"
        assert traduzido["numero"] is None
        assert set(traduzido) == {"cep", "endereco", "numero", "bairro",
                                  "cidade", "uf", "complemento"}


class TesteIdaAoHarmonit:
    """🚨 Nada aqui sai da VPS: a ponte e o `por_id` são trocados."""

    def _cena(self, monkeypatch, linha, resposta):
        monkeypatch.setattr(agendamento, "por_id", lambda i: linha)
        monkeypatch.setattr(agendamento, "escreve_no_harmonit", lambda cfg: True)
        monkeypatch.setattr(banco, "executar", lambda *a, **k: 1)
        enviados = []

        def gravar(numero_os, endereco):
            enviados.append((numero_os, endereco))
            return resposta(numero_os) if callable(resposta) else resposta

        monkeypatch.setattr(fpsl_ponte, "gravar_endereco_da_os", gravar)
        return enviados

    def teste_desligado_nao_escreve_nada_e_nao_e_erro(self, monkeypatch):
        monkeypatch.setattr(agendamento, "escreve_no_harmonit", lambda cfg: False)
        def naodeve(*a, **k):
            raise AssertionError("escreveu com o interruptor desligado")
        monkeypatch.setattr(fpsl_ponte, "gravar_endereco_da_os", naodeve)
        r = agendamento.levar_endereco_ao_harmonit(1)
        assert r == {"ligado": False, "resultados": []}

    def teste_sem_rua_NAO_TENTA(self, monkeypatch):
        """🚨 CEP sozinho sobrescreveria o endereço bom que a OS já tem."""
        enviados = self._cena(
            monkeypatch,
            {"id": 1, "cep": "19013180", "logradouro": None, "numero": "26",
             "bairro": None, "cidade": None, "uf": None, "complemento": None,
             "ordens": [{"numero_os": 16991}]},
            {"ok": True})
        r = agendamento.levar_endereco_ao_harmonit(1)
        assert enviados == []
        assert r["resultados"] == []
        assert "não tem rua" in r["erro"]

    def teste_com_rua_escreve_em_cada_OS_do_compromisso(self, monkeypatch):
        enviados = self._cena(
            monkeypatch,
            {"id": 1, **COMPLETO, "ordens": [{"numero_os": 16991},
                                             {"numero_os": 17000}]},
            {"ok": True})
        r = agendamento.levar_endereco_ao_harmonit(1)
        assert [n for n, _ in enviados] == [16991, 17000]
        # O que vai é o vocabulário do Harmonit, não o da tabela.
        assert enviados[0][1]["endereco"] == "Rua Marcondes Salgado"
        assert r["quantas_foram"] == 2
        assert r["erro"] is None

    def teste_falha_numa_OS_grava_o_motivo_e_nao_derruba(self, monkeypatch):
        enviados = self._cena(
            monkeypatch,
            {"id": 1, **COMPLETO, "ordens": [{"numero_os": 16991},
                                             {"numero_os": 17000}]},
            lambda n: ({"ok": True} if n == 16991
                       else {"ok": False, "numero_os": n,
                             "motivo": "o Harmonit recusou"}))
        r = agendamento.levar_endereco_ao_harmonit(1)
        assert len(enviados) == 2
        assert r["quantas_foram"] == 1
        assert "OS 17000" in r["erro"]
        assert "o Harmonit recusou" in r["erro"]

    def teste_compromisso_que_nao_existe_e_erro_alto(self, monkeypatch):
        monkeypatch.setattr(agendamento, "escreve_no_harmonit", lambda cfg: True)
        monkeypatch.setattr(agendamento, "por_id", lambda i: None)
        with pytest.raises(ValueError):
            agendamento.levar_endereco_ao_harmonit(999999)
