"""Consulta das ligações: o grid da aba e o modal da ficha (Bloco 3, 15/10).

🚨 Escreve em `atendente`, `agente_ligacao`, `ligacao`, `ligacao_gravacao`,
`cliente`, `contato` e `contato_telefone`, tabelas de PRODUÇÃO, e grava
arquivos em pasta TEMPORÁRIA. Ramais `99xxx`, login `zz_teste_cons_` e
cliente `Zz Teste Consulta`; tudo apagado no fim.

O que estes testes guardam:
  · ligação com DUAS gravações não vira duas linhas no grid (o MicroSIP
    reinicia o arquivo no meio da chamada, e o agente manda os dois pedaços);
  · número em DUAS empresas também não duplica linha -- vem uma lista;
  · número SEM cadastro vem com lista vazia, que a tela traduz por "sem
    cadastro" (e não por "não consultei");
  · os totais são do FILTRO INTEIRO, não da página;
  · busca por pedaço de número funciona ("9811");
  · o modal da ficha separa por sentido e diz a COBERTURA (quantos ramais têm
    agente), senão a tela afirma "nenhuma ligação" onde a verdade é "aquele PC
    não manda";
  · o CSV abre no Excel brasileiro e não executa fórmula.
"""
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

sys.path.insert(0, "/home/claude/movizap_painel")
pytest.importorskip("psycopg")

from movizap import (banco, ligacoes, ligacoes_consulta, operacao,  # noqa: E402
                     relatorio_csv)
from movizap.operacao import DadoInvalido  # noqa: E402

ENV = Path("/home/claude/movizap_painel/.env")
pytestmark = pytest.mark.skipif(
    not ENV.exists() or "MOVIZAP_DB_SENHA" not in ENV.read_text(encoding="utf-8"),
    reason="banco nao configurado no .env")

LOGIN = "zz_teste_cons_"
CLIENTE = "Zz Teste Consulta"
RAMAL = "99500"
# Números só deste teste, para não casar com ligação real da base.
NUM_COM_CADASTRO = "+5518977770001"
NUM_DUAS_EMPRESAS = "+5518977770002"
NUM_SEM_CADASTRO = "+5518977770003"
# O grupo de teste se identifica pelo JID, nunca por "telefone nulo":
# limpar por telefone nulo apagaria grupo de verdade.
JID_TESTE = "zz-teste-consulta@g.us"

_mp3 = [0]


def mp3() -> bytes:
    _mp3[0] += 1
    return b"\xff\xe2\x48\xc4" + _mp3[0].to_bytes(8, "big") + b"\x00" * 300


def limpar():
    banco.executar("""DELETE FROM ligacao_gravacao WHERE ligacao_id IN
                       (SELECT id FROM ligacao WHERE ramal LIKE '995' || '%%')""")
    banco.executar("DELETE FROM ligacao WHERE ramal LIKE '995' || '%%'")
    banco.executar("DELETE FROM agente_ligacao WHERE ramal LIKE '995' || '%%'")
    # O rastro de exportação aponta para o atendente: sai antes dele.
    banco.executar("""DELETE FROM ligacao_exportacao WHERE atendente_id IN
                       (SELECT id FROM atendente WHERE login LIKE %s)""", (LOGIN + "%",))
    banco.executar("DELETE FROM atendente WHERE login LIKE %s", (LOGIN + "%",))
    banco.executar("""DELETE FROM contato_telefone WHERE contato_id IN
                       (SELECT ct.id FROM contato ct JOIN cliente cl ON cl.id = ct.cliente_id
                         WHERE cl.nome LIKE %s)""", (CLIENTE + "%",))
    banco.executar("""DELETE FROM contato WHERE cliente_id IN
                       (SELECT id FROM cliente WHERE nome LIKE %s)""", (CLIENTE + "%",))
    banco.executar("DELETE FROM cliente WHERE nome LIKE %s", (CLIENTE + "%",))
    banco.executar("DELETE FROM conversa WHERE telefone_e164 = ANY(%s)",
                   ([NUM_COM_CADASTRO, NUM_DUAS_EMPRESAS, NUM_SEM_CADASTRO],))
    banco.executar("DELETE FROM conversa WHERE grupo_jid = %s", (JID_TESTE,))


