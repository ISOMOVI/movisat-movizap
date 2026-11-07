# -*- coding: utf-8 -*-
r"""A PERMISSÃO DOS PAINÉIS, por pessoa e por aba — a aba `CFG_15.1` (06/11).

🔵 Pedido dele: *"em configuração, crie uma aba de permissão para os paineis,
ali vou definir quem pode ver o que e por aba tbm, como notará que o pós venda
ja possui abas"*.

🚨 **AS QUATRO REGRAS QUE ESTE ARQUIVO PRENDE:**

1. **A CONCESSÃO NOMEADA VENCE O `permissao: owner` DA TELA.** É a regra nova, e
   sem ela a aba gravaria sem efeito nenhum: as três telas de painel são
   `owner`, e `pode_acessar` recusava todo não-owner. ⚠️ A prova forte é por
   HTTP: a mesma pessoa, **403 antes e 200 depois**, sem reiniciar nada e sem
   token novo.
2. **A CONCESSÃO NÃO VAZA PARA FORA DO QUE FOI MARCADO.** Ter `PNL_1.3` não abre
   `PNL_1.2`, nem `CFG_1.1` (os canais do WhatsApp), nem a própria `CFG_15.1`.
3. **SÓ O GRUPO "PAINÉIS" É CONCEDÍVEL, e a trava é no backend.** Código de fora
   é **422 de regra**, não 500 nem 200 calado. ⚠️ E a lista sai do REGISTRO: um
   painel novo (o Financeiro, quando ele der as colunas) entra sozinho.
4. **DESMARCAR REVOGA DE VERDADE.** A rota recebe o estado completo da linha, e
   a releitura é o que a tela redesenha.

⚠️ **A GRAVAÇÃO É POR DELTA**, e isso tem teste próprio: regravar a mesma lista
não pode trocar `concedida_em` -- quem concedeu quando é o único histórico que a
tabela guarda.

🚨 **TODO TESTE DAQUI FOI VISTO VERMELHO ANTES DE FICAR VERDE** (o defeito que
guarda, forjado e pego). Os dois que mais importam: tirar a linha da concessão
do `pode_acessar` derruba 6; devolver `permitidos` em vez de recusar no
`definir` derruba a 3.

Roda:  venv/bin/python -m pytest tests/teste_permissao_paineis.py
"""
import pathlib
import sys

import pytest

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from fastapi.testclient import TestClient  # noqa: E402

from movizap import auth, banco, main, permissao_paineis  # noqa: E402
from movizap import telas as registro_telas  # noqa: E402
from movizap.config import settings  # noqa: E402

# ⚠️ Login de sentinela, com prefixo próprio: a suíte escreve no banco de
# PRODUÇÃO (é o desenho da casa), e nome genérico um dia colide com gente de
# verdade. O `limpar()` roda antes E depois, porque rodada interrompida deixa
# sobra -- e sobra aqui é uma pessoa com painel concedido.
LOGIN = "teste_perm_paineis"


def os_paineis() -> set[str]:
    """As telas de painel, SAINDO DO REGISTRO.

    🚨 Era uma constante `AS_TRES = {"PNL_1.1", "PNL_1.2", "PNL_1.3"}`, e ficou
    vermelha no mesmo dia: o Financeiro (`PNL_1.4`) e o Contratual (`PNL_1.5`)
    entraram horas depois. ⚠️ Num arquivo cujo assunto e *"painel novo entra
    sozinho na aba de permissao"*, lista fixa era o proprio defeito que ele
    cobrava -- obrigava a editar teste a cada painel novo, que e exatamente o
    que o desenho promete nao ser necessario.
    """
    return {t["codigo"] for t in registro_telas.ativas()
            if registro_telas.grupo_da(t) == "Painéis"}


