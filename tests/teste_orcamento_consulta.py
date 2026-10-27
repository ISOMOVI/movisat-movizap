"""Consulta dos orçamentos: o grid da aba `ORC_1.1` (26/10).

🚨 ESCREVE EM TABELAS DE PRODUÇÃO (`orcamento`, `orcamento_item`,
`agendamento`, `conversa`, `contato`, `cliente`, `atendente`) e apaga tudo no
fim. Marcas deste teste: números de orçamento na faixa **99.90x.xxx**, login
`zz_teste_orc_`, cliente `Zz Teste Orcamento`.

🚨 **O TESTE NÃO CHAMA `orcamento.emitir()`, E ISSO É DE PROPÓSITO.** Emitir
GASTA o número do `config.orcamento_proximo_numero`, que é a numeração de
documento de verdade -- um teste que rodasse dez vezes empurraria a
numeração dele dez números para frente, e buraco em documento numerado é
exatamente o que o `orcamento.py` existe para evitar. Então o teste INSERE as
linhas direto, com número numa faixa que nenhum documento real alcança.

O que estes testes guardam:
  · a SOMA é do filtro inteiro, não da página -- senão o rodapé mentiria a
    cada virada (foi o defeito que a aba de Ligações já teve de evitar);
  · orçamento de DUAS linhas não vira duas linhas no grid;
  · o nome do técnico vem de `harmonit_tecnico_nome`, e só cai no
    `contato.nome` quando não há vínculo -- em conversa de técnico o
    `contato.nome` é o TELEFONE CRU, e o grid mostraria "+5518…" nos três
    orçamentos reais se lesse a coluna errada;
  · o dinheiro vem ESCRITO do backend ("1.234,56"), nunca dividido por 100 na
    tela;
  · número e OS são busca EXATA, e letra é recusada com frase (não com 500);
  · `ate` é INCLUSIVO -- quem filtra "até dia 21" espera o dia 21 inteiro;
  · as duas rotas existem, exigem token e devolvem o que a tela espera.
"""
import sys
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import pytest

sys.path.insert(0, "/home/claude/movizap_painel")
pytest.importorskip("psycopg")

from fastapi.testclient import TestClient  # noqa: E402

from movizap import auth, banco, main, orcamento, orcamento_consulta  # noqa: E402
from movizap.config import settings  # noqa: E402
from movizap.operacao import DadoInvalido  # noqa: E402

ENV = Path("/home/claude/movizap_painel/.env")
pytestmark = pytest.mark.skipif(
    not ENV.exists() or "MOVIZAP_DB_SENHA" not in ENV.read_text(encoding="utf-8"),
    reason="banco nao configurado no .env")

LOGIN = "zz_teste_orc_"
CLIENTE = "Zz Teste Orcamento"
# 🚨 Faixa reservada ao teste. O próximo número real era 4 em 26/10; nenhum
# documento chega aqui, e o `numero` é UNIQUE -- se um dia chegar, o teste
# estoura em vez de sobrescrever documento.
N1, N2, N3 = 99_901_001, 99_901_002, 99_901_003
FAIXA = (N1, N2, N3)
# O telefone cru, que é o que `contato.nome` guarda em conversa de técnico.
TEL_CRU = "+5518977778888"
NOME_HARMONIT = "Zz Tecnico Do Harmonit"


