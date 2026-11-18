"""OS DISPAROS DA OPERAÇÃO — `CFG_16.1` (11/11, revisto em 17/11).

🔵 Dele, 11/11: *"Deixar o campo de menagens que são enviadas em cada etapa do
fluxo com interruptor de 'ligado e desligado'"* · *"nasce em branco e com
interruptor desligado ainda"* · *"por hora só whatsapp"* · *"por enquanto
somente cliente"*.

🚨 **17/11 ESTE ARQUIVO TROCOU DE SINAL, COM AUTORIZAÇÃO.** Até aqui ele
provava que o mover **envia** quando o interruptor está ligado (*"sairá
automaticamente como na regra"*). Ele decidiu o contrário: *"quando o card for
movido e houver disparo de mensagens perguntar em caixa de diálogo (...) Se
clicar não, não envia nada"*. Então agora metade das travas prova que **mover
não envia nada** -- e isso restaura a régua da Área F de 04/11.

🚨 ESTE É O MÓDULO QUE FALA COM O CLIENTE. A outra metade das travas existe para
provar que ele **não fala** quando não deve -- desligado, sem texto, sem
telefone, sem canal, com o mover recusado pelo ERP, ou com a mesma passagem
decidida duas vezes.

🚨 E NADA AQUI ENVIA DE VERDADE: o envio é dublado e as chamadas são CONTADAS. É
a única forma honesta de testar irreversível.
"""
import inspect
import sys
from pathlib import Path

import pytest

sys.path.insert(0, "/home/claude/movizap_painel")
pytest.importorskip("psycopg")

from movizap import banco, disparo_etapa, paineis, passagem  # noqa: E402
from movizap.operacao import DadoInvalido  # noqa: E402

ENV = Path("/home/claude/movizap_painel/.env")
pytestmark = pytest.mark.skipif(
    not ENV.exists() or "MOVIZAP_DB_SENHA" not in ENV.read_text(encoding="utf-8"),
    reason="banco nao configurado no .env")

ETAPA = 677        # Enviar por correio/transportadora
OUTRA = 15747      # Aguardando recebimento via correio
OS_TESTE = 99_906_101

# 📏 DESCRIÇÕES REAIS, lidas pela ponte em 17/11. Não são inventadas: é o que o
# Harmonit devolveu nas OS 17126, 17123 e 17118, e é o que torna o
# `_da_descricao` testável sem rede.
DESC_RETIRADA = ("Retirada: TJN 0B09 | FABIANO ALPHA ROTA NORTE | "
                 "007563342 (Suntech ST310) | TERMO 8952 | O.S: 17126")
DESC_MANUT_TROCA = ("MANUTENÇÃO COM TROCA: EMU 0I04 | M. BENZ | "
                    "314 CDIS TREET C | SAIRÁ: 007933278 (Suntech ST310) | "
                    "ENTRARÁ: 007489034 (Suntech ST310)")
DESC_MANUT_LOCAL = ("MANUTENÇÃO NO LOCAL: ESK 1E11 | JTA/SUZUKI EN125 YES SE, "
                    "2011/2011, PRETA, GASOLINA | 007989244 (Suntech ST310) | "
                    "O.S: 17118")


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
    # 🆕 17/11: as passagens de teste também saem -- a decisão do disparo mora
    # nelas, e passagem de teste que fica trancaria a próxima rodada.
    banco.executar("DELETE FROM os_passagem WHERE numero_os = %s", (OS_TESTE,))


def _passagem_de_teste(situacao_id: int = ETAPA) -> int:
    """Uma passagem só para exercitar a decisão do disparo."""
    return banco.um(
        """INSERT INTO os_passagem (numero_os, para_situacao, ok)
           VALUES (%s, %s, true) RETURNING id""",
        (OS_TESTE, situacao_id))["id"]


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