def cadastro(nome: str, contato: str, e164: str) -> int:
    with banco.cursor() as cur:
        cur.execute("""INSERT INTO cliente (nome, ativo, origem)
                       VALUES (%s, true, 'movizap') RETURNING id""", (nome,))
        cliente_id = cur.fetchone()["id"]
        cur.execute("""INSERT INTO contato (cliente_id, nome, origem, ativo)
                       VALUES (%s, %s, 'movizap', true) RETURNING id""",
                    (cliente_id, contato))
        contato_id = cur.fetchone()["id"]
        cur.execute("""INSERT INTO contato_telefone (contato_id, e164, bruto, principal)
                       VALUES (%s, %s, %s, true)""", (contato_id, e164, e164))
    return cliente_id


@pytest.fixture(scope="module", autouse=True)
def base():
    banco.abrir()
    limpar()
    pasta = tempfile.TemporaryDirectory()
    raiz_antiga = ligacoes.RAIZ
    ligacoes.RAIZ = Path(pasta.name)

    pessoa = operacao.criar_atendente("Zz Consulta Um", LOGIN + "1",
                                      LOGIN + "1@teste.invalid")
    chave = ligacoes.gerar_chave(pessoa["id"], RAMAL)
    agente = ligacoes.agente_da_chave(chave)

    cliente_a = cadastro(CLIENTE + " A", "Contato A", NUM_COM_CADASTRO)
    cadastro(CLIENTE + " B", "Contato B", NUM_DUAS_EMPRESAS)
    cliente_c = cadastro(CLIENTE + " C", "Contato C", NUM_DUAS_EMPRESAS)

    agora = datetime.now(timezone.utc)

    def liga(call_id, sentido, numero, dias_atras, duracao=30, gravacoes=0):
        inicio = agora - timedelta(days=dias_atras)
        dados = {"call_id": call_id, "sentido": sentido, "numero": numero,
                 "inicio": inicio.isoformat(), "duracao_s": duracao,
                 "situacao": "Chamada encerrada"}
        r = ligacoes.registrar(agente, dados, mp3() if gravacoes else None, "a.mp3", "PC-CONS")
        for _ in range(max(0, gravacoes - 1)):
            # Segunda gravação da MESMA ligação: é o caso do MicroSIP que
            # reinicia o arquivo no meio da chamada.
            ligacoes.registrar(agente, dados, mp3(), "b.mp3", "PC-CONS")
        return r["ligacao_id"]

    ids = {
        "hoje_feita_2grav": liga("c-hoje-1", "feita", NUM_COM_CADASTRO, 0, 95, gravacoes=2),
        "hoje_recebida": liga("c-hoje-2", "recebida", NUM_DUAS_EMPRESAS, 0, 60),
        "tres_dias_perdida": liga("c-3d", "perdida", NUM_SEM_CADASTRO, 3, 0),
        "vinte_dias_feita": liga("c-20d", "feita", NUM_COM_CADASTRO, 20, 10),
    }
    yield {"agente": agente, "pessoa": pessoa, "ids": ids,
           "cliente_a": cliente_a, "cliente_c": cliente_c, "pasta": Path(pasta.name)}

    ligacoes.RAIZ = raiz_antiga
    limpar()
    pasta.cleanup()
    banco.fechar()


def meus(**filtros) -> dict:
    """Só as ligações deste teste: a base tem ligações reais."""
    return ligacoes_consulta.consultar(ramal=RAMAL, **filtros)


# ------------------------------------------------------------------- o grid

def test_o_grid_traz_as_quatro_e_os_totais_por_sentido():
    r = meus()
    assert r["total"] == 4
    assert r["por_sentido"] == {"feita": 2, "recebida": 1, "perdida": 1}
    # Mais nova primeiro: é a ordem que a aba mostra.
    assert r["itens"][0]["inicio"] >= r["itens"][-1]["inicio"]


def test_duas_gravacoes_na_mesma_ligacao_nao_viram_duas_linhas(base):
    r = meus()
    linha = [i for i in r["itens"] if i["id"] == base["ids"]["hoje_feita_2grav"]]
    assert len(linha) == 1, "a ligação apareceu duplicada no grid"
    assert len(linha[0]["gravacoes"]) == 2
    assert all(g["bytes"] > 0 for g in linha[0]["gravacoes"])


def test_numero_em_duas_empresas_vem_como_lista_e_nao_duplica_linha(base):
    r = meus()
    linha = [i for i in r["itens"] if i["id"] == base["ids"]["hoje_recebida"]]
    assert len(linha) == 1
    nomes = sorted(c["nome"] for c in linha[0]["clientes"])
    assert nomes == [CLIENTE + " B", CLIENTE + " C"]