def limpar():
    banco.executar("""DELETE FROM agendamento WHERE orcamento_id IN
                       (SELECT id FROM orcamento WHERE numero = ANY(%s))""", (list(FAIXA),))
    banco.executar("""DELETE FROM orcamento_item WHERE orcamento_id IN
                       (SELECT id FROM orcamento WHERE numero = ANY(%s))""", (list(FAIXA),))
    banco.executar("DELETE FROM orcamento WHERE numero = ANY(%s)", (list(FAIXA),))
    # O agendamento e o orçamento apontam para a conversa e o contato: saem antes.
    banco.executar("""DELETE FROM agendamento WHERE tecnico_contato_id IN
                       (SELECT id FROM contato WHERE nome IN (%s, %s))""",
                   (TEL_CRU, CLIENTE + " sem vinculo"))
    banco.executar("""DELETE FROM conversa WHERE contato_id IN
                       (SELECT id FROM contato WHERE nome IN (%s, %s))""",
                   (TEL_CRU, CLIENTE + " sem vinculo"))
    banco.executar("DELETE FROM contato WHERE nome IN (%s, %s)",
                   (TEL_CRU, CLIENTE + " sem vinculo"))
    banco.executar("DELETE FROM cliente WHERE nome LIKE %s", (CLIENTE + "%",))
    banco.executar("DELETE FROM atendente WHERE login LIKE %s", (LOGIN + "%",))


def _contato(nome: str, harmonit_nome: str | None) -> int:
    with banco.cursor() as cur:
        cur.execute("""INSERT INTO contato (nome, relacao, origem, ativo,
                                            harmonit_tecnico_nome)
                       VALUES (%s, 'tecnico', 'movizap', true, %s) RETURNING id""",
                    (nome, harmonit_nome))
        return cur.fetchone()["id"]


def _conversa(contato_id: int) -> int:
    with banco.cursor() as cur:
        # ⚠️ `canal_id` é NOT NULL sem default: pega um canal que já existe em
        # vez de criar canal de mentira (canal é configuração, não dado).
        cur.execute("SELECT id FROM canal ORDER BY id LIMIT 1")
        canal = cur.fetchone()
        if not canal:
            pytest.skip("a base nao tem canal para pendurar a conversa de teste")
        cur.execute("""INSERT INTO conversa (canal_id, contato_id, telefone_e164, estado)
                       VALUES (%s, %s, %s, 'nova') RETURNING id""",
                    (canal["id"], contato_id, TEL_CRU))
        return cur.fetchone()["id"]


