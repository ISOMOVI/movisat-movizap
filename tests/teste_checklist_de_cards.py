"""CFG_17.1 CHECKLIST DE CARDS — a aba, as rotas e a permissão (11/11).

🔵 Sugestão minha que ele aceitou: *"boa sugestão, pode fazer uma outra aba só
para isso de 'Checklist de Cards' vamos centralizar os fixos ali"*, e
*"sim, toda tela nova nasce somente owner"*.

🚨 AS ROTAS DE MODELO ESTAVAM NO AR DESDE 04/11 **SEM UMA ÚNICA TRAVA** —
`grep checklist/modelo tests/` dava zero, e não havia tela. Este arquivo é a
primeira trava delas, e é por isso que ele cobre também o que já existia.

⚠️ NÃO SOBE HTTP: a permissão é afirmada pelo REGISTRO e pela dependência
declarada na rota, lidas do código. Subir servidor por isto seria caro e mediria
o FastAPI, não a nossa regra.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, "/home/claude/movizap_painel")
pytest.importorskip("psycopg")

from movizap import banco, checklist, paineis  # noqa: E402
from movizap import telas as registro  # noqa: E402
from movizap.operacao import DadoInvalido  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from movizap import auth, main  # noqa: E402
from movizap.config import settings  # noqa: E402


# TestClient de MODULO: um segundo no mesmo `app` da "Event is bound
# to a different event loop".
@pytest.fixture(scope="module")
def cliente():
    with TestClient(main.app) as c:
        yield c


@pytest.fixture(scope="module")
def token_owner():
    return auth.criar_token(settings.admin_login)


ENV = Path("/home/claude/movizap_painel/.env")
pytestmark = pytest.mark.skipif(
    not ENV.exists() or "MOVIZAP_DB_SENHA" not in ENV.read_text(encoding="utf-8"),
    reason="banco nao configurado no .env")

MARCA = "Zz Teste CFG17"
ETAPA = 890  # Agendar serviço


def limpar():
    banco.executar("DELETE FROM checklist_modelo WHERE texto LIKE %s",
                   (MARCA + "%",))


@pytest.fixture(scope="module", autouse=True)
def base():
    banco.abrir()
    limpar()
    yield
    banco.abrir()
    limpar()


class TestAAba:
    def test_a_CFG_17_1_esta_no_registro_e_e_do_owner(self):
        """🔵 *"toda tela nova nasce somente owner"*."""
        t = next(x for x in registro.TELAS if x["codigo"] == "CFG_17.1")
        assert t["permissao"] == "owner"
        assert t["aba_de"] == "CFG_0.1"
        assert t["grupo"] == "Configuração"
        assert t["rota"] == "/config/checklist-de-cards"

    def test_o_codigo_nao_colide_nem_com_aposentado(self):
        codigos = [x["codigo"] for x in registro.TELAS]
        assert codigos.count("CFG_17.1") == 1
        assert "CFG_17.1" not in getattr(registro, "CODIGOS_APOSENTADOS", ())

    def test_a_CFG_16_1_E_a_dos_disparos(self):
        """⚠️ ESTA TRAVA MUDOU DE ALVO NO MESMO DIA, E FEZ O TRABALHO DELA.
        Pela manhã ela afirmava que a `CFG_16.1` estava LIVRE, reservada para os
        *Disparos Operação*; à tarde a aba entrou, a trava ficou vermelha e foi
        isso que me obrigou a conferir se o código reservado era de fato o
        usado. Agora ela guarda o outro lado: a `CFG_16.1` existe E é a dos
        disparos -- ninguém a usa para outra coisa."""
        t = next(x for x in registro.TELAS if x["codigo"] == "CFG_16.1")
        assert t["titulo"] == "Disparos Operação"
        assert t["permissao"] == "owner"
        assert t["rota"] == "/config/disparos-operacao"


class TestAPermissaoDasRotas:
    def _fonte(self, nome):
        import inspect
        from movizap import main
        return inspect.getsource(getattr(main, nome))

    def test_LER_continua_sendo_de_quem_OPERA(self):
        """O card precisa saber onde há checklist, para mostrar o botão e dar o
        aviso ao entrar — então ler é `PNL_1.1`, não a aba de configuração."""
        assert 'requer_tela("PNL_1.1")' in self._fonte("modelos_do_checklist")

    def test_ESCREVER_passou_para_a_aba_nova(self):
        """🚨 Mexer na lista muda o card de todo mundo. Era `CFG_7.1` (Geral),
        que nunca teve tela para isso."""
        for nome in ("criar_modelo_do_checklist",
                     "atualizar_modelo_do_checklist"):
            fonte = self._fonte(nome)
            assert 'requer_tela("CFG_17.1")' in fonte, nome
            assert 'CFG_7.1' not in fonte, nome

    def test_a_leitura_da_ABA_e_da_aba(self):
        assert 'requer_tela("CFG_17.1")' in self._fonte("ver_checklist_de_cards")


class TestOQueARotaDaAbaDevolve:
    def _etapas(self):
        from movizap import main
        return main.ver_checklist_de_cards.__wrapped__() \
            if hasattr(main.ver_checklist_de_cards, "__wrapped__") \
            else None

    def test_devolve_TODAS_as_etapas_inclusive_as_vazias(self):
        """🚨 Tela que só mostra etapa COM lista não deixa acrescentar na que
        está vazia — e são as vazias que ele precisa preencher.

        ⚠️ Monto a resposta aqui com as mesmas peças da rota, em vez de chamar a
        rota: ela depende de `Depends`, e subir HTTP mediria o FastAPI.
        """
        por_etapa: dict = {}
        for m in checklist.modelos(incluir_inativos=True):
            por_etapa.setdefault(m["situacao_id"], []).append(m)
        etapas = [{"situacao_id": sid, "nome": nome,
                   "itens": por_etapa.get(sid, [])}
                  for sid, nome in paineis.SITUACOES]

        assert len(etapas) == 14
        vazias = [e for e in etapas if not e["itens"]]
        assert vazias, "sem etapa vazia a trava não prova nada"
        assert all(e["nome"] for e in etapas)

    def test_a_coluna_Chamados_NAO_entra(self):
        """Não é situação do ERP, e `_etapa_conhecida` recusaria o item."""
        ids = [sid for sid, _ in paineis.SITUACOES]
        assert None not in ids
        with pytest.raises(DadoInvalido):
            checklist.criar_modelo(0, MARCA + " fantasma")


class TestAcrescentarEDesativar:
    def test_acrescentar_entra_no_fim_e_fica_ativo(self):
        antes = len(checklist.modelos(ETAPA))
        m = checklist.criar_modelo(ETAPA, MARCA + " novo", ordem=antes + 1)
        assert m["ativo"] is True
        assert len(checklist.modelos(ETAPA)) == antes + 1

    def test_desativar_TIRA_da_lista_e_a_lista_ainda_o_mostra(self):
        """⚠️ Desativar, não apagar: o item segue no card de quem já o tinha, e
        esconder aqui faria a tela mentir sobre o que existe."""
        m = checklist.criar_modelo(ETAPA, MARCA + " vai sair")
        checklist.atualizar_modelo(m["id"], m["texto"], m["ordem"], False)
        ativos = [x["id"] for x in checklist.modelos(ETAPA)]
        todos = [x["id"] for x in checklist.modelos(ETAPA,
                                                    incluir_inativos=True)]
        assert m["id"] not in ativos
        assert m["id"] in todos

    def test_renomear_NAO_reescreve_card_ja_aberto(self):
        """🚨 A regra da 090, e a que todo mundo supõe errado. O item do card é
        CÓPIA: o texto fica como estava quando foi copiado."""
        m = checklist.criar_modelo(ETAPA, MARCA + " antes")
        os_teste = 99_905_101
        try:
            checklist.do_card(os_teste, ETAPA)
            checklist.atualizar_modelo(m["id"], MARCA + " depois",
                                       m["ordem"], True)
            textos = [i["texto"] for i in checklist.itens(os_teste, ETAPA)]
            assert MARCA + " antes" in textos
            assert MARCA + " depois" not in textos
        finally:
            banco.executar("DELETE FROM checklist_item WHERE numero_os = %s",
                           (os_teste,))

    def test_item_NOVO_entra_em_card_que_JA_estava_aberto(self):
        """✅ A outra metade da regra, e a que faz o pedido dele funcionar:
        acrescentar é ADITIVO."""
        os_teste = 99_905_102
        try:
            checklist.do_card(os_teste, ETAPA)
            quantos = len(checklist.itens(os_teste, ETAPA))
            checklist.criar_modelo(ETAPA, MARCA + " aditivo")
            depois = checklist.do_card(os_teste, ETAPA)
            assert len(depois) == quantos + 1
            assert MARCA + " aditivo" in [i["texto"] for i in depois]
        finally:
            banco.executar("DELETE FROM checklist_item WHERE numero_os = %s",
                           (os_teste,))

    def test_texto_vazio_e_etapa_fora_das_17_recusam(self):
        with pytest.raises(DadoInvalido):
            checklist.criar_modelo(ETAPA, "   ")
        with pytest.raises(DadoInvalido) as e:
            checklist.criar_modelo(999_999, MARCA + " fora")
        assert "não é uma das 17" in str(e.value)


# ===========================================================================
# 🚨 A TRAVA QUE FALTAVA: CHAMAR A ROTA, NAO REMONTAR A ROTA
# ===========================================================================
# Em 12/11 a aba "Checklist de Cards" abriu EM BRANCO com "Erro interno." e
# "0 de 0 etapas". A causa era uma palavra: `main.py` importa o modulo como
# `paineis_mod` e a rota escrevia `paineis.SITUACOES` -- `NameError` em tempo
# de execucao, 500 na tela.
#
# 🚨 E HAVIA 19 TRAVAS VERDES SOBRE ESSA TELA. O `TestOQueARotaDaAbaDevolve`
# REMONTA a resposta "com as mesmas pecas da rota" em vez de chamar a rota:
# monta a lista usando `paineis.SITUACOES` importado no PROPRIO TESTE, onde o
# nome existe. Nenhuma trava nunca executou a funcao da rota.
#
# ⚠️ `py_compile` tambem nao pega: nome inexistente nao e erro de sintaxe, e
# so estoura quando a linha roda.
#
# A trava abaixo faz a unica coisa que prova: uma chamada HTTP real, com
# sessao de owner, exigindo 200 e as 14 etapas no corpo.
class TestARotaRESPONDE:
    def test_a_rota_de_config_responde_200_com_as_etapas(
            self, cliente, token_owner):
        r = cliente.get("/api/config/checklist-de-cards",
                        headers={"Authorization": f"Bearer {token_owner}"})
        assert r.status_code == 200, (
            f"a aba abre em branco: {r.status_code} {r.text[:200]}")
        etapas = r.json()["etapas"]
        assert len(etapas) == len(paineis.SITUACOES) == 14
        assert all(e["nome"] for e in etapas)
        assert all(isinstance(e["itens"], list) for e in etapas)

    def test_sem_credencial_a_rota_RECUSA(self, cliente):
        """⚠️ 401/403 e recusa; 500 e defeito. A trava separa os dois, porque
        foi um 500 que apareceu como tela em branco."""
        r = cliente.get("/api/config/checklist-de-cards")
        assert r.status_code in (401, 403), r.status_code
