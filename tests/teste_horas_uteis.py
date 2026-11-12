"""O PRAZO EM HORAS ÚTEIS — 11/11.

🔵 Decisão dele: *"use 08:30 - 17:00 para calculo, será fixo"*, e o prazo do
chamado é de **24 horas úteis** da abertura até a conclusão.

🚨 ESTAS TRAVAS NÃO TOCAM NO BANCO. `horas_uteis` é aritmética de data, e foi
escrito assim de propósito -- prazo é a conta mais fácil de errar na borda do
dia, e teste de borda não pode depender de fixture.

⚠️ AS DATAS SÃO FIXAS E O DIA DA SEMANA ESTÁ CONFERIDO no próprio teste
(`test_as_datas_do_arquivo_sao_os_dias_que_eu_digo`). Teste de prazo que usa
`now()` reprova sozinho em dia de semana diferente -- é o defeito que o
`teste_agendamento` tem por fuso, e que está anotado como conhecido.
"""
import datetime as dt

from movizap import horas_uteis as hu

# 2026-11-09 é SEGUNDA; 13/11 sexta; 14/11 sábado; 15/11 domingo.
SEG = dt.datetime(2026, 11, 9, 9, 0, tzinfo=hu.FUSO)
SEX = dt.datetime(2026, 11, 13, 16, 0, tzinfo=hu.FUSO)
SAB = dt.datetime(2026, 11, 14, 10, 0, tzinfo=hu.FUSO)


class TestAJanela:
    def test_as_datas_do_arquivo_sao_os_dias_que_eu_digo(self):
        """⚠️ Se esta reprovar, as outras estão medindo o dia errado."""
        assert SEG.weekday() == 0
        assert SEX.weekday() == 4
        assert SAB.weekday() == 5

    def test_a_janela_e_a_dele_e_da_oito_horas_e_meia(self):
        assert (hu.ABRE.hour, hu.ABRE.minute) == (8, 30)
        assert (hu.FECHA.hour, hu.FECHA.minute) == (17, 0)
        assert hu._SEGUNDOS_NO_DIA == int(8.5 * 3600)

    def test_o_prazo_do_chamado_e_de_24_horas(self):
        """🔵 O número é dele. Trocar isto é decisão dele, não minha."""
        assert hu.PRAZO_CHAMADO_HORAS == 24

    def test_dentro_do_expediente(self):
        assert hu.dentro_do_expediente(SEG) is True
        assert hu.dentro_do_expediente(SAB) is False
        # As bordas: 08:30 está dentro, 17:00 já está fora.
        assert hu.dentro_do_expediente(SEG.replace(hour=8, minute=30)) is True
        assert hu.dentro_do_expediente(SEG.replace(hour=17, minute=0)) is False
        assert hu.dentro_do_expediente(SEG.replace(hour=8, minute=29)) is False


class TestOsSegundosUteis:
    def test_so_conta_o_que_esta_dentro_da_janela(self):
        fim = SEG.replace(hour=17, minute=0)
        assert hu.segundos_uteis_entre(SEG, fim) == 8 * 3600

    def test_a_noite_nao_conta(self):
        """Das 16h de segunda às 10h de terça há 18h de relógio e 2,5h úteis."""
        ter = SEG.replace(day=10, hour=10, minute=0)
        assert hu.segundos_uteis_entre(SEG.replace(hour=16), ter) == int(2.5 * 3600)

    def test_o_fim_de_semana_nao_conta(self):
        """Sexta 16:00 -> segunda 09:00: 1h na sexta + 0,5h na segunda."""
        seg_seguinte = dt.datetime(2026, 11, 16, 9, 0, tzinfo=hu.FUSO)
        assert hu.segundos_uteis_entre(SEX, seg_seguinte) == int(1.5 * 3600)

    def test_nunca_negativo_e_zero_quando_invertido(self):
        assert hu.segundos_uteis_entre(SEX, SEG) == 0.0
        assert hu.segundos_uteis_entre(SEG, SEG) == 0.0

    def test_sabado_inteiro_vale_zero(self):
        domingo = dt.datetime(2026, 11, 15, 23, 0, tzinfo=hu.FUSO)
        assert hu.segundos_uteis_entre(SAB, domingo) == 0.0


