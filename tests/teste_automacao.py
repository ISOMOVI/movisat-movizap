"""Automação por tipo de contato — o filtro de uso pedido em 25/08.

🚨 O QUE MAIS IMPORTA AQUI NÃO É ENVIAR: É NÃO ENVIAR DUAS VEZES. O Evolution
reentrega webhook por desenho, e "seja bem-vindo" repetido é pior do que
ausente. A trava é o `UPDATE ... WHERE boas_vindas_em IS NULL`, e é ela que
estes testes atacam.

🚨 Escreve em `conversa`, `contato`, `relacao_automacao` e `mensagem`, tabelas
de PRODUÇÃO. Telefone de DDD inexistente; a automação é devolvida ao estado
anterior no fim.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, "/home/claude/movizap_painel")
pytest.importorskip("psycopg")

from movizap import automacao, banco, conversas, evolution  # noqa: E402

ENV = Path("/home/claude/movizap_painel/.env")
pytestmark = pytest.mark.skipif(
    not ENV.exists() or "MOVIZAP_DB_SENHA" not in ENV.read_text(encoding="utf-8"),
    reason="banco nao configurado no .env")

PREFIXO = "+559995555%"
NUMERO = "+5599955550001"
MARCA = "zz teste automacao"


def limpar():
    banco.executar(
        """DELETE FROM mensagem WHERE conversa_id IN
           (SELECT id FROM conversa WHERE telefone_e164 LIKE %s)""", (PREFIXO,))
    banco.executar("DELETE FROM conversa WHERE telefone_e164 LIKE %s", (PREFIXO,))
    banco.executar(
        """DELETE FROM contato_telefone WHERE contato_id IN
           (SELECT id FROM contato WHERE nome LIKE %s)""", (MARCA + "%",))
    banco.executar("DELETE FROM contato WHERE nome LIKE %s", (MARCA + "%",))


@pytest.fixture(scope="module", autouse=True)
def pool():
    banco.abrir()
    # ⚠️ Guarda o estado real da automação e devolve no fim: estes testes
    # ligam interruptores numa tabela de produção.
    antes = banco.varios(
        "SELECT relacao, boas_vindas_ligado, boas_vindas_texto "
        "  FROM relacao_automacao")
    limpar()
    yield
    limpar()
    for linha in antes:
        banco.executar(
            """UPDATE relacao_automacao
                  SET boas_vindas_ligado = %s, boas_vindas_texto = %s
                WHERE relacao = %s""",
            (linha["boas_vindas_ligado"], linha["boas_vindas_texto"],
             linha["relacao"]))
    banco.fechar()


@pytest.fixture(autouse=True)
def sem_enviar(monkeypatch):
    """🚨 Nenhum teste manda mensagem de verdade."""
    enviadas = []

    # ⚠️ A ASSINATURA ACOMPANHA A REAL. `citando` entrou em 25/08, com o
    # responder citando; mock que não aceita o argumento reprova código
    # correto e faz procurar defeito onde não há.
    def falso(instancia, numero, texto, citando=None):
        enviadas.append({"numero": numero, "texto": texto})
        return {"id_externo": f"zz-aut-{len(enviadas)}", "status": "PENDING",
                "bruto": {}}

    monkeypatch.setattr(evolution, "enviar_texto", falso)
    yield enviadas


@pytest.fixture()
def conversa_sem_cadastro():
    limpar()
    canal = banco.um(
        "SELECT id FROM canal WHERE tipo = 'atendimento' AND ativo LIMIT 1")
    if not canal:
        pytest.skip("nenhum canal de atendimento ativo")
    cid = banco.um(
        """INSERT INTO conversa (canal_id, telefone_e164, estado)
           VALUES (%s, %s, 'nova') RETURNING id""",
        (canal["id"], NUMERO))["id"]
    yield cid
    limpar()


def _ligar(relacao, texto="Olá, recebemos sua mensagem."):
    return automacao.definir(relacao, boas_vindas_ligado=True,
                             boas_vindas_texto=texto)


class TestNaoLigaSemTexto:
    def test_ligar_sem_texto_e_recusado(self):
        """🚨 Ligado com texto vazio mandaria mensagem em branco para o
        cliente, e o defeito só apareceria do lado dele."""
        automacao.definir("teste", boas_vindas_ligado=False,
                          boas_vindas_texto="")
        r = automacao.definir("teste", boas_vindas_ligado=True)
        assert r["ok"] is False
        assert "antes de ligar" in r["motivo"]

    def test_tipo_desconhecido_e_recusado(self):
        assert automacao.definir("presidente", boas_vindas_ligado=True)["ok"] is False

    def test_texto_gigante_e_recusado(self):
        r = automacao.definir("teste", boas_vindas_texto="x" * 5000)
        assert r["ok"] is False


class TestDesligadoNaoManda:
    def test_com_tudo_desligado_nao_sai_nada(self, conversa_sem_cadastro,
                                             sem_enviar):
        automacao.definir("sem_cadastro", boas_vindas_ligado=False)
        r = automacao.boas_vindas(conversa_sem_cadastro)
        assert r["enviou"] is False
        assert r["motivo"] == "desligado"
        assert sem_enviar == []


class TestManda:
    def test_liga_e_manda_uma_vez(self, conversa_sem_cadastro, sem_enviar):
        _ligar("sem_cadastro")
        r = automacao.boas_vindas(conversa_sem_cadastro)
        assert r["enviou"] is True
        assert r["tipo"] == "sem_cadastro"
        assert len(sem_enviar) == 1

    def test_a_segunda_chamada_NAO_manda_de_novo(self, conversa_sem_cadastro,
                                                 sem_enviar):
        """🚨 O Evolution reentrega webhook por desenho. Sem a trava, o cliente
        receberia a saudação duas ou três vezes."""
        _ligar("sem_cadastro")
        automacao.boas_vindas(conversa_sem_cadastro)
        segunda = automacao.boas_vindas(conversa_sem_cadastro)
        assert segunda["enviou"] is False
        assert segunda["motivo"] == "ja recebeu"
        assert len(sem_enviar) == 1

    def test_a_marca_fica_gravada_na_conversa(self, conversa_sem_cadastro):
        _ligar("sem_cadastro")
        automacao.boas_vindas(conversa_sem_cadastro)
        assert banco.um("SELECT boas_vindas_em FROM conversa WHERE id = %s",
                        (conversa_sem_cadastro,))["boas_vindas_em"] is not None

    def test_a_mensagem_entra_na_conversa_como_SISTEMA(self,
                                                       conversa_sem_cadastro):
        """⚠️ Autor 'sistema', não um atendente: atribuir a saudação a uma
        pessoa faria o histórico dizer que ela escreveu o que o sistema
        escreveu."""
        _ligar("sem_cadastro", "Bem-vindo à Movisat.")
        automacao.boas_vindas(conversa_sem_cadastro)
        msgs = conversas.mensagens(conversa_sem_cadastro)
        assert msgs[-1]["conteudo"] == "Bem-vindo à Movisat."
        assert msgs[-1]["autor"] == "sistema"
        assert msgs[-1]["direcao"] == "saida"

    def test_NAO_conta_como_primeira_resposta(self, conversa_sem_cadastro):
        """🚨 Se contasse, todo tempo de primeira resposta viraria zero no dia
        em que a saudação fosse ligada -- e a métrica pareceria excelente
        justamente porque ninguém atendeu."""
        _ligar("sem_cadastro")
        automacao.boas_vindas(conversa_sem_cadastro)
        linha = banco.um(
            "SELECT primeira_resposta_em, segundos_ate_resposta "
            "  FROM conversa WHERE id = %s", (conversa_sem_cadastro,))
        assert linha["primeira_resposta_em"] is None
        assert linha["segundos_ate_resposta"] is None


class TestOTipoCerto:
    def test_contato_cadastrado_usa_a_regra_do_TIPO_dele(self,
                                                        conversa_sem_cadastro,
                                                        sem_enviar):
        contato = banco.um(
            """INSERT INTO contato (nome, relacao, origem)
               VALUES (%s, 'fornecedor', 'movizap') RETURNING id""",
            (MARCA + " fornecedor",))["id"]
        banco.executar("UPDATE conversa SET contato_id = %s WHERE id = %s",
                       (contato, conversa_sem_cadastro))

        # A regra de "sem cadastro" está ligada, a de fornecedor não.
        _ligar("sem_cadastro")
        automacao.definir("fornecedor", boas_vindas_ligado=False)

        r = automacao.boas_vindas(conversa_sem_cadastro)
        assert r["enviou"] is False
        assert r["tipo"] == "fornecedor"
        assert sem_enviar == []

    def test_ligando_o_tipo_dele_a_mensagem_sai(self, conversa_sem_cadastro,
                                                sem_enviar):
        contato = banco.um(
            """INSERT INTO contato (nome, relacao, origem)
               VALUES (%s, 'fornecedor', 'movizap') RETURNING id""",
            (MARCA + " fornecedor2",))["id"]
        banco.executar("UPDATE conversa SET contato_id = %s WHERE id = %s",
                       (contato, conversa_sem_cadastro))
        _ligar("fornecedor", "Olá, parceiro.")
        assert automacao.boas_vindas(conversa_sem_cadastro)["enviou"] is True
        assert sem_enviar[0]["texto"] == "Olá, parceiro."


class TestNuncaEmGrupo:
    def test_grupo_nao_recebe_saudacao(self, sem_enviar):
        """⚠️ Saudação automática num grupo de quinze é ruído para catorze."""
        canal = banco.um(
            "SELECT id FROM canal WHERE tipo = 'atendimento' AND ativo LIMIT 1")
        cid = banco.um(
            """INSERT INTO conversa (canal_id, tipo, grupo_jid, estado)
               VALUES (%s, 'grupo', %s, 'nova') RETURNING id""",
            (canal["id"], "zz-grupo-aut@g.us"))["id"]
        _ligar("sem_cadastro")
        try:
            r = automacao.boas_vindas(cid)
            assert r["enviou"] is False
            assert r["motivo"] == "grupo"
            assert sem_enviar == []
        finally:
            banco.executar("DELETE FROM conversa WHERE id = %s", (cid,))


class TestNadaNasceLigado:
    def test_todos_os_tipos_nascem_desligados(self):
        """Automação que nasce ligada manda mensagem para cliente antes de
        alguém decidir que devia."""
        colunas = banco.um(
            """SELECT column_default AS d FROM information_schema.columns
                WHERE table_name = 'relacao_automacao'
                  AND column_name = 'boas_vindas_ligado'""")
        assert "false" in colunas["d"]