def limpar():
    # 🚨 REABRE O POOL ANTES DE LIMPAR, e não é zelo: o `TestClient`, ao sair do
    # `with`, dispara o `shutdown` do app -- que chama `banco.fechar()`. A
    # fixture `pessoa` é de FUNÇÃO e a `cliente` é de MÓDULO, então a limpeza do
    # último teste do arquivo cai depois do banco já fechado e estoura com
    # *"banco não foi aberto"*. ⚠️ Erro em TEARDOWN é o pior dos dois mundos: o
    # teste passa, o arquivo fica vermelho, e a sobra (uma pessoa com painel
    # concedido) continua no banco de produção. `abrir()` é no-op se já estiver
    # aberto.
    banco.abrir()
    banco.executar(
        """DELETE FROM tela_concedida
            WHERE atendente_id IN (SELECT id FROM atendente WHERE login LIKE %s)""",
        (LOGIN + "%",),
    )
    banco.executar("DELETE FROM atendente WHERE login LIKE %s", (LOGIN + "%",))


@pytest.fixture(scope="module", autouse=True)
def pool():
    banco.abrir()
    limpar()
    yield
    limpar()


@pytest.fixture(scope="module")
def cliente():
    # ⚠️ `TestClient` de MÓDULO: um segundo no mesmo `app` dá *"Event is bound
    # to a different event loop"* -- já documentado no `teste_rotas_pipeline`.
    with TestClient(main.app) as c:
        yield c


@pytest.fixture(scope="module")
def token_owner():
    return auth.criar_token(settings.admin_login)


@pytest.fixture()
def pessoa():
    """Uma conta de atendimento, viva e sem painel nenhum.

    ⚠️ `perfil='atendimento'` de propósito: é o perfil mais apertado em uso, e
    é nele que a concessão tem de aparecer. Com um perfil largo o teste passaria
    por acidente.
    """
    limpar()
    linha = banco.um(
        """INSERT INTO atendente (nome, login, email, senha_hash, perfil, ativo)
                VALUES ('Teste Permissao', %s, %s, 'x', 'atendimento', true)
             RETURNING id""",
        (LOGIN, LOGIN + "@movisat.com.br"),
    )
    yield {"id": linha["id"], "login": LOGIN}
    limpar()


# ============================================================================
# O CATÁLOGO — sem entrada no `telas.py` a aba sobe INVISÍVEL
# ============================================================================
def teste_a_aba_tem_entrada_no_catalogo():
    """🚨 Lição dele de 03/11: *"ESTÁ NO AR NÃO É 200"*. A tela da CAR subiu sem
    registro, ficou fora do menu e não dava nem 403."""
    t = registro_telas.por_codigo("CFG_15.1")
    assert t["titulo"] == "Permissão dos painéis"
    assert t["rota"] == "/config/permissao-paineis"
    assert t["grupo"] == "Configuração"
    # 🔵 Quem concede painel é ele.
    assert t["permissao"] == "owner"
    # ⚠️ É aba do `/config`, como as outras quatorze.
    assert t["aba_de"] == "CFG_0.1"


def teste_a_aba_nao_pode_conceder_a_si_mesma():
    """🚨 A trava mais importante do desenho: a `CFG_15.1` concede o grupo
    "Painéis", e ela é do grupo "Configuração". Ninguém se concede a própria
    chave -- nem concede os canais do WhatsApp por descuido."""
    concediveis = permissao_paineis.codigos_concediveis()
    assert "CFG_15.1" not in concediveis
    assert "CFG_1.1" not in concediveis
    assert "CFG_0.1" not in concediveis


def teste_o_que_e_concedivel_sai_do_REGISTRO_e_nao_de_lista_escrita_a_mao():
    """⚠️ Painel novo entra sozinho. É o que o Financeiro vai precisar quando
    ele der as colunas -- sem tocar o `permissao_paineis.py`."""
    do_registro = {t["codigo"] for t in registro_telas.ativas()
                   if registro_telas.grupo_da(t) == "Painéis"}
    assert permissao_paineis.codigos_concediveis() == do_registro
    # E hoje são exatamente as três que existem.
    assert do_registro == os_paineis()