def test_numero_sem_cadastro_vem_com_lista_vazia(base):
    r = meus()
    linha = [i for i in r["itens"] if i["id"] == base["ids"]["tres_dias_perdida"]][0]
    assert linha["clientes"] == [], "sem cadastro é lista vazia, nunca None"
    assert linha["gravacoes"] == []


def test_filtro_por_sentido_data_e_atendente(base):
    assert meus(sentido="perdida")["total"] == 1
    assert meus(atendente_id=base["pessoa"]["id"])["total"] == 4
    hoje = datetime.now(timezone.utc).date()
    assert meus(de=hoje - timedelta(days=5))["total"] == 3, "20 dias atrás ficou de fora"
    # `ate` é inclusivo: filtrar até hoje tem de pegar as de hoje.
    assert meus(ate=hoje)["total"] == 4


def test_filtro_por_sentido_invalido_recusa():
    with pytest.raises(DadoInvalido):
        meus(sentido="atendida")


def test_busca_por_numero_inteiro_e_por_pedaco():
    assert meus(numero=NUM_SEM_CADASTRO)["total"] == 1
    assert meus(numero="18977770003")["total"] == 1, "sem o + também acha"
    assert meus(numero="7777000")["total"] == 4, "pedaço de número acha todas"
    with pytest.raises(DadoInvalido):
        meus(numero="abc")


def test_filtro_por_cliente(base):
    assert meus(cliente_id=base["cliente_a"])["total"] == 2
    assert meus(cliente_id=base["cliente_c"])["total"] == 1


def test_filtro_por_ter_gravacao():
    assert meus(com_gravacao=True)["total"] == 1
    assert meus(com_gravacao=False)["total"] == 3


def test_os_totais_sao_do_filtro_inteiro_nao_da_pagina():
    """Rodapé que conta só a página mente a cada virada de página."""
    r = meus(pagina=1, por_pagina=2)
    assert len(r["itens"]) == 2 and r["total"] == 4 and r["paginas"] == 2
    assert r["por_sentido"]["feita"] == 2
    segunda = meus(pagina=2, por_pagina=2)
    assert len(segunda["itens"]) == 2
    assert {i["id"] for i in r["itens"]} & {i["id"] for i in segunda["itens"]} == set()


# ------------------------------------------------------- o modal da ficha

def test_o_modal_da_ficha_separa_por_sentido_e_respeita_os_dias():
    r = ligacoes_consulta.do_telefone(NUM_COM_CADASTRO, dias=7)
    assert r["total"] == 1, "a de 20 dias atrás não entra em 7 dias"
    assert len(r["por_sentido"]["feita"]) == 1
    assert r["por_sentido"]["recebida"] == [] and r["por_sentido"]["perdida"] == []
    assert len(r["por_sentido"]["feita"][0]["gravacoes"]) == 2
    de_30 = ligacoes_consulta.do_telefone(NUM_COM_CADASTRO, dias=30)
    assert de_30["total"] == 2


def test_o_modal_diz_a_cobertura():
    """Sem isto a tela afirma 'nenhuma ligação' onde a verdade é 'aquele PC
    não tem agente'."""
    r = ligacoes_consulta.do_telefone(NUM_SEM_CADASTRO, dias=7)
    assert r["cobertura"]["com_agente"] >= 1
    assert r["cobertura"]["atendentes"] >= r["cobertura"]["com_agente"]


def test_o_modal_recusa_numero_invalido():
    with pytest.raises(DadoInvalido):
        ligacoes_consulta.do_telefone("nao-e-numero")


# ------------------------------------------------------------ gravação e CSV

def test_a_gravacao_devolve_caminho_que_existe_no_disco(base):
    r = meus(com_gravacao=True)
    gid = r["itens"][0]["gravacoes"][0]["id"]
    g = ligacoes_consulta.gravacao(gid)
    assert g and Path(g["caminho"]).exists()
    assert g["ligacao_id"] == base["ids"]["hoje_feita_2grav"]
    assert ligacoes_consulta.gravacao(-1) is None


def test_agentes_mostra_quem_tem_e_quem_nao_tem():
    linhas = ligacoes_consulta.agentes()
    meu = [a for a in linhas if a["ramal"] == RAMAL]
    assert len(meu) == 1 and meu[0]["agente_id"] and meu[0]["ligacoes"] == 4
    assert any(a["agente_id"] is None for a in linhas), "quem não tem agente também aparece"


