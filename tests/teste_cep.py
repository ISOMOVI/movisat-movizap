"""A consulta de CEP (21/10) — as TRÊS respostas, e o buraco que a auditoria achou.

🚨 Este arquivo nasceu de uma auditoria, não de uma entrega: o `movizap/cep.py`
entrou em produção com a tela coberta (api mockada no vitest) e **zero teste
Python**. O que ele guarda:

  · 🚨 as três respostas são DIFERENTES e a tela precisa das três: dicionário
    (achou), `None` ("não existe", que o ViaCEP devolve como **200 com
    `{"erro": true}`**) e exceção (não deu para consultar). Juntar as duas
    últimas faria a tela chamar de CEP errado um CEP que ela não conferiu;
  · CEP com menos de 8 dígitos **nem sai da VPS**;
  · os nomes saem já no vocabulário do Harmonit (`localidade` → `cidade`);
  · o cache é memória de processo, e guarda também o "não existe".

⚠️ Nenhum teste aqui vai à internet: o `httpx.get` é trocado por função nossa.
Teste que depende do ViaCEP de verdade fica vermelho quando a rede oscila e
passa a ser ignorado -- o pior estado de um teste.
"""
import sys

import httpx
import pytest

sys.path.insert(0, "/home/claude/movizap_painel")

from movizap import cep  # noqa: E402


class RespostaFalsa:
    def __init__(self, dados, status=200, json_quebrado=False):
        self._dados = dados
        self.status_code = status
        self._quebrado = json_quebrado

    def json(self):
        if self._quebrado:
            raise ValueError("nao e json")
        return self._dados


@pytest.fixture(autouse=True)
def memoria_limpa():
    """🚨 O cache é de PROCESSO: sem limpar, um teste responderia pelo outro."""
    cep._memoria.clear()
    yield
    cep._memoria.clear()


def responder(monkeypatch, resposta):
    chamadas = []

    def falso(url, **k):
        chamadas.append(url)
        if isinstance(resposta, Exception):
            raise resposta
        return resposta

    monkeypatch.setattr(cep.httpx, "get", falso)
    return chamadas


class TesteOQueEhCepInvalido:
    def teste_curto_nao_sai_da_vps(self, monkeypatch):
        chamadas = responder(monkeypatch, RespostaFalsa({}))
        with pytest.raises(cep.CepInvalido):
            cep.consultar("190131")
        assert chamadas == []

    def teste_vazio_e_nulo_tambem(self, monkeypatch):
        responder(monkeypatch, RespostaFalsa({}))
        for ruim in ("", None, "abc", "1901318099"):
            with pytest.raises(cep.CepInvalido):
                cep.consultar(ruim)

    def teste_pontuacao_no_meio_e_aceita(self, monkeypatch):
        """"19013-180" é o que a pessoa digita."""
        responder(monkeypatch, RespostaFalsa(
            {"logradouro": "Rua Marcondes Salgado", "bairro": "Centro",
             "localidade": "Presidente Prudente", "uf": "SP"}))
        achado = cep.consultar("19013-180")
        assert achado["cep"] == "19013180"


class TesteAsTresRespostas:
    def teste_achou_devolve_dicionario_no_vocabulario_do_harmonit(self, monkeypatch):
        responder(monkeypatch, RespostaFalsa(
            {"cep": "19013-180", "logradouro": "Rua Marcondes Salgado",
             "complemento": "", "bairro": "Centro",
             "localidade": "Presidente Prudente", "uf": "SP"}))
        achado = cep.consultar("19013180")
        # 🚨 `localidade` do ViaCEP é `cidade` nossa -- a tradução mora num
        # lugar só, senão a tela e a gravação discordam.
        assert achado == {"cep": "19013180",
                          "logradouro": "Rua Marcondes Salgado",
                          "bairro": "Centro",
                          "cidade": "Presidente Prudente",
                          "uf": "SP"}
        assert "localidade" not in achado

    def teste_nao_existe_e_200_com_erro_true_e_devolve_None(self, monkeypatch):
        """🚨 O ViaCEP responde 200 para CEP inexistente. Medido em 21/10."""
        responder(monkeypatch, RespostaFalsa({"erro": True}))
        assert cep.consultar("99999999") is None

    def teste_erro_de_rede_e_EXCECAO_nao_None(self, monkeypatch):
        """🚨 "não deu para consultar" ≠ "não existe"."""
        responder(monkeypatch, httpx.ConnectError("sem rede"))
        with pytest.raises(cep.CepIndisponivel):
            cep.consultar("19013180")

    def teste_status_de_erro_tambem_e_indisponivel(self, monkeypatch):
        responder(monkeypatch, RespostaFalsa({}, status=500))
        with pytest.raises(cep.CepIndisponivel):
            cep.consultar("19013180")

    def teste_resposta_que_nao_e_json_e_indisponivel(self, monkeypatch):
        """200 com HTML é o que um portal cativo devolve."""
        responder(monkeypatch, RespostaFalsa(None, json_quebrado=True))
        with pytest.raises(cep.CepIndisponivel):
            cep.consultar("19013180")

    def teste_campo_vazio_vira_None_e_nao_string_vazia(self, monkeypatch):
        """Rua sem nome no ViaCEP não pode virar `""` e parecer preenchida."""
        responder(monkeypatch, RespostaFalsa(
            {"logradouro": "  ", "bairro": "", "localidade": "Prudente",
             "uf": "SP"}))
        achado = cep.consultar("19013180")
        assert achado["logradouro"] is None
        assert achado["bairro"] is None
        assert achado["cidade"] == "Prudente"


class TesteCache:
    def teste_segunda_consulta_nao_vai_a_rede(self, monkeypatch):
        chamadas = responder(monkeypatch, RespostaFalsa(
            {"logradouro": "Rua X", "bairro": "B", "localidade": "C", "uf": "SP"}))
        cep.consultar("19013180")
        cep.consultar("19013-180")
        assert len(chamadas) == 1

    def teste_o_nao_existe_tambem_e_guardado(self, monkeypatch):
        chamadas = responder(monkeypatch, RespostaFalsa({"erro": True}))
        assert cep.consultar("99999999") is None
        assert cep.consultar("99999999") is None
        assert len(chamadas) == 1

    def teste_indisponivel_NAO_e_guardado(self, monkeypatch):
        """⚠️ Guardar a falha ensinaria o processo a recusar o CEP para sempre."""
        responder(monkeypatch, httpx.ConnectError("sem rede"))
        with pytest.raises(cep.CepIndisponivel):
            cep.consultar("19013180")
        assert "19013180" not in cep._memoria
