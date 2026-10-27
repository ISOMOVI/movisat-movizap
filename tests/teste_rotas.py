"""A calculadora de KM do técnico: distância, memória da origem e cache (26/10).

🚨 **NENHUM TESTE AQUI CHAMA A API DE VERDADE.** A consulta é **dublada**, como
`teste_cep.py` faz com o ViaCEP — e aqui há um motivo a mais que lá: a Routes
API **cobra por consulta**. Suíte que gasta dinheiro é suíte que alguém
desliga.

🚨 ESCREVE EM TABELAS DE PRODUÇÃO (`tecnico_origem`, `rota_cache`, `contato`) e
apaga tudo no fim. Marca deste teste: contato `Zz Teste Rota`, e pares de
endereço com a palavra `zzteste`.

O que estes testes guardam:
  · as QUATRO respostas distinguíveis — achou · não localizou · não deu para
    perguntar · **sem chave**. Juntar as duas últimas faria a tela dizer
    "endereço errado" sobre um endereço certo que não deu para conferir;
  · **"falta a rua" é 400 mesmo sem chave** — a ordem das checagens, que a
    prova ao vivo pegou errada;
  · **só resultado BOM entra no cache** — falha nunca, que é o medo escrito no
    `cep.py` ("cache que guarda erro para sempre");
  · o cache **respeita o prazo** e a segunda consulta **não paga de novo**;
  · a normalização faz "Rua X, 123" e "rua x 123" serem a MESMA consulta;
  · a memória da origem **sobrescreve** ("se for alterado, permanece
    alterado") e é gravada **mesmo quando o cálculo falha**;
  · ida e volta é o padrão, e o arredondamento bate com os orçamentos reais.
"""
import sys
from decimal import Decimal
from pathlib import Path

import pytest

sys.path.insert(0, "/home/claude/movizap_painel")
pytest.importorskip("psycopg")

from fastapi.testclient import TestClient  # noqa: E402

from movizap import auth, banco, main, rotas  # noqa: E402
from movizap.config import settings  # noqa: E402

ENV = Path("/home/claude/movizap_painel/.env")
pytestmark = pytest.mark.skipif(
    not ENV.exists() or "MOVIZAP_DB_SENHA" not in ENV.read_text(encoding="utf-8"),
    reason="banco nao configurado no .env")

CONTATO = "Zz Teste Rota"

ORIGEM = {"cep": "19013180", "logradouro": "Rua Zzteste Origem", "numero": "1",
          "bairro": "Centro", "cidade": "Presidente Prudente", "uf": "SP",
          "complemento": ""}
DESTINO = {"cep": "19020000", "logradouro": "Rua Zzteste Destino", "numero": "2",
           "bairro": "Centro", "cidade": "Presidente Prudente", "uf": "SP",
           "complemento": ""}


def limpar():
    banco.executar(
        "DELETE FROM tecnico_origem WHERE tecnico_contato_id IN "
        "  (SELECT id FROM contato WHERE nome = %s)", (CONTATO,))
    banco.executar(
        "DELETE FROM conversa WHERE contato_id IN "
        "  (SELECT id FROM contato WHERE nome = %s)", (CONTATO,))
    banco.executar("DELETE FROM contato WHERE nome = %s", (CONTATO,))
    banco.executar("DELETE FROM rota_cache WHERE origem_norm LIKE %s",
                   ("%zzteste%",))


@pytest.fixture(scope="module", autouse=True)
def base():
    banco.abrir()
    limpar()
    with banco.cursor() as cur:
        cur.execute("INSERT INTO contato (nome, relacao, origem, ativo) "
                    "VALUES (%s, 'tecnico', 'movizap', true) RETURNING id",
                    (CONTATO,))
        contato_id = cur.fetchone()["id"]
        # 🚨 Uma CONVERSA de técnico: é por ela que o servidor descobre de quem
        # é a origem -- o navegador não manda o id do contato, de propósito.
        cur.execute("SELECT id FROM canal ORDER BY id LIMIT 1")
        canal = cur.fetchone()
        if not canal:
            pytest.skip("a base nao tem canal para pendurar a conversa de teste")
        cur.execute("INSERT INTO conversa (canal_id, contato_id, telefone_e164, "
                    "    estado) VALUES (%s, %s, %s, 'nova') RETURNING id",
                    (canal["id"], contato_id, "+5518977779999"))
        conversa_id = cur.fetchone()["id"]
    yield {"contato_id": contato_id, "conversa_id": conversa_id}
    # Reabre: o `TestClient` roda o lifespan, cujo fim fecha o pool.
    banco.abrir()
    limpar()


