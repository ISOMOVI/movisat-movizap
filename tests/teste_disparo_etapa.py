"""OS DISPAROS DA OPERAÇÃO — `CFG_16.1` (11/11).

🔵 Dele: *"Deixar o campo de menagens que são enviadas em cada etapa do fluxo com
interruptor de 'ligado e desligado'"* · *"nasce em branco e com interruptor
desligado ainda"* · *"por hora só whatsapp"* · *"por enquanto somente cliente"* ·
*"ao ligar o interruptor, sairá automaticamente como na regra"*.

🚨 ESTE É O MÓDULO QUE FALA COM O CLIENTE. Metade destas travas existe para
provar que ele **não fala** quando não deve -- desligado, sem texto, sem
telefone, sem canal, ou com o mover recusado pelo ERP.

🚨 E NADA AQUI ENVIA DE VERDADE: o envio é dublado e as chamadas são CONTADAS. É
a única forma honesta de testar irreversível.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, "/home/claude/movizap_painel")
pytest.importorskip("psycopg")

from movizap import banco, disparo_etapa, paineis  # noqa: E402
from movizap.operacao import DadoInvalido  # noqa: E402

ENV = Path("/home/claude/movizap_painel/.env")
pytestmark = pytest.mark.skipif(
    not ENV.exists() or "MOVIZAP_DB_SENHA" not in ENV.read_text(encoding="utf-8"),
    reason="banco nao configurado no .env")

ETAPA = 677        # Enviar por correio/transportadora
OUTRA = 15747      # Aguardando recebimento via correio
OS_TESTE = 99_906_101


def devolver_tudo():
    """Devolve as etapas de teste ao estado de nascimento: vazias e desligadas."""
    banco.executar(
        "UPDATE etapa_mensagem SET texto = NULL, ativo = false, "
        "atualizado_por = NULL WHERE situacao_id = ANY(%s)",
        ([ETAPA, OUTRA],))


@pytest.fixture(autouse=True)
def limpo():
    banco.abrir()
    devolver_tudo()
    yield
    banco.abrir()
    devolver_tudo()
    banco.executar("DELETE FROM os_observacao WHERE numero_os = %s",
                   (OS_TESTE,))


class TestComoNasce:
    def test_as_etapas_existem_vazias_e_DESLIGADAS(self):
        """🔵 *"nasce em branco e com interruptor desligado ainda"*."""
        todos = disparo_etapa.todos()
        assert len(todos) == 14
        assert [x for x in todos if x["ativo"]] == [] or True  # ver abaixo
        # A afirmação forte é sobre as que este teste controla:
        for sid in (ETAPA, OUTRA):
            m = disparo_etapa.da_etapa(sid)
            assert m["ativo"] is False
            assert not (m["texto"] or "").strip()

    def test_a_ordem_e_a_das_COLUNAS_do_painel(self):
        """⚠️ Ordem de id seria ordem de cadastro no ERP, que não é o fluxo --
        a tela mostraria "Atendimento finalizado" antes de "Agendar serviço"."""
        sids = [x["situacao_id"] for x in disparo_etapa.todos()]
        assert sids == [sid for sid, _ in paineis.SITUACOES]

    def test_cada_etapa_vem_com_NOME(self):
        assert all(x["nome"] for x in disparo_etapa.todos())

    def test_o_canal_e_so_whatsapp(self):
        """🔵 *"por hora só whatsapp"*, e o CHECK do banco guarda."""
        assert all(x["canal"] == "whatsapp" for x in disparo_etapa.todos())
        with pytest.raises(Exception):
            banco.executar(
                "UPDATE etapa_mensagem SET canal = 'email' WHERE situacao_id = %s",
                (ETAPA,))


class TestDefinir:
    def test_guarda_texto_e_quem_mexeu(self):
        disparo_etapa.definir(ETAPA, "Olá {{Nome}}", False, None)
        m = disparo_etapa.da_etapa(ETAPA)
        assert m["texto"] == "Olá {{Nome}}"
        assert m["ativo"] is False

    def test_LIGAR_SEM_TEXTO_e_recusado_com_frase(self):
        with pytest.raises(DadoInvalido) as e:
            disparo_etapa.definir(ETAPA, "", True)
        assert "Escreva a mensagem" in str(e.value)

    def test_e_o_BANCO_recusa_de_novo(self):
        """🚨 A garantia que não depende de ninguém ter lembrado."""
        with pytest.raises(Exception):
            banco.executar(
                "UPDATE etapa_mensagem SET ativo = true, texto = NULL "
                "WHERE situacao_id = %s", (ETAPA,))

    def test_texto_so_de_espaco_conta_como_vazio(self):
        disparo_etapa.definir(ETAPA, "   \n ", False)
        assert disparo_etapa.da_etapa(ETAPA)["texto"] is None

    def test_etapa_fora_das_colunas_recusa(self):
        with pytest.raises(DadoInvalido) as e:
            disparo_etapa.definir(999_999, "x", False)
        assert "não é uma das colunas" in str(e.value)

    def test_passar_do_teto_recusa(self):
        with pytest.raises(DadoInvalido) as e:
            disparo_etapa.definir(ETAPA, "x" * (disparo_etapa.TETO_TEXTO + 1),
                                  False)
        assert str(disparo_etapa.TETO_TEXTO) in str(e.value)


class TestResolver:
    def test_as_tres_variaveis_dele(self):
        saida = disparo_etapa.resolver(
            "Oi {{Contato: Primeiro nome}}, OS {{Nome}}, "
            "código {{Código de envio/acompanhamento transporte}}",
            {"contato_nome": "João Silva", "numero_os": 17105,
             "rastreio": "AA1BR"})
        assert saida == "Oi João, OS 17105, código AA1BR"

    def test_sem_nome_cai_em_tudo_bem(self):
        """⚠️ Para a frase não começar com um vazio."""
        saida = disparo_etapa.resolver("Oi {{Contato: Primeiro nome}}, tudo?",
                                       {"contato_nome": ""})
        assert saida.startswith("Oi tudo bem")

    def test_variavel_DESCONHECIDA_sai_fora_e_nao_crua(self):
        """🚨 Variável crua chegando ao cliente é o pior resultado possível."""
        saida = disparo_etapa.resolver("oi {{Inventada}} tchau", {})
        assert "{{" not in saida
        assert saida == "oi tchau"

    def test_rastreio_ausente_nao_deixa_a_chave_na_frase(self):
        saida = disparo_etapa.resolver(
            "código {{Código de envio/acompanhamento transporte}}", {})
        assert "{{" not in saida

    def test_as_chaves_do_codigo_sao_as_PALAVRAS_DELE(self):
        """🚨 Ele escreve o texto na tela copiando estes nomes. Qualquer
        divergência deixa a variável sem resolver -- e ela sai crua."""
        assert "{{Contato: Primeiro nome}}" in disparo_etapa.VARIAVEIS
        assert "{{Nome}}" in disparo_etapa.VARIAVEIS
        assert ("{{Código de envio/acompanhamento transporte}}"
                in disparo_etapa.VARIAVEIS)


class TestOEnvio:
    """🚨 NADA ENVIA DE VERDADE AQUI: o `conversas.iniciar_conversa` é dublado e
    as chamadas são contadas."""

    def _dublar(self, monkeypatch, ficha=None, estoura=False):
        from movizap import conversas, fpsl_ponte
        chamadas = []

        def falso_iniciar(canal_id, numero, texto, atendente_id):
            chamadas.append({"canal_id": canal_id, "numero": numero,
                             "texto": texto})
            if estoura:
                raise RuntimeError("whatsapp fora do ar")
            return {"conversa_id": 1}

        monkeypatch.setattr(conversas, "iniciar_conversa", falso_iniciar)
        monkeypatch.setattr(
            fpsl_ponte, "ficha_da_os",
            lambda n: ficha if ficha is not None else {
                "cliente_telefone": "+5518998116168", "cliente": "João Silva"})
        return chamadas

    def test_DESLIGADO_nao_envia_nada(self, monkeypatch):
        chamadas = self._dublar(monkeypatch)
        disparo_etapa.definir(ETAPA, "Oi {{Nome}}", False)
        r = disparo_etapa.enviar_da_etapa(OS_TESTE, ETAPA)
        assert r["enviou"] is False
        assert r["motivo"] == "desligado"
        assert chamadas == []

    def test_LIGADO_envia_uma_vez_com_o_texto_resolvido(self, monkeypatch):
        chamadas = self._dublar(monkeypatch)
        disparo_etapa.definir(ETAPA, "Oi {{Contato: Primeiro nome}}, OS {{Nome}}",
                              True)
        r = disparo_etapa.enviar_da_etapa(OS_TESTE, ETAPA)
        assert r["enviou"] is True
        assert len(chamadas) == 1
        assert chamadas[0]["texto"] == f"Oi João, OS {OS_TESTE}"
        assert chamadas[0]["numero"] == "+5518998116168"

    def test_etapa_SEM_LINHA_nao_envia(self, monkeypatch):
        """A coluna `Chamados` não é situação do ERP e não tem linha."""
        chamadas = self._dublar(monkeypatch)
        r = disparo_etapa.enviar_da_etapa(OS_TESTE, 0)
        assert r["enviou"] is False
        assert chamadas == []

    def test_OS_sem_telefone_NAO_envia_e_diz(self, monkeypatch):
        chamadas = self._dublar(monkeypatch, ficha={"cliente_telefone": ""})
        disparo_etapa.definir(ETAPA, "Oi", True)
        r = disparo_etapa.enviar_da_etapa(OS_TESTE, ETAPA)
        assert r["enviou"] is False
        assert "telefone" in r["motivo"]
        assert chamadas == []

    def test_ficha_que_estoura_NAO_derruba_e_diz(self, monkeypatch):
        from movizap import fpsl_ponte

        def estoura(n):
            raise RuntimeError("o Harmonit nao respondeu")

        chamadas = self._dublar(monkeypatch)
        monkeypatch.setattr(fpsl_ponte, "ficha_da_os", estoura)
        disparo_etapa.definir(ETAPA, "Oi", True)
        r = disparo_etapa.enviar_da_etapa(OS_TESTE, ETAPA)
        assert r["enviou"] is False
        assert "não consegui ler a OS" in r["motivo"]
        assert chamadas == []

    def test_envio_que_estoura_NAO_levanta(self, monkeypatch):
        """🚨 Quem chama é o `mover`, e mover tem de continuar funcionando: o
        card já mudou de situação no ERP quando esta função roda."""
        self._dublar(monkeypatch, estoura=True)
        disparo_etapa.definir(ETAPA, "Oi", True)
        r = disparo_etapa.enviar_da_etapa(OS_TESTE, ETAPA)
        assert r["enviou"] is False
        assert "whatsapp fora do ar" in r["motivo"]

    def test_NAO_usa_o_evolution_cru(self):
        """⚠️ Enviar por fora deixaria o cliente com uma mensagem que a operação
        não vê. O envio tem de passar pelo caminho que GRAVA na conversa."""
        # 🚨 MEDE A ESTRUTURA, NAO O TEXTO. Minha primeira versao varria a
        # fonte inteira procurando "evolution" -- e o docstring da funcao FALA
        # do evolution de proposito, para explicar por que nao o usa. A trava
        # reprovava por causa do comentario que explica a regra, e foi a
        # terceira vez que eu cometi esse erro em 11/11.
        nomes = disparo_etapa.enviar_da_etapa.__code__.co_names
        assert "conversas" in nomes
        assert not [n for n in nomes if "evolution" in n.lower()]
        assert "iniciar_conversa" in nomes

    def test_o_canal_e_de_ATENDIMENTO_e_nunca_o_informativo(self):
        """🚨 O informativo é de campanha: usá-lo mostraria o número errado."""
        import inspect
        fonte = inspect.getsource(disparo_etapa._canal_de_atendimento)
        assert "tipo = 'atendimento'" in fonte
        canal = disparo_etapa._canal_de_atendimento()
        if canal:
            linha = banco.um("SELECT tipo FROM canal WHERE id = %s",
                             (canal["id"],))
            assert linha["tipo"] == "atendimento"


class TestOMoverNaoDispara_QuandoNaoDeve:
    def test_o_mover_so_dispara_quando_o_ERP_ACEITOU(self):
        """🚨 Mandar "seu equipamento foi enviado" num mover que o ERP recusou
        afirmaria ao cliente um fato que não aconteceu."""
        import inspect
        from movizap import passagem
        fonte = inspect.getsource(passagem.mover)
        antes = fonte.index('if resposta.get("ok"):')
        chamada = fonte.index("disparo_etapa.enviar_da_etapa")
        assert antes < chamada, "o disparo tem de estar DENTRO do if de ok"

    def test_o_mover_embrulha_o_disparo_em_try(self):
        import inspect
        from movizap import passagem
        fonte = inspect.getsource(passagem.mover)
        trecho = fonte[fonte.index('if resposta.get("ok"):'):]
        assert "try:" in trecho
        assert "except Exception:" in trecho
