"""A busca de conversa — os defeitos de 12/08 e o que os impede de voltar.

Três coisas estavam erradas, todas medidas antes de escrever isto:

  1. `998116168` (sem DDD) devolvia ZERO. `tel.normalizar` devolve None sem
     DDD, e o código caía no ramo de nome, procurando dígitos em
     `contato.nome`. Não dizia que faltava o DDD -- devolvia vazio.
  2. `iago` achava "Vendedor Thiago" e NÃO achava "Iago Do Ó". A tela mostra
     `nome_whatsapp`, o SQL procurava em `contato.nome`, e 85 das 131
     conversas não têm contato.
  3. A caixa procurava em `ct.nome`; o Histórico em `ct.nome OR cl.nome`.
     Dois trechos copiados que divergiram.

🚨 Escreve em `conversa`, `mensagem`, `contato` e `cliente` -- tabelas de
PRODUÇÃO. Telefone de DDD inexistente (+55 99 ...) e nomes com prefixo `zz`,
que não colidem com dado real. A fixture apaga só o que criou.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, "/home/claude/movizap_painel")
pytest.importorskip("psycopg")

from movizap import banco, conversas  # noqa: E402

ENV = Path("/home/claude/movizap_painel/.env")
pytestmark = pytest.mark.skipif(
    not ENV.exists() or "MOVIZAP_DB_SENHA" not in ENV.read_text(encoding="utf-8"),
    reason="banco nao configurado no .env")

FONE = "+5599944440000"
APELIDO = "zz Iago Do Teste"          # só em nome_whatsapp, sem cadastro
NOME_CONTATO = "zz contato de busca"
NOME_CLIENTE = "zz Pastelaria Zebrinha ME"
SEGREDO = "zzabracadabra"             # só existe no corpo de uma mensagem
NA_NOTA = "zzanotadoaqui"             # só existe numa nota interna


def limpar():
    banco.executar(
        """DELETE FROM mensagem WHERE conversa_id IN
           (SELECT id FROM conversa WHERE telefone_e164 = %s)""", (FONE,))
    banco.executar("DELETE FROM conversa WHERE telefone_e164 = %s", (FONE,))
    banco.executar("DELETE FROM contato WHERE nome = %s", (NOME_CONTATO,))
    banco.executar("DELETE FROM cliente WHERE nome = %s", (NOME_CLIENTE,))


@pytest.fixture(scope="module", autouse=True)
def pool():
    banco.abrir()
    limpar()
    yield
    limpar()
    banco.fechar()


@pytest.fixture()
def cena():
    """Uma conversa SEM vínculo, com apelido do WhatsApp e duas mensagens.

    Sem vínculo de propósito: é o caso de 65% da base, e era exatamente o que
    a busca não achava.
    """
    limpar()
    canal = banco.um("SELECT id FROM canal WHERE instancia = 'atendimento'")
    if not canal:
        pytest.skip("canal atendimento não cadastrado")

    conversa = banco.um(
        """INSERT INTO conversa (canal_id, telefone_e164, estado, nome_whatsapp)
           VALUES (%s, %s, 'nova', %s) RETURNING id""",
        (canal["id"], FONE, APELIDO))["id"]
    # ⚠️ `criada_em` é NOT NULL e NÃO tem padrão: é a hora do PROVEDOR, que o
    # webhook sempre traz. Omitir aqui derruba a fixture com NotNullViolation.
    banco.executar(
        """INSERT INTO mensagem (conversa_id, direcao, autor, tipo, conteudo,
                                 criada_em)
           VALUES (%s, 'entrada', 'cliente', 'texto', %s, now())""",
        (conversa, f"bom dia, {SEGREDO} por favor"))
    banco.executar(
        """INSERT INTO mensagem (conversa_id, direcao, autor, tipo, conteudo,
                                 criada_em)
           VALUES (%s, 'interna', 'atendente', 'nota', %s, now())""",
        (conversa, f"lembrete: {NA_NOTA}"))
    yield {"conversa": conversa, "canal": canal["id"]}
    limpar()


def achou(termo) -> list[int]:
    return [c["id"] for c in conversas.listar(busca=termo)]


class TestOsDefeitosDe1208:
    def test_telefone_SEM_DDD_acha(self, cena):
        """O caso que o usuário digitou: 998116168, sem DDD, devolvia zero."""
        assert cena["conversa"] in achou("944440000")

    def test_pedaco_do_telefone_acha(self, cena):
        """"6168 mostra o cel" -- pedaço, não sufixo inteiro nem número todo."""
        assert cena["conversa"] in achou("4440000")
        assert cena["conversa"] in achou("0000")

    def test_telefone_completo_continua_achando(self, cena):
        assert cena["conversa"] in achou("5599944440000")
        assert cena["conversa"] in achou("(99) 94444-0000")

    def test_acha_pelo_APELIDO_do_whatsapp(self, cena):
        """🚨 O defeito mais caro: a tela mostrava o nome e a busca não o via.

        Esta conversa NÃO tem contato_id -- como 85 das 131 da base.
        """
        assert cena["conversa"] in achou("Iago Do Teste")

    def test_pedaco_de_nome_acha_varios(self, cena):
        """"ago mostra iagos, thiagos, tiagos, yagos" -- pedaço, não prefixo."""
        assert cena["conversa"] in achou("ago")

    def test_busca_nao_diferencia_maiuscula(self, cena):
        assert achou("IAGO DO TESTE") == achou("iago do teste")


def achou_no_conteudo(termo):
    """A busca COM o interruptor "o que foi dito na conversa" ligado.

    🔵 30/09: o conteúdo das mensagens deixou de entrar na busca da Caixa por
    PADRÃO (pedido dele: *"Se é na conversa ou nome"*). Ele entrava sempre,
    num `OR` achatado com os nomes, e era o que trazia volume sem relação com
    o termo -- "weso" devolvia 10, sendo 4 os grupos e 6 conversas que só
    mencionavam a palavra.

    ⚠️ A CAPACIDADE NÃO MORREU, o padrão mudou. Por isso estes testes passaram
    a pedir o interruptor em vez de serem apagados: o que eles provam --
    inclusive a nota interna, decisão dele em 12/08 -- continua valendo.
    """
    return [c["id"] for c in conversas.listar(busca=termo, em_mensagens=True)]


class TestBuscaPorConteudo:
    def test_acha_pelo_texto_da_mensagem(self, cena):
        assert cena["conversa"] in achou_no_conteudo(SEGREDO)

    def test_acha_pelo_texto_da_NOTA_INTERNA(self, cena):
        """Decisão do usuário em 12/08: "a nota, uma vez dentro da conversa,
        faz parte da conversa". Segue valendo -- com o interruptor ligado."""
        assert cena["conversa"] in achou_no_conteudo(NA_NOTA)

    def test_conversa_aparece_UMA_vez_mesmo_com_varias_mensagens(self, cena):
        """🚨 Por isso é `EXISTS` e não JOIN: com JOIN a conversa em que o
        termo aparece em N mensagens voltaria N vezes na lista."""
        for _ in range(3):
            banco.executar(
                """INSERT INTO mensagem (conversa_id, direcao, autor, tipo,
                                         conteudo, criada_em)
                   VALUES (%s, 'entrada', 'cliente', 'texto', %s, now())""",
                (cena["conversa"], f"de novo {SEGREDO}"))
        assert achou_no_conteudo(SEGREDO).count(cena["conversa"]) == 1