@pytest.fixture
def com_chave(monkeypatch):
    """Finge que a chave existe. ⚠️ Valor de mentira: nada sai para a internet
    porque `_perguntar` é dublado em todo teste que chega lá."""
    monkeypatch.setattr(settings, "rotas_chave", "chave-de-teste", raising=False)


@pytest.fixture(autouse=True)
def cache_limpo():
    """⚠️ REABRE O BANCO NAS DUAS PONTAS, e não é zelo à toa: o `TestClient`
    roda o lifespan do `main.app`, cujo encerramento chama `banco.fechar()`.
    Sem isto, a limpeza DEPOIS de um teste HTTP estoura -- e deixaria linha de
    teste na tabela de produção. `abrir()` é idempotente."""
    banco.abrir()
    banco.executar("DELETE FROM rota_cache WHERE origem_norm LIKE %s", ("%zzteste%",))
    yield
    banco.abrir()
    banco.executar("DELETE FROM rota_cache WHERE origem_norm LIKE %s", ("%zzteste%",))


# ---------------------------------------------------------------------------
# [1] AS QUATRO RESPOSTAS
# ---------------------------------------------------------------------------
class TestAsQuatroRespostas:
    def test_sem_chave_nao_ha_calculo_e_ele_DIZ_isso(self, base):
        """🚨 A quarta resposta, que o `cep.py` não tem: o ViaCEP é público,
        este serviço não. Sem chave, a tela cai no campo manual **dizendo por
        quê** — e não mostra um botão que falha."""
        assert rotas.disponivel() is False
        with pytest.raises(rotas.RotaIndisponivel) as e:
            rotas.distancia(ORIGEM, DESTINO)
        assert "não está configurado" in str(e.value)

    def test_falta_rua_e_400_MESMO_sem_chave(self, base):
        """🚨 A ORDEM DAS CHECAGENS, que a prova ao vivo pegou errada: "falta a
        rua" é sabível sem chave nenhuma. Dizer "não deu para perguntar" ali
        manda o operador procurar defeito no serviço quando o problema é o
        campo em branco na frente dele."""
        magro = {**ORIGEM, "logradouro": "", "cidade": ""}
        with pytest.raises(rotas.EnderecoInsuficiente) as e:
            rotas.distancia(magro, DESTINO)
        assert "rua e cidade" in str(e.value)

    def test_achou(self, base, com_chave, monkeypatch):
        monkeypatch.setattr(rotas, "_perguntar", lambda o, d: (38_500, 2700))
        achado = rotas.distancia(ORIGEM, DESTINO)
        assert achado["km"] == 38.5
        assert achado["segundos"] == 2700
        assert achado["do_cache"] is False

    def test_nao_localizou_e_None_e_NAO_zero(self, base, com_chave, monkeypatch):
        """🚨 `None`, nunca 0.0. Zero é um número que vai para orçamento: "não
        achei a rota" virando "0 km" cobraria deslocamento nenhum por um
        serviço que tem deslocamento."""
        monkeypatch.setattr(rotas, "_perguntar", lambda o, d: None)
        assert rotas.distancia(ORIGEM, DESTINO) is None

    def test_nao_deu_para_perguntar(self, base, com_chave, monkeypatch):
        def caiu(o, d):
            raise rotas.RotaIndisponivel("o serviço não respondeu")
        monkeypatch.setattr(rotas, "_perguntar", caiu)
        with pytest.raises(rotas.RotaIndisponivel):
            rotas.distancia(ORIGEM, DESTINO)

    def test_mesmo_endereco_da_zero_sem_gastar_consulta(self, base, com_chave,
                                                        monkeypatch):
        def nao_deveria(o, d):
            raise AssertionError("gastou consulta para origem == destino")
        monkeypatch.setattr(rotas, "_perguntar", nao_deveria)
        assert rotas.distancia(ORIGEM, dict(ORIGEM))["km"] == 0.0


