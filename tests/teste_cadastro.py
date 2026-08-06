"""Testes da leitura da base cadastral (CAD_1.1 e CAD_1.2).

🚨 O teste que importa aqui é o da busca por telefone. Metodologia §2: "busca
NUNCA por igualdade do que chegou -- sempre pelo normalizado". Se isso quebrar,
o cliente escreve e o sistema responde que ele não é cliente, sem estourar
nada e sem logar nada.

Estes testes leem a base REAL sincronizada do Harmonit. Não escrevem, então
não precisam da própria linha -- mas por isso mesmo não podem depender de um
registro específico existir. Onde é preciso um caso concreto, é a Pastelaria
Velasco (998063), que é a empresa de teste oficial.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, "/home/claude/movizap_painel")
pytest.importorskip("psycopg")

from movizap import banco, cadastro  # noqa: E402

ENV = Path("/home/claude/movizap_painel/.env")
pytestmark = pytest.mark.skipif(
    not ENV.exists() or "MOVIZAP_DB_SENHA" not in ENV.read_text(encoding="utf-8"),
    reason="banco nao configurado no .env")


@pytest.fixture(scope="module", autouse=True)
def pool():
    banco.abrir()
    yield
    banco.fechar()


class TestInterpretarBusca:
    """A tela mostra a interpretação de volta. Quando alguém procura um
    telefone e não acha, a diferença entre "não existe" e "procurei pelo nome"
    é a diferença entre desistir e corrigir a digitação."""

    def test_vazio(self):
        assert cadastro.interpretar_busca("")["tipo"] == "vazio"
        assert cadastro.interpretar_busca(None)["tipo"] == "vazio"

    @pytest.mark.parametrize("termo", [
        "18 99811-6168", "(18) 9811-6168", "5518998116168",
        "+55 18 99811-6168", "18998116168",
    ])
    def test_toda_grafia_de_telefone_e_reconhecida(self, termo):
        r = cadastro.interpretar_busca(termo)
        assert r["tipo"] == "telefone"
        assert r["e164"] == "+5518998116168"

    def test_telefone_traz_as_duas_variantes(self):
        r = cadastro.interpretar_busca("18 99811-6168")
        assert set(r["variantes"]) == {"+5518998116168", "+551898116168"}

    def test_cnpj_alfanumerico_e_documento(self):
        """🚨 O CNPJ alfanumérico já existe na base -- exigir só dígito
        deixaria a Pastelaria Velasco impossível de achar pelo documento."""
        r = cadastro.interpretar_busca("WQ0P6GLD000108")
        assert r["tipo"] == "documento"
        assert r["limpo"] == "WQ0P6GLD000108"

    def test_cpf_com_pontuacao_e_documento(self):
        r = cadastro.interpretar_busca("123.456.789-00")
        assert r["tipo"] == "documento"
        assert r["limpo"] == "12345678900"

    def test_nome_e_nome(self):
        assert cadastro.interpretar_busca("velasco")["tipo"] == "nome"
        assert cadastro.interpretar_busca("Pastelaria")["tipo"] == "nome"


class TestBuscaDeCliente:
    def test_por_nome_acha_a_velasco(self):
        r = cadastro.listar_clientes(busca="velasco")
        assert r["total"] >= 1
        assert any("Velasco" in i["nome"] for i in r["itens"])

    def test_por_nome_fantasia_tambem_acha(self):
        r = cadastro.listar_clientes(busca="Pastelaria Velasco")
        assert r["total"] >= 1

    def test_por_documento_alfanumerico(self):
        r = cadastro.listar_clientes(busca="WQ0P6GLD000108")
        assert r["total"] == 1
        assert "Velasco" in r["itens"][0]["nome"]

    @pytest.mark.parametrize("termo", [
        "18 99811-6168", "(18) 9811-6168", "5518998116168", "18 9811 6168",
    ])
    def test_AS_TRES_GRAFIAS_ACHAM_O_MESMO(self, termo):
        """🚨 O teste que justifica o módulo existir."""
        r = cadastro.listar_clientes(busca=termo)
        assert r["total"] >= 1, f"{termo!r} não achou ninguém"
        assert r["busca"]["e164"] == "+5518998116168"

    def test_grafias_diferentes_dao_o_MESMO_conjunto(self):
        """Não basta cada uma achar alguém: têm que achar os mesmos."""
        a = {i["id"] for i in cadastro.listar_clientes(busca="18 99811-6168")["itens"]}
        b = {i["id"] for i in cadastro.listar_clientes(busca="18 9811-6168")["itens"]}
        c = {i["id"] for i in cadastro.listar_clientes(busca="5518998116168")["itens"]}
        assert a == b == c
        assert a, "as três acharam o mesmo... nada"

    def test_termo_que_nao_existe_devolve_vazio_sem_estourar(self):
        r = cadastro.listar_clientes(busca="zzzzznaoexistezzzzz")
        assert r["total"] == 0
        assert r["itens"] == []

    def test_paginacao_nao_repete_nem_pula(self):
        p1 = cadastro.listar_clientes(pagina=1, por_pagina=25)
        p2 = cadastro.listar_clientes(pagina=2, por_pagina=25)
        ids1 = {i["id"] for i in p1["itens"]}
        ids2 = {i["id"] for i in p2["itens"]}
        assert len(ids1) == 25 and len(ids2) == 25
        assert not (ids1 & ids2), "página 2 repetiu itens da página 1"
        assert p1["total"] == p2["total"]

    def test_por_pagina_tem_teto(self):
        r = cadastro.listar_clientes(por_pagina=9999)
        assert r["por_pagina"] == cadastro.POR_PAGINA_MAX

    def test_apenas_ativos_filtra_de_verdade(self):
        todos = cadastro.listar_clientes()["total"]
        ativos = cadastro.listar_clientes(apenas_ativos=True)["total"]
        assert 0 < ativos < todos, "o filtro não mudou nada -- não está filtrando"

    def test_tipo_pessoa_tem_descricao_inclusive_o_zero(self):
        r = cadastro.listar_clientes(por_pagina=200)
        for item in r["itens"]:
            assert item["tipo_pessoa_desc"], f"{item['nome']} sem descrição de tipo"


class TestDetalhe:
    def _velasco(self):
        r = cadastro.listar_clientes(busca="WQ0P6GLD000108")
        return r["itens"][0]["id"]

    def test_cliente_traz_contatos_com_telefones(self):
        c = cadastro.cliente(self._velasco())
        assert c["nome"] == "Velasco Leite Pastelaria ME"
        assert c["contatos"], "cliente sem contato"
        telefones = c["contatos"][0]["telefones"]
        assert {t["e164"] for t in telefones} == {"+5518998116168", "+556837148157"}

    def test_o_principal_vem_primeiro(self):
        c = cadastro.cliente(self._velasco())
        assert c["contatos"][0]["telefones"][0]["principal"] is True

    def test_o_bruto_esta_junto_do_e164(self):
        """O bruto é o que prova que o e164 não foi inventado."""
        c = cadastro.cliente(self._velasco())
        for t in c["contatos"][0]["telefones"]:
            assert t["bruto"], "telefone sem o bruto guardado"

    def test_cliente_inexistente_devolve_none(self):
        assert cadastro.cliente(999999999) is None

    def test_contato_inexistente_devolve_none(self):
        assert cadastro.contato(999999999) is None

    def test_contato_traz_papeis_mesmo_vazios(self):
        cid = cadastro.cliente(self._velasco())["contatos"][0]["id"]
        c = cadastro.contato(cid)
        assert isinstance(c["papeis"], list)
        assert c["cliente_nome"] == "Velasco Leite Pastelaria ME"


class TestPorTelefone:
    """O que o webhook vai chamar no passo 4."""

    def test_acha_por_qualquer_grafia(self):
        a = cadastro.por_telefone("5518998116168")
        b = cadastro.por_telefone("18 9811-6168")
        assert a and {x["id"] for x in a} == {x["id"] for x in b}

    def test_devolve_LISTA_porque_numero_pode_ter_varios_donos(self):
        """🚨 Dez números da base estão em mais de um contato, um deles em 8.

        Devolver `contato | None` obrigaria a escolher arbitrariamente, e a
        escolha arbitrária é o que não se pode esconder de quem vai atender.
        """
        assert isinstance(cadastro.por_telefone("5518998116168"), list)

    def test_numero_desconhecido_devolve_lista_vazia(self):
        assert cadastro.por_telefone("+5511999998888") == []

    def test_lixo_devolve_lista_vazia_sem_estourar(self):
        assert cadastro.por_telefone("abc") == []
        assert cadastro.por_telefone("") == []
        assert cadastro.por_telefone(None) == []