def test_o_csv_abre_no_excel_brasileiro_e_nao_executa_formula():
    linhas = [{"quem": "=cmd|' /c calc'!A0", "n": 1}, {"quem": "Normal", "n": 2}]
    dados = relatorio_csv.gerar([("quem", "Quem"), ("n", "N")], linhas)
    assert dados.startswith(b"\xef\xbb\xbf"), "sem BOM o Excel estraga o acento"
    texto = dados.decode("utf-8-sig")
    assert texto.splitlines()[0] == "Quem;N", "o Excel pt-BR separa por ponto e vírgula"
    assert "\r\n" in texto
    assert "'=cmd" in texto, "fórmula tem de virar texto"


def test_o_csv_das_ligacoes_sai_com_as_linhas_do_filtro():
    linhas = ligacoes_consulta.para_csv(ramal=RAMAL, sentido="feita")
    assert len(linhas) == 2
    assert all(l["ramal"] == RAMAL for l in linhas)


# ----------------------------------------------------------------- a rota

class TestARotaDaFicha:
    """`GET /api/conversas/{id}/ligacoes` — o que o modal do botão Ligações usa.

    🚨 É `ATD_1.2` (a permissão da conversa), não a da aba: quem atende vê as
    ligações do número que está atendendo.
    """

    @pytest.fixture(autouse=True)
    def cena(self, base):
        from fastapi.testclient import TestClient

        from movizap import auth, main
        # Um atendente para a classe inteira: a fixture roda por teste, e
        # `ux_atendente_login` (em lower(login)) recusaria o segundo.
        banco.executar(
            """INSERT INTO atendente (nome, login, email, senha_hash, perfil, ativo)
               VALUES ('Zz Consulta Rota', %s, %s, 'x', 'atendimento', true)
               ON CONFLICT DO NOTHING""",
            (LOGIN + "rota", LOGIN + "rota@teste.invalid"))
        self.pessoa = banco.um("SELECT id FROM atendente WHERE login = %s",
                               (LOGIN + "rota",))
        canal = banco.um("SELECT id FROM canal ORDER BY id LIMIT 1")
        # Limpa ANTES: `ux_conversa_aberta` recusa duas conversas abertas do
        # mesmo número, e uma execução interrompida deixa a anterior de pé.
        banco.executar("DELETE FROM conversa WHERE telefone_e164 = %s", (NUM_COM_CADASTRO,))
        banco.executar("DELETE FROM conversa WHERE grupo_jid = %s", (JID_TESTE,))
        self.conversa = banco.um(
            """INSERT INTO conversa (canal_id, telefone_e164, estado)
               VALUES (%s, %s, 'nova') RETURNING id""",
            (canal["id"], NUM_COM_CADASTRO))["id"]
        self.sem_numero = banco.um(
            """INSERT INTO conversa (canal_id, grupo_jid, estado, tipo)
               VALUES (%s, %s, 'nova', 'grupo') RETURNING id""",
            (canal["id"], JID_TESTE))["id"]
        self.c = TestClient(main.app)
        self.c.headers.update(
            {"Authorization": f"Bearer {auth.criar_token(LOGIN + 'rota')}"})
        yield
        banco.executar("DELETE FROM conversa WHERE id IN (%s, %s)",
                       (self.conversa, self.sem_numero))

    def test_traz_as_ligacoes_do_numero_da_conversa(self):
        r = self.c.get(f"/api/conversas/{self.conversa}/ligacoes")
        assert r.status_code == 200, r.text
        corpo = r.json()
        assert corpo["dias"] == 7 and corpo["total"] == 1
        assert len(corpo["por_sentido"]["feita"]) == 1
        assert corpo["cobertura"]["com_agente"] >= 1

    def test_o_parametro_dias_manda_no_recorte(self):
        assert self.c.get(f"/api/conversas/{self.conversa}/ligacoes?dias=30").json()["total"] == 2

    def test_conversa_sem_numero_responde_vazio_sem_erro(self):
        """Grupo não tem ficha; a rota não pode explodir se chamada do mesmo
        jeito."""
        r = self.c.get(f"/api/conversas/{self.sem_numero}/ligacoes")
        assert r.status_code == 200 and r.json()["total"] == 0
        assert r.json()["telefone_e164"] is None

    def test_conversa_que_nao_existe_da_404(self):
        assert self.c.get("/api/conversas/999999999/ligacoes").status_code == 404

    def test_sem_token_nao_entra(self):
        from fastapi.testclient import TestClient

        from movizap import main
        assert TestClient(main.app).get(
            f"/api/conversas/{self.conversa}/ligacoes").status_code == 401