# ---------------------------------------------------------------------------
# [2] O CACHE — e o princípio do `cep.py` que ele contraria
# ---------------------------------------------------------------------------
class TestCache:
    def test_a_segunda_consulta_NAO_paga_de_novo(self, base, com_chave, monkeypatch):
        vezes = []
        monkeypatch.setattr(rotas, "_perguntar",
                            lambda o, d: (vezes.append(1), (10_000, 600))[1])
        primeira = rotas.distancia(ORIGEM, DESTINO)
        segunda = rotas.distancia(ORIGEM, DESTINO)
        assert len(vezes) == 1, "pagou duas vezes pela mesma rota"
        assert primeira["do_cache"] is False
        assert segunda["do_cache"] is True
        assert segunda["km"] == primeira["km"]

    def test_a_grafia_nao_cria_consulta_nova(self, base, com_chave, monkeypatch):
        """"Rua X, 123" e "rua x, 123" são a MESMA consulta. Pagar duas vezes
        por isso é desperdício que ninguém vê na fatura, porque cada linha
        parece legítima."""
        vezes = []
        monkeypatch.setattr(rotas, "_perguntar",
                            lambda o, d: (vezes.append(1), (10_000, 600))[1])
        rotas.distancia(ORIGEM, DESTINO)
        outra_grafia = {**ORIGEM, "logradouro": "rua zzteste origem"}
        rotas.distancia(outra_grafia, DESTINO)
        assert len(vezes) == 1

    def test_FALHA_NUNCA_ENTRA_no_cache(self, base, com_chave, monkeypatch):
        """🚨 É o medo escrito no `cep.py` — *"cache que sobrevive a deploy é
        cache que guarda erro para sempre"*. A tabela existe apesar dele, e é
        esta condição que responde à objeção."""
        def caiu(o, d):
            raise rotas.RotaIndisponivel("caiu")
        monkeypatch.setattr(rotas, "_perguntar", caiu)
        with pytest.raises(rotas.RotaIndisponivel):
            rotas.distancia(ORIGEM, DESTINO)
        assert banco.um("SELECT count(*) AS n FROM rota_cache "
                        " WHERE origem_norm LIKE %s", ("%zzteste%",))["n"] == 0

    def test_nao_localizou_tambem_nao_entra(self, base, com_chave, monkeypatch):
        monkeypatch.setattr(rotas, "_perguntar", lambda o, d: None)
        assert rotas.distancia(ORIGEM, DESTINO) is None
        assert banco.um("SELECT count(*) AS n FROM rota_cache "
                        " WHERE origem_norm LIKE %s", ("%zzteste%",))["n"] == 0

    def test_o_cache_tem_PRAZO_e_o_vencido_nao_serve(self, base, com_chave,
                                                     monkeypatch):
        """Rota muda (obra, estrada nova), e cache sem prazo é afirmação sem
        data — a régua da migração 076, que guardou a situação COM a hora."""
        vezes = []
        monkeypatch.setattr(rotas, "_perguntar",
                            lambda o, d: (vezes.append(1), (10_000, 600))[1])
        rotas.distancia(ORIGEM, DESTINO)
        banco.executar(
            "UPDATE rota_cache SET consultado_em = now() - make_interval(days => %s) "
            " WHERE origem_norm LIKE %s", (rotas.DIAS_DE_CACHE + 1, "%zzteste%"))
        rotas.distancia(ORIGEM, DESTINO)
        assert len(vezes) == 2, "o cache vencido continuou valendo"

    def test_a_data_da_leitura_vem_junto(self, base, com_chave, monkeypatch):
        monkeypatch.setattr(rotas, "_perguntar", lambda o, d: (10_000, 600))
        rotas.distancia(ORIGEM, DESTINO)
        do_cache = rotas.distancia(ORIGEM, DESTINO)
        assert do_cache["consultado_em"] is not None