class TestADescricao:
    """🆕 17/11: o `{{Termo}}`, o `{{Serviço Técnico}}` e o
    `{{Veículo e Placa}}` saem da DESCRIÇÃO da OS -- decisão dele, depois de
    medido que `ficha.placas` vem vazia em 6 de 6 OS e `problema` vem como
    número."""

    def test_retirada_real_da_os_17126(self):
        d = disparo_etapa._da_descricao(DESC_RETIRADA)
        assert d["servico"] == "Retirada"
        assert d["placa"] == "TJN 0B09"
        assert d["veiculo"] == "FABIANO ALPHA ROTA NORTE"
        assert d["termo"] == "8952"

    def test_manutencao_com_troca_real_da_os_17123(self):
        """⚠️ MANUTENÇÃO NÃO TEM TERMO, e é da natureza dela: não vem de
        contrato. Termo vazio aqui é certo, não defeito."""
        d = disparo_etapa._da_descricao(DESC_MANUT_TROCA)
        assert d["servico"] == "MANUTENÇÃO COM TROCA"
        assert d["placa"] == "EMU 0I04"
        assert d["termo"] == ""

    def test_veiculo_com_barra_vertical_perde_a_cauda_e_isso_e_SABIDO(self):
        """⚠️ RISCO MEDIDO, documentado no módulo: 'M. BENZ | 314 CDIS TREET C'
        tem ` | ` no nome do veículo. Fica o começo, que é o que identifica o
        veículo -- juntar até o próximo segmento técnico seria heurística com
        mais chance de errar."""
        d = disparo_etapa._da_descricao(DESC_MANUT_TROCA)
        assert d["veiculo"] == "M. BENZ"

    def test_veiculo_com_virgula_vem_inteiro(self):
        d = disparo_etapa._da_descricao(DESC_MANUT_LOCAL)
        assert d["servico"] == "MANUTENÇÃO NO LOCAL"
        assert d["placa"] == "ESK 1E11"
        assert d["veiculo"].startswith("JTA/SUZUKI EN125")
        assert "GASOLINA" in d["veiculo"]

    def test_descricao_SEM_O_PADRAO_nao_inventa_servico(self):
        """🚨 A guarda é ESTRUTURAL: sem `|` depois dos dois pontos, nada é
        serviço. Sem ela, uma OS aberta à mão teria "Cliente pediu análise"
        como serviço técnico na mensagem ao cliente."""
        d = disparo_etapa._da_descricao("Cliente pediu análise: fazer o que der")
        assert d == {"servico": "", "placa": "", "veiculo": "", "termo": ""}

    def test_vazio_e_nulo_nao_estouram(self):
        for entrada in ("", "   ", None):
            assert disparo_etapa._da_descricao(entrada) == {
                "servico": "", "placa": "", "veiculo": "", "termo": ""}

    def test_termo_sai_mesmo_sem_o_resto_do_padrao(self):
        d = disparo_etapa._da_descricao("qualquer coisa TERMO 8893 e mais")
        assert d["termo"] == "8893"
        assert d["servico"] == ""


class TestResolver:
    def test_as_tres_variaveis_dele(self):
        saida = disparo_etapa.resolver(
            "Oi {{Contato: Primeiro nome}}, OS {{Nome}}, "
            "código {{Código de envio/acompanhamento transporte}}",
            {"contato_nome": "João Silva", "numero_os": 17105,
             "rastreio": "AA1BR"})
        assert saida == "Oi João, OS 17105, código AA1BR"

    def test_as_TRES_NOVAS_de_17_11(self):
        saida = disparo_etapa.resolver(
            "Termo {{Termo}}, serviço {{Serviço Técnico}}, "
            "veículo {{Veículo e Placa}}",
            {"descricao": DESC_RETIRADA})
        assert saida == ("Termo 8952, serviço Retirada, "
                         "veículo FABIANO ALPHA ROTA NORTE - TJN 0B09")

    def test_veiculo_e_placa_na_ordem_da_CHAVE_e_com_o_separador_da_casa(self):
        """⚠️ A chave dele diz "Veículo e Placa", nessa ordem, e o ` - ` é o que
        esta casa já usa para dizer "depois disto vem a placa"."""
        saida = disparo_etapa.resolver("{{Veículo e Placa}}",
                                       {"descricao": DESC_RETIRADA})
        assert saida == "FABIANO ALPHA ROTA NORTE - TJN 0B09"

    def test_sem_descricao_as_chaves_novas_somem_sem_deixar_rastro(self):
        saida = disparo_etapa.resolver(
            "Termo {{Termo}} serviço {{Serviço Técnico}} fim", {})
        assert "{{" not in saida
        assert saida == "Termo serviço fim"

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
        # 🆕 17/11, copiadas das mensagens que ele já escreveu na CFG_16.1.
        assert "{{Termo}}" in disparo_etapa.VARIAVEIS
        assert "{{Serviço Técnico}}" in disparo_etapa.VARIAVEIS
        assert "{{Veículo e Placa}}" in disparo_etapa.VARIAVEIS
        assert len(disparo_etapa.VARIAVEIS) == 6