class TestOPadraoDaCaixaNaoOlhaMensagem:
    """🔵 30/09: o padrão novo, travado. Sem isto, voltar o conteúdo ao padrão
    passaria calado -- e era ele que fazia a busca parecer não funcionar."""

    def test_conteudo_NAO_vem_no_padrao(self, cena):
        assert cena["conversa"] not in achou(SEGREDO)

    def test_nota_interna_NAO_vem_no_padrao(self, cena):
        assert cena["conversa"] not in achou(NA_NOTA)

    def test_o_interruptor_liga_de_volta(self, cena):
        assert cena["conversa"] in achou_no_conteudo(SEGREDO)

    def test_nome_continua_achando_no_padrao(self, cena):
        """O padrão não é "não achar nada" -- é achar por quem a conversa é."""
        assert cena["conversa"] in achou("Iago Do Teste")

    def test_os_dois_desligados_NAO_devolvem_a_lista_inteira(self, cena):
        """🚨 Condição vazia quer dizer "sem filtro", e a lista voltaria
        INTEIRA para quem digitou um termo. Sem onde procurar, procura no
        nome."""
        onde, _ = conversas._condicao_busca(
            "zznaoexisteemlugarnenhum", em_nome=False, em_mensagens=False)
        assert onde, "condição vazia devolveria a base inteira"
        assert conversas.listar(busca="zznaoexisteemlugarnenhum",
                                em_nome=False, em_mensagens=False) == []