# ---------------------------------------------------------------------------
# [3] A MEMÓRIA DA ORIGEM
# ---------------------------------------------------------------------------
class TestMemoriaDaOrigem:
    def test_na_primeira_vez_nao_ha_nada(self, base):
        banco.executar("DELETE FROM tecnico_origem WHERE tecnico_contato_id = %s",
                       (base["contato_id"],))
        assert rotas.origem_do_tecnico(base["contato_id"]) is None

    def test_grava_e_le(self, base):
        rotas.lembrar_origem(base["contato_id"], ORIGEM)
        lido = rotas.origem_do_tecnico(base["contato_id"])
        assert lido["logradouro"] == ORIGEM["logradouro"]
        assert lido["cidade"] == ORIGEM["cidade"]

    def test_SOBRESCREVE_e_nao_acumula(self, base):
        """🔵 *"se for alterado, permanece alterado"* — um sobrescrever, não um
        histórico. Daí a PK ser o técnico."""
        rotas.lembrar_origem(base["contato_id"], ORIGEM)
        rotas.lembrar_origem(base["contato_id"],
                             {**ORIGEM, "logradouro": "Rua Zzteste Outra"})
        assert banco.um("SELECT count(*) AS n FROM tecnico_origem "
                        " WHERE tecnico_contato_id = %s",
                        (base["contato_id"],))["n"] == 1
        assert rotas.origem_do_tecnico(
            base["contato_id"])["logradouro"] == "Rua Zzteste Outra"

    def test_campo_vazio_vira_nulo_e_nao_string_vazia(self, base):
        """`''` e `NULL` diferentes no banco viram duas formas do mesmo nada, e
        a primeira consulta que comparar com `IS NULL` mente."""
        rotas.lembrar_origem(base["contato_id"], {**ORIGEM, "complemento": "   "})
        assert rotas.origem_do_tecnico(base["contato_id"])["complemento"] is None


# ---------------------------------------------------------------------------
# [4] IDA E VOLTA
# ---------------------------------------------------------------------------
class TestIdaEVolta:
    def test_ida_e_volta_e_o_PADRAO(self):
        """🔵 Decidido por ele em 26/10, e casa com os três orçamentos
        emitidos (77, 77 e 15 km): o técnico volta."""
        assert rotas.arredondar(38.5) == Decimal("77.0")

    def test_so_ida_quando_pedido(self):
        assert rotas.arredondar(38.5, ida_e_volta=False) == Decimal("38.5")

    def test_arredonda_meio_pra_cima_como_o_dinheiro(self):
        """Duas regras de arredondamento no mesmo documento é uma delas
        errada: o `orcamento.centavos` já é meio pra cima."""
        assert rotas.arredondar(7.77, ida_e_volta=False) == Decimal("7.8")
        assert rotas.arredondar(7.74, ida_e_volta=False) == Decimal("7.7")


# ---------------------------------------------------------------------------
# [5] AS ROTAS HTTP — lição de 22/10: prova ao vivo não substitui teste
# ---------------------------------------------------------------------------
@pytest.fixture
def cliente():
    with TestClient(main.app) as c:
        yield c


@pytest.fixture
def cab():
    return {"Authorization": f"Bearer {auth.criar_token(settings.admin_login)}"}