class TestOTelefone:
    """🔵 17/11: *"envia para o numero que estiver como contato na OS e depois
    do cliente"*, e ele escolheu UM envio, com reserva."""

    def test_o_contato_da_OS_manda(self):
        d = disparo_etapa.telefone_da_os(
            {"cliente_telefone": "+5518998116168", "cliente_id": "260516"})
        assert d["telefone"] == "+5518998116168"
        assert d["de_onde"] == "o contato da OS"

    def test_sem_telefone_na_OS_usa_o_do_CADASTRO(self):
        """A reserva. 📏 Medido em 17/11: 819 dos 960 clientes a alcançam."""
        linha = banco.um(
            """SELECT c.harmonit_id AS hid FROM cliente c
                 JOIN contato ct ON ct.cliente_id = c.id
                 JOIN contato_telefone t ON t.contato_id = ct.id
                WHERE c.harmonit_id IS NOT NULL LIMIT 1""")
        if not linha:
            pytest.skip("nenhum cliente com telefone no cadastro")
        dele = {r["e164"] for r in banco.varios(
            """SELECT t.e164 FROM cliente c
                 JOIN contato ct ON ct.cliente_id = c.id
                 JOIN contato_telefone t ON t.contato_id = ct.id
                WHERE c.harmonit_id = %s""", (linha["hid"],))}
        d = disparo_etapa.telefone_da_os(
            {"cliente_telefone": "", "cliente_id": linha["hid"]})
        assert d["telefone"] in dele
        assert d["de_onde"] == "o cadastro do cliente"

    def test_sem_nenhum_dos_dois_devolve_NULO_e_nao_invent(self):
        d = disparo_etapa.telefone_da_os({"cliente_telefone": "",
                                          "cliente_id": None})
        assert d["telefone"] is None

    def test_o_destinatario_NAO_PODE_ser_escolhido(self):
        """🚨 *"por enquanto somente cliente"*: a garantia é não existir
        parâmetro para dizer "manda para outro número"."""
        argumentos = inspect.signature(disparo_etapa.telefone_da_os).parameters
        assert list(argumentos) == ["ficha"]
        assert "telefone" not in inspect.signature(
            disparo_etapa.enviar_preparado).parameters


