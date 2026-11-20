"""O PAREAMENTO NÃO PODE ATROPELAR A DECISÃO DE GRUPO — 19/11.

🚨 O defeito que estes testes guardam é real e foi ELE quem o achou, pela
tela: *"parece que temos mensagens ainda sem chegar, como de hj e do grupo
wezo e demais"*.

📏 Medido em 19/11: o `confirmar_pareamento` chamava
`evolution.aplicar_settings(instancia)` **sem argumento**, e o
`SETTINGS_PADRAO` tem `groupsIgnore = True`. Quando ele leu o QR às 09:21:23,
o pareamento reescreveu o valor que o `scripts/ligar_grupo.py --ligar` havia
posto em 12/08 — e **nenhuma mensagem de grupo chegou depois das 08:01:59**,
contra 208 entradas de grupo em 17/11.

⚠️ O teste de `SETTINGS_PADRAO` que já existe no `teste_canais.py` continua
valendo e NÃO é afrouxado aqui: o padrão de instância NOVA segue `True`. O que
se trava é o pareamento de uma instância EXISTENTE não herdar esse padrão.

🚨 A terceira trava é a que importa mais: **a chamada sem valor explícito**.
Foi ela que permitiu a regressão, e é ela que voltaria a permitir.
"""
import sys

import pytest

sys.path.insert(0, "/home/claude/movizap_painel")

from movizap import canais  # noqa: E402


class _Espiao:
    """Captura como `aplicar_settings` foi chamado."""

    def __init__(self):
        self.chamadas = []

    def __call__(self, instancia, valores=None):
        self.chamadas.append({"instancia": instancia, "valores": valores})
        corpo = {"groupsIgnore": True, "syncFullHistory": False,
                 "readMessages": False, "alwaysOnline": False,
                 "readStatus": False, "rejectCall": False}
        if valores:
            corpo.update(valores)
        return corpo


@pytest.fixture
def espiao(monkeypatch):
    e = _Espiao()
    monkeypatch.setattr(canais.evolution, "aplicar_settings", e)
    monkeypatch.setattr(canais, "registrar_evento", lambda *a, **k: None)
    return e


def _canal(tipo):
    return {"id": 86, "instancia": "atendimento", "tipo": tipo,
            "nome": "Atendimento"}


class TestOPareamentoRespeitaOTipoDoCanal:

    def test_canal_de_atendimento_pareia_RECEBENDO_grupo(self, espiao, monkeypatch):
        monkeypatch.setattr(canais, "por_id", lambda _id: _canal("atendimento"))
        canais.confirmar_pareamento(86, "teste")
        assert len(espiao.chamadas) == 1
        valores = espiao.chamadas[0]["valores"]
        assert valores is not None, (
            "o pareamento chamou aplicar_settings SEM valor explicito -- "
            "e exatamente a regressao de 19/11")
        assert valores["groupsIgnore"] is False, (
            "canal de atendimento tem de parear RECEBENDO grupo: foi a decisao "
            "dele em 12/08, e o pareamento a apagou em 19/11")

    def test_canal_informativo_pareia_IGNORANDO_grupo(self, espiao, monkeypatch):
        monkeypatch.setattr(canais, "por_id", lambda _id: _canal("informativo"))
        canais.confirmar_pareamento(86, "teste")
        valores = espiao.chamadas[0]["valores"]
        assert valores is not None
        assert valores["groupsIgnore"] is True, (
            "o informativo e disparo: grupo ali seria resposta num canal que "
            "ninguem le")

    def test_o_valor_de_grupo_vai_SEMPRE_explicito(self, espiao, monkeypatch):
        """🚨 A trava da causa, não do sintoma.

        Deixar o `SETTINGS_PADRAO` decidir é o que produziu a regressão. Se
        alguém voltar a chamar sem valor, este teste reprova — mesmo que o
        padrão por acaso esteja correto naquele dia.
        """
        for tipo in ("atendimento", "informativo"):
            espiao.chamadas.clear()
            monkeypatch.setattr(canais, "por_id", lambda _id, t=tipo: _canal(t))
            canais.confirmar_pareamento(86, "teste")
            valores = espiao.chamadas[0]["valores"]
            assert valores is not None and "groupsIgnore" in valores

    def test_o_padrao_de_instancia_nova_continua_ignorando(self):
        """⚠️ O conserto NÃO afrouxa o padrão: instância nova não começa
        recebendo todo grupo de que o número participa."""
        from movizap import evolution
        assert evolution.SETTINGS_PADRAO["groupsIgnore"] is True

    def test_canal_sem_instancia_recusa_antes_de_tocar_no_evolution(
            self, espiao, monkeypatch):
        monkeypatch.setattr(canais, "por_id",
                            lambda _id: {"id": 86, "instancia": None,
                                         "tipo": "atendimento"})
        with pytest.raises(ValueError):
            canais.confirmar_pareamento(86, "teste")
        assert espiao.chamadas == [], (
            "recusou e ainda assim falou com o Evolution")