class TestOVencimento:
    def test_24_horas_uteis_da_segunda_caem_na_quarta(self):
        """🚨 8h na segunda (09:00->17:00) + 8,5h na terça + 7,5h na quarta."""
        assert hu.vencimento(SEG, 24) == dt.datetime(
            2026, 11, 11, 16, 0, tzinfo=hu.FUSO)

    def test_24_horas_uteis_da_sexta_atravessam_o_fim_de_semana(self):
        """1h na sexta + 8,5 + 8,5 + 6h = quarta da semana seguinte, 14:30."""
        assert hu.vencimento(SEX, 24) == dt.datetime(
            2026, 11, 18, 14, 30, tzinfo=hu.FUSO)

    def test_aberto_fora_do_expediente_comeca_a_contar_no_dia_util_seguinte(self):
        """🚨 Chamado das 19h30 não nasce com meio prazo gasto."""
        noite = SEG.replace(hour=19, minute=30)
        assert hu.vencimento(noite, 8.5) == dt.datetime(
            2026, 11, 10, 17, 0, tzinfo=hu.FUSO)

    def test_aberto_no_sabado_comeca_na_segunda(self):
        assert hu.vencimento(SAB, 1) == dt.datetime(
            2026, 11, 16, 9, 30, tzinfo=hu.FUSO)

    def test_aberto_antes_de_abrir_comeca_as_8h30(self):
        madrugada = SEG.replace(hour=5, minute=0)
        assert hu.vencimento(madrugada, 1) == dt.datetime(
            2026, 11, 9, 9, 30, tzinfo=hu.FUSO)

    def test_o_vencimento_cai_sempre_dentro_do_expediente(self):
        """⚠️ Dizer "vence domingo às 3h" seria mentir com precisão."""
        for horas in (1, 3, 8, 8.5, 9, 16, 24, 40, 100):
            quando = hu.vencimento(SEX, horas)
            assert quando.weekday() < 5, horas
            limite_de_cima = dt.datetime.combine(
                quando.date(), hu.FECHA, tzinfo=hu.FUSO)
            limite_de_baixo = dt.datetime.combine(
                quando.date(), hu.ABRE, tzinfo=hu.FUSO)
            assert limite_de_baixo <= quando <= limite_de_cima, horas

    def test_datetime_ingenuo_e_tratado_como_local(self):
        """⚠️ Assumir UTC deslocaria o prazo em 3 horas, e o erro só apareceria
        perto da borda do dia."""
        ingenuo = dt.datetime(2026, 11, 9, 9, 0)
        assert hu.vencimento(ingenuo, 24) == hu.vencimento(SEG, 24)


class TestOPrazoDoChamado:
    def test_sem_data_de_criacao_devolve_nada(self):
        """Quem mostra escreve "não medido" -- não se inventa prazo de agora."""
        assert hu.prazo_do_chamado(None) is None

    def test_traz_o_vencimento_a_janela_e_as_horas(self):
        p = hu.prazo_do_chamado(SEG)
        assert p["vence_em"].startswith("2026-11-11T16:00")
        assert p["horas"] == 24
        assert p["janela"] == "08:30-17:00"

    def test_chamado_antigo_esta_atrasado_e_o_saldo_e_negativo(self):
        velho = dt.datetime(2026, 1, 5, 9, 0, tzinfo=hu.FUSO)
        p = hu.prazo_do_chamado(velho)
        assert p["atrasado"] is True
        assert p["segundos_uteis"] < 0

    def test_chamado_de_agora_nao_esta_atrasado_e_o_saldo_e_positivo(self):
        agora = dt.datetime.now(hu.FUSO)
        p = hu.prazo_do_chamado(agora)
        assert p["atrasado"] is False
        assert p["segundos_uteis"] > 0