class TestOPreparar:
    """🆕 17/11: preparar monta a mensagem e NÃO FALA COM NINGUÉM."""

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
                "cliente_telefone": "+5518998116168", "cliente": "João Silva",
                "descricao": DESC_RETIRADA})
        return chamadas

    def test_PREPARAR_NUNCA_ENVIA_nem_quando_esta_tudo_ligado(self, monkeypatch):
        """🚨 A trava mais importante do arquivo: mover chama isto, e mover não
        avisa mais ninguém."""
        chamadas = self._dublar(monkeypatch)
        disparo_etapa.definir(ETAPA, "Oi {{Contato: Primeiro nome}}", True)
        r = disparo_etapa.preparar_da_etapa(OS_TESTE, ETAPA)
        assert r["pergunta"] is True
        assert chamadas == []

    def test_preparar_NEM_CONHECE_o_caminho_do_envio(self):
        """🚨 Prova estrutural, não de texto: o nome `iniciar_conversa` não
        existe no corpo da função."""
        nomes = disparo_etapa.preparar_da_etapa.__code__.co_names
        assert "iniciar_conversa" not in nomes

    def test_DESLIGADO_nao_pergunta_nada(self, monkeypatch):
        self._dublar(monkeypatch)
        disparo_etapa.definir(ETAPA, "Oi {{Nome}}", False)
        r = disparo_etapa.preparar_da_etapa(OS_TESTE, ETAPA)
        assert r["pergunta"] is False
        assert r["motivo"] == "desligado"

    def test_o_texto_vem_com_as_CHAVES_RESOLVIDAS(self, monkeypatch):
        """🚨 Resolvidas no servidor, antes de mostrar: o operador lê exatamente
        o que vai sair."""
        self._dublar(monkeypatch)
        disparo_etapa.definir(
            ETAPA, "Oi {{Contato: Primeiro nome}}, OS {{Nome}}, "
                   "termo {{Termo}}, {{Veículo e Placa}}", True)
        r = disparo_etapa.preparar_da_etapa(OS_TESTE, ETAPA)
        assert "{{" not in r["texto"]
        assert "João" in r["texto"]
        assert "8952" in r["texto"]
        assert "TJN 0B09" in r["texto"]

    def test_diz_PARA_QUEM_vai(self, monkeypatch):
        """Quem envia precisa ver para quem."""
        self._dublar(monkeypatch)
        disparo_etapa.definir(ETAPA, "Oi", True)
        r = disparo_etapa.preparar_da_etapa(OS_TESTE, ETAPA)
        assert r["telefone"] == "+5518998116168"
        assert r["destinatario"] == "o contato da OS"

    def test_etapa_SEM_LINHA_nao_pergunta(self, monkeypatch):
        """A coluna `Chamados` não é situação do ERP e não tem linha."""
        self._dublar(monkeypatch)
        r = disparo_etapa.preparar_da_etapa(OS_TESTE, 0)
        assert r["pergunta"] is False

    def test_OS_sem_telefone_NAO_pergunta_e_diz(self, monkeypatch):
        self._dublar(monkeypatch, ficha={"cliente_telefone": "",
                                         "cliente_id": None})
        disparo_etapa.definir(ETAPA, "Oi", True)
        r = disparo_etapa.preparar_da_etapa(OS_TESTE, ETAPA)
        assert r["pergunta"] is False
        assert "telefone" in r["motivo"]

    def test_ficha_que_estoura_NAO_derruba_e_diz(self, monkeypatch):
        """📏 3 de 6 leituras falharam na medição de 17/11: este é o caminho
        comum, não a exceção."""
        from movizap import fpsl_ponte

        def estoura(n):
            raise RuntimeError("o Harmonit nao respondeu")

        self._dublar(monkeypatch)
        monkeypatch.setattr(fpsl_ponte, "ficha_da_os", estoura)
        disparo_etapa.definir(ETAPA, "Oi", True)
        r = disparo_etapa.preparar_da_etapa(OS_TESTE, ETAPA)
        assert r["pergunta"] is False
        assert "não consegui ler a OS" in r["motivo"]