def teste_a_aba_de_dentro_tem_o_titulo_DA_ABA_e_nao_o_do_registro():
    """🚨 Ele antecipou isto: *"como notará que o pós venda ja possui abas"*.
    No registro, `PNL_1.2` e `PNL_1.3` se chamam as DUAS "Pós-venda" -- o nome
    que as distingue mora no banco (`painel_aba.titulo`). Sem ele, a grade teria
    duas colunas iguais e marcar uma seria chute."""
    por_codigo = {t["codigo"]: t for t in permissao_paineis.concediveis()}
    assert por_codigo["PNL_1.2"]["titulo"] == por_codigo["PNL_1.3"]["titulo"]
    assert por_codigo["PNL_1.2"]["aba_titulo"] == "Treinamentos"
    assert por_codigo["PNL_1.3"]["aba_titulo"] == "Pós-venda"
    # ⚠️ E a hierarquia vem como DADO, para a tela recuar a coluna.
    assert por_codigo["PNL_1.2"]["aba_de"] is None
    assert por_codigo["PNL_1.3"]["aba_de"] == "PNL_1.2"


# ============================================================================
# A REGRA — a concessão vence o `owner` da tela
# ============================================================================
class TestARegra:
    """🚨 Sem a linha da concessão no `pode_acessar`, todo este bloco fica
    vermelho -- e era o estado do sistema até 06/11."""

    def teste_sem_concessao_a_tela_de_painel_e_recusada(self):
        u = {"permissoes": ["atendimento"]}
        for codigo in sorted(os_paineis()):
            assert registro_telas.pode_acessar(u, codigo) is False

    def teste_com_concessao_a_mesma_tela_e_aceita(self):
        u = {"permissoes": ["atendimento"], "telas_concedidas": ["PNL_1.3"]}
        assert registro_telas.pode_acessar(u, "PNL_1.3") is True

    def teste_a_concessao_nao_vaza_para_as_outras(self):
        """⚠️ Ter a aba de dentro NÃO dá a principal. É o caso dele: *"a Erika,
        apenas a aba 3"*."""
        u = {"permissoes": ["atendimento"], "telas_concedidas": ["PNL_1.3"]}
        assert registro_telas.pode_acessar(u, "PNL_1.2") is False
        assert registro_telas.pode_acessar(u, "PNL_1.1") is False
        assert registro_telas.pode_acessar(u, "CFG_1.1") is False
        assert registro_telas.pode_acessar(u, "CFG_15.1") is False

    def teste_a_tela_continua_owner_no_registro(self):
        """🚨 A concessão é EXCEÇÃO NOMEADA, não rebaixamento. Se um dia alguém
        "resolver" isto trocando a permissão da tela, esta trava fica vermelha --
        e a diferença é enorme: `equipe` abriria o painel para todo admin de uma
        vez, sem ninguém marcar nada."""
        for codigo in sorted(os_paineis()):
            assert registro_telas.por_codigo(codigo)["permissao"] == "owner"

    def teste_o_menu_do_usuario_passa_a_trazer_a_tela_concedida(self):
        """⚠️ `do_usuario` monta a resposta À MÃO, e é ela que o menu e a guarda
        de rota do front leem. Regra que vale em `pode_acessar` e não chega aqui
        é tela invisível com permissão -- o defeito de 27/08."""
        u = {"permissoes": ["atendimento"], "telas_concedidas": ["PNL_1.3"]}
        vistas = {t["codigo"] for t in registro_telas.do_usuario(u)}
        assert "PNL_1.3" in vistas
        assert "PNL_1.2" not in vistas
        # ⚠️ E `aba_de` continua vindo: é o que o menu usa para saber que esta
        # tela é aba de outra -- e, desde 06/11, para desenhar o item dela
        # quando a mãe NÃO veio (a porta trancada).
        aba = [t for t in registro_telas.do_usuario(u) if t["codigo"] == "PNL_1.3"]
        assert aba and aba[0]["aba_de"] == "PNL_1.2"