class TestAsRotasDaAba:
    """As quatro rotas de `LIG_1.1` — a aba Ligações.

    🚨 A aba nasce com permissão que NENHUM perfil lista: só o owner entra.
    Estes testes provam as duas pontas — o owner entra, o atendimento não.
    """

    @pytest.fixture(autouse=True)
    def cena(self, base):
        from fastapi.testclient import TestClient

        from movizap import auth, main
        for login, perfil in ((LOGIN + "owner", "owner"), (LOGIN + "atd", "atendimento"),
                              (LOGIN + "cad", "cadastro")):
            banco.executar(
                """INSERT INTO atendente (nome, login, email, senha_hash, perfil, ativo)
                   VALUES (%s, %s, %s, 'x', %s, true) ON CONFLICT DO NOTHING""",
                (f"Zz Consulta {perfil}", login, login + "@teste.invalid", perfil))
        self.app = main.app
        self.owner = TestClient(main.app)
        self.owner.headers.update(
            {"Authorization": f"Bearer {auth.criar_token(LOGIN + 'owner')}"})
        self.atendente = TestClient(main.app)
        self.atendente.headers.update(
            {"Authorization": f"Bearer {auth.criar_token(LOGIN + 'atd')}"})
        self.cadastro = TestClient(main.app)
        self.cadastro.headers.update(
            {"Authorization": f"Bearer {auth.criar_token(LOGIN + 'cad')}"})
        yield

    def test_o_grid_responde_a_quem_atende_e_nega_o_resto(self):
        """🔵 15/10, horas depois de a aba nascer: *"pode exibir a aba para
        todos"*. Virou permissão `atendimento` — então quem atende entra, e o
        perfil `cadastro` (que só vê clientes e contatos) continua fora."""
        for cliente in (self.owner, self.atendente):
            r = cliente.get(f"/api/ligacoes?ramal={RAMAL}")
            assert r.status_code == 200, r.text
            assert r.json()["total"] == 4
        # 403, não 404: a aba existe, a pessoa é que não tem.
        assert self.cadastro.get("/api/ligacoes").status_code == 403

    def test_a_cobertura_responde(self):
        r = self.owner.get("/api/ligacoes/agentes")
        assert r.status_code == 200
        assert any(a["ramal"] == RAMAL for a in r.json()["agentes"])
        assert any(a["agente_id"] is None for a in r.json()["agentes"])

    def test_o_csv_sai_com_nome_de_arquivo_e_deixa_rastro(self):
        antes = banco.um("SELECT count(*) n FROM ligacao_exportacao")["n"]
        r = self.owner.get(f"/api/ligacoes/exportar.csv?ramal={RAMAL}")
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("text/csv")
        assert 'filename="ligacoes-' in r.headers["content-disposition"]
        assert r.content.startswith(b"\xef\xbb\xbf")
        assert "Quem" not in r.text and "Quando;Sentido" in r.text
        depois = banco.um("SELECT count(*) n FROM ligacao_exportacao")["n"]
        assert depois == antes + 1, "exportação sem rastro"

    def test_a_gravacao_toca_para_quem_atende_tambem(self, base):
        """O player do modal da ficha é de quem atende: se a gravação exigisse
        a aba, o modal não funcionaria para ninguém além do owner."""
        g = ligacoes_consulta.consultar(ramal=RAMAL, com_gravacao=True)["itens"][0]["gravacoes"][0]
        for cliente in (self.owner, self.atendente):
            r = cliente.get(f"/api/ligacoes/gravacao/{g['id']}")
            assert r.status_code == 200, r.text
            assert r.headers["content-type"] == "audio/mpeg"
            assert r.content[:3] == b"\xff\xe2\x48"[:3]

    def test_gravacao_que_nao_existe_da_404(self):
        assert self.owner.get("/api/ligacoes/gravacao/999999999").status_code == 404

    def test_sem_token_nenhuma_das_rotas_responde(self):
        from fastapi.testclient import TestClient
        anonimo = TestClient(self.app)
        for rota in ("/api/ligacoes", "/api/ligacoes/agentes",
                     "/api/ligacoes/exportar.csv", "/api/ligacoes/gravacao/1"):
            assert anonimo.get(rota).status_code == 401, rota