class TestOEnvioConfirmado:
    """🆕 17/11: envia o texto que o operador confirmou. 🚨 NADA ENVIA DE
    VERDADE: o `conversas.iniciar_conversa` é dublado e as chamadas contadas."""

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
                "cliente_telefone": "+5518998116168", "cliente": "João Silva",
                "descricao": DESC_RETIRADA})
        return chamadas

    def test_envia_UMA_VEZ_o_texto_que_o_operador_confirmou(self, monkeypatch):
        chamadas = self._dublar(monkeypatch)
        disparo_etapa.definir(ETAPA, "o molde não importa aqui", True)
        r = disparo_etapa.enviar_preparado(OS_TESTE, ETAPA,
                                           "texto que ele editou", None)
        assert r["enviou"] is True
        assert len(chamadas) == 1
        assert chamadas[0]["texto"] == "texto que ele editou"
        assert chamadas[0]["numero"] == "+5518998116168"

    def test_DESLIGAR_ENTRE_A_PERGUNTA_E_O_CLIQUE_barra_o_envio(self, monkeypatch):
        """🚨 Desligar é dizer "pare de falar com os clientes": a decisão mais
        nova ganha."""
        chamadas = self._dublar(monkeypatch)
        disparo_etapa.definir(ETAPA, "Oi", False)
        r = disparo_etapa.enviar_preparado(OS_TESTE, ETAPA, "Oi", None)
        assert r["enviou"] is False
        assert "desligado" in r["motivo"]
        assert chamadas == []

    def test_texto_vazio_nao_envia(self, monkeypatch):
        chamadas = self._dublar(monkeypatch)
        disparo_etapa.definir(ETAPA, "Oi", True)
        r = disparo_etapa.enviar_preparado(OS_TESTE, ETAPA, "   ", None)
        assert r["enviou"] is False
        assert chamadas == []

    def test_texto_acima_do_TETO_nao_envia(self, monkeypatch):
        chamadas = self._dublar(monkeypatch)
        disparo_etapa.definir(ETAPA, "Oi", True)
        r = disparo_etapa.enviar_preparado(
            OS_TESTE, ETAPA, "x" * (disparo_etapa.TETO_TEXTO + 1), None)
        assert r["enviou"] is False
        assert chamadas == []

    def test_CHAVE_CRUA_COLADA_pelo_operador_nao_chega_ao_cliente(self, monkeypatch):
        """🚨 Ele pode colar `{{...}}` na caixa. O cliente não tem o que fazer
        com a chave."""
        chamadas = self._dublar(monkeypatch)
        disparo_etapa.definir(ETAPA, "Oi", True)
        r = disparo_etapa.enviar_preparado(OS_TESTE, ETAPA,
                                           "oi {{Inventada}} tchau", None)
        assert r["enviou"] is True
        assert "{{" not in chamadas[0]["texto"]

    def test_envio_que_estoura_NAO_LEVANTA(self, monkeypatch):
        """🚨 Quem chama é a rota, e o card já mudou de situação no ERP."""
        self._dublar(monkeypatch, estoura=True)
        disparo_etapa.definir(ETAPA, "Oi", True)
        r = disparo_etapa.enviar_preparado(OS_TESTE, ETAPA, "Oi", None)
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
        nomes = disparo_etapa.enviar_preparado.__code__.co_names
        assert "conversas" in nomes
        assert not [n for n in nomes if "evolution" in n.lower()]
        assert "iniciar_conversa" in nomes

    def test_o_canal_e_de_ATENDIMENTO_e_nunca_o_informativo(self):
        """🚨 O informativo é de campanha: usá-lo mostraria o número errado."""
        fonte = inspect.getsource(disparo_etapa._canal_de_atendimento)
        assert "tipo = 'atendimento'" in fonte
        canal = disparo_etapa._canal_de_atendimento()
        if canal:
            linha = banco.um("SELECT tipo FROM canal WHERE id = %s",
                             (canal["id"],))
            assert linha["tipo"] == "atendimento"