class TestGrupoEhEncontravelPeloNome:
    """🚨 O DEFEITO DE 30/09: `grupo_nome` não estava na busca, e nenhuma
    conversa de grupo era encontrável pelo próprio nome.

    Medido na base real: das 15 conversas de grupo, **14 têm `grupo_nome` e
    ZERO têm `nome_whatsapp`** -- e só `nome_whatsapp` era olhado. Buscar
    "Tecnofrota" devolvia 0 existindo 2 grupos com esse nome. Mesma família do
    defeito do `assumir`, corrigido no mesmo dia: coluna de grupo esquecida em
    código escrito para conversa direta.
    """

    def test_a_condicao_olha_grupo_nome(self):
        onde, _ = conversas._condicao_busca("qualquer")
        assert "c.grupo_nome" in onde, (
            "grupo_nome saiu da busca -- todo grupo volta a ser inencontrável "
            "pelo próprio nome")

    def test_olha_tambem_onde_ja_olhava(self):
        """A correção não podia trocar uma coluna por outra."""
        onde, _ = conversas._condicao_busca("qualquer")
        for coluna in ("c.nome_whatsapp", "ct.nome", "cl.nome"):
            assert coluna in onde, f"{coluna} saiu da busca"


class TestPedacoDeTelefoneNaoArrastaABase:
    """🚨 O SEGUNDO DEFEITO DE 30/09, e o que o usuário estava vendo: um dígito
    perdido no meio de letras virava `telefone_e164 LIKE '%d%'`, que casa com
    quase toda a base.

    "x3tech" devolvia **100 conversas** -- o teto da lista -- porque o "3"
    casava com quase todo telefone. A busca respondia com a base cortada no
    limite, e não com o que se procurou.
    """

    def test_termo_com_letra_nao_vira_busca_de_telefone(self):
        onde, _ = conversas._condicao_busca("x3tech")
        assert "telefone_e164" not in onde, (
            "termo com letra voltou a virar busca de telefone -- um dígito "
            "solto arrasta a base inteira")

    def test_numero_continua_sendo_telefone(self):
        for termo in ("6168", "944440000", "(99) 94444-0000"):
            onde, _ = conversas._condicao_busca(termo)
            assert "telefone_e164" in onde, f"{termo!r} deixou de buscar telefone"

    def test_um_digito_so_nao_basta(self):
        """Piso de 3 dígitos: "1" casaria com quase tudo do mesmo jeito."""
        onde, _ = conversas._condicao_busca("1")
        assert "telefone_e164" not in onde

    def test_pedaco_de_telefone_segue_achando(self, cena):
        """O requisito de 12/08 -- "6168 mostra o cel" -- não pode ter morrido."""
        assert cena["conversa"] in achou("4440000")
        assert cena["conversa"] in achou("0000")


class TestEscopoContatoOuGrupo:
    """🔵 30/09, pedido dele: *"pode ter abas de opção como Contato; Grupos"*.

    ⚠️ É FILTRO, NÃO ABA: a migração 027 criou aba separada de grupo e a 028
    desfez. Um escopo estreita quando se pede; a lista segue unificada por
    padrão.
    """

    def test_contatos_exclui_grupo(self, cena):
        assert all(c.get("tipo") != "grupo"
                   for c in conversas.listar(escopo="contatos"))

    def test_grupos_traz_so_grupo(self, cena):
        assert all(c.get("tipo") == "grupo"
                   for c in conversas.listar(escopo="grupos"))

    def test_tudo_e_o_padrao(self, cena):
        assert (len(conversas.listar())
                == len(conversas.listar(escopo="tudo")))

    def test_escopo_desconhecido_nao_esconde_conversa(self, cena):
        """Valor estranho não pode virar filtro silencioso."""
        assert (len(conversas.listar(escopo="banana"))
                == len(conversas.listar()))


