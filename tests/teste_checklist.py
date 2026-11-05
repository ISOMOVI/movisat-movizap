"""O checklist por etapa do painel da Operação — `PNL_1.1` (04/11).

🚨 ESCREVE EM TABELAS DE PRODUÇÃO (`checklist_modelo`, `checklist_item`,
`os_observacao`, `atendente`) e apaga tudo no fim. Marcas deste teste: OS na
faixa **99.90x**, etapa de teste **251** com itens cujo texto começa com
`Zz Teste Check`, login `zz_teste_chk_`.

🚨 **O SEED DE PRODUÇÃO NÃO É TOCADO.** As três etapas que ele detalhou (251,
16488, 677) têm itens reais; este teste cria os **seus próprios** itens de
modelo, com texto marcado, e só conta os dele. Renomear ou desativar um item
real mudaria o checklist de todos os cards.

O que estes testes guardam:
  · abrir o card duas vezes **não duplica** a lista;
  · **editar o modelo depois não reescreve** o que já está no card — o card é
    registro, não espelho;
  · **desmarcar não apaga**, vira `feito = false` com hora nova;
  · item **de modelo não sai** do card; o **avulso** sai;
  · o selo de 50 cards numa consulta só;
  · ao sair da etapa o checklist vira **texto de observação** — e etapa sem
    item **não** gera linha nenhuma.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, "/home/claude/movizap_painel")
pytest.importorskip("psycopg")

from movizap import banco, checklist, operacao, paineis  # noqa: E402
from movizap.operacao import DadoInvalido  # noqa: E402

ENV = Path("/home/claude/movizap_painel/.env")
pytestmark = pytest.mark.skipif(
    not ENV.exists() or "MOVIZAP_DB_SENHA" not in ENV.read_text(encoding="utf-8"),
    reason="banco nao configurado no .env")

LOGIN = "zz_teste_chk_"
MARCA = "Zz Teste Check"
OS1, OS2 = 99_901_101, 99_901_102
ETAPA = 251          # Configurar equipamentos e Sistemas
OUTRA_ETAPA = 677    # Enviar por correio/transportadora


def limpar():
    banco.executar("DELETE FROM checklist_item WHERE numero_os = ANY(%s)",
                   ([OS1, OS2],))
    banco.executar("DELETE FROM checklist_item WHERE texto LIKE %s", (MARCA + "%",))
    banco.executar("DELETE FROM checklist_modelo WHERE texto LIKE %s", (MARCA + "%",))
    banco.executar("DELETE FROM os_observacao WHERE numero_os = ANY(%s)",
                   ([OS1, OS2],))
    banco.executar("DELETE FROM atendente WHERE login LIKE %s", (LOGIN + "%",))


@pytest.fixture(scope="module", autouse=True)
def base():
    banco.abrir()
    limpar()
    pessoa = operacao.criar_atendente(MARCA + " Operador", LOGIN + "1",
                                      LOGIN + "1@teste.invalid")
    modelos = [checklist.criar_modelo(ETAPA, f"{MARCA} {n}", ordem=90 + n)
               for n in (1, 2)]
    yield {"pessoa": pessoa, "modelos": modelos}
    banco.abrir()
    limpar()


def meus(numero_os, etapa=ETAPA):
    """Só os itens deste teste: a etapa 251 tem os 3 itens REAIS do seed."""
    return [i for i in checklist.itens(numero_os, etapa)
            if i["texto"].startswith(MARCA)]


# ---------------------------------------------------------------------------
# O MODELO
# ---------------------------------------------------------------------------

class TestOModelo:
    def test_o_seed_das_tres_etapas_dele_esta_de_pe(self):
        """🔵 As listas são dele, literais. Se alguém as mudar, aqui reprova."""
        por_etapa = {251: 3, 16488: 4, 677: 2}
        for etapa, quantos in por_etapa.items():
            reais = [m for m in checklist.modelos(etapa)
                     if not m["texto"].startswith(MARCA)]
            assert len(reais) == quantos, f"etapa {etapa}"
        textos = [m["texto"] for m in checklist.modelos(16488)]
        assert "Nota Fiscal (emitir e enviar)" in textos

    def test_as_seis_etapas_sem_lista_continuam_sem(self):
        """⚠️ Ele citou seis etapas e não escreveu os itens. Inventar tarefa de
        operação seria adivinhar o trabalho de quem faz."""
        for etapa in (15747, 15797, 890, 16489, 1316, 15696):
            assert checklist.modelos(etapa) == []

    def test_etapa_fora_das_17_recusa_com_frase(self):
        with pytest.raises(DadoInvalido) as e:
            checklist.criar_modelo(999999, MARCA + " fantasma")
        assert "não é uma das 17" in str(e.value)

    def test_texto_vazio_recusa(self):
        with pytest.raises(DadoInvalido):
            checklist.criar_modelo(ETAPA, "   ")

    def test_etapas_com_modelo_diz_onde_tem_checklist(self):
        """É isto que decide se o botão aparece no card e se o aviso é dado."""
        assert {251, 16488, 677} <= checklist.etapas_com_modelo()
        assert 1316 not in checklist.etapas_com_modelo()


# ---------------------------------------------------------------------------
# A CÓPIA para o card
# ---------------------------------------------------------------------------

class TestACopia:
    def test_abrir_o_card_cria_a_lista(self, base):
        checklist.do_card(OS1, ETAPA, base["pessoa"]["id"])
        assert len(meus(OS1)) == 2

    def test_abrir_DUAS_vezes_nao_duplica(self, base):
        """🚨 A cópia é idempotente — o `UNIQUE` + `ON CONFLICT DO NOTHING`."""
        checklist.do_card(OS1, ETAPA, base["pessoa"]["id"])
        checklist.do_card(OS1, ETAPA, base["pessoa"]["id"])
        checklist.do_card(OS1, ETAPA, base["pessoa"]["id"])
        assert len(meus(OS1)) == 2

    def test_editar_o_modelo_NAO_reescreve_o_card(self, base):
        """🚨 O card é REGISTRO, não espelho. Era este o motivo de copiar o
        texto em vez de ler por referência."""
        checklist.do_card(OS1, ETAPA, base["pessoa"]["id"])
        antes = sorted(i["texto"] for i in meus(OS1))
        m = base["modelos"][0]
        checklist.atualizar_modelo(m["id"], MARCA + " RENOMEADO", m["ordem"], True)
        assert sorted(i["texto"] for i in meus(OS1)) == antes
        # E o card NOVO nasce com o texto novo.
        checklist.do_card(OS2, ETAPA, base["pessoa"]["id"])
        assert any(i["texto"] == MARCA + " RENOMEADO" for i in meus(OS2))
        checklist.atualizar_modelo(m["id"], MARCA + " 1", m["ordem"], True)

    def test_modelo_desativado_nao_entra_em_card_novo_mas_fica_no_antigo(self, base):
        novo = checklist.criar_modelo(ETAPA, MARCA + " some", ordem=99)
        checklist.do_card(OS1, ETAPA, base["pessoa"]["id"])
        assert any(i["texto"] == MARCA + " some" for i in meus(OS1))
        checklist.atualizar_modelo(novo["id"], novo["texto"], novo["ordem"], False)
        # continua no card que já o tinha...
        assert any(i["texto"] == MARCA + " some" for i in meus(OS1))
        # ...e não entra no card que ainda não abriu esta etapa
        banco.executar("DELETE FROM checklist_item WHERE numero_os = %s", (OS2,))
        checklist.do_card(OS2, ETAPA, base["pessoa"]["id"])
        assert not any(i["texto"] == MARCA + " some" for i in meus(OS2))

    def test_itens_nao_cria_nada(self, base):
        banco.executar("DELETE FROM checklist_item WHERE numero_os = %s", (OS2,))
        assert meus(OS2) == []
        assert checklist.itens(OS2, ETAPA) == [] or True  # só não pode criar
        assert banco.um("SELECT count(*) AS n FROM checklist_item "
                        " WHERE numero_os = %s", (OS2,))["n"] == 0


# ---------------------------------------------------------------------------
# MARCAR
# ---------------------------------------------------------------------------

class TestMarcar:
    def test_marcar_grava_quem_e_quando(self, base):
        checklist.do_card(OS1, ETAPA, base["pessoa"]["id"])
        item = meus(OS1)[0]
        checklist.marcar(item["id"], True, base["pessoa"]["id"])
        depois = next(i for i in meus(OS1) if i["id"] == item["id"])
        assert depois["feito"] is True
        assert depois["feito_por"] == base["pessoa"]["nome"]
        assert depois["feito_em"] is not None

    def test_desmarcar_NAO_apaga(self, base):
        checklist.do_card(OS1, ETAPA, base["pessoa"]["id"])
        item = meus(OS1)[0]
        checklist.marcar(item["id"], True, base["pessoa"]["id"])
        quantos = len(meus(OS1))
        checklist.marcar(item["id"], False, base["pessoa"]["id"])
        assert len(meus(OS1)) == quantos
        depois = next(i for i in meus(OS1) if i["id"] == item["id"])
        assert depois["feito"] is False
        assert depois["feito_em"] is not None     # a hora do desmarque

    def test_item_inexistente_recusa(self):
        with pytest.raises(DadoInvalido):
            checklist.marcar(0, True, None)


# ---------------------------------------------------------------------------
# O ITEM AVULSO (O3)
# ---------------------------------------------------------------------------

class TestAvulso:
    def test_acrescentar_entra_como_avulso(self, base):
        r = checklist.acrescentar(OS1, ETAPA, MARCA + " avulso",
                                  base["pessoa"]["id"])
        avulso = next(i for i in r["itens"] if i["texto"] == MARCA + " avulso")
        assert avulso["avulso"] is True
        assert avulso["de_modelo_id"] is None

    def test_o_avulso_SAI_do_card(self, base):
        r = checklist.acrescentar(OS2, ETAPA, MARCA + " vai sair",
                                  base["pessoa"]["id"])
        item = next(i for i in r["itens"] if i["texto"] == MARCA + " vai sair")
        checklist.remover(item["id"])
        assert not any(i["texto"] == MARCA + " vai sair" for i in meus(OS2))

    def test_item_DE_MODELO_nao_sai(self, base):
        """🚨 Deixar apagar faria o "mapa do operador" virar lista que cada um
        edita — e aí duas OS na mesma etapa deixariam de ser comparáveis."""
        checklist.do_card(OS1, ETAPA, base["pessoa"]["id"])
        do_modelo = next(i for i in meus(OS1) if not i["avulso"])
        with pytest.raises(DadoInvalido) as e:
            checklist.remover(do_modelo["id"])
        assert "mexa no modelo" in str(e.value)

    def test_avulso_em_etapa_fora_das_17_recusa(self, base):
        with pytest.raises(DadoInvalido):
            checklist.acrescentar(OS1, 999999, MARCA + " nao", None)


# ---------------------------------------------------------------------------
# O SELO do card fechado
# ---------------------------------------------------------------------------

class TestOSelo:
    def test_conta_feitos_e_total_por_etapa(self, base):
        banco.executar("DELETE FROM checklist_item WHERE numero_os = %s", (OS2,))
        checklist.do_card(OS2, ETAPA, base["pessoa"]["id"])
        itens = meus(OS2)
        checklist.marcar(itens[0]["id"], True, base["pessoa"]["id"])
        r = checklist.resumo([OS2])
        assert r[(OS2, ETAPA)]["feitos"] == 1
        assert r[(OS2, ETAPA)]["total"] == len(checklist.itens(OS2, ETAPA))

    def test_uma_consulta_para_muitos_cards(self, base):
        """⚠️ O quadro desenha até 50 por coluna; uma consulta por card seriam
        850. O molde é `passagem.quantas_observacoes`.

        ⚠️ MONTA O PRÓPRIO ESTADO: na primeira escrita este teste dependia de
        `TestACopia` ter rodado antes, e reprovava isolado. Teste que depende da
        ordem de coleta é teste que um dia reprova sem nada ter mudado — já
        aconteceu duas vezes nesta base."""
        checklist.do_card(OS1, ETAPA, base["pessoa"]["id"])
        r = checklist.resumo([OS1, OS2, 99_909_999])
        assert (OS1, ETAPA) in r
        assert not any(chave[0] == 99_909_999 for chave in r)

    def test_lista_vazia_nao_consulta_nada(self):
        assert checklist.resumo([]) == {}


# ---------------------------------------------------------------------------
# O TEXTO que vira observação ao sair (O4)
# ---------------------------------------------------------------------------

class TestComoTexto:
    def test_escreve_o_placar_e_os_itens(self, base):
        banco.executar("DELETE FROM checklist_item WHERE numero_os = %s", (OS2,))
        checklist.do_card(OS2, ETAPA, base["pessoa"]["id"])
        itens = meus(OS2)
        checklist.marcar(itens[0]["id"], True, base["pessoa"]["id"])

        texto = checklist.como_texto(OS2, ETAPA)
        assert texto.startswith("[checklist] Configurar equipamentos e Sistemas — ")
        assert "✓" in texto and "✗" in texto
        assert base["pessoa"]["nome"] in texto
        # O nome da etapa vem das 17, não do id cru.
        assert dict(paineis.SITUACOES)[ETAPA] in texto

    def test_etapa_SEM_item_nao_gera_linha(self, base):
        """🚨 Etapa sem checklist não enche a linha do tempo — a mesma régua do
        conflito, que não vira passagem."""
        assert checklist.como_texto(OS1, OUTRA_ETAPA) is None

    def test_item_sem_autor_nao_vira_parenteses_vazio(self, base):
        """⚠️ `feito_por` é `ON DELETE SET NULL`: atendente apagado não pode
        deixar '(None, )' no recado."""
        banco.executar("DELETE FROM checklist_item WHERE numero_os = %s", (OS2,))
        checklist.do_card(OS2, ETAPA, base["pessoa"]["id"])
        item = meus(OS2)[0]
        checklist.marcar(item["id"], True, None)
        banco.executar("UPDATE checklist_item SET feito_em = NULL WHERE id = %s",
                       (item["id"],))
        texto = checklist.como_texto(OS2, ETAPA)
        assert "(None" not in texto
        assert "()" not in texto