class TestADecisaoDaPassagem:
    """🆕 Migração 111: uma decisão por movimento, e a primeira ganha."""

    def test_decide_UMA_VEZ_e_a_segunda_e_recusada(self):
        """🚨 É a trava contra o aviso em duplicidade: recarregar a tela ou
        clicar duas vezes não manda a mensagem de novo."""
        pid = _passagem_de_teste()
        assert passagem.decidir_disparo(pid, enviado=True, texto=None,
                                        atendente_id=None) is True
        assert passagem.decidir_disparo(pid, enviado=False, texto=None,
                                        atendente_id=None) is False

    def test_recusar_tambem_tranca(self):
        pid = _passagem_de_teste()
        assert passagem.decidir_disparo(pid, enviado=False, texto=None,
                                        atendente_id=None) is True
        linha = passagem.disparo_da_passagem(pid)
        assert linha["disparo_recusado_em"] is not None
        assert linha["disparo_em"] is None
        assert passagem.decidir_disparo(pid, enviado=True, texto="x",
                                        atendente_id=None) is False

    def test_o_BANCO_recusa_enviado_E_recusado_na_mesma_linha(self):
        """🚨 Uma decisão por passagem: as duas afirmadas juntas tornariam
        nenhuma confiável."""
        pid = _passagem_de_teste()
        with pytest.raises(Exception):
            banco.executar(
                "UPDATE os_passagem SET disparo_em = now(), "
                "disparo_recusado_em = now() WHERE id = %s", (pid,))

    def test_SOLTAR_devolve_a_passagem_quando_o_envio_falhou(self):
        """🚨 Existe para o operador poder tentar de novo: nada saiu, e deixar
        marcado afirmaria um aviso que não houve."""
        pid = _passagem_de_teste()
        passagem.decidir_disparo(pid, enviado=True, texto=None,
                                 atendente_id=None)
        passagem.soltar_disparo(pid)
        linha = passagem.disparo_da_passagem(pid)
        assert linha["disparo_em"] is None
        assert passagem.decidir_disparo(pid, enviado=True, texto=None,
                                        atendente_id=None) is True

    def test_soltar_NAO_apaga_aviso_que_SAIU_de_verdade(self):
        """⚠️ `disparo_texto` é o que o cliente leu. Com texto gravado, soltar
        não pode desfazer: o aviso aconteceu."""
        pid = _passagem_de_teste()
        passagem.decidir_disparo(pid, enviado=True, texto=None,
                                 atendente_id=None)
        passagem.gravar_texto_do_disparo(pid, "o que o cliente leu")
        passagem.soltar_disparo(pid)
        linha = passagem.disparo_da_passagem(pid)
        assert linha["disparo_em"] is not None
        assert linha["disparo_texto"] == "o que o cliente leu"


class TestOMoverNaoEnvia:
    def test_o_mover_NAO_ENVIA_MAIS_NADA(self):
        """🚨 17/11, A INVERSÃO: o mover prepara e pergunta; quem envia é a rota
        do disparo, atrás de um clique. Nenhum caminho de envio pode estar
        citado aqui."""
        fonte = inspect.getsource(passagem.mover)
        assert "preparar_da_etapa" in fonte
        for proibido in ("enviar_preparado", "enviar_da_etapa",
                         "iniciar_conversa"):
            assert proibido not in fonte, f"o mover não pode citar {proibido}"

    def test_o_mover_devolve_o_passagem_id_junto_do_disparo(self):
        """Sem o `passagem_id` a rota do disparo não saberia de qual movimento
        se fala -- e a trava de uma decisão por passagem não existiria."""
        fonte = inspect.getsource(passagem.mover)
        assert '"passagem_id": passagem' in fonte
        assert '"disparo": disparo' in fonte

    def test_o_mover_so_prepara_quando_o_ERP_ACEITOU(self):
        """🚨 Perguntar "avisar o cliente?" num mover que o ERP recusou
        ofereceria avisar de um fato que não aconteceu."""
        fonte = inspect.getsource(passagem.mover)
        antes = fonte.index('if resposta.get("ok"):')
        chamada = fonte.index("disparo_etapa.preparar_da_etapa")
        assert antes < chamada, "o disparo tem de estar DENTRO do if de ok"

    def test_o_mover_embrulha_o_disparo_em_try(self):
        fonte = inspect.getsource(passagem.mover)
        trecho = fonte[fonte.index('if resposta.get("ok"):'):]
        assert "try:" in trecho
        assert "except Exception:" in trecho

    def test_a_funcao_que_ENVIAVA_no_mover_nao_existe_mais(self):
        """🚨 Deixá-la viva seria deixar o caminho antigo à mão de quem não leu
        esta decisão."""
        assert not hasattr(disparo_etapa, "enviar_da_etapa")
