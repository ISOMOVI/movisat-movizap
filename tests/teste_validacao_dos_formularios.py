"""A VALIDAÇÃO DECLARADA NOS 14 FORMULÁRIOS — migrações 103 e 104 (11/11).

🔵 Ele: *"Os formulários devem seguir como a padronização do formulário de
suporte, no quesito de estilo, validação de campos, disposição e lógica"* · *"o
formulario suporte é a base, os erros de bitrix ficam para tras, ja temos
validações uteis no suporte"*.

🚨 O BURACO QUE ISTO FECHOU, MEDIDO: os 14 formulários tinham **215 campos e
ZERO validação declarada**. Aceitavam CNPJ inválido, telefone de três dígitos e
e-mail sem arroba — herdamos a definição do Bitrix e herdamos o buraco.

🚨 E A TRAVA MAIS IMPORTANTE DESTE ARQUIVO É A DA ARMADILHA: um `LIKE '%cnpj%'`
pegaria o campo *"CNPJ e Nome da Empresa que será transferida"*, e passaria a
RECUSAR a resposta certa. É a mesma lição do *"Veículo e Placa"* do Suporte.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, "/home/claude/movizap_painel")
pytest.importorskip("psycopg")

from movizap import banco, formularios  # noqa: E402
from movizap.operacao import DadoInvalido  # noqa: E402

ENV = Path("/home/claude/movizap_painel/.env")
pytestmark = pytest.mark.skipif(
    not ENV.exists() or "MOVIZAP_DB_SENHA" not in ENV.read_text(encoding="utf-8"),
    reason="banco nao configurado no .env")


@pytest.fixture(scope="module", autouse=True)
def base():
    banco.abrir()
    yield


def campos(**onde):
    sql = """SELECT c.nosso_nome, c.tipo, c.validacao, c.rotulo, f.slug
               FROM formulario_campo c JOIN formulario f ON f.id = c.formulario_id"""
    if "nosso_nome" in onde:
        sql += " WHERE c.nosso_nome = %s"
        return banco.varios(sql, (onde["nosso_nome"],))
    return banco.varios(sql)


class TestAArmadilhaDoLIKE:
    """🚨 A razão de a migração ser por LISTA EXPLÍCITA."""

    def test_o_campo_de_DOIS_dados_numa_caixa_NAO_tem_validacao_de_cnpj(self):
        """*"CNPJ e Nome da Empresa que será transferida"* pede as duas coisas na
        mesma caixa. Com `validacao = 'cnpj'`, o servidor passaria a exigir 14
        caracteres e **recusaria a resposta certa**
        (`12.345.678/0001-90 Acme Ltda`).
        """
        achados = campos(nosso_nome="cnpj-e-nome-da-empresa-que-sera-transfer")
        assert achados, "o campo da armadilha não existe mais — confira o nome"
        for c in achados:
            assert c["validacao"] is None, c

    def test_e_o_campo_cnpj_DE_VERDADE_tem(self):
        """A trava de cima só vale se esta passar: o contrário de \"nenhum CNPJ
        é validado\" é \"o CNPJ certo é validado\"."""
        achados = campos(nosso_nome="cnpj")
        assert achados
        assert all(c["validacao"] == "cnpj" for c in achados)

    def test_o_RG_continua_SEM_validacao(self):
        """Não há dígito verificador padrão: cada estado emite o seu, e recusar
        formato recusaria RG de verdade."""
        for c in campos(nosso_nome="rg"):
            assert c["validacao"] is None


