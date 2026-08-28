"""O tipo do contato sem depender de empresa vinculada — E.1, 28/08.

Pedido dele: *"o tipo… não precisa depender de empresa vinculada para ter o
campo"*. Ele disse EMPRESA, não contato — e o tipo mora em `contato.relacao`.
O que faltava não era o campo: era o registro.

🚨 ESTE ARQUIVO DEFENDE OS QUATRO CONSERTOS QUE A VALIDAÇÃO ACHOU ANTES de eu
escrever a tela. Sem eles a função "funcionaria" e estragaria o resto da ficha:

  1. os candidatos sumiriam no instante em que a pessoa marcasse o tipo;
  2. o selo do Bitrix sumiria junto;
  3. a gaveta continuaria dizendo "Sem cadastro" depois de criar um;
  4. o contato nasceria com o default e não com o tipo escolhido.

⚠️ Escreve em tabelas de PRODUÇÃO, como os outros testes daqui. O telefone é de
um DDD que não existe (+55 99 ...), e a limpeza apaga só o que criou —
inclusive o `contato` novo, que é a novidade deste bloco.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, "/home/claude/movizap_painel")
pytest.importorskip("psycopg")

from movizap import automacao, banco, conversas  # noqa: E402

ENV = Path("/home/claude/movizap_painel/.env")
pytestmark = pytest.mark.skipif(
    not ENV.exists() or "MOVIZAP_DB_SENHA" not in ENV.read_text(encoding="utf-8"),
    reason="banco nao configurado no .env")

FONE = "+5599922220000"
# 🚨 GRUPO NÃO TEM TELEFONE. O CHECK `ck_conversa_identidade` exige
# `tipo='grupo' AND grupo_jid IS NOT NULL AND telefone_e164 IS NULL` -- eu
# tinha escrito o teste supondo que grupo era só um `tipo` diferente, e o
# banco recusou. A regra estava no schema o tempo todo.
JID_GRUPO = "zz-teste-tipo-999@g.us"


def limpar():
    banco.executar("DELETE FROM contato_telefone WHERE e164 = %s", (FONE,))
    banco.executar("DELETE FROM conversa WHERE telefone_e164 = %s", (FONE,))
    banco.executar("DELETE FROM conversa WHERE grupo_jid = %s", (JID_GRUPO,))
    # O contato nasce sem empresa e com origem 'movizap': é exatamente o que
    # este bloco cria, e não existe na base fora daqui.
    banco.executar(
        "DELETE FROM contato WHERE origem = 'movizap' AND cliente_id IS NULL "
        "AND nome = %s", (FONE,))


@pytest.fixture(scope="module", autouse=True)
def pool():
    banco.abrir()
    limpar()
    yield
    limpar()
    banco.fechar()


@pytest.fixture(autouse=True)
def entre_testes():
    yield
    limpar()


def canal_id():
    linha = banco.um("SELECT id FROM canal WHERE instancia = 'atendimento'")
    if not linha:
        pytest.skip("canal atendimento não cadastrado")
    return linha["id"]


def conversa_nova() -> int:
    """Uma conversa direta sem contato — o caso de 61% da base."""
    linha = banco.um(
        """INSERT INTO conversa (canal_id, telefone_e164, estado, tipo,
                                 ultima_atividade_em)
           VALUES (%s, %s, 'nova', 'direta', now()) RETURNING id""",
        (canal_id(), FONE))
    return linha["id"]


def grupo_novo() -> int:
    linha = banco.um(
        """INSERT INTO conversa (canal_id, grupo_jid, grupo_nome, estado, tipo,
                                 ultima_atividade_em)
           VALUES (%s, %s, 'Plantao zz teste', 'nova', 'grupo', now())
           RETURNING id""",
        (canal_id(), JID_GRUPO))
    return linha["id"]


class TestTipoSemEmpresa:

    def test_marcar_tipo_sem_cadastro_cria_o_contato(self):
        cid = conversa_nova()
        r = conversas.definir_tipo(cid, "teste")
        assert r["ok"], r.get("motivo")
        assert r["criou_contato"] is True
        assert banco.um("SELECT contato_id FROM conversa WHERE id = %s",
                        (cid,))["contato_id"] == r["id"]

    def test_o_contato_nasce_SEM_empresa(self):
        """⚠️ `contato.cliente_id` é anulável no schema, mas medido em 28/08:
        0 dos 1.756 contatos existiam assim. O caminho nunca tinha rodado."""
        r = conversas.definir_tipo(conversa_nova(), "fornecedor")
        contato = banco.um(
            "SELECT cliente_id, origem FROM contato WHERE id = %s", (r["id"],))
        assert contato["cliente_id"] is None
        assert contato["origem"] == "movizap", (
            "origem 'movizap' é o que protege este contato do sync: toda "
            "escrita do sync.py filtra origem='harmonit'")

    def test_nasce_COM_O_TIPO_ESCOLHIDO_e_nao_com_o_default(self):
        """🚨 `relacao` tem default `sem_identificacao` (migração 031). Criar e
        depois atualizar deixaria uma janela em que o contato existe dizendo o
        que ninguém disse."""
        r = conversas.definir_tipo(conversa_nova(), "tecnico")
        assert banco.um("SELECT relacao FROM contato WHERE id = %s",
                        (r["id"],))["relacao"] == "tecnico"

    def test_o_telefone_entra_marcado_como_do_atendimento(self):
        r = conversas.definir_tipo(conversa_nova(), "cliente")
        tel = banco.um(
            "SELECT origem_campo FROM contato_telefone WHERE contato_id = %s",
            (r["id"],))
        assert tel is not None, "o telefone tem de passar a existir no cadastro"
        assert tel["origem_campo"] == "atendimento"

    def test_a_automacao_troca_de_linha_e_a_resposta_DIZ(self):
        """🚨 Muda o comportamento na hora: boas-vindas e `ia_ligada` daquela
        pessoa passam a seguir a linha do tipo. A tela avisa em vez de deixar
        a pessoa descobrir pelo comportamento."""
        r = conversas.definir_tipo(conversa_nova(), "parceiro")
        assert r["automacao_antes"] == "sem_cadastro"
        assert r["automacao_depois"] == "parceiro"
        assert automacao.chave_do_contato(r["id"]) == "parceiro"

    def test_tipo_invalido_e_recusado(self):
        r = conversas.definir_tipo(conversa_nova(), "sem_cadastro")
        assert not r["ok"], (
            "'sem_cadastro' é chave da relacao_automacao, não valor do CHECK "
            "de contato.relacao -- aceitar faria o banco recusar depois")

    def test_grupo_nao_tem_tipo(self):
        r = conversas.definir_tipo(grupo_novo(), "cliente")
        assert not r["ok"]

    def test_com_contato_existente_apenas_troca(self):
        cid = conversa_nova()
        primeiro = conversas.definir_tipo(cid, "cliente")
        segundo = conversas.definir_tipo(cid, "lead")
        assert segundo["ok"]
        assert segundo["criou_contato"] is False
        assert banco.um("SELECT relacao FROM contato WHERE id = %s",
                        (primeiro["id"],))["relacao"] == "lead"


class TestOsQuatroConsertos:
    """O que teria quebrado se eu tivesse escrito a tela sem validar."""

    def test_os_candidatos_SOBREVIVEM_a_marcacao_do_tipo(self):
        """🚨 O PIOR DOS QUATRO. `conversa()` só calculava `candidatos` quando
        `contato_id IS NULL`. Marcar o tipo cria o contato -- e a pessoa
        perderia a lista que leva à empresa certa, como castigo por ter
        classificado. O critério passou a ser SEM EMPRESA, não sem contato."""
        cid = conversa_nova()
        conversas.definir_tipo(cid, "cliente")
        detalhe = conversas.conversa(cid)
        assert detalhe["contato_id"] is not None, "o contato foi criado"
        assert isinstance(detalhe["candidatos"], list), (
            "a chave não pode sumir só porque agora existe contato")

    def test_a_ficha_reconhece_cadastro_SEM_empresa(self):
        """🚨 O template chaveava em `empresa.cliente`. Um contato sem empresa
        devolve `cliente: None` e cairia no ramo "sem vínculo" -- a gaveta
        diria "Sem cadastro" logo depois de a pessoa ter criado um."""
        cid = conversa_nova()
        conversas.definir_tipo(cid, "colaborador")
        detalhe = conversas.conversa(cid)
        assert detalhe["empresa"] is not None
        assert detalhe["empresa"]["contato"] is not None
        assert detalhe["empresa"]["cliente"] is None
        assert detalhe["empresa"]["contato"]["relacao"] == "colaborador"

    def test_o_selo_do_bitrix_sobrevive_enquanto_nao_ha_empresa(self):
        """O selo serve para ACHAR a empresa: vale enquanto ela não existe."""
        cid = conversa_nova()
        conversas.definir_tipo(cid, "cliente")
        assert "bitrix" in conversas.conversa(cid)