class TestOTrechoNaPrevia:
    def _linha(self, termo, conversa_id, em_mensagens=False):
        for c in conversas.listar(busca=termo, em_mensagens=em_mensagens):
            if c["id"] == conversa_id:
                return c
        return None

    def test_casou_por_texto_traz_o_trecho(self, cena):
        """Sem isto a conversa aparece na lista sem nada visível batendo.

        ⚠️ Pede `em_mensagens=True` desde 30/09: sem o interruptor não existe
        "casou por texto" na Caixa, porque o conteúdo não entra no padrão.
        """
        linha = self._linha(SEGREDO, cena["conversa"], em_mensagens=True)
        assert linha is not None
        assert linha["trecho"] and SEGREDO in linha["trecho"]

    def test_casou_pelo_NOME_nao_traz_trecho(self, cena):
        """O motivo do acerto já está à vista -- trecho ali seria ruído."""
        linha = self._linha("Iago Do Teste", cena["conversa"])
        assert linha is not None
        assert linha["trecho"] is None

    def test_casou_pelo_TELEFONE_nao_traz_trecho(self, cena):
        linha = self._linha("944440000", cena["conversa"])
        assert linha is not None
        assert linha["trecho"] is None

    def test_sem_busca_ninguem_tem_trecho(self, cena):
        assert all(c["trecho"] is None for c in conversas.listar())


class TestCaixaEHistoricoConcordam:
    """🚨 A regra virou função para os dois não poderem divergir de novo."""

    @pytest.fixture()
    def encerrada(self, cena):
        banco.executar(
            "UPDATE conversa SET estado = 'resolvida', resolvida_em = now() "
            " WHERE id = %s", (cena["conversa"],))
        return cena["conversa"]

    def test_historico_acha_pelo_apelido(self, encerrada):
        assert encerrada in [c["id"] for c in conversas.historico(busca="ago")]

    def test_historico_acha_pelo_conteudo(self, encerrada):
        assert encerrada in [c["id"] for c in conversas.historico(busca=SEGREDO)]

    def test_historico_acha_sem_DDD(self, encerrada):
        assert encerrada in [c["id"] for c in conversas.historico(busca="944440000")]

    def test_as_duas_usam_a_MESMA_funcao(self):
        """Prova estrutural: se alguém copiar a condição de novo, isto cai."""
        import inspect
        for fn in (conversas.listar, conversas.historico):
            assert "_condicao_busca" in inspect.getsource(fn), (
                f"{fn.__name__} deixou de usar a função comum -- a divergência "
                f"entre caixa e histórico está voltando")


class TestBuscaVazia:
    def test_termo_vazio_nao_filtra(self, cena):
        assert conversas._condicao_busca("") == ("", [])
        assert conversas._condicao_busca("   ") == ("", [])

    def test_termo_que_nao_existe_devolve_nada(self, cena):
        assert achou("zznaoexisteemlugarnenhum") == []


