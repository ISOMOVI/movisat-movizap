"""A identidade do owner — o que 12/08 consertou e o que não pode voltar.

O estado antes:

  · o login do `.env` colidia com `atendente.login`, e `buscar_usuario`
    consultava o `.env` PRIMEIRO e retornava ali. O dono entrava por senha e
    recebia identidade SEM `id`, com nome "Administrador". O vínculo com a
    linha dele só acontecia porque `_atendente_do_usuario` resolvia pelo TEXTO
    do login -- coincidência dos dois nomes, não desenho;
  · trocar a senha na CAD_2.1 não fazia nada, em silêncio;
  · `perfil='owner'` e a coluna `owner` diziam o mesmo e podiam discordar;
  · nada impedia promover alguém a owner;
  · atendente sem e-mail atendia normalmente, gravando autor NULL.

🚨 Escreve em `atendente`, tabela de PRODUÇÃO. Logins com prefixo `zz`, que
não colidem com os quatro reais. A fixture apaga só o que criou.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, "/home/claude/movizap_painel")
pytest.importorskip("psycopg")

from movizap import auth, banco, operacao, telas  # noqa: E402

ENV = Path("/home/claude/movizap_painel/.env")
pytestmark = pytest.mark.skipif(
    not ENV.exists() or "MOVIZAP_DB_SENHA" not in ENV.read_text(encoding="utf-8"),
    reason="banco nao configurado no .env")

LOGIN = "zz_teste_ident_"


def limpar():
    banco.executar("DELETE FROM atendente WHERE login LIKE %s", (LOGIN + "%",))


@pytest.fixture(scope="module", autouse=True)
def pool():
    banco.abrir()
    limpar()
    yield
    limpar()
    banco.fechar()


@pytest.fixture()
def zerado():
    limpar()
    yield
    limpar()


class TestOwnerEUnico:
    def test_nao_se_cria_owner(self, zerado):
        with pytest.raises(operacao.DadoInvalido) as e:
            operacao.criar_atendente(
                nome="Teste Owner Novo", login=LOGIN + "novo",
                email="zz@movisat.com.br", perfil="owner")
        assert "owner" in str(e.value).lower()
        assert banco.um("SELECT id FROM atendente WHERE login = %s",
                        (LOGIN + "novo",)) is None

    def test_nao_se_promove_a_owner(self, zerado):
        """🚨 Depois da migração 025 promover concede owner PLENO na hora,
        porque `owner` virou coluna derivada de `perfil`."""
        novo = operacao.criar_atendente(
            nome="Teste Comum", login=LOGIN + "comum",
            email="zzcomum@movisat.com.br", perfil="atendimento")
        with pytest.raises(operacao.DadoInvalido):
            operacao.atualizar_atendente(
                novo["id"], nome="Teste Comum", login=LOGIN + "comum",
                email="zzcomum@movisat.com.br", perfil="owner",
                estado="disponivel", max_conversas=None, ativo=True)
        lido = banco.um("SELECT perfil, owner FROM atendente WHERE id = %s",
                        (novo["id"],))
        assert lido["perfil"] == "atendimento"
        assert lido["owner"] is False

    def test_o_owner_de_verdade_nao_pode_ser_rebaixado(self):
        """Tirar o perfil do único administrador é o mesmo estrago que
        desativar a própria conta, por um campo que parece inofensivo."""
        dono = banco.um("SELECT id, nome, login, email FROM atendente WHERE owner")
        if not dono:
            pytest.skip("nenhum owner na base")
        with pytest.raises(operacao.EmUso):
            operacao.atualizar_atendente(
                dono["id"], nome=dono["nome"], login=dono["login"],
                email=dono["email"], perfil="atendimento",
                estado="disponivel", max_conversas=None, ativo=True)
        assert banco.um("SELECT owner FROM atendente WHERE id = %s",
                        (dono["id"],))["owner"] is True


class TestOwnerDerivadoDoPerfil:
    def test_a_coluna_e_gerada_pelo_banco(self):
        """Estado inconsistente vira IMPOSSÍVEL, não improvável."""
        col = banco.um(
            """SELECT is_generated, generation_expression FROM
               information_schema.columns
                WHERE table_name = 'atendente' AND column_name = 'owner'""")
        assert col["is_generated"] == "ALWAYS"
        assert "perfil" in col["generation_expression"]

    def test_escrever_owner_direto_e_recusado_pelo_banco(self, zerado):
        """A garantia não é disciplina do código -- é o Postgres recusando."""
        import psycopg
        novo = operacao.criar_atendente(
            nome="Teste Gerada", login=LOGIN + "gerada",
            email="zzgerada@movisat.com.br", perfil="atendimento")
        with pytest.raises(psycopg.errors.GeneratedAlways):
            banco.executar("UPDATE atendente SET owner = true WHERE id = %s",
                           (novo["id"],))

    def test_perfil_e_owner_nunca_discordam(self):
        divergentes = banco.varios(
            "SELECT id FROM atendente WHERE owner <> (perfil = 'owner')")
        assert divergentes == []


class TestAdminSaiuDoVocabulario:
    def test_nenhum_perfil_admin(self):
        assert "admin" not in telas.PERFIS

    def test_nenhuma_tela_usa_permissao_admin(self):
        assert [t["codigo"] for t in telas.TELAS if t["permissao"] == "admin"] == []

    def test_o_banco_recusa_perfil_admin(self):
        import psycopg
        with pytest.raises(psycopg.errors.CheckViolation):
            banco.executar(
                """INSERT INTO atendente (login, nome, perfil)
                   VALUES (%s, 'Teste Admin', 'admin')""", (LOGIN + "admin",))


class TestVinculoDeAtendimentoExigeEmail:
    """Regra do usuário em 12/08: sem e-mail, sem vínculo de atendimento."""

    def _vinculo(self, login):
        from movizap.main import _atendente_do_usuario
        return _atendente_do_usuario(auth.buscar_usuario(login))

    def test_com_email_tem_vinculo(self, zerado):
        novo = operacao.criar_atendente(
            nome="Teste Com Email", login=LOGIN + "comemail",
            email="zzcomemail@movisat.com.br", perfil="atendimento")
        assert self._vinculo(LOGIN + "comemail") == novo["id"]

    def test_sem_email_NAO_tem_vinculo(self, zerado):
        """🚨 Antes disto a pessoa respondia o cliente e a mensagem saía com
        autor NULL -- a conversa não sabia dizer quem tinha respondido."""
        operacao.criar_atendente(
            nome="Teste Sem Email", login=LOGIN + "sememail",
            email=None, perfil="atendimento")
        assert self._vinculo(LOGIN + "sememail") is None

    def test_email_apagado_TIRA_o_vinculo(self, zerado):
        novo = operacao.criar_atendente(
            nome="Teste Apagar", login=LOGIN + "apagar",
            email="zzapagar@movisat.com.br", perfil="atendimento")
        assert self._vinculo(LOGIN + "apagar") == novo["id"]
        banco.executar("UPDATE atendente SET email = NULL WHERE id = %s",
                       (novo["id"],))
        assert self._vinculo(LOGIN + "apagar") is None

    def test_email_so_com_espaco_nao_vale(self, zerado):
        novo = operacao.criar_atendente(
            nome="Teste Branco", login=LOGIN + "branco",
            email="zzbranco@movisat.com.br", perfil="atendimento")
        banco.executar("UPDATE atendente SET email = '   ' WHERE id = %s",
                       (novo["id"],))
        assert self._vinculo(LOGIN + "branco") is None


class TestTrocarEmailPassaAConta:
    def test_trocar_o_email_ZERA_o_google_sub(self, zerado):
        """🚨 O `sub` é o que identifica a conta Google para sempre. Trocar só
        o e-mail deixava o dono ANTERIOR entrando, porque o `sub` dele
        continuava casando em `google_sub OR email` -- em silêncio, até o novo
        entrar pela primeira vez e sobrescrever."""
        novo = operacao.criar_atendente(
            nome="Teste Passa", login=LOGIN + "passa",
            email="zzantigo@movisat.com.br", perfil="atendimento")
        banco.executar("UPDATE atendente SET google_sub = %s WHERE id = %s",
                       ("sub-do-dono-antigo", novo["id"]))

        operacao.atualizar_atendente(
            novo["id"], nome="Teste Passa", login=LOGIN + "passa",
            email="zznovo@movisat.com.br", perfil="atendimento",
            estado="disponivel", max_conversas=None, ativo=True)

        lido = banco.um("SELECT email, google_sub FROM atendente WHERE id = %s",
                        (novo["id"],))
        assert lido["email"] == "zznovo@movisat.com.br"
        assert lido["google_sub"] is None, "o dono anterior ainda entraria"

    def test_editar_sem_mexer_no_email_PRESERVA_o_sub(self, zerado):
        """Trocar o fuso não pode expulsar ninguém do Google."""
        novo = operacao.criar_atendente(
            nome="Teste Mantem", login=LOGIN + "mantem",
            email="zzmantem@movisat.com.br", perfil="atendimento")
        banco.executar("UPDATE atendente SET google_sub = %s WHERE id = %s",
                       ("sub-que-fica", novo["id"]))
        operacao.atualizar_atendente(
            novo["id"], nome="Outro Nome", login=LOGIN + "mantem",
            email="zzmantem@movisat.com.br", perfil="atendimento",
            estado="ausente", max_conversas=None, ativo=True)
        assert banco.um("SELECT google_sub FROM atendente WHERE id = %s",
                        (novo["id"],))["google_sub"] == "sub-que-fica"


class TestAContaDoEnvNaoRoubaAIdentidade:
    def test_o_login_do_env_traz_a_linha_da_tabela(self):
        """🚨 O defeito central: a conta do `.env` respondia ANTES da tabela e
        devolvia identidade sem `id`, com nome "Administrador"."""
        from movizap.config import settings
        if not settings.admin_login:
            pytest.skip("sem conta no .env")
        u = auth.buscar_usuario(settings.admin_login)
        if u is None:
            pytest.skip("a conta do .env não tem linha na tabela")
        assert u.get("id"), "voltou sem id -- a porta do .env roubou a identidade"
        assert u["nome"] != "Administrador", "voltou o nome genérico do .env"
        assert u.get("email"), "identidade sem e-mail não tem vínculo"

    def test_a_senha_do_env_ainda_abre_quando_a_linha_nao_tem_hash(self):
        """A porta de emergência continua existindo: a linha do dono tem
        `senha_hash` NULL e mesmo assim ele entra por senha."""
        from movizap.config import settings
        if not settings.admin_login:
            pytest.skip("sem conta no .env")
        u = auth.buscar_usuario(settings.admin_login)
        if u is None or u.get("id") is None:
            pytest.skip("a conta do .env não tem linha na tabela")
        assert u["senha_hash"], "o dono ficaria sem senha nenhuma"

    def test_login_desconhecido_continua_None(self):
        assert auth.buscar_usuario("zz_nao_existe_ninguem") is None