def _orcamento(*, numero, conversa_id, contato_id, atendente_id, quando,
               ordens, itens) -> int:
    """Insere direto. Ver o aviso do topo: emitir gastaria numeração real."""
    linhas, total = orcamento.calcular(itens)
    with banco.cursor() as cur:
        cur.execute("""INSERT INTO orcamento (numero, tecnico_contato_id, conversa_id,
                                              total_centavos, criado_por, criado_em,
                                              ordens_os, midia_id)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, NULL) RETURNING id""",
                    (numero, contato_id, conversa_id, total, atendente_id,
                     quando, ordens))
        orcamento_id = cur.fetchone()["id"]
        for linha in linhas:
            cur.execute("""INSERT INTO orcamento_item
                               (orcamento_id, ordem, servico, preco_unit_centavos,
                                quantidade, unidade, valor_centavos)
                           VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                        (orcamento_id, linha["ordem"], linha["servico"],
                         linha["preco_unit_centavos"], linha["quantidade"],
                         linha["unidade"], linha["valor_centavos"]))
    return orcamento_id


@pytest.fixture(scope="module", autouse=True)
def base():
    banco.abrir()
    limpar()

    from movizap import operacao
    pessoa = operacao.criar_atendente("Zz Orcamento Um", LOGIN + "1",
                                      LOGIN + "1@teste.invalid")

    com_vinculo = _contato(TEL_CRU, NOME_HARMONIT)
    sem_vinculo = _contato(CLIENTE + " sem vinculo", None)
    conversa_id = _conversa(com_vinculo)

    agora = datetime.now(timezone.utc)
    km = {"servico": "KM DESLOCAMENTO", "unidade": "km",
          "preco_unit_centavos": 100, "quantidade": Decimal("77")}
    pagamento = {"servico": "PAGAMENTO DE TECNICO", "unidade": "un",
                 "preco_unit_centavos": 18000, "quantidade": Decimal("1")}

    ids = {
        # DUAS linhas: o grid tem de continuar com UMA linha por orçamento.
        "duas_linhas": _orcamento(
            numero=N1, conversa_id=conversa_id, contato_id=com_vinculo,
            atendente_id=pessoa["id"], quando=agora - timedelta(days=5),
            ordens=[], itens=[km, pagamento]),
        "com_os": _orcamento(
            numero=N2, conversa_id=conversa_id, contato_id=com_vinculo,
            atendente_id=pessoa["id"], quando=agora - timedelta(days=1),
            ordens=[99_990_001, 99_990_002], itens=[km]),
        # Sem vínculo no Harmonit: o nome tem de cair no `contato.nome`.
        "sem_vinculo": _orcamento(
            numero=N3, conversa_id=conversa_id, contato_id=sem_vinculo,
            atendente_id=pessoa["id"], quando=agora, ordens=[], itens=[pagamento]),
    }

    with banco.cursor() as cur:
        cur.execute("""INSERT INTO agendamento
                           (conversa_id, tecnico_contato_id, cliente_harmonit_id,
                            cliente_nome, inicio, estado, criado_por, orcamento_id)
                       VALUES (%s, %s, %s, %s, %s, 'confirmado', %s, %s)
                       RETURNING id""",
                    (conversa_id, com_vinculo, "zz-0001", CLIENTE + " Cliente",
                     agora + timedelta(days=1), pessoa["id"], ids["com_os"]))
        agendamento_id = cur.fetchone()["id"]

    yield {"pessoa": pessoa, "ids": ids, "conversa_id": conversa_id,
           "com_vinculo": com_vinculo, "sem_vinculo": sem_vinculo,
           "agendamento_id": agendamento_id}

    # 🚨 REABRE ANTES DE LIMPAR, e não é zelo à toa: o `TestClient` roda o
    # lifespan do `main.app`, cujo encerramento chama `banco.fechar()` -- então
    # ao chegar aqui o pool pode estar fechado e a limpeza estouraria, deixando
    # orçamento de teste na base de produção. `abrir()` é idempotente.
    #
    # ⚠️ E NÃO SE CHAMA `fechar()` AQUI, de propósito: é o que os três outros
    # testes com `TestClient` fazem (`teste_rotas_formularios`, `teste_paineis`,
    # `teste_agendamento`). Fechar faria o próximo arquivo da suíte achar o
    # banco fechado, dependendo da ordem de coleta.
    banco.abrir()
    limpar()


def meus(**filtros) -> list[dict]:
    """Só os orçamentos deste teste: a base tem orçamentos reais."""
    itens = orcamento_consulta.consultar(por_pagina=200, **filtros)["itens"]
    return [i for i in itens if i["numero"] in FAIXA]


# ---------------------------------------------------------------------------
# [1] A FORMA DO GRID
# ---------------------------------------------------------------------------
class TestFormaDoGrid:
    def test_orcamento_de_duas_linhas_e_UMA_linha_no_grid(self, base):
        """🚨 O risco do JOIN. Com JOIN em `orcamento_item`, um orçamento de
        duas linhas viraria dois no grid -- e a contagem do cabeçalho
        dobraria. Por isso os itens vêm por subconsulta `json_agg`."""
        achados = [i for i in meus() if i["numero"] == N1]
        assert len(achados) == 1
        assert len(achados[0]["itens"]) == 2

    def test_os_itens_vem_na_ordem_gravada(self, base):
        o = [i for i in meus() if i["numero"] == N1][0]
        assert [i["ordem"] for i in o["itens"]] == [1, 2]
        assert o["itens"][0]["servico"] == "KM DESLOCAMENTO"

    def test_a_ordem_e_do_numero_maior_para_o_menor(self, base):
        numeros = [i["numero"] for i in meus()]
        assert numeros == sorted(numeros, reverse=True)

    def test_sem_os_vem_lista_vazia_e_nao_None(self, base):
        """A tela escreve "sem OS" a partir de lista vazia. `None` a faria
        quebrar no `.length`, e um `v-if` a mais esconderia a diferença entre
        "não tem OS" e "não consultei"."""
        o = [i for i in meus() if i["numero"] == N1][0]
        assert o["ordens_os"] == []

    def test_sem_agendamento_vem_None_e_nao_erro(self, base):
        """1 de 3 dos orçamentos reais tem agendamento: "sem" é o estado
        comum, não defeito."""
        assert [i for i in meus() if i["numero"] == N1][0]["agendamento"] is None

    def test_o_agendamento_vem_com_estado_e_cliente(self, base):
        o = [i for i in meus() if i["numero"] == N2][0]
        assert o["agendamento"]["id"] == base["agendamento_id"]
        assert o["agendamento"]["estado"] == "confirmado"
        assert o["agendamento"]["cliente_nome"] == CLIENTE + " Cliente"


# ---------------------------------------------------------------------------
# [2] O NOME DO TÉCNICO -- o defeito que a medição de 26/10 pegou
# ---------------------------------------------------------------------------
class TestNomeDoTecnico:
    def test_o_nome_vem_do_vinculo_do_harmonit(self, base):
        """🚨 Em conversa de técnico o `contato.nome` é o TELEFONE CRU. Os
        três orçamentos reais sairiam como "+5518998116168" se o grid lesse a
        coluna óbvia -- medido em 26/10, antes de escrever a consulta."""
        o = [i for i in meus() if i["numero"] == N1][0]
        assert o["tecnico"] == NOME_HARMONIT
        assert o["tecnico"] != TEL_CRU

    def test_sem_vinculo_cai_no_nome_do_contato(self, base):
        """⚠️ Degrada, não some: sem vínculo o grid mostra o que tem. Mostrar
        vazio seria esconder o orçamento de quem procura por ele."""
        o = [i for i in meus() if i["numero"] == N3][0]
        assert o["tecnico"] == CLIENTE + " sem vinculo"

    def test_o_tecnico_aparece_no_seletor_com_a_contagem(self, base):
        por_id = {t["contato_id"]: t for t in orcamento_consulta.tecnicos()}
        assert por_id[base["com_vinculo"]]["tecnico"] == NOME_HARMONIT
        assert por_id[base["com_vinculo"]]["orcamentos"] >= 2

    def test_quem_emitiu_aparece_no_seletor(self, base):
        por_id = {a["atendente_id"]: a for a in orcamento_consulta.atendentes()}
        assert por_id[base["pessoa"]["id"]]["orcamentos"] == 3


# ---------------------------------------------------------------------------
# [3] DINHEIRO -- escrito no backend, nunca dividido na tela
# ---------------------------------------------------------------------------
class TestDinheiro:
    def test_o_total_vem_escrito_em_portugues(self, base):
        o = [i for i in meus() if i["numero"] == N1][0]
        # 77 km x R$ 1,00 + 1 un x R$ 180,00 = R$ 257,00
        assert o["total_centavos"] == 25700
        assert o["total"] == "257,00"

    def test_a_linha_tambem_vem_escrita(self, base):
        o = [i for i in meus() if i["numero"] == N1][0]
        km = o["itens"][0]
        assert km["valor"] == "77,00"
        assert km["preco_unit"] == "1,00"

    def test_a_quantidade_e_a_MESMA_frase_do_PDF(self, base):
        """🚨 "77 km", não "77.000 km". O texto sai de
        `orcamento._quantidade_texto`, o mesmo que o PDF imprime -- se o grid
        formatasse por conta, grid e papel divergiriam."""
        o = [i for i in meus() if i["numero"] == N1][0]
        assert o["itens"][0]["quantidade_texto"] == "77 km"
        assert o["itens"][1]["quantidade_texto"] == "1 un"

    def test_a_soma_do_filtro_bate_com_os_itens(self, base):
        r = orcamento_consulta.consultar(por_pagina=200,
                                         tecnico_contato_id=base["com_vinculo"])
        soma = sum(i["total_centavos"] for i in r["itens"])
        assert r["soma_centavos"] == soma
        assert r["soma"] == orcamento.reais(soma)


# ---------------------------------------------------------------------------
# [4] PAGINAÇÃO -- a soma é do FILTRO, não da página
# ---------------------------------------------------------------------------
class TestPaginacao:
    def test_a_soma_nao_muda_ao_virar_a_pagina(self, base):
        """🚨 O defeito que a aba de Ligações já teve de evitar: total de
        página faz o rodapé mentir a cada clique."""
        filtro = {"tecnico_contato_id": base["com_vinculo"]}
        inteiro = orcamento_consulta.consultar(por_pagina=200, **filtro)
        p1 = orcamento_consulta.consultar(pagina=1, por_pagina=1, **filtro)
        p2 = orcamento_consulta.consultar(pagina=2, por_pagina=1, **filtro)
        assert p1["soma_centavos"] == p2["soma_centavos"] == inteiro["soma_centavos"]
        assert p1["total"] == p2["total"] == inteiro["total"]
        assert len(p1["itens"]) == 1
        assert p1["itens"][0]["numero"] != p2["itens"][0]["numero"]

    def test_paginas_nunca_e_zero(self, base):
        """Filtro que não acha nada tem 1 página, não 0: a tela divide por
        ela para desenhar a paginação."""
        r = orcamento_consulta.consultar(numero=99_909_999)
        assert r["total"] == 0
        assert r["paginas"] == 1

    def test_o_teto_por_pagina_e_da_consulta(self, base):
        """`?por_pagina=999999` não devolve a base inteira."""
        r = orcamento_consulta.consultar(por_pagina=999_999)
        assert r["por_pagina"] == orcamento_consulta.POR_PAGINA_MAX


# ---------------------------------------------------------------------------
# [5] FILTROS
# ---------------------------------------------------------------------------
class TestFiltros:
    def test_numero_e_busca_EXATA(self, base):
        """🚨 Número de orçamento é DOCUMENTO. Busca parcial faria o "1" casar
        com o 10 e o 21 -- útil num telefone, errado num documento."""
        assert [i["numero"] for i in meus(numero=N2)] == [N2]

    def test_os_procura_DENTRO_do_array(self, base):
        assert [i["numero"] for i in meus(os_numero=99_990_002)] == [N2]
        assert meus(os_numero=99_999_999) == []

    def test_letra_no_numero_e_recusada_com_frase(self, base):
        """⚠️ `DadoInvalido`, não 500: quem digitou errado precisa ler o que
        fazer."""
        for campo in ("numero", "os_numero"):
            with pytest.raises(DadoInvalido):
                orcamento_consulta.consultar(**{campo: "abc"})

    def test_ate_e_INCLUSIVO(self, base):
        """Quem filtra "até hoje" espera o dia de hoje inteiro, não até a
        meia-noite dele. Mesma régua da aba de Ligações."""
        hoje = datetime.now(timezone.utc).date().isoformat()
        assert N3 in [i["numero"] for i in meus(ate=hoje)]

    def test_de_corta_o_que_e_mais_velho(self, base):
        ontem = (datetime.now(timezone.utc) - timedelta(days=2)).date().isoformat()
        numeros = [i["numero"] for i in meus(de=ontem)]
        assert N1 not in numeros      # 5 dias atrás
        assert N2 in numeros          # 1 dia atrás

    def test_com_pdf_separa_quem_tem_de_quem_nao_tem(self, base):
        """Os três do teste nascem sem PDF (não emitimos), então o filtro
        positivo não traz nenhum deles e o negativo traz os três."""
        assert meus(com_pdf=True) == []
        assert len(meus(com_pdf=False)) == 3

    def test_sem_filtro_nenhum_a_consulta_e_valida(self, base):
        """O WHERE começa em TRUE: consulta sem filtro não vira SQL quebrado."""
        assert orcamento_consulta.consultar()["total"] >= 3


# ---------------------------------------------------------------------------
# [6] AS ROTAS -- lição de 22/10: prova ao vivo não substitui teste HTTP
# ---------------------------------------------------------------------------
@pytest.fixture
def cliente():
    with TestClient(main.app) as c:
        yield c


@pytest.fixture
def token():
    """O login do `.env` é o do OWNER. ⚠️ A recusa de quem não tem a tela se
    prova no registro (`teste_telas.py`), sem criar conta de mentira."""
    return auth.criar_token(settings.admin_login)


class TestRotas:
    def test_a_lista_exige_token(self, cliente):
        assert cliente.get("/api/orcamentos").status_code in (401, 403)

    def test_os_filtros_exigem_token(self, cliente):
        assert cliente.get("/api/orcamentos/filtros").status_code in (401, 403)

    def test_a_lista_devolve_o_que_a_tela_espera(self, cliente, token, base):
        r = cliente.get("/api/orcamentos?por_pagina=200",
                        headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200
        corpo = r.json()
        for chave in ("itens", "total", "pagina", "por_pagina", "paginas",
                      "soma", "soma_centavos"):
            assert chave in corpo, f"a tela lê {chave!r} e a rota não manda"
        meu = [i for i in corpo["itens"] if i["numero"] == N1]
        assert meu and meu[0]["tecnico"] == NOME_HARMONIT

    def test_a_rota_recusa_letra_com_400_e_nao_500(self, cliente, token):
        r = cliente.get("/api/orcamentos?numero=abc",
                        headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 400
        assert "inteiro" in r.json()["detail"]

    def test_os_filtros_trazem_os_dois_seletores(self, cliente, token, base):
        r = cliente.get("/api/orcamentos/filtros",
                        headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200
        assert "tecnicos" in r.json() and "atendentes" in r.json()

    def test_nao_existe_rota_de_escrita_nesta_aba(self, base):
        """🚨 A aba é de CONSULTA, e isto se prova pelas rotas, não pela tela:
        nenhum POST, PUT, PATCH ou DELETE em `/api/orcamentos`. Orçamento
        emitido não muda de conteúdo."""
        from fastapi.routing import APIRoute
        escrita = []
        for r in main.app.routes:
            if not isinstance(r, APIRoute):
                continue
            if r.path.startswith("/api/orcamentos"):
                escrita += [m for m in r.methods
                            if m in {"POST", "PUT", "PATCH", "DELETE"}]
        assert escrita == [], f"a aba de consulta ganhou escrita: {escrita}"


# ---------------------------------------------------------------------------
# [7] O QUE A ABA NÃO FAZ -- e a tela tem de DIZER (M12)
# ---------------------------------------------------------------------------
TELA = Path("/home/claude/movizap_painel/frontend/src/telas/Orcamentos.vue")


class TestATelaNaoMente:
    def test_a_tela_diz_que_e_so_consulta(self):
        """🚨 Precedente do card do `PNL_1.1`: oferecer o gesto sem gravar é
        pior que não ter o gesto -- e não ter o gesto sem explicar faz a aba
        parecer incompleta. A frase é parte da entrega."""
        fonte = TELA.read_text(encoding="utf-8")
        assert "só de consulta" in fonte
        assert "não se edita" in fonte

    def test_a_tela_diz_onde_se_emite(self):
        """Dizer "não dá aqui" sem dizer onde dá é meio recado."""
        fonte = TELA.read_text(encoding="utf-8")
        assert "conversa do técnico" in fonte

    def test_a_tela_nao_divide_dinheiro_por_cem(self):
        """🚨 O valor chega escrito do backend. Um `/ 100` nesta tela seria o
        segundo lugar do projeto a escrever dinheiro -- com outro
        arredondamento que o PDF."""
        fonte = TELA.read_text(encoding="utf-8")
        assert "/ 100" not in fonte
        assert "total_centavos" not in fonte.split("<template>")[1]