# ============================================================================
# O MOTOR — gravar, revogar, e as recusas de regra
# ============================================================================
class TestDefinir:
    def teste_concede_e_revoga(self, pessoa):
        assert permissao_paineis.do_atendente(pessoa["id"]) == set()
        permissao_paineis.definir(pessoa["id"], ["PNL_1.2", "PNL_1.3"])
        assert permissao_paineis.do_atendente(pessoa["id"]) == {"PNL_1.2",
                                                               "PNL_1.3"}
        # 🚨 DESMARCAR REVOGA: a rota recebe o estado completo da linha.
        permissao_paineis.definir(pessoa["id"], ["PNL_1.3"])
        assert permissao_paineis.do_atendente(pessoa["id"]) == {"PNL_1.3"}
        permissao_paineis.definir(pessoa["id"], [])
        assert permissao_paineis.do_atendente(pessoa["id"]) == set()

    def teste_regravar_a_mesma_lista_nao_mexe_em_quem_concedeu_quando(self, pessoa):
        """⚠️ A gravação é por DELTA. Um `DELETE` + `INSERT` inteiro seria mais
        curto e apagaria o único histórico que a tabela guarda."""
        permissao_paineis.definir(pessoa["id"], ["PNL_1.1"], concedida_por=121)
        antes = banco.um(
            "SELECT concedida_em, concedida_por FROM tela_concedida "
            "WHERE atendente_id = %s AND codigo_tela = 'PNL_1.1'",
            (pessoa["id"],),
        )
        permissao_paineis.definir(pessoa["id"], ["PNL_1.1"], concedida_por=None)
        depois = banco.um(
            "SELECT concedida_em, concedida_por FROM tela_concedida "
            "WHERE atendente_id = %s AND codigo_tela = 'PNL_1.1'",
            (pessoa["id"],),
        )
        assert depois["concedida_em"] == antes["concedida_em"]
        assert depois["concedida_por"] == antes["concedida_por"] == 121

    def teste_uma_linha_por_pessoa_e_tela(self, pessoa):
        """🚨 Sem a UNIQUE, conceder duas vezes daria duas linhas e revogar
        apagaria uma só: a pessoa continuaria vendo o painel e a tela diria
        "não concedido". Tela que mente é `M12`."""
        permissao_paineis.definir(pessoa["id"], ["PNL_1.1"])
        permissao_paineis.definir(pessoa["id"], ["PNL_1.1"])
        n = banco.um(
            "SELECT count(*) n FROM tela_concedida WHERE atendente_id = %s",
            (pessoa["id"],),
        )["n"]
        assert n == 1

    def teste_codigo_fora_dos_paineis_e_recusado(self, pessoa):
        """🚨 Recusa de REGRA, e por isso estoura em vez de ignorar: ignorar
        gravaria com 200 e mostraria outra coisa na releitura."""
        for fora in ("CFG_1.1", "CFG_15.1", "ATD_1.1", "inventado"):
            with pytest.raises(permissao_paineis.TelaNaoConcedivel):
                permissao_paineis.definir(pessoa["id"], [fora])
        # ⚠️ E NADA foi gravado no caminho -- a recusa é antes da escrita.
        assert permissao_paineis.do_atendente(pessoa["id"]) == set()

    def teste_um_codigo_bom_no_meio_de_um_ruim_nao_grava_nada(self, pessoa):
        """⚠️ Tudo ou nada. Gravar o que deu e calar sobre o resto deixaria a
        tela mostrando uma linha que ninguém pediu."""
        with pytest.raises(permissao_paineis.TelaNaoConcedivel):
            permissao_paineis.definir(pessoa["id"], ["PNL_1.1", "CFG_1.1"])
        assert permissao_paineis.do_atendente(pessoa["id"]) == set()

    def teste_o_owner_nao_recebe_concessao(self):
        """⚠️ Ele já vê tudo pela primeira linha do `pode_acessar`. Linha aqui
        não mudaria nada e a tela diria "concedido" por um motivo falso."""
        owner = banco.um("SELECT id FROM atendente WHERE owner LIMIT 1")
        with pytest.raises(permissao_paineis.TelaNaoConcedivel):
            permissao_paineis.definir(owner["id"], ["PNL_1.1"])

    def teste_conta_inativa_nao_recebe_painel(self, pessoa):
        banco.executar("UPDATE atendente SET ativo = false WHERE id = %s",
                       (pessoa["id"],))
        with pytest.raises(permissao_paineis.TelaNaoConcedivel):
            permissao_paineis.definir(pessoa["id"], ["PNL_1.1"])

    def teste_atendente_que_nao_existe_e_recusado(self):
        with pytest.raises(permissao_paineis.TelaNaoConcedivel):
            permissao_paineis.definir(999_999_999, ["PNL_1.1"])