class TestRotasHttp:
    def test_as_duas_exigem_token(self, cliente):
        assert cliente.get("/api/rotas/origem").status_code in (401, 403)
        assert cliente.post("/api/rotas/km", json={
            "origem": ORIGEM, "destino": DESTINO}).status_code in (401, 403)

    def test_a_memoria_diz_se_o_calculo_existe(self, cliente, cab, base):
        r = cliente.get("/api/rotas/origem", headers=cab)
        assert r.status_code == 200
        assert "disponivel" in r.json(), "a tela lê isto para não mentir"

    def test_sem_chave_a_rota_devolve_503_com_motivo(self, cliente, cab, base):
        r = cliente.post("/api/rotas/km", headers=cab,
                         json={"origem": ORIGEM, "destino": DESTINO})
        assert r.status_code == 503
        assert "configurado" in r.json()["detail"]

    def test_endereco_magro_e_400(self, cliente, cab, base):
        r = cliente.post("/api/rotas/km", headers=cab, json={
            "origem": {**ORIGEM, "logradouro": "", "cidade": ""},
            "destino": DESTINO})
        assert r.status_code == 400

    def test_a_MEMORIA_e_gravada_mesmo_com_o_calculo_FALHANDO(self, cliente, cab,
                                                              base):
        """🚨 O achado que muda o valor da entrega de hoje: a origem é o que o
        atendente DIGITOU, e guardá-la não depende de a API responder. É o que
        faz a metade *"fica salvo para proximas"* funcionar **sem chave**."""
        banco.executar("DELETE FROM tecnico_origem WHERE tecnico_contato_id = %s",
                       (base["contato_id"],))
        r = cliente.post("/api/rotas/km", headers=cab, json={
            "conversa_id": base["conversa_id"],
            "origem": ORIGEM, "destino": DESTINO})
        assert r.status_code == 503          # o cálculo não aconteceu
        lido = cliente.get(f"/api/rotas/origem?conversa_id={base['conversa_id']}",
                           headers=cab).json()
        assert lido["origem"]["logradouro"] == ORIGEM["logradouro"]
        # 🚨 E prova a outra metade: quem achou o técnico foi o SERVIDOR, pela
        # conversa -- o corpo da requisição nem menciona o contato.
        assert rotas.origem_do_tecnico(base["contato_id"])["logradouro"]             == ORIGEM["logradouro"]

    def test_com_chave_a_rota_devolve_ida_e_total(self, cliente, cab, base,
                                                  com_chave, monkeypatch):
        monkeypatch.setattr(rotas, "_perguntar", lambda o, d: (38_500, 2700))
        corpo = cliente.post("/api/rotas/km", headers=cab, json={
            "origem": ORIGEM, "destino": DESTINO}).json()
        # As duas contas à vista: ninguém cobra errado por distração.
        assert corpo["km_ida"] == 38.5
        assert corpo["km"] == 77.0
        assert corpo["ida_e_volta"] is True

    def test_nao_localizou_vem_com_MOTIVO_e_km_nulo(self, cliente, cab, base,
                                                    com_chave, monkeypatch):
        monkeypatch.setattr(rotas, "_perguntar", lambda o, d: None)
        corpo = cliente.post("/api/rotas/km", headers=cab, json={
            "origem": ORIGEM, "destino": DESTINO}).json()
        assert corpo["km"] is None
        assert "não achei" in corpo["motivo"]


    def test_conversa_que_NAO_e_de_tecnico_nao_grava_memoria_de_ninguem(
            self, cliente, cab, base):
        """⚠️ Conversa de cliente, ou sem contato, não tem origem a lembrar --
        e inventar uma gravaria a origem errada em nome de alguém."""
        antes = banco.um("SELECT count(*) AS n FROM tecnico_origem")["n"]
        cliente.post("/api/rotas/km", headers=cab,
                     json={"conversa_id": 0, "origem": ORIGEM, "destino": DESTINO})
        assert banco.um("SELECT count(*) AS n FROM tecnico_origem")["n"] == antes

    def test_sem_conversa_o_calculo_ainda_funciona(self, cliente, cab, base,
                                                   com_chave, monkeypatch):
        """O cálculo não depende de haver técnico: só a memória depende."""
        monkeypatch.setattr(rotas, "_perguntar", lambda o, d: (10_000, 600))
        corpo = cliente.post("/api/rotas/km", headers=cab,
                             json={"origem": ORIGEM, "destino": DESTINO}).json()
        assert corpo["km"] == 20.0