class TestOQueGanhouValidacao:
    def test_todo_campo_de_e_mail_tem_a_regra_de_e_mail(self):
        for c in campos():
            if c["tipo"] == "email":
                assert c["validacao"] == "email", c

    def test_todo_campo_de_telefone_tem_a_regra_de_telefone(self):
        for c in campos():
            if c["tipo"] == "phone":
                assert c["validacao"] == "telefone", c

    def test_cpf_cep_e_placa_pelos_nomes_exatos(self):
        for nome, regra in (("cpf", "cpf"), ("cep", "cep"),
                            ("veiculo-e-placa", "placa")):
            achados = campos(nosso_nome=nome)
            assert achados, nome
            assert all(c["validacao"] == regra for c in achados), nome

    def test_o_SUPORTE_nao_foi_mexido(self):
        """🚨 Ele é a BASE (*"o formulario suporte é a base"*). As migrações
        usam `validacao IS NULL`, então não tocam no que já estava certo."""
        do_suporte = [c for c in campos() if c["slug"] == "suporte"]
        regras = {c["nosso_nome"]: c["validacao"] for c in do_suporte}
        assert regras["cnpj"] == "cnpj"
        assert regras["cpf"] == "cpf"
        assert regras["e-mail"] == "email"
        assert regras["telefone"] == "telefone"
        assert regras["veiculo-e-placa-somente-se-for-referente"] == "placa"

    def test_as_regras_usadas_existem_TODAS_no_validador(self):
        """🚨 Regra declarada que o validador não conhece é validação que não
        acontece -- e passa calada. É o elo *quem devolve → quem lê*."""
        usadas = {c["validacao"] for c in campos() if c["validacao"]}
        conhecidas = set(formularios._TAMANHO_DO_DOCUMENTO) | {
            "email", "telefone", "placa"}
        assert usadas <= conhecidas, usadas - conhecidas


class TestOTipoErradoDoBitrix:
    """🔵 *"os erros de bitrix ficam para tras"* (migração 104)."""

    def test_o_e_mail_do_novo_titular_virou_tipo_email(self):
        """🚨 Vinha como `string`, e o servidor decide e-mail pelo TIPO -- então
        a validação ficaria **só no navegador**, no campo que identifica quem
        passa a ser dono do contrato."""
        for c in campos(nosso_nome="e-mail-do-novo-titular"):
            assert c["tipo"] == "email"
            assert c["validacao"] == "email"

    def test_o_telefone_do_novo_titular_virou_tipo_phone(self):
        for c in campos(nosso_nome="telefone-com-ddd-do-novo-titular"):
            assert c["tipo"] == "phone"
            assert c["validacao"] == "telefone"


class TestOServidorDeFatoRECUSA:
    """⚠️ Declarar a regra não é aplicá-la: estas travas exercitam o
    `formularios.validar` com dado ruim."""

    def _um(self, slug, nosso_nome):
        d = formularios.definicao(slug, so_ativo=False)
        for c in d["campos"]:
            if c["nosso_nome"] == nosso_nome:
                return d, c
        pytest.skip(f"{slug} nao tem {nosso_nome}")

    # ⚠️ AS TRAVAS CHAMAM `_um_valor`, E NAO `validar`. A primeira versao
    # chamava o `validar`, que percorre o formulario INTEIRO e para no primeiro
    # campo obrigatorio ausente -- entao ela reprovava por um motivo que nao era
    # o medido ("Contrato Pessoa Fisica ou Juridica?: preencha este campo"). A
    # unidade sob teste e a conferencia de UM valor.

    def test_cnpj_curto_e_recusado_com_frase(self):
        _d, campo = self._um("ficha-cadastral", "cnpj")
        with pytest.raises(DadoInvalido) as e:
            formularios._um_valor(campo, "123")
        assert "14" in str(e.value)

    def test_cpf_curto_e_recusado(self):
        _d, campo = self._um("ficha-cadastral", "cpf")
        with pytest.raises(DadoInvalido) as e:
            formularios._um_valor(campo, "123")
        assert "11" in str(e.value)

    def test_e_mail_sem_arroba_e_recusado(self):
        _d, campo = self._um("ficha-cadastral", "e-mail-geral-da-empresa")
        with pytest.raises(DadoInvalido) as e:
            formularios._um_valor(campo, "abc")
        assert "e-mail" in str(e.value).lower()

    def test_o_DIGITO_VERIFICADOR_nao_e_conferido_no_servidor(self):
        """🚨 ISTO É DECISÃO DELE, NÃO BURACO. Está escrito em
        `formularios.py`: o servidor garante o FORMATO e a frase que a pessoa lê
        é da tela. Passar a recusar DV no servidor **é mudança de régua**.
        ⚠️ A trava existe para que a mudança seja deliberada, não acidental.
        """
        _d, campo = self._um("ficha-cadastral", "cnpj")
        # 14 dígitos, DV errado: o servidor ACEITA, de propósito.
        assert formularios._um_valor(campo, "11111111111111") == "11111111111111"