# ============================================================================
# A GRADE — o que a tela desenha
# ============================================================================
class TestGrade:
    def teste_o_owner_vem_com_tudo_marcado_e_sem_caixa_para_marcar(self):
        """⚠️ Verdade sem gesto inútil: ele vê tudo, e a tela não oferece um
        clique que não faz nada (o precedente é o `ModalAgendar`)."""
        g = permissao_paineis.grade()
        donos = [p for p in g["pessoas"] if p["owner"]]
        assert donos, "nenhum owner ativo na base"
        for d in donos:
            assert set(d["concedidas"]) == os_paineis()
            assert d["editavel"] is False

    def teste_quem_nao_e_owner_nasce_sem_nada_e_editavel(self, pessoa):
        g = permissao_paineis.grade()
        linha = [p for p in g["pessoas"] if p["atendente_id"] == pessoa["id"]]
        assert linha, "a conta de teste não apareceu na grade"
        assert linha[0]["concedidas"] == []
        assert linha[0]["editavel"] is True

    def teste_a_grade_mostra_quem_concedeu(self, pessoa):
        permissao_paineis.definir(pessoa["id"], ["PNL_1.2"], concedida_por=121)
        g = permissao_paineis.grade()
        linha = [p for p in g["pessoas"] if p["atendente_id"] == pessoa["id"]][0]
        assert linha["concedidas"] == ["PNL_1.2"]
        assert linha["detalhe"]["PNL_1.2"]["concedida_por"] == 121
        assert linha["detalhe"]["PNL_1.2"]["concedida_por_nome"]

    def teste_conta_inativa_nao_aparece_na_grade(self, pessoa):
        banco.executar("UPDATE atendente SET ativo = false WHERE id = %s",
                       (pessoa["id"],))
        g = permissao_paineis.grade()
        ids = {p["atendente_id"] for p in g["pessoas"]}
        assert pessoa["id"] not in ids


