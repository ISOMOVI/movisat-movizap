"""ATD_6.1 — chat entre atendentes.

Pendência de 11/08 que eu empurrei duas vezes como "decisão" antes de fazer.

🚨 Escreve em `chat_sala`, `chat_membro`, `chat_mensagem` e `atendente`, que
são tabelas de PRODUÇÃO. Logins com prefixo `zz`, e a fixture apaga só o que
criou.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, "/home/claude/movizap_painel")
pytest.importorskip("psycopg")

from movizap import banco, chat  # noqa: E402

ENV = Path("/home/claude/movizap_painel/.env")
pytestmark = pytest.mark.skipif(
    not ENV.exists() or "MOVIZAP_DB_SENHA" not in ENV.read_text(encoding="utf-8"),
    reason="banco nao configurado no .env")

LOGIN = "zz_teste_chat_"


def limpar():
    """⚠️ A SALA VAZIA TAMBÉM PRECISA SAIR, e foi um teste que me ensinou.

    A primeira versão apagava sala pela MEMBRESIA. Quando o teste
    `test_a_sala_SOBREVIVE_a_saida_de_todos` esvaziou um grupo -- que é o
    comportamento correto --, a sala ficou sem membro, escapou da limpeza, e as
    mensagens dela seguraram os atendentes por chave estrangeira. A suíte
    inteira caiu depois, em ForeignKeyViolation, longe da causa.

    Agora a sala é achada por membresia OU por autoria de mensagem.
    """
    alvo = """(SELECT sala_id FROM chat_membro WHERE atendente_id IN
                 (SELECT id FROM atendente WHERE login LIKE %s)
               UNION
               SELECT sala_id FROM chat_mensagem WHERE atendente_id IN
                 (SELECT id FROM atendente WHERE login LIKE %s))"""
    banco.executar(f"DELETE FROM chat_sala WHERE id IN {alvo}",
                   (LOGIN + "%", LOGIN + "%"))
    banco.executar("DELETE FROM atendente WHERE login LIKE %s", (LOGIN + "%",))


@pytest.fixture(scope="module", autouse=True)
def pool():
    banco.abrir()
    limpar()
    yield
    limpar()
    banco.fechar()


@pytest.fixture()
def gente():
    limpar()
    ids = []
    for n in ("ana", "bruno", "carla"):
        ids.append(banco.um(
            """INSERT INTO atendente (nome, login, email, senha_hash, perfil, ativo)
               VALUES (%s, %s, %s, 'x', 'atendimento', true) RETURNING id""",
            (f"Teste {n}", LOGIN + n, f"{LOGIN}{n}@movisat.com.br"))["id"])
    yield {"ana": ids[0], "bruno": ids[1], "carla": ids[2]}
    limpar()


class TestAbrirSala:
    def test_abre_e_põe_os_dois_dentro(self, gente):
        r = chat.abrir_direta(gente["ana"], gente["bruno"])
        assert r["ok"] is True
        assert chat.e_membro(r["sala_id"], gente["ana"])
        assert chat.e_membro(r["sala_id"], gente["bruno"])

    def test_abrir_DE_NOVO_devolve_a_MESMA_sala(self, gente):
        """🚨 Sem a chave do par, dois cliques criariam duas salas e a
        conversa se partiria em duas metades sem nada acusar."""
        a = chat.abrir_direta(gente["ana"], gente["bruno"])["sala_id"]
        b = chat.abrir_direta(gente["ana"], gente["bruno"])["sala_id"]
        assert a == b

    def test_a_ordem_de_quem_ABRE_nao_cria_sala_nova(self, gente):
        """`12:34` e `34:12` seriam duas salas para as mesmas duas pessoas."""
        a = chat.abrir_direta(gente["ana"], gente["bruno"])["sala_id"]
        b = chat.abrir_direta(gente["bruno"], gente["ana"])["sala_id"]
        assert a == b

    def test_pares_diferentes_sao_salas_diferentes(self, gente):
        a = chat.abrir_direta(gente["ana"], gente["bruno"])["sala_id"]
        c = chat.abrir_direta(gente["ana"], gente["carla"])["sala_id"]
        assert a != c

    def test_nao_da_para_falar_consigo_mesmo(self, gente):
        assert chat.abrir_direta(gente["ana"], gente["ana"])["ok"] is False

    def test_atendente_inativo_e_recusado(self, gente):
        banco.executar("UPDATE atendente SET ativo = false WHERE id = %s",
                       (gente["bruno"],))
        r = chat.abrir_direta(gente["ana"], gente["bruno"])
        assert r["ok"] is False
        assert "inativo" in r["motivo"]

    def test_atendente_inexistente(self, gente):
        assert chat.abrir_direta(gente["ana"], -1)["ok"] is False


class TestEscreverELer:
    def test_escreve_e_le(self, gente):
        s = chat.abrir_direta(gente["ana"], gente["bruno"])["sala_id"]
        assert chat.escrever(s, gente["ana"], "bom dia")["ok"] is True
        msgs = chat.mensagens(s, gente["bruno"])
        assert [m["texto"] for m in msgs] == ["bom dia"]
        assert msgs[0]["autor"] == "Teste ana"
        assert msgs[0]["minha"] is False

    def test_minha_e_relativo_a_quem_le(self, gente):
        s = chat.abrir_direta(gente["ana"], gente["bruno"])["sala_id"]
        chat.escrever(s, gente["ana"], "oi")
        assert chat.mensagens(s, gente["ana"])[0]["minha"] is True
        assert chat.mensagens(s, gente["bruno"])[0]["minha"] is False

    def test_ordem_e_cronologica(self, gente):
        s = chat.abrir_direta(gente["ana"], gente["bruno"])["sala_id"]
        for t in ("um", "dois", "tres"):
            chat.escrever(s, gente["ana"], t)
        assert [m["texto"] for m in chat.mensagens(s, gente["ana"])] == \
            ["um", "dois", "tres"]

    def test_o_teto_pega_as_MAIS_RECENTES(self, gente):
        """Mesmo cuidado do `conversas.mensagens`: cortar pelo lado errado
        mostraria o começo da sala e esconderia o que acabou de ser dito."""
        s = chat.abrir_direta(gente["ana"], gente["bruno"])["sala_id"]
        for i in range(6):
            chat.escrever(s, gente["ana"], f"m{i}")
        assert [m["texto"] for m in chat.mensagens(s, gente["ana"], limite=3)] == \
            ["m3", "m4", "m5"]

    def test_mensagem_vazia_e_recusada(self, gente):
        s = chat.abrir_direta(gente["ana"], gente["bruno"])["sala_id"]
        assert chat.escrever(s, gente["ana"], "   ")["ok"] is False
        assert chat.mensagens(s, gente["ana"]) == []

    def test_quem_NAO_e_membro_nao_escreve(self, gente):
        """🚨 Aqui o isolamento é REAL, diferente da conversa de cliente."""
        s = chat.abrir_direta(gente["ana"], gente["bruno"])["sala_id"]
        r = chat.escrever(s, gente["carla"], "intrometida")
        assert r["ok"] is False
        assert chat.mensagens(s, gente["ana"]) == []

    def test_e_membro_diz_a_verdade(self, gente):
        s = chat.abrir_direta(gente["ana"], gente["bruno"])["sala_id"]
        assert chat.e_membro(s, gente["ana"]) is True
        assert chat.e_membro(s, gente["carla"]) is False


class TestNaoLidas:
    def test_quem_recebe_tem_nao_lida(self, gente):
        s = chat.abrir_direta(gente["ana"], gente["bruno"])["sala_id"]
        chat.escrever(s, gente["ana"], "oi")
        assert chat.nao_lidas(gente["bruno"]) == 1

    def test_quem_ESCREVE_nao_fica_com_nao_lida(self, gente):
        """⚠️ Sem marcar na escrita, a própria mensagem contaria como não
        lida para o autor no carregamento seguinte."""
        s = chat.abrir_direta(gente["ana"], gente["bruno"])["sala_id"]
        chat.escrever(s, gente["ana"], "oi")
        assert chat.nao_lidas(gente["ana"]) == 0

    def test_marcar_lido_zera(self, gente):
        s = chat.abrir_direta(gente["ana"], gente["bruno"])["sala_id"]
        chat.escrever(s, gente["ana"], "oi")
        chat.marcar_lido(s, gente["bruno"])
        assert chat.nao_lidas(gente["bruno"]) == 0

    def test_o_marcador_NUNCA_VOLTA(self, gente):
        """🚨 `GREATEST`: abrir uma sala antiga não pode fazer mensagens já
        lidas voltarem a contar."""
        s = chat.abrir_direta(gente["ana"], gente["bruno"])["sala_id"]
        chat.escrever(s, gente["ana"], "um")
        chat.escrever(s, gente["ana"], "dois")
        chat.marcar_lido(s, gente["bruno"])
        assert chat.nao_lidas(gente["bruno"]) == 0
        chat.marcar_lido(s, gente["bruno"], 1)   # tentativa de retroceder
        assert chat.nao_lidas(gente["bruno"]) == 0

    def test_reabrir_a_sala_nao_zera_o_lido(self, gente):
        """O `ON CONFLICT DO NOTHING` do membro protege isto."""
        s = chat.abrir_direta(gente["ana"], gente["bruno"])["sala_id"]
        chat.escrever(s, gente["ana"], "oi")
        chat.marcar_lido(s, gente["bruno"])
        chat.abrir_direta(gente["ana"], gente["bruno"])
        assert chat.nao_lidas(gente["bruno"]) == 0

    def test_nao_lidas_conta_so_as_minhas_salas(self, gente):
        s = chat.abrir_direta(gente["ana"], gente["bruno"])["sala_id"]
        chat.escrever(s, gente["ana"], "oi")
        assert chat.nao_lidas(gente["carla"]) == 0


class TestListaDeSalas:
    def test_traz_a_ultima_mensagem_e_com_quem_e(self, gente):
        s = chat.abrir_direta(gente["ana"], gente["bruno"])["sala_id"]
        chat.escrever(s, gente["ana"], "ultima coisa")
        linha = next(x for x in chat.salas(gente["bruno"]) if x["id"] == s)
        assert linha["com"] == "Teste ana", "o nome tem de ser o do OUTRO"
        assert linha["ultima_mensagem"] == "ultima coisa"
        assert linha["nao_lidas"] == 1

    def test_para_o_autor_o_com_e_a_outra_pessoa(self, gente):
        s = chat.abrir_direta(gente["ana"], gente["bruno"])["sala_id"]
        linha = next(x for x in chat.salas(gente["ana"]) if x["id"] == s)
        assert linha["com"] == "Teste bruno"

    def test_ordena_por_atividade(self, gente):
        a = chat.abrir_direta(gente["ana"], gente["bruno"])["sala_id"]
        c = chat.abrir_direta(gente["ana"], gente["carla"])["sala_id"]
        chat.escrever(a, gente["ana"], "primeiro")
        chat.escrever(c, gente["ana"], "depois")
        minhas = [x["id"] for x in chat.salas(gente["ana"])
                  if x["id"] in (a, c)]
        assert minhas[0] == c, "a mais recente tem de vir no topo"

    def test_nao_mostra_sala_alheia(self, gente):
        chat.abrir_direta(gente["ana"], gente["bruno"])
        assert chat.salas(gente["carla"]) == []


class TestGrupo:
    def test_cria_com_o_criador_dentro(self, gente):
        r = chat.criar_grupo("Comercial", gente["ana"],
                             [gente["bruno"], gente["carla"]])
        assert r["ok"] is True
        assert r["membros"] == 3
        dentro = {m["atendente_id"] for m in chat.membros(r["sala_id"])}
        assert dentro == {gente["ana"], gente["bruno"], gente["carla"]}

    def test_o_criador_entra_MESMO_fora_da_lista(self, gente):
        """Criar um grupo e ficar de fora não é caso de uso, é engano."""
        r = chat.criar_grupo("Sem mim", gente["ana"], [gente["bruno"]])
        assert gente["ana"] in {m["atendente_id"] for m in chat.membros(r["sala_id"])}

    def test_grupo_de_um_e_recusado(self, gente):
        assert chat.criar_grupo("Só eu", gente["ana"], [])["ok"] is False

    def test_nome_vazio_e_recusado(self, gente):
        assert chat.criar_grupo("   ", gente["ana"],
                                [gente["bruno"]])["ok"] is False

    def test_membro_inativo_derruba_a_criacao(self, gente):
        banco.executar("UPDATE atendente SET ativo = false WHERE id = %s",
                       (gente["carla"],))
        r = chat.criar_grupo("Com inativo", gente["ana"],
                             [gente["bruno"], gente["carla"]])
        assert r["ok"] is False

    def test_dois_grupos_com_o_MESMO_NOME_sao_grupos_diferentes(self, gente):
        """Diferente da sala direta, grupo não tem chave de par: 'Financeiro'
        de hoje e 'Financeiro' do ano que vem não são a mesma conversa."""
        a = chat.criar_grupo("Financeiro", gente["ana"], [gente["bruno"]])
        b = chat.criar_grupo("Financeiro", gente["ana"], [gente["carla"]])
        assert a["sala_id"] != b["sala_id"]

    def test_a_lista_mostra_o_NOME_do_grupo_e_nao_um_membro(self, gente):
        """🚨 O `com` da sala direta é a outra pessoa. Num grupo de três, sem
        o CASE, viria o nome de UM membro qualquer no lugar do nome do
        grupo -- e a lista teria salas que ninguém reconhece."""
        r = chat.criar_grupo("Plantão", gente["ana"],
                             [gente["bruno"], gente["carla"]])
        linha = next(x for x in chat.salas(gente["ana"]) if x["id"] == r["sala_id"])
        assert linha["com"] is None
        assert linha["nome"] == "Plantão"
        assert linha["qtd_membros"] == 3

    def test_a_sala_direta_continua_mostrando_a_pessoa(self, gente):
        s = chat.abrir_direta(gente["ana"], gente["bruno"])["sala_id"]
        linha = next(x for x in chat.salas(gente["ana"]) if x["id"] == s)
        assert linha["com"] == "Teste bruno"
        assert linha["qtd_membros"] == 2


class TestEntrarESairDoGrupo:
    def test_membro_chama_outro(self, gente):
        r = chat.criar_grupo("Suporte", gente["ana"], [gente["bruno"]])
        assert chat.adicionar_ao_grupo(
            r["sala_id"], gente["ana"], gente["carla"])["ok"] is True
        assert chat.e_membro(r["sala_id"], gente["carla"]) is True

    def test_quem_esta_de_FORA_nao_chama_ninguem(self, gente):
        r = chat.criar_grupo("Fechado", gente["ana"], [gente["bruno"]])
        fora = chat.adicionar_ao_grupo(r["sala_id"], gente["carla"], gente["carla"])
        assert fora["ok"] is False
        assert chat.e_membro(r["sala_id"], gente["carla"]) is False

    def test_quem_chega_NAO_herda_nao_lidas_do_passado(self, gente):
        """Entrar num grupo antigo com 200 não lidas seria inútil."""
        r = chat.criar_grupo("Antigo", gente["ana"], [gente["bruno"]])
        for i in range(4):
            chat.escrever(r["sala_id"], gente["ana"], f"antes {i}")
        chat.adicionar_ao_grupo(r["sala_id"], gente["ana"], gente["carla"])
        assert chat.nao_lidas(gente["carla"]) == 0
        chat.escrever(r["sala_id"], gente["ana"], "depois que ela entrou")
        assert chat.nao_lidas(gente["carla"]) == 1

    def test_quem_chega_LE_o_historico(self, gente):
        """Não receber contador não é o mesmo que não ver o que foi dito."""
        r = chat.criar_grupo("Historico", gente["ana"], [gente["bruno"]])
        chat.escrever(r["sala_id"], gente["ana"], "combinado de ontem")
        chat.adicionar_ao_grupo(r["sala_id"], gente["ana"], gente["carla"])
        textos = [m["texto"] for m in chat.mensagens(r["sala_id"], gente["carla"])]
        assert "combinado de ontem" in textos

    def test_chamar_quem_ja_esta_e_inofensivo(self, gente):
        r = chat.criar_grupo("Repetido", gente["ana"], [gente["bruno"]])
        out = chat.adicionar_ao_grupo(r["sala_id"], gente["ana"], gente["bruno"])
        assert out["ok"] is True and out.get("ja_estava") is True
        assert len(chat.membros(r["sala_id"])) == 2

    def test_sair_do_grupo(self, gente):
        r = chat.criar_grupo("Saida", gente["ana"],
                             [gente["bruno"], gente["carla"]])
        assert chat.sair_do_grupo(r["sala_id"], gente["carla"])["ok"] is True
        assert chat.e_membro(r["sala_id"], gente["carla"]) is False
        assert len(chat.membros(r["sala_id"])) == 2

    def test_quem_saiu_para_de_ver_a_sala(self, gente):
        r = chat.criar_grupo("Some", gente["ana"], [gente["bruno"], gente["carla"]])
        chat.sair_do_grupo(r["sala_id"], gente["carla"])
        assert r["sala_id"] not in [x["id"] for x in chat.salas(gente["carla"])]

    def test_a_sala_SOBREVIVE_a_saida_de_todos(self, gente):
        """⚠️ As mensagens são o registro do que foi combinado. Apagar a
        conversa por esvaziamento perderia isso sem ninguém pedir."""
        r = chat.criar_grupo("Esvazia", gente["ana"], [gente["bruno"]])
        chat.escrever(r["sala_id"], gente["ana"], "fica registrado")
        chat.sair_do_grupo(r["sala_id"], gente["ana"])
        chat.sair_do_grupo(r["sala_id"], gente["bruno"])
        assert banco.um("SELECT id FROM chat_sala WHERE id = %s",
                        (r["sala_id"],)) is not None
        assert banco.um("SELECT count(*) n FROM chat_mensagem WHERE sala_id = %s",
                        (r["sala_id"],))["n"] == 1

    def test_NAO_da_para_por_gente_numa_sala_DIRETA(self, gente):
        """Conversa de dois que vira de três é outra conversa. Transformá-la
        escondido faria os dois primeiros descobrirem o terceiro no histórico."""
        s = chat.abrir_direta(gente["ana"], gente["bruno"])["sala_id"]
        r = chat.adicionar_ao_grupo(s, gente["ana"], gente["carla"])
        assert r["ok"] is False
        assert chat.e_membro(s, gente["carla"]) is False

    def test_NAO_da_para_sair_de_uma_sala_DIRETA(self, gente):
        s = chat.abrir_direta(gente["ana"], gente["bruno"])["sala_id"]
        assert chat.sair_do_grupo(s, gente["ana"])["ok"] is False


class TestComQuemFalar:
    def test_nao_me_lista(self, gente):
        assert gente["ana"] not in [c["id"] for c in chat.com_quem_falar(gente["ana"])]

    def test_lista_os_outros_ativos(self, gente):
        ids = [c["id"] for c in chat.com_quem_falar(gente["ana"])]
        assert gente["bruno"] in ids and gente["carla"] in ids

    def test_sem_email_nao_aparece(self, gente):
        """Mesma régua do vínculo de atendimento: quem não tem e-mail não tem
        vínculo, e não teria como responder."""
        banco.executar("UPDATE atendente SET email = NULL WHERE id = %s",
                       (gente["carla"],))
        assert gente["carla"] not in [
            c["id"] for c in chat.com_quem_falar(gente["ana"])]

    def test_inativo_nao_aparece(self, gente):
        banco.executar("UPDATE atendente SET ativo = false WHERE id = %s",
                       (gente["bruno"],))
        assert gente["bruno"] not in [
            c["id"] for c in chat.com_quem_falar(gente["ana"])]


class TestNaoContaminaOAtendimento:
    """🚨 A razão de existirem tabelas próprias (migração 026).

    Se o chat vivesse em `conversa`/`mensagem`, TODA consulta sobre cliente
    precisaria filtrá-lo -- e esquecer uma vez faria conversa interna aparecer
    na caixa de entrada ou entrar na contagem do painel.
    """

    def test_o_chat_nao_cria_conversa_nem_mensagem(self, gente):
        from movizap import conversas
        antes_c = banco.um("SELECT count(*) n FROM conversa")["n"]
        antes_m = banco.um("SELECT count(*) n FROM mensagem")["n"]

        s = chat.abrir_direta(gente["ana"], gente["bruno"])["sala_id"]
        chat.escrever(s, gente["ana"], "conversa interna")

        assert banco.um("SELECT count(*) n FROM conversa")["n"] == antes_c
        assert banco.um("SELECT count(*) n FROM mensagem")["n"] == antes_m
        # E não aparece em lugar nenhum do atendimento.
        assert not [c for c in conversas.listar(busca="conversa interna")]

    def test_o_modulo_de_chat_NAO_IMPORTA_o_evolution(self):
        """Nada daqui pode sair para o WhatsApp, e a garantia é estrutural:
        não existe caminho de código até o gateway.

        ⚠️ Lê os IMPORTS pela AST, não a palavra no texto. A primeira versão
        procurava "evolution" no fonte inteiro e reprovava por causa de um
        comentário que dizia justamente que o módulo não o conhece -- teste
        que reprova a própria documentação da regra que ele guarda.
        """
        import ast
        import inspect

        arvore = ast.parse(inspect.getsource(chat))
        importados = set()
        for no in ast.walk(arvore):
            if isinstance(no, ast.Import):
                importados |= {a.name.split(".")[0] for a in no.names}
            elif isinstance(no, ast.ImportFrom):
                if no.module:
                    importados.add(no.module.split(".")[0])
                importados |= {a.name for a in no.names}
        assert "evolution" not in importados, (
            f"o chat interno passou a importar o gateway do WhatsApp: {importados}")