class TestJanelaDeMensagens:
    """🚨 O TETO DE 1.000 SAIU EM 25/08. Ele foi decidido em 12/08 quando a
    maior conversa tinha 130 mensagens; em 25/08 ela chegou a 776, e teto que
    se encosta silencia mensagem antiga. No lugar entrou paginação por cursor:
    60 ao abrir, 200 por vez para trás, sem teto.
    """

    def test_abre_com_a_janela_inicial(self):
        """Decisão do usuário em 25/08: 60 ao abrir, 200 por vez."""
        assert conversas.JANELA_INICIAL == 60
        assert conversas.JANELA_ANTERIORES == 200

    def test_conversa_curta_nao_oferece_anteriores(self, cena):
        assert conversas.conversa(cena["conversa"])["tem_anteriores"] is False

    def test_a_janela_pega_as_mensagens_MAIS_RECENTES(self, cena):
        """🚨 `ORDER BY criada_em ASC LIMIT n` devolvia as n MAIS ANTIGAS.

        Numa conversa acima do teto o atendente veria o começo dela e nunca o
        que o cliente acabou de dizer. Nenhuma conversa passou do teto ainda,
        então isso nunca apareceu -- é defeito latente, e o teste o prende
        agora, com limite pequeno, em vez de esperar a conversa de 1.001.
        """
        for i in range(6):
            banco.executar(
                """INSERT INTO mensagem (conversa_id, direcao, autor, tipo,
                                         conteudo, criada_em)
                   VALUES (%s, 'entrada', 'cliente', 'texto', %s,
                           now() + (%s || ' minutes')::interval)""",
                (cena["conversa"], f"marco {i}", i + 1))

        ultimas = conversas.mensagens(cena["conversa"], limite=3)
        textos = [m["conteudo"] for m in ultimas]
        assert textos == ["marco 3", "marco 4", "marco 5"], (
            f"o teto cortou pelo lado errado: {textos}")

    def test_carregar_anteriores_traz_o_que_vem_ANTES(self, cena):
        """O cursor é o id da mensagem mais antiga que a tela tem no topo."""
        for i in range(6):
            banco.executar(
                """INSERT INTO mensagem (conversa_id, direcao, autor, tipo,
                                         conteudo, criada_em)
                   VALUES (%s, 'entrada', 'cliente', 'texto', %s,
                           now() + (%s || ' minutes')::interval)""",
                (cena["conversa"], f"pagina {i}", i + 1))

        primeira_janela = conversas.mensagens(cena["conversa"], limite=3)
        topo = primeira_janela[0]["id"]
        anteriores = conversas.mensagens(cena["conversa"], limite=3,
                                         antes_de=topo)
        # Nada se repete entre as duas janelas.
        assert not ({m["id"] for m in anteriores}
                    & {m["id"] for m in primeira_janela})
        # E o que veio é mais VELHO que o topo.
        assert all(m["criada_em"] <= primeira_janela[0]["criada_em"]
                   for m in anteriores)

    def test_tem_anteriores_diz_a_verdade_nos_dois_sentidos(self, cena):
        for i in range(6):
            banco.executar(
                """INSERT INTO mensagem (conversa_id, direcao, autor, tipo,
                                         conteudo, criada_em)
                   VALUES (%s, 'entrada', 'cliente', 'texto', %s,
                           now() + (%s || ' minutes')::interval)""",
                (cena["conversa"], f"pag {i}", i + 1))

        janela = conversas.mensagens(cena["conversa"], limite=3)
        assert conversas.tem_anteriores(cena["conversa"], janela[0]["id"]) is True

        tudo = conversas.mensagens(cena["conversa"], limite=500)
        assert conversas.tem_anteriores(cena["conversa"], tudo[0]["id"]) is False


class TestBuscaDentroDaConversaNoServidor:
    """🚨 A BUSCA SUBIU PARA O SERVIDOR JUNTO COM A PAGINAÇÃO. Ela rodava no
    navegador sobre o que estava carregado. Com a tela abrindo em 60, a mesma
    busca passaria a dizer "nada com esse termo" sobre mensagem que existe
    três telas acima -- e o usuário registrou em 25/08 que essa busca "está
    ótima". Paginar sem mover a busca teria quebrado exatamente o que ele
    elogiou.
    """

    def test_acha_mensagem_FORA_da_janela_inicial(self, cena):
        alvo = "zzagulhanopalheiro"
        banco.executar(
            """INSERT INTO mensagem (conversa_id, direcao, autor, tipo,
                                     conteudo, criada_em)
               VALUES (%s, 'entrada', 'cliente', 'texto', %s,
                       now() - interval '10 days')""",
            (cena["conversa"], alvo))
        for i in range(5):
            banco.executar(
                """INSERT INTO mensagem (conversa_id, direcao, autor, tipo,
                                         conteudo, criada_em)
                   VALUES (%s, 'entrada', 'cliente', 'texto', %s, now())""",
                (cena["conversa"], f"ruido {i}"))

        # A janela pequena NÃO contém a agulha...
        janela = conversas.mensagens(cena["conversa"], limite=3)
        assert alvo not in [m["conteudo"] for m in janela]
        # ...e a busca acha assim mesmo.
        achados = conversas.buscar_na_conversa(cena["conversa"], alvo)
        assert len(achados) == 1

    def test_termo_vazio_nao_devolve_a_conversa_inteira(self, cena):
        assert conversas.buscar_na_conversa(cena["conversa"], "  ") == []

    def test_devolve_em_ordem_de_conversa(self, cena):
        for i in range(3):
            banco.executar(
                """INSERT INTO mensagem (conversa_id, direcao, autor, tipo,
                                         conteudo, criada_em)
                   VALUES (%s, 'entrada', 'cliente', 'texto', %s,
                           now() + (%s || ' minutes')::interval)""",
                (cena["conversa"], f"zzordem {i}", i + 1))
        achados = conversas.buscar_na_conversa(cena["conversa"], "zzordem")
        assert [a["id"] for a in achados] == sorted(a["id"] for a in achados)