# ============================================================================
# POR HTTP — a prova forte: 403 antes, 200 depois, sem token novo
# ============================================================================
class TestPelaRota:
    def teste_403_antes_e_200_depois_da_concessao(self, cliente, pessoa):
        """🚨 ESTE É O TESTE QUE PROVA A ENTREGA. O mesmo token, a mesma
        pessoa, o mesmo processo: só a linha em `tela_concedida` muda.

        ⚠️ E prova também que a concessão NÃO está no token: se estivesse, só
        valeria no próximo login dela -- e o token do MoviZap vale até a virada
        do dia. Permissão que demora um dia para entrar (ou para sair) não é
        permissão.
        """
        token = auth.criar_token(pessoa["login"])
        cab = {"Authorization": f"Bearer {token}"}

        antes = cliente.get("/api/paineis/aba/PNL_1.3", headers=cab)
        assert antes.status_code == 403

        permissao_paineis.definir(pessoa["id"], ["PNL_1.3"], concedida_por=121)

        depois = cliente.get("/api/paineis/aba/PNL_1.3", headers=cab)
        assert depois.status_code == 200
        assert depois.json()["aba"]

        # 🚨 E A OUTRA ABA CONTINUA FECHADA no mesmo instante: é o *"apenas a
        # aba 3"* dele.
        assert cliente.get("/api/paineis/aba/PNL_1.2",
                           headers=cab).status_code == 403

        # ⚠️ Revogar fecha na mesma hora, pelo mesmo token.
        permissao_paineis.definir(pessoa["id"], [])
        assert cliente.get("/api/paineis/aba/PNL_1.3",
                           headers=cab).status_code == 403

    def teste_a_aba_de_permissao_e_so_do_owner(self, cliente, pessoa):
        """⚠️ Inclusive para quem já recebeu painel: ter painel não é poder
        conceder painel."""
        permissao_paineis.definir(pessoa["id"], ["PNL_1.1"])
        token = auth.criar_token(pessoa["login"])
        cab = {"Authorization": f"Bearer {token}"}
        assert cliente.get("/api/config/permissao-paineis",
                           headers=cab).status_code == 403
        assert cliente.put("/api/config/permissao-paineis", headers=cab,
                           json={"atendente_id": pessoa["id"],
                                 "codigos": []}).status_code == 403

    def teste_sem_login_e_401_e_nao_403(self, cliente):
        """⚠️ 401 é "quem é você", 403 é "você não pode". Trocar os dois faz
        sessão expirada parecer falta de permissão."""
        assert cliente.get("/api/config/permissao-paineis").status_code == 401

    def teste_a_rota_grava_e_devolve_a_grade_relida(self, cliente, token_owner,
                                                    pessoa):
        cab = {"Authorization": f"Bearer {token_owner}"}
        r = cliente.put("/api/config/permissao-paineis", headers=cab,
                        json={"atendente_id": pessoa["id"],
                              "codigos": ["PNL_1.1", "PNL_1.3"]})
        assert r.status_code == 200
        corpo = r.json()
        # 🚨 A resposta é a GRADE, e não um `ok`: a tela redesenha do que o
        # banco respondeu, nunca do que ela achava que tinha mandado.
        assert "telas" in corpo and "pessoas" in corpo
        linha = [p for p in corpo["pessoas"]
                 if p["atendente_id"] == pessoa["id"]][0]
        assert set(linha["concedidas"]) == {"PNL_1.1", "PNL_1.3"}
        # ⚠️ E quem concedeu é quem está logado, não um valor fixo.
        assert linha["detalhe"]["PNL_1.1"]["concedida_por_nome"]

    def teste_codigo_de_fora_e_422_de_regra(self, cliente, token_owner, pessoa):
        """🚨 422 com o motivo escrito. 500 esconderia a regra; 200 calado
        mentiria."""
        cab = {"Authorization": f"Bearer {token_owner}"}
        r = cliente.put("/api/config/permissao-paineis", headers=cab,
                        json={"atendente_id": pessoa["id"],
                              "codigos": ["CFG_1.1"]})
        assert r.status_code == 422
        assert "painéis" in r.json()["detail"]
        assert permissao_paineis.do_atendente(pessoa["id"]) == set()

    def teste_a_identidade_carrega_a_concessao_a_cada_requisicao(self, pessoa):
        """⚠️ `buscar_usuario` é quem monta a identidade. Campo que não entra
        nesta montagem à mão fica no banco e nunca chega à porta -- é a mesma
        advertência do `do_usuario`."""
        u = auth.buscar_usuario(pessoa["login"])
        assert u["telas_concedidas"] == []
        permissao_paineis.definir(pessoa["id"], ["PNL_1.2"])
        u2 = auth.buscar_usuario(pessoa["login"])
        assert u2["telas_concedidas"] == ["PNL_1.2"]
