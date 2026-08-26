"""O motor da IA — o passo 8.

🚨 NENHUM TESTE DAQUI FALA COM O MODELO. O provedor é trocado por um duplo que
devolve o que o teste mandar. Quem exercita contra o modelo de verdade é
`scripts/exercitar_ia.py`, que é outro assunto e custa dinheiro.

🚨 O QUE MAIS IMPORTA AQUI NÃO É RESPONDER: É NÃO RESPONDER. Três travas
(canal, tipo de contato, `ia_atendeu_ate`), o silêncio quando um humano
assume, e o nunca-em-grupo. Uma IA que responde a mais é pior que uma IA
desligada -- ela fala com cliente real no lugar errado.

🚨 Escreve em `conversa`, `mensagem` e `relacao_automacao`, tabelas de
PRODUÇÃO. Telefone de DDD inexistente; o estado anterior volta no fim.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, "/home/claude/movizap_painel")
pytest.importorskip("psycopg")

from movizap import automacao, banco, conversas, evolution, ia  # noqa: E402
from movizap import prompt as prompt_ia                         # noqa: E402
from movizap.llm import Params, gateway as gw                   # noqa: E402

ENV = Path("/home/claude/movizap_painel/.env")
pytestmark = pytest.mark.skipif(
    not ENV.exists() or "MOVIZAP_DB_SENHA" not in ENV.read_text(encoding="utf-8"),
    reason="banco nao configurado no .env")

PREFIXO = "+559995556%"
NUMERO = "+5599955560001"


def limpar():
    banco.executar(
        """DELETE FROM mensagem WHERE conversa_id IN
           (SELECT id FROM conversa WHERE telefone_e164 LIKE %s)""", (PREFIXO,))
    banco.executar(
        """DELETE FROM transferencia WHERE conversa_id IN
           (SELECT id FROM conversa WHERE telefone_e164 LIKE %s)""", (PREFIXO,))
    banco.executar("DELETE FROM conversa WHERE telefone_e164 LIKE %s", (PREFIXO,))


@pytest.fixture(scope="module", autouse=True)
def pool():
    banco.abrir()
    # ⚠️ `ia_ligada_em` VAI JUNTO. A primeira versão restaurava só `ia_ligada`
    # e deixava a hora gravada num canal desligado -- rastro de teste em tabela
    # de produção. Inofensivo (ligar reescreve a hora), mas mentira: a coluna
    # existe para responder "desde quando a IA responde os clientes?".
    antes_canal = banco.varios("SELECT id, ia_ligada, ia_ligada_em FROM canal")
    antes_relacao = banco.varios("SELECT relacao, ia_ligada FROM relacao_automacao")
    limpar()

    # 🚨 SEM VERSÃO DE PROMPT PUBLICADA, O MOTOR SE RECUSA A RESPONDER -- e
    # está certo: prompt é o que ela lê. Isto NÃO é conveniência de teste, é a
    # cena real. Quando não há nenhuma, o teste publica uma sua e a remove no
    # fim; quando já há, usa a do painel e não toca em nada.
    ativa_antes = prompt_ia.ativa()
    minha = None
    if not ativa_antes:
        minha = prompt_ia.criar(prompt_ia.SUGESTAO_INICIAL, None, True)

    yield
    limpar()
    if minha:
        banco.executar(
            "UPDATE conversa SET prompt_versao_id = NULL WHERE prompt_versao_id = %s",
            (minha["id"],))
        banco.executar("DELETE FROM prompt_versao WHERE id = %s", (minha["id"],))
    for c in antes_canal:
        banco.executar(
            "UPDATE canal SET ia_ligada = %s, ia_ligada_em = %s WHERE id = %s",
            (c["ia_ligada"], c["ia_ligada_em"], c["id"]))
    for r in antes_relacao:
        banco.executar("UPDATE relacao_automacao SET ia_ligada = %s WHERE relacao = %s",
                       (r["ia_ligada"], r["relacao"]))
    banco.fechar()


@pytest.fixture(autouse=True)
def sem_enviar(monkeypatch):
    """🚨 Nenhum teste manda mensagem de verdade."""
    enviadas = []

    def falso(instancia, numero, texto, citando=None):
        enviadas.append({"numero": numero, "texto": texto})
        return {"id_externo": f"zz-ia-{len(enviadas)}", "status": "PENDING",
                "bruto": {}}

    monkeypatch.setattr(evolution, "enviar_texto", falso)
    yield enviadas


class ProvedorFalso:
    """Devolve as respostas que o teste enfileirar. Nunca sai da máquina."""

    nome = "falso"
    modelo = "falso-1"

    def __init__(self, respostas):
        self.respostas = list(respostas)
        self.chamadas = []

    @property
    def configurado(self):
        return True

    def completar(self, mensagens, params, ferramentas=None, escolha=None):
        self.chamadas.append({"mensagens": list(mensagens),
                              "tinha_ferramentas": bool(ferramentas)})
        if not self.respostas:
            return {"mensagem": {"content": "acabou"}, "tokens": 1,
                    "cache_hit": None, "provedor": self.nome}
        return self.respostas.pop(0)


def texto(conteudo, tokens=10):
    return {"mensagem": {"content": conteudo}, "tokens": tokens,
            "cache_hit": None, "provedor": "falso"}


def chamada(nome, argumentos="{}", tokens=10):
    return {"mensagem": {"content": None, "tool_calls": [
                {"id": "c1", "type": "function",
                 "function": {"name": nome, "arguments": argumentos}}]},
            "tokens": tokens, "cache_hit": None, "provedor": "falso"}


def com_motor(monkeypatch, respostas):
    """Troca o provedor do gateway pelo duplo, e devolve o duplo."""
    falso = ProvedorFalso(respostas)
    g = gw.Gateway()
    g.principal = falso
    g.reserva = falso
    g.estrategia = "single"
    monkeypatch.setattr(gw, "_gateway", g)
    monkeypatch.setattr(ia, "obter", lambda: g)
    return falso


@pytest.fixture()
def conversa():
    limpar()
    canal = banco.um(
        "SELECT id FROM canal WHERE tipo = 'atendimento' AND ativo LIMIT 1")
    if not canal:
        pytest.skip("nenhum canal de atendimento ativo")
    cid = banco.um(
        """INSERT INTO conversa (canal_id, telefone_e164, estado)
           VALUES (%s, %s, 'nova') RETURNING id""",
        (canal["id"], NUMERO))["id"]
    # A pergunta nasce VELHA de propósito: `SILENCIO_S` recusa mensagem
    # recém-chegada, e uma fixture com `now()` testaria só a espera.
    banco.executar(
        """INSERT INTO mensagem (conversa_id, id_externo, direcao, autor, tipo,
                                 conteudo, criada_em)
           VALUES (%s, 'zz-ia-entrada-1', 'entrada', 'cliente', 'texto',
                   'oi, preciso de ajuda', now() - interval '1 minute')""",
        (cid,))
    # ⚠️ LIGADA NO PASSADO. A IA só atende o que chegou DEPOIS de ela ser
    # ligada; com `ia_ligada_em = now()` a fixture montaria uma cena que a
    # regra recusa, e o teste mediria a recusa em vez do comportamento.
    banco.executar(
        "UPDATE canal SET ia_ligada = true, ia_ligada_em = now() - interval '1 hour' "
        " WHERE id = %s", (canal["id"],))
    banco.executar(
        "UPDATE relacao_automacao SET ia_ligada = true WHERE relacao = 'sem_cadastro'")
    yield cid
    limpar()


# ── O laço de ferramentas, sem banco e sem rede ──────────────────────────────

class TestLacoDeFerramentas:
    def test_resposta_direta_nao_chama_ferramenta(self, monkeypatch):
        com_motor(monkeypatch, [texto("olá!")])
        r = gw._gateway.conversar([{"role": "user", "content": "oi"}],
                                  ia.FERRAMENTAS, lambda n, a: {}, Params())
        assert r["texto"] == "olá!"
        assert r["ferramentas_usadas"] == []

    def test_a_ultima_rodada_vai_sem_ferramentas(self, monkeypatch):
        """🚨 Com o catálogo ainda oferecido no fim, o modelo tenta emitir
        sintaxe de chamada e os tokens especiais vazam como TEXTO PURO na
        resposta que o cliente lê. Defeito real, medido no MoviChat em 15/07."""
        falso = com_motor(monkeypatch, [chamada("identificar_contato"),
                                        chamada("identificar_contato"),
                                        texto("pronto")])
        gw._gateway.conversar([{"role": "user", "content": "oi"}], ia.FERRAMENTAS,
                              lambda n, a: {"ok": True}, Params())
        assert len(falso.chamadas) == gw.MAX_RODADAS
        assert falso.chamadas[-1]["tinha_ferramentas"] is False
        assert falso.chamadas[0]["tinha_ferramentas"] is True

    def test_falha_de_ferramenta_vira_instrucao_de_conduta(self, monkeypatch):
        """🚨 Sem a instrução junto, o modelo improvisa e conta ao cliente que
        houve erro no sistema -- expor o mecanismo é o item 5 do contrato."""
        falso = com_motor(monkeypatch, [chamada("qualquer"), texto("ok")])

        def estoura(nome, args):
            raise RuntimeError("caiu")

        gw._gateway.conversar([{"role": "user", "content": "oi"}], ia.FERRAMENTAS,
                              estoura, Params())
        devolvido = falso.chamadas[-1]["mensagens"][-1]["content"]
        assert "como_responder" in devolvido
        assert "NÃO mencione erro" in devolvido

    def test_ferramenta_final_encerra_o_laco(self, monkeypatch):
        """`transferir` JÁ É a resposta. Deixar o modelo escrever por cima
        produziria o "vou transferir você" que o handoff proíbe."""
        falso = com_motor(monkeypatch, [chamada("transferir"), texto("nunca chega")])
        r = gw._gateway.conversar([{"role": "user", "content": "oi"}], ia.FERRAMENTAS,
                                  lambda n, a: {"__final__": "já já te respondem",
                                                "encerrou": True}, Params())
        assert r["texto"] == "já já te respondem"
        assert r["encerrou"] is True
        assert len(falso.chamadas) == 1


# ── O que sai para o cliente ────────────────────────────────────────────────

class TestFormatoDaResposta:
    def test_markdown_vira_formato_do_whatsapp(self):
        """🚨 ACHADO NO PRIMEIRO EXERCÍCIO CONTRA O MODELO REAL (26/08): ele
        devolveu `**Fulano**`, e no WhatsApp os asteriscos aparecem."""
        assert ia.para_whatsapp("olá **Fulano**") == "olá *Fulano*"
        assert ia.para_whatsapp("## Título\ntexto") == "Título\ntexto"

    def test_nao_apaga_negrito_ja_correto(self):
        assert ia.para_whatsapp("olá *Fulano*") == "olá *Fulano*"


# ── As travas ────────────────────────────────────────────────────────────────

class TestNaoResponde:
    def test_canal_desligado_nao_responde(self, conversa, monkeypatch):
        com_motor(monkeypatch, [texto("não deveria sair")])
        banco.executar("UPDATE canal SET ia_ligada = false")
        r = ia.responder(conversa)
        assert r["respondeu"] is False
        assert r["motivo"] == "IA desligada no canal"

    def test_tipo_desligado_nao_responde(self, conversa, monkeypatch):
        com_motor(monkeypatch, [texto("não deveria sair")])
        banco.executar("UPDATE relacao_automacao SET ia_ligada = false")
        r = ia.responder(conversa)
        assert r["respondeu"] is False
        assert r["motivo"] == "IA desligada para este tipo"

    def test_humano_assumiu_cala(self, conversa, monkeypatch):
        """🚨 `docs/04`: quando um humano assume, a IA cala imediatamente e
        não volta sozinha."""
        com_motor(monkeypatch, [texto("não deveria sair")])
        atendente = banco.um("SELECT id FROM atendente LIMIT 1")
        if not atendente:
            pytest.skip("nenhum atendente cadastrado")
        banco.executar("UPDATE conversa SET atendente_id = %s WHERE id = %s",
                       (atendente["id"], conversa))
        assert ia.responder(conversa)["motivo"] == "humano assumiu"

    def test_conversa_em_fila_cala(self, conversa, monkeypatch):
        com_motor(monkeypatch, [texto("não deveria sair")])
        banco.executar("UPDATE conversa SET estado = 'fila' WHERE id = %s", (conversa,))
        assert ia.responder(conversa)["motivo"] == "conversa fila"

    def test_mensagem_recem_chegada_espera_o_silencio(self, conversa, monkeypatch):
        """O cliente manda três seguidas; responder a primeira é o que mais
        denuncia um robô."""
        com_motor(monkeypatch, [texto("não deveria sair")])
        banco.executar(
            "UPDATE mensagem SET criada_em = now() WHERE conversa_id = %s", (conversa,))
        assert ia.responder(conversa)["motivo"] == "aguardando silencio"


class TestNaoRespondeDuasVezes:
    def test_a_trava_e_do_banco(self, conversa, monkeypatch, sem_enviar):
        """🚨 `processar_pendentes` roda no laço E na rota: são duas threads.
        Um `if` no Python perde a corrida e o cliente recebe duas respostas."""
        com_motor(monkeypatch, [texto("primeira"), texto("segunda")])
        primeira = ia.responder(conversa)
        segunda = ia.responder(conversa)
        assert primeira["respondeu"] is True
        assert segunda["respondeu"] is False
        assert segunda["motivo"] == "ja atendida"
        assert len(sem_enviar) == 1

    def test_mensagem_nova_destrava(self, conversa, monkeypatch, sem_enviar):
        com_motor(monkeypatch, [texto("primeira"), texto("segunda")])
        ia.responder(conversa)
        banco.executar(
            """INSERT INTO mensagem (conversa_id, id_externo, direcao, autor,
                                     tipo, conteudo, criada_em)
               VALUES (%s, 'zz-ia-entrada-2', 'entrada', 'cliente', 'texto',
                       'e aí?', now() - interval '1 minute')""", (conversa,))
        assert ia.responder(conversa)["respondeu"] is True
        assert len(sem_enviar) == 2


class TestGravaOQueDeve:
    def test_a_saida_e_da_ia_e_nao_de_uma_pessoa(self, conversa, monkeypatch):
        """`autor='ia'`, `atendente_id` nulo: o histórico não pode dizer que
        alguém escreveu o que a máquina escreveu."""
        com_motor(monkeypatch, [texto("posso ajudar")])
        ia.responder(conversa)
        m = banco.um(
            """SELECT autor, direcao, atendente_id FROM mensagem
                WHERE conversa_id = %s AND direcao = 'saida'
                ORDER BY id DESC LIMIT 1""", (conversa,))
        assert m["autor"] == "ia"
        assert m["atendente_id"] is None

    def test_nao_mexe_em_primeira_resposta(self, conversa, monkeypatch):
        """Se contasse, o tempo de primeira resposta humana viraria zero no dia
        em que a IA fosse ligada, e a métrica pareceria excelente."""
        com_motor(monkeypatch, [texto("posso ajudar")])
        ia.responder(conversa)
        c = banco.um("SELECT primeira_resposta_em, estado FROM conversa WHERE id = %s",
                     (conversa,))
        assert c["primeira_resposta_em"] is None
        assert c["estado"] == "bot"

    def test_transferir_deixa_nota_interna_e_rastro(self, conversa, monkeypatch):
        com_motor(monkeypatch, [
            chamada("transferir",
                    '{"time": "Suporte", "resumo": "quer saber da placa",'
                    ' "despedida": "ja ja te respondem"}')])
        r = ia.responder(conversa)
        assert r["respondeu"] is True
        nota = banco.um(
            """SELECT autor, direcao, tipo, conteudo FROM mensagem
                WHERE conversa_id = %s AND direcao = 'interna'""", (conversa,))
        assert nota["autor"] == "ia"
        assert nota["tipo"] == "nota"
        assert "placa" in nota["conteudo"]
        t = banco.um("SELECT motivo, para_time_id FROM transferencia "
                     " WHERE conversa_id = %s", (conversa,))
        assert t["motivo"] == "ia_triagem"
        assert t["para_time_id"] is not None
        assert banco.um("SELECT estado FROM conversa WHERE id = %s",
                        (conversa,))["estado"] == "fila"

    def test_time_inventado_cai_no_transbordo_em_vez_de_perder_a_transferencia(
            self, conversa, monkeypatch):
        """⚠️ Devolver "time inexistente" faria o modelo gastar rodada, tentar
        outro nome e às vezes desistir -- deixando o cliente com a IA. Perder a
        precisão do time é muito menos grave que perder a transferência."""
        com_motor(monkeypatch, [
            chamada("transferir",
                    '{"time": "Departamento de Marte", "resumo": "x",'
                    ' "despedida": "ja ja"}')])
        assert ia.responder(conversa)["respondeu"] is True
        assert banco.um("SELECT para_time_id FROM transferencia WHERE conversa_id = %s",
                        (conversa,))["para_time_id"] is not None

    def test_encerrar_marca_resolvida_pela_ia(self, conversa, monkeypatch):
        com_motor(monkeypatch, [
            chamada("encerrar", '{"motivo": "resolvido", "despedida": "de nada!"}')])
        ia.responder(conversa)
        c = banco.um("SELECT estado, resolvida_pela_ia, resolvida_por "
                     "  FROM conversa WHERE id = %s", (conversa,))
        assert c["estado"] == "resolvida"
        assert c["resolvida_pela_ia"] is True
        assert c["resolvida_por"] is None

    def test_resposta_vazia_transfere_em_vez_de_calar(self, conversa, monkeypatch):
        """🚨 SILÊNCIO NÃO É RESPOSTA. Sem isto a conversa ficaria marcada como
        atendida e ninguém apareceria."""
        com_motor(monkeypatch, [texto("")])
        r = ia.responder(conversa)
        assert r["respondeu"] is False
        assert banco.um("SELECT estado FROM conversa WHERE id = %s",
                        (conversa,))["estado"] == "fila"


# ── A varredura ──────────────────────────────────────────────────────────────

class TestNaoRespondeOPassado:
    """🚨 ACHADO AO ESCREVER O TESTE DA VARREDURA, EM 26/08. A base tem 357
    conversas abertas. Sem a guarda de `ia_ligada_em`, ligar o interruptor
    faria a IA responder a TODAS de uma vez, a mensagens de dias atrás, no
    meio de conversas que já seguiram sem ela. É a mesma lição que a saudação
    automática deu em 25/08 -- e é a que o placar verde não conta."""

    def test_mensagem_anterior_a_ligar_nao_e_respondida(self, conversa, monkeypatch,
                                                        sem_enviar):
        com_motor(monkeypatch, [texto("não deveria sair")])
        banco.executar("UPDATE canal SET ia_ligada_em = now()")
        r = ia.responder(conversa)
        assert r["respondeu"] is False
        assert r["motivo"] == "anterior a IA ser ligada"
        assert sem_enviar == []

    def test_varredura_ignora_o_passado(self, conversa):
        banco.executar("UPDATE canal SET ia_ligada_em = now()")
        assert conversa not in ia.pendentes(limite=500)

    def test_canal_sem_hora_de_ligar_nao_atende(self, conversa):
        """Ligado sem hora é estado impossível pelo caminho oficial -- mas se
        alguém ligar a coluna na mão, a IA não pode sair respondendo o passado
        inteiro por causa disso."""
        banco.executar("UPDATE canal SET ia_ligada_em = NULL")
        assert ia.responder(conversa)["motivo"] == "anterior a IA ser ligada"
        assert conversa not in ia.pendentes(limite=500)


class TestVarredura:
    def test_pega_conversa_com_pergunta_esperando(self, conversa):
        # ⚠️ `limite=500`: a varredura ordena pela mais ANTIGA e a conversa do
        # teste é a mais nova da base. Com o teto padrão de 20 ela ficaria de
        # fora e o teste reprovaria código correto.
        assert conversa in ia.pendentes(limite=500)

    def test_nao_pega_o_que_ja_foi_atendido(self, conversa, monkeypatch):
        com_motor(monkeypatch, [texto("respondi")])
        ia.responder(conversa)
        assert conversa not in ia.pendentes(limite=500)

    def test_nao_pega_conversa_com_dono(self, conversa):
        atendente = banco.um("SELECT id FROM atendente LIMIT 1")
        if not atendente:
            pytest.skip("nenhum atendente cadastrado")
        banco.executar("UPDATE conversa SET atendente_id = %s WHERE id = %s",
                       (atendente["id"], conversa))
        assert conversa not in ia.pendentes(limite=500)

    def test_falha_da_ia_nao_derruba_a_fila_de_eventos(self, conversa, monkeypatch):
        """⚠️ A mensagem do cliente chegou, e é isso que importa guardar."""
        def estoura(limite=20):
            raise RuntimeError("motor caiu")

        monkeypatch.setattr(ia, "atender_pendentes", estoura)
        contas = conversas.processar_pendentes(limite=1)
        assert contas["ia"]["falhas"] == 1


# ── O prompt de sistema ──────────────────────────────────────────────────────

class TestPromptDeSistema:
    def test_diz_em_voz_alta_o_que_ela_nao_consegue_consultar(self):
        """🚨 A classe de erro que reincidiu três vezes no MoviChat: a IA não
        distingue "não achei" de "não consigo ler", e reporta ausência como
        fato. O remédio é ela SABER que não consegue."""
        ctx = {"id": 0, "contato_id": None, "cliente_id": None,
               "contato_nome": None, "relacao": None, "cliente_nome": None,
               "nome_fantasia": None, "cliente_ativo": None,
               "nome_whatsapp": None}
        sistema, _ = ia.montar_sistema(ctx)
        for item in ia.SEM_ACESSO:
            assert item in sistema

    def test_a_conduta_nao_depende_do_texto_versionado(self):
        """As regras que ela NUNCA pode quebrar ficam em código: o prompt é
        editável na tela, e ninguém pode ser obrigado a lembrar de reescrever
        "não prometa prazo" em toda versão nova."""
        for frase in ("Nunca prometa prazo", "Nunca invente",
                      "Nunca fale de sistema"):
            assert frase in ia.CONDUTA


# ── O interruptor ────────────────────────────────────────────────────────────

class TestInterruptor:
    def test_nao_liga_ia_no_canal_informativo(self):
        """🚨 O informativo é disparo, não conversa. A recusa é a coluna, não a
        disciplina de lembrar de desligar antes de cada disparo."""
        from movizap import canais
        c = banco.um("SELECT id FROM canal WHERE tipo = 'informativo' LIMIT 1")
        if not c:
            pytest.skip("nenhum canal informativo")
        r = canais.ligar_ia(c["id"], True, "teste")
        assert r["ok"] is False
        assert "atendimento" in r["motivo"]

    def test_desligar_funciona_mesmo_sem_motor(self, monkeypatch):
        """⚠️ Desligar tem de funcionar com o motor fora do ar -- é exatamente
        quando alguém quer desligar."""
        from movizap import canais
        monkeypatch.setattr(ia, "estado",
                            lambda: {"disponivel": False, "motivo": "sem chave"})
        c = banco.um("SELECT id FROM canal WHERE tipo = 'atendimento' LIMIT 1")
        assert canais.ligar_ia(c["id"], False, "teste")["ok"] is True

    def test_ligar_ia_por_tipo_exige_motor(self, monkeypatch):
        monkeypatch.setattr(ia, "estado",
                            lambda: {"disponivel": False, "motivo": "sem chave"})
        banco.executar(
            "UPDATE relacao_automacao SET ia_ligada = false WHERE relacao = 'teste'")
        r = automacao.definir("teste", ia_ligada=True)
        assert r["ok"] is False
        assert r["motivo"] == "sem chave"


# ── O ensaio ─────────────────────────────────────────────────────────────────

class TestEnsaio:
    def test_ensaio_nao_envia_nem_grava(self, conversa, monkeypatch, sem_enviar):
        """🚨 Se ensaiar operasse, não seria ensaio."""
        com_motor(monkeypatch, [texto("resposta de ensaio")])
        antes = banco.um("SELECT ia_atendeu_ate FROM conversa WHERE id = %s",
                         (conversa,))["ia_atendeu_ate"]
        r = ia.responder(conversa, ensaio=True)
        assert r["texto"] == "resposta de ensaio"
        assert r["respondeu"] is False
        assert sem_enviar == []
        assert banco.um("SELECT ia_atendeu_ate FROM conversa WHERE id = %s",
                        (conversa,))["ia_atendeu_ate"] == antes

    def test_ensaio_nao_transfere_de_verdade(self, conversa, monkeypatch):
        com_motor(monkeypatch, [
            chamada("transferir",
                    '{"time": "Suporte", "resumo": "x", "despedida": "ja ja"}')])
        r = ia.responder(conversa, ensaio=True)
        assert r["acoes"][0]["acao"] == "transferir"
        assert banco.um("SELECT count(*) AS n FROM transferencia "
                        " WHERE conversa_id = %s", (conversa,))["n"] == 0

    def test_ensaio_ignora_os_interruptores(self, conversa, monkeypatch):
        """O ensaio existe justamente para rodar ANTES de ligar."""
        com_motor(monkeypatch, [texto("oi")])
        banco.executar("UPDATE canal SET ia_ligada = false")
        assert ia.responder(conversa, ensaio=True)["texto"] == "oi"

    def test_ensaio_respeita_o_nunca_em_grupo(self, monkeypatch):
        """`docs/04`: nunca responde em grupo. Nem em ensaio."""
        com_motor(monkeypatch, [texto("oi")])
        canal = banco.um(
            "SELECT id FROM canal WHERE tipo = 'atendimento' AND ativo LIMIT 1")
        cid = banco.um(
            """INSERT INTO conversa (canal_id, tipo, grupo_jid, estado)
               VALUES (%s, 'grupo', %s, 'nova') RETURNING id""",
            (canal["id"], "zz-ia-grupo@g.us"))["id"]
        try:
            assert ia.responder(cid, ensaio=True)["motivo"] == "grupo"
        finally:
            banco.executar("DELETE FROM conversa WHERE id = %s", (cid,))


# ── O que a tela lê ──────────────────────────────────────────────────────────

class TestEstadoDoMotor:
    def test_a_chave_sai_mascarada(self):
        """🚨 Em tela mostra-se `sk-...a3f9`. Nunca o valor."""
        e = ia.estado()
        assert "..." in e["chave"] or e["chave"] == ""
        assert len(e["chave"]) < 20

    def test_motor_existe_e_medido_e_nao_escrito(self):
        """Era literal `False` e teria continuado `False` depois de o motor
        entrar -- contador em prosa nasce errado e ninguém percebe."""
        assert prompt_ia.estado()["motor_existe"] == ia.estado()["disponivel"]


def test_o_pacote_llm_e_o_unico_que_le_a_chave():
    """🚨 `docs/04`: *"chave lida do .env por um único gateway; nenhum outro
    módulo sabe que ela existe"*. Esta trava mede a LIGAÇÃO (o atributo sendo
    lido), não a palavra -- comentário citando o nome não a faz reprovar."""
    import re
    raiz = Path("/home/claude/movizap_painel/movizap")
    padrao = re.compile(r"settings\.(deepseek_api_key|groq_api_key)")
    fora = []
    for arquivo in raiz.rglob("*.py"):
        if arquivo.parent.name == "llm":
            continue
        fonte = arquivo.read_text(encoding="utf-8")
        # Tira comentário e docstring antes de varrer: trava que mede palavra
        # já reprovou código correto oito vezes neste projeto.
        sem_comentario = re.sub(r"#.*", "", fonte)
        sem_comentario = re.sub(r'"""[\s\S]*?"""', "", sem_comentario)
        if padrao.search(sem_comentario):
            fora.append(arquivo.name)
    assert fora == [], f"a chave é lida fora do pacote llm: {fora}"
