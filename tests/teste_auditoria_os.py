# -*- coding: utf-8 -*-
"""Os dois agentes da auditoria de OS — 🔵 desenho dele, 18/11.

🚨 NENHUM DESTES TESTES FALA COM O HARMONIT: a leitura e a escrita entram por
parâmetro (`ler=`, `gravar=`, `esperar=`), que é como o módulo foi escrito.

O que estes testes guardam, e cada um nasceu de um fato medido:

  · **duas leituras, não uma.** Na OS 17133 (18/11) a mesma rota devolveu 251
    e, 31 segundos depois, 16488, sem escrita no meio. Com uma leitura só, o
    escritor reescreveria situação correta por cima de situação correta.
  · **valor que NÓS escrevemos antes é atraso, não erro** — e atraso não vai ao
    escritor nem vira red flag.
  · **o escritor não decide**: a lista é do auditor.
  · **quem fecha é a releitura**, nunca o escritor.
  · **silêncio quando está tudo em dia.**

🚨 ESCREVE EM `os_passagem` E `auditoria_os`, que são de produção, com faixa
própria de OS (`9973xx`; as reais vão até 17 mil) e tudo apagado no fim.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, "/home/claude/movizap_painel")
pytest.importorskip("psycopg")

from movizap import auditoria_os, banco  # noqa: E402

ENV = Path("/home/claude/movizap_painel/.env")
pytestmark = pytest.mark.skipif(
    not ENV.exists() or "MOVIZAP_DB_SENHA" not in ENV.read_text(encoding="utf-8"),
    reason="banco nao configurado no .env")

OS_BASE = 997300
FAIXA = list(range(OS_BASE, OS_BASE + 40))


@pytest.fixture(autouse=True)
def limpo():
    banco.abrir()
    _limpar()
    yield
    banco.abrir()
    _limpar()


def _limpar():
    banco.executar("DELETE FROM auditoria_os WHERE numero_os = ANY(%s)",
                   (FAIXA,))
    banco.executar("DELETE FROM os_passagem WHERE numero_os = ANY(%s)",
                   (FAIXA,))


def _moveu(numero_os, de, para, *, ha_segundos=120):
    """Uma passagem nossa confirmada: é isto que cria 'a coluna nossa'."""
    banco.executar(
        "INSERT INTO os_passagem (numero_os, de_situacao, para_situacao, ok, em) "
        "VALUES (%s, %s, %s, true, now() - make_interval(secs => %s))",
        (numero_os, de, para, ha_segundos))


def _leitor(mapa, contador=None):
    """Um Harmonit de mentira. `mapa[os]` pode ser valor ou lista (1ª, 2ª…)."""
    estado = {k: list(v) if isinstance(v, list) else [v]
              for k, v in mapa.items()}

    def ler(numero_os):
        if contador is not None:
            contador.append(numero_os)
        fila = estado.get(numero_os)
        if not fila:
            return None, "OS fora do cenario"
        return (fila.pop(0) if len(fila) > 1 else fila[0]), ""
    return ler


def _linha(numero_os):
    return banco.um(
        "SELECT * FROM auditoria_os WHERE numero_os = %s "
        " ORDER BY id DESC LIMIT 1", (numero_os,))


class TestOAuditor:
    def test_situacao_IGUAL_nao_abre_nada(self):
        _moveu(OS_BASE + 1, 251, 16488)
        r = auditoria_os.auditar(ler=_leitor({OS_BASE + 1: 16488}))
        assert r["iguais"] >= 1
        assert _linha(OS_BASE + 1) is None

    def test_valor_QUE_NUNCA_ESCREVEMOS_e_MUDANCA_NO_ERP_e_nao_se_reescreve(self):
        """🚨 O CONSERTO QUE O ENSAIO A SECO OBRIGOU, em 18/11.

        Rodando contra a produção antes de ligar a escrita, o auditor achou:

            OS 17054: o painel diz 251   e o Harmonit diz 16490
            OS 17114: o painel diz 15696 e o Harmonit diz 16490

        E 16490 **nunca foi escrito por nós**: alguém avançou essas OS dentro
        do Harmonit. O ERP está certo e o nosso card está velho.

        ⚠️ O escritor, como eu o havia escrito, puxaria a 17054 de *"Analise de
        Equipamentos Retornados"* de volta para *"Configurar equipamentos e
        Sistemas"* -- desfazendo, numa OS de cliente, o trabalho de quem fez a
        coisa certa.
        """
        _moveu(OS_BASE + 2, 251, 16488)
        r = auditoria_os.auditar(ler=_leitor({OS_BASE + 2: 15694}))
        assert r["mudou_no_erp"] == 1, r
        assert r["escritas_perdidas"] == 0
        linha = _linha(OS_BASE + 2)
        assert linha["veredito"] == "mudou_no_erp"
        assert linha["coluna_nossa"] == 16488
        assert linha["situacao_do_erp"] == 15694
        # 🚨 E NÃO VAI PARA O ESCRITOR.
        assert [d for d in auditoria_os.abertas()
                if d["numero_os"] == OS_BASE + 2] == []

    def test_mudanca_no_ERP_vira_AVISO_e_nao_trabalho(self):
        """⚠️ Informação: o card é que estava atrás, e quem olhar precisa
        saber. Mas ninguém tem de fazer nada no ERP."""
        _moveu(OS_BASE + 20, 251, 16488)
        auditoria_os.auditar(ler=_leitor({OS_BASE + 20: 15694}))
        aviso = [d for d in auditoria_os.para_a_red_flag()
                 if d["numero_os"] == OS_BASE + 20]
        assert aviso, "mudanca no ERP tem de aparecer"
        assert aviso[0]["veredito"] == "mudou_no_erp"

    def test_valor_NOSSO_e_escrita_ANTIGA_e_ESCRITA_PERDIDA(self):
        """🔵 1 hora, número dele: acima disso não é mais atraso de leitura, a
        escrita se perdeu. É a ÚNICA que o escritor reescreve."""
        _moveu(OS_BASE + 21, 38, 251, ha_segundos=86400)
        _moveu(OS_BASE + 21, 251, 16488, ha_segundos=7200)
        r = auditoria_os.auditar(ler=_leitor({OS_BASE + 21: 251}))
        assert r["escritas_perdidas"] == 1, r
        assert _linha(OS_BASE + 21)["veredito"] == "escrita_perdida"
        assert [d for d in auditoria_os.abertas()
                if d["numero_os"] == OS_BASE + 21]

    def test_valor_QUE_NOS_ESCREVEMOS_antes_e_ATRASO(self):
        """🚨 O caso exato da OS 17133. Escrevemos 251 e depois 16488; o ERP
        responde 251 — o valor é NOSSO, de uma escrita anterior. A leitura dele
        atrasou, ninguém mexeu em nada."""
        _moveu(OS_BASE + 3, 38, 251, ha_segundos=600)
        _moveu(OS_BASE + 3, 251, 16488, ha_segundos=300)
        r = auditoria_os.auditar(ler=_leitor({OS_BASE + 3: 251}))
        assert r["atrasos"] == 1, r
        assert r["escritas_perdidas"] == 0
        assert _linha(OS_BASE + 3)["veredito"] == "atraso"

    def test_atraso_NAO_vai_para_o_escritor(self):
        """⚠️ É o ponto todo: reescrever aqui gastaria o pool que a madrugada
        deveria poupar, sobre uma OS que já está certa."""
        _moveu(OS_BASE + 4, 38, 251, ha_segundos=600)
        _moveu(OS_BASE + 4, 251, 16488, ha_segundos=300)
        auditoria_os.auditar(ler=_leitor({OS_BASE + 4: 251}))
        assert [d for d in auditoria_os.abertas()
                if d["numero_os"] == OS_BASE + 4] == []

    def test_atraso_NAO_vira_RED_FLAG(self):
        _moveu(OS_BASE + 5, 38, 251, ha_segundos=600)
        _moveu(OS_BASE + 5, 251, 16488, ha_segundos=300)
        auditoria_os.auditar(ler=_leitor({OS_BASE + 5: 251}))
        assert [d for d in auditoria_os.para_a_red_flag()
                if d["numero_os"] == OS_BASE + 5] == []

    def test_LE_DUAS_VEZES_e_a_2a_so_para_quem_divergiu(self):
        """🚨 A regra que a 17133 obrigou — e a 2ª leitura é só das divergentes,
        senão a rodada custaria o dobro para confirmar o que já estava igual."""
        lidas = []
        _moveu(OS_BASE + 6, 251, 16488)   # vai bater
        _moveu(OS_BASE + 7, 251, 16488)   # vai divergir
        auditoria_os.auditar(ler=_leitor(
            {OS_BASE + 6: 16488, OS_BASE + 7: 15694}, contador=lidas))
        assert lidas.count(OS_BASE + 6) == 1
        assert lidas.count(OS_BASE + 7) == 2

    def test_o_ATRASO_que_se_RESOLVE_entre_as_duas_leituras(self):
        """🚨 Literalmente a 17133 às 11:43: a 1ª leitura trouxe o valor velho,
        a 2ª já trouxe o certo. Não é divergência nem leitura instável: é o
        atraso passando."""
        _moveu(OS_BASE + 8, 251, 16488)
        r = auditoria_os.auditar(ler=_leitor({OS_BASE + 8: [251, 16488]}))
        assert r["atrasos"] == 1, r
        assert _linha(OS_BASE + 8)["veredito"] == "atraso"

    def test_duas_leituras_QUE_DISCORDAM_nao_confirmam_nada(self):
        _moveu(OS_BASE + 9, 251, 16488)
        r = auditoria_os.auditar(ler=_leitor({OS_BASE + 9: [15694, 890]}))
        assert r["nao_confirmadas"] == 1, r
        assert _linha(OS_BASE + 9)["veredito"] == "nao_confirmada"

    def test_leitura_que_FALHA_nao_vira_divergencia(self):
        """⚠️ ERP sem responder não é OS errada. Chamar isso de divergência
        mandaria o escritor gravar por cima de um estado desconhecido."""
        _moveu(OS_BASE + 10, 251, 16488)

        def cai(numero_os):
            return None, "FpslIndisponivel: encenado"

        r = auditoria_os.auditar(ler=cai)
        assert r["sem_leitura"] >= 1
        assert _linha(OS_BASE + 10) is None

    def test_o_auditor_NAO_ESCREVE_no_erp(self):
        """🚨 A separação é a decisão dele. Trava por texto porque nenhum dublê
        pega: se alguém acrescentar a escrita aqui, tudo continua "funcionando"."""
        import inspect
        fonte = inspect.getsource(auditoria_os.auditar)
        assert "gravar_situacao" not in fonte
        assert "gravar" not in fonte

    def test_UMA_linha_aberta_por_OS_mesmo_em_duas_rodadas(self):
        """⚠️ Sem isto, uma OS parada criaria uma linha por noite e a red flag
        contaria o mesmo problema várias vezes.

        🚨 O cenário é `escrita_perdida`, que é a que FICA aberta esperando o
        escritor. `mudou_no_erp` fecha na hora (migração 116) — ali não há o que
        fazer, e o que impede a repetição é o `avisada_em`, não o índice.
        """
        _moveu(OS_BASE + 11, 38, 251, ha_segundos=86400)
        _moveu(OS_BASE + 11, 251, 16488, ha_segundos=7200)
        auditoria_os.auditar(ler=_leitor({OS_BASE + 11: 251}))
        auditoria_os.auditar(ler=_leitor({OS_BASE + 11: 251}))
        n = banco.um("SELECT COUNT(*) AS n FROM auditoria_os "
                     " WHERE numero_os = %s AND fechada_em IS NULL",
                     (OS_BASE + 11,))["n"]
        assert n == 1


class TestOEscritor:
    def _abrir(self, numero_os, nossa=16488):
        """Abre uma `escrita_perdida`, que é a única que o escritor pega.

        ⚠️ O ERP devolve 251, que É um valor nosso (escrito antes), e a nossa
        última passagem é de 2h -- acima da 1 hora dele.
        """
        _moveu(numero_os, 38, 251, ha_segundos=86400)
        _moveu(numero_os, 251, nossa, ha_segundos=7200)
        auditoria_os.auditar(ler=_leitor({numero_os: 251}))

    def test_escreve_A_COLUNA_NOSSA_e_anota_na_MESMA_linha(self):
        """🔵 *"guardar os logs juntos para evitar perca"*."""
        vistos = []
        self._abrir(OS_BASE + 12)

        def gravar(numero_os, situacao_id, **k):
            vistos.append((numero_os, situacao_id, k))
            return {"ok": True}

        feito = auditoria_os.escrever(gravar=gravar, esperar=lambda s: None)
        assert feito["escritas"] == 1, feito
        assert vistos[0][0] == OS_BASE + 12
        assert vistos[0][1] == 16488
        # ⚠️ `conferir_antes=False`: a trava de concorrência compararia com uma
        # situacao_esperada que não existe aqui, e recusaria a própria correção.
        assert vistos[0][2].get("conferir_antes") is False
        linha = _linha(OS_BASE + 12)
        assert linha["tentativas"] >= 1
        assert linha["escrito_em"] is not None

    def test_o_escritor_NAO_fecha_a_linha(self):
        """🚨 Quem diz que ficou bom é a releitura, nunca o escritor."""
        self._abrir(OS_BASE + 13)
        auditoria_os.escrever(gravar=lambda *a, **k: {"ok": True},
                              esperar=lambda s: None)
        assert _linha(OS_BASE + 13)["fechada_em"] is None

    def test_recusa_de_NEGOCIO_nao_consome_os_grupos(self):
        """🔵 *"só cansa a req"*. Repetir colhe o mesmo não e gasta o pool."""
        chamadas = []
        self._abrir(OS_BASE + 14)

        def gravar(numero_os, situacao_id, **k):
            chamadas.append(numero_os)
            return {"ok": False, "causa": "recusa_do_erp",
                    "motivo": "Produto e obrigatorio", "pode_retentar": False}

        feito = auditoria_os.escrever(gravar=gravar, esperar=lambda s: None)
        assert feito["desistiu"] == 1, feito
        # Uma tentativa, não nove.
        assert len(chamadas) == 1, chamadas
        assert _linha(OS_BASE + 14)["veredito"] == "desistiu"

    def test_falha_RETENTAVEL_usa_os_tres_grupos(self):
        chamadas = []
        esperas = []
        self._abrir(OS_BASE + 15)

        def gravar(numero_os, situacao_id, **k):
            chamadas.append(numero_os)
            return {"ok": False, "causa": "leitura_falhou",
                    "motivo": "pool esgotado", "pode_retentar": True}

        feito = auditoria_os.escrever(gravar=gravar,
                                      esperar=lambda s: esperas.append(s))
        # 🔵 3 grupos de 3 = 9 tentativas, números dele.
        assert len(chamadas) == 9, chamadas
        assert feito["grupos_usados"] == 3
        # 🔵 5 minutos entre os grupos, e dois intervalos para três grupos.
        assert esperas == [300, 300], esperas
        assert feito["desistiu"] == 1

    def test_o_escritor_NAO_decide_a_lista(self):
        """🚨 Se ele olhasse o ERP para escolher, voltaria a ser um agente só —
        e a separação que ele pediu existe para a escrita ficar longe da
        leitura."""
        import inspect
        fonte = inspect.getsource(auditoria_os.escrever)
        assert "abertas()" in fonte
        assert "ficha_da_os" not in fonte
        assert "_ler_do_erp" not in fonte


class TestAVoltaEOVerde:
    def test_a_RELEITURA_fecha_verde(self):
        _moveu(OS_BASE + 16, 38, 251, ha_segundos=86400)
        _moveu(OS_BASE + 16, 251, 16488, ha_segundos=7200)
        auditoria_os.auditar(ler=_leitor({OS_BASE + 16: 251}))
        auditoria_os.escrever(gravar=lambda *a, **k: {"ok": True},
                              esperar=lambda s: None)
        fechadas = auditoria_os.fechar_relendo(
            ler=_leitor({OS_BASE + 16: 16488}))
        assert fechadas["verdes"] == 1, fechadas
        linha = _linha(OS_BASE + 16)
        assert linha["veredito"] == "resolvida"
        assert linha["fechada_como"] == "igual"

    def test_releitura_que_AINDA_DIFERE_vira_red_flag(self):
        _moveu(OS_BASE + 17, 38, 251, ha_segundos=86400)
        _moveu(OS_BASE + 17, 251, 16488, ha_segundos=7200)
        auditoria_os.auditar(ler=_leitor({OS_BASE + 17: 251}))
        auditoria_os.escrever(gravar=lambda *a, **k: {"ok": True},
                              esperar=lambda s: None)
        fechadas = auditoria_os.fechar_relendo(
            ler=_leitor({OS_BASE + 17: 15694}))
        assert fechadas["ainda_diferentes"] == 1, fechadas
        assert [d for d in auditoria_os.para_a_red_flag()
                if d["numero_os"] == OS_BASE + 17]

    def test_escrita_ACEITA_mas_OS_inalterada_NAO_e_verde(self):
        """🚨 O retorno da escrita não prova nada: foi assim que a recusa falsa
        da 17133 sobreviveu sete tentativas."""
        _moveu(OS_BASE + 18, 38, 251, ha_segundos=86400)
        _moveu(OS_BASE + 18, 251, 16488, ha_segundos=7200)
        auditoria_os.auditar(ler=_leitor({OS_BASE + 18: 251}))
        auditoria_os.escrever(gravar=lambda *a, **k: {"ok": True},
                              esperar=lambda s: None)
        auditoria_os.fechar_relendo(ler=_leitor({OS_BASE + 18: 251}))
        assert _linha(OS_BASE + 18)["veredito"] == "desistiu"


class TestOSilencio:
    def test_sem_divergencia_a_RED_FLAG_e_vazia(self):
        """🚨 *"aviso que aparece todo dia vira aviso que ninguém lê"*."""
        _moveu(OS_BASE + 19, 251, 16488)
        auditoria_os.auditar(ler=_leitor({OS_BASE + 19: 16488}))
        assert [d for d in auditoria_os.para_a_red_flag()
                if d["numero_os"] in FAIXA] == []

    def test_os_numeros_sao_DELE(self):
        """⚠️ 3 grupos, 3 tentativas, 5 min, e a hora 03:00 — todos escolhidos
        por ele em 18/11. Não se mudam sem a palavra dele."""
        assert auditoria_os.GRUPOS == 3
        assert auditoria_os.TENTATIVAS_POR_GRUPO == 3
        assert auditoria_os.SEGUNDOS_ENTRE_GRUPOS == 300
        assert auditoria_os.HORAS_DE_ESPERA_DO_ATRASO == 1


class TestOAvisoSaiUMAVezSo:
    """🚨 DEFEITO MEU, achado em 18/11 ao conferir o que a rodada SEGUINTE diria.

    As duas linhas que o ensaio a seco abriu (OS 17054 e 17114, `mudou_no_erp`)
    ficavam com `fechada_em` nulo para sempre, e a red flag as pegava por
    `veredito = 'mudou_no_erp' AND fechada_em IS NULL`. **As mesmas duas OS
    sairiam na mensagem todas as noites, indefinidamente.**

    ⚠️ E o problema é mais fundo que a coluna que faltava: `coluna_nossa` é a
    nossa última passagem confirmada, e ela **nunca** vai voltar a bater com um
    valor que nós não escrevemos. A divergência é permanente por construção —
    avisar dela sem parar é avisar de um fato que não tem conserto, e treina a
    pessoa a ignorar o vigia.

    🔵 Contra a regra dele que o resto do desenho respeita: *"aviso que aparece
    todo dia vira aviso que ninguém lê"*.
    """

    def test_mudanca_no_ERP_FECHA_a_linha_na_hora(self):
        """⚠️ Não há o que fazer: o card já segue o ERP, que vem do cache. A
        linha existe para avisar uma vez e ficar no histórico."""
        _moveu(OS_BASE + 22, 251, 16488)
        auditoria_os.auditar(ler=_leitor({OS_BASE + 22: 15694}))
        linha = _linha(OS_BASE + 22)
        assert linha["veredito"] == "mudou_no_erp"
        assert linha["fechada_em"] is not None

    def test_a_SEGUNDA_rodada_nao_avisa_de_novo(self):
        """🚨 O teste que guarda o defeito."""
        _moveu(OS_BASE + 23, 251, 16488)
        auditoria_os.auditar(ler=_leitor({OS_BASE + 23: 15694}))
        quais = [d for d in auditoria_os.para_a_red_flag()
                 if d["numero_os"] == OS_BASE + 23]
        assert len(quais) == 1, "a primeira rodada tem de avisar"
        auditoria_os.marcar_avisadas([d["id"] for d in quais])
        # A noite seguinte, o mesmo cenário:
        r = auditoria_os.auditar(ler=_leitor({OS_BASE + 23: 15694}))
        assert r["ja_aceito"] == 1, r
        assert [d for d in auditoria_os.para_a_red_flag()
                if d["numero_os"] == OS_BASE + 23] == []

    def test_mas_um_TERCEIRO_valor_volta_a_avisar(self):
        """⚠️ Aceitar é lembrar DAQUELA mudança, não calar para sempre: se
        alguém mover a OS outra vez, para outro valor que também não é nosso,
        isso é fato novo."""
        _moveu(OS_BASE + 24, 251, 16488)
        auditoria_os.auditar(ler=_leitor({OS_BASE + 24: 15694}))
        quais = [d for d in auditoria_os.para_a_red_flag()
                 if d["numero_os"] == OS_BASE + 24]
        auditoria_os.marcar_avisadas([d["id"] for d in quais])
        r = auditoria_os.auditar(ler=_leitor({OS_BASE + 24: 16491}))
        assert r["mudou_no_erp"] == 1, r
        assert [d for d in auditoria_os.para_a_red_flag()
                if d["numero_os"] == OS_BASE + 24]

    def test_marcar_avisadas_NAO_apaga_o_historico(self):
        """⚠️ A linha fica: ela é o registro de que aquilo aconteceu e foi
        aceito. O que muda é só o aviso."""
        _moveu(OS_BASE + 25, 251, 16488)
        auditoria_os.auditar(ler=_leitor({OS_BASE + 25: 15694}))
        quais = [d for d in auditoria_os.para_a_red_flag()
                 if d["numero_os"] == OS_BASE + 25]
        auditoria_os.marcar_avisadas([d["id"] for d in quais])
        linha = _linha(OS_BASE + 25)
        assert linha is not None
        assert linha["situacao_do_erp"] == 15694
        assert linha["avisada_em"] is not None
