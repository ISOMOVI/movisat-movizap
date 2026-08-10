"""Testes do registro de telas -- a fonte única de navegação, permissão e auditoria.

O que se protege aqui:
  - código duplicado ou reaproveitado (faria log antigo mentir);
  - permissão vazando para quem não tem;
  - tela de fase futura subindo antes da hora.
"""
import pytest

from movizap import telas


class TestIntegridadeDoRegistro:
    def test_codigos_sao_unicos(self):
        codigos = [t["codigo"] for t in telas.TELAS]
        assert len(codigos) == len(set(codigos)), "código repetido no registro"

    def test_codigo_aposentado_nunca_volta(self):
        """🚨 Reaproveitar código faria o log antigo mentir.

        ATD_4.1 era do e-mail na fase 2; virou EML_1.1 em 10/08, quando o
        usuário decidiu que e-mail não se mistura com WhatsApp.
        """
        vivos = {t["codigo"] for t in telas.TELAS}
        assert not (vivos & telas.CODIGOS_APOSENTADOS), (
            f"código aposentado voltou: {vivos & telas.CODIGOS_APOSENTADOS}")

    def test_rotas_sao_unicas(self):
        rotas = [t["rota"] for t in telas.TELAS]
        assert len(rotas) == len(set(rotas)), "duas telas na mesma rota"

    def test_todo_codigo_segue_o_formato(self):
        for t in telas.TELAS:
            modulo, _, numero = t["codigo"].partition("_")
            # INI entrou em 10/08 com a tela inicial: é a porta de entrada,
            # não atendimento nem cadastro. Prefixo novo se registra AQUI --
            # é este teste que impede código inventado passar despercebido.
            assert modulo in {"INI", "EML", "ATD", "CAD", "CFG", "REL"}, t["codigo"]
            assert numero, t["codigo"]
            for parte in numero.split("."):
                assert parte.isdigit(), f"{t['codigo']}: parte não numérica"

    def test_toda_tela_tem_os_campos_obrigatorios(self):
        for t in telas.TELAS:
            for campo in ("codigo", "titulo", "rota", "icone", "descricao", "permissao", "fase"):
                assert t.get(campo), f"{t.get('codigo')}: falta {campo}"

    def test_toda_permissao_usada_existe_em_algum_perfil(self):
        # permissão que nenhum perfil concede é tela que ninguém alcança
        concedidas = set()
        for perfil in telas.PERFIS:
            concedidas |= telas.permissoes_do_perfil(perfil)
        orfas = telas.PERMISSOES_VALIDAS - concedidas
        assert not orfas, f"permissões que nenhum perfil concede: {orfas}"


class TestBusca:
    def test_por_codigo_encontra(self):
        assert telas.por_codigo("ATD_1.1")["titulo"] == "Caixa de entrada"

    def test_por_codigo_estoura_em_codigo_inexistente(self):
        # estourar é de propósito: é erro de programação, não de uso
        with pytest.raises(telas.CodigoDeTelaInvalido):
            telas.por_codigo("XXX_9.9")

    def test_ativas_nao_traz_fase_futura(self):
        for t in telas.ativas():
            assert t["fase"] <= telas.FASE_ATUAL

    def test_telas_reservadas_existem_mas_nao_sobem(self):
        """⚠️ A `ATD_3.1` SAIU desta lista em 07/08: o usuário decidiu que o
        informativo entra na Fase 1 ("é o que vai enviar, sem resposta de
        cliente"), o canal foi pareado no mesmo dia e a tela subiu.

        A guarda continua valendo para as que seguem reservadas -- e foi ela
        que acusou a mudança, que é exatamente o trabalho dela."""
        codigos_ativos = {t["codigo"] for t in telas.ativas()}
        # ⚠️ A `ATD_4.1` SAIU desta lista em 10/08 -- e não porque subiu, como
        # a ATD_3.1: ela foi APOSENTADA. Era o e-mail dentro do módulo de
        # atendimento; o usuário decidiu que e-mail JAMAIS se mistura com
        # WhatsApp, e o e-mail virou EML_1.1, módulo próprio. O código não
        # volta -- está em CODIGOS_APOSENTADOS, com teste próprio.
        for reservada in ("CFG_2.2", "REL_1.1"):
            assert reservada in telas.CODIGOS_VALIDOS, \
                f"{reservada}: o código precisa continuar reservado"
            assert reservada not in codigos_ativos, \
                f"{reservada}: tela de fase futura não pode subir na fase 1"

    def test_informativo_subiu_para_fase_1(self):
        """🚨 É a única tela que alcança cliente de verdade EM LOTE, e o canal
        é irreversível. Se ela sumir das ativas sem decisão, alguém mexeu na
        fase sem querer."""
        assert "ATD_3.1" in {t["codigo"] for t in telas.ativas()}


class TestPermissao:
    def test_owner_ve_tudo(self):
        owner = {"owner": True, "permissoes": []}
        for t in telas.ativas():
            assert telas.pode_acessar(owner, t["codigo"])

    def test_conta_nova_nao_ve_nada(self):
        # falha fechado: conta sem permissão não alcança nenhuma tela
        novo = {"owner": False, "permissoes": []}
        for t in telas.ativas():
            assert not telas.pode_acessar(novo, t["codigo"])

    def test_permissao_nao_vaza_entre_modulos(self):
        so_atendimento = {"owner": False, "permissoes": ["atendimento"]}
        assert telas.pode_acessar(so_atendimento, "ATD_1.1")
        assert not telas.pode_acessar(so_atendimento, "CAD_1.1")
        assert not telas.pode_acessar(so_atendimento, "CFG_1.1")

    def test_tela_de_owner_nunca_e_concedida(self):
        # CFG_9.1 é do owner: nem admin com todas as permissões alcança
        admin = {"owner": False, "permissoes": sorted(telas.PERMISSOES_VALIDAS)}
        assert not telas.pode_acessar(admin, "CFG_9.1")

    def test_do_usuario_respeita_a_permissao(self):
        so_cadastro = {"owner": False, "permissoes": ["cadastro"]}
        codigos = {t["codigo"] for t in telas.do_usuario(so_cadastro)}
        assert codigos == {"CAD_1.1", "CAD_1.2"}

    def test_do_usuario_preserva_a_ordem_do_registro(self):
        owner = {"owner": True, "permissoes": []}
        vistas = [t["codigo"] for t in telas.do_usuario(owner)]
        esperada = [t["codigo"] for t in telas.ativas()]
        assert vistas == esperada, "o menu tem que sair sempre na mesma sequência"


class TestPerfis:
    def test_owner_tem_todas_as_permissoes(self):
        assert telas.permissoes_do_perfil("owner") == telas.PERMISSOES_VALIDAS

    def test_perfil_inexistente_nao_concede_nada(self):
        assert telas.permissoes_do_perfil("inventado") == set()

    def test_atendimento_nao_alcanca_configuracao(self):
        assert "admin" not in telas.permissoes_do_perfil("atendimento")
