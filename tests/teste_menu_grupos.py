"""Grupo e subgrupo do menu -- 21/10.

🔵 Pedido dele em 19/10: o menu abrindo "em grupos e subgrupos", e **Ligações
dentro de Atendimento**. Até aqui o grupo saía do PREFIXO do código, dentro do
`MenuLateral.vue` -- e o código é imutável por regra do registro, então mover
uma tela de grupo era impossível sem mentir no código dela.

O que se protege aqui:
  - o grupo chega ao frontend (campo que não entra no `do_usuario` fica no
    registro e nunca aparece -- foi assim com o `aba_de` em 27/08);
  - 🚨 o FALLBACK pelo prefixo: tela sem `grupo` continua onde estava. Sem
    isto, toda tela não tocada por esta entrega muda de lugar em silêncio;
  - grupo é APRESENTAÇÃO: não mexe em quem vê o quê;
  - `INI_1.1` continua sendo a primeira da lista (a rota `/` redireciona para
    `sessao.telas[0].rota`).
"""
from movizap import telas


class TestGrupoChegaAoFrontend:
    def test_toda_tela_traz_grupo_e_subgrupo(self):
        for t in telas.do_usuario({"owner": True}):
            assert t["grupo"], f"{t['codigo']} sem grupo"
            assert "subgrupo" in t, f"{t['codigo']} sem a chave subgrupo"

    def test_ligacoes_vai_para_atendimento(self):
        """🔵 O pedido que abriu o assunto, e a prova de que o código não mudou."""
        por_codigo = {t["codigo"]: t for t in telas.do_usuario({"owner": True})}
        assert por_codigo["LIG_1.1"]["grupo"] == "Atendimento"
        assert por_codigo["LIG_1.1"]["codigo"] == "LIG_1.1"

    def test_inicio_e_email_tem_nome_de_verdade(self):
        """Antes de hoje `INI` e `EML` não estavam no mapa do menu e saíam crus."""
        por_codigo = {t["codigo"]: t for t in telas.do_usuario({"owner": True})}
        assert por_codigo["INI_1.1"]["grupo"] == "Início"
        assert por_codigo["EML_1.1"]["grupo"] == "E-mail"


class TestFallbackPeloPrefixo:
    def test_tela_sem_grupo_cai_no_prefixo(self):
        assert telas.grupo_da({"codigo": "REL_1.1"}) == "Relatórios"
        assert telas.grupo_da({"codigo": "CFG_9.1"}) == "Configuração"

    def test_prefixo_desconhecido_vira_o_proprio_prefixo(self):
        """Degrada mostrando o prefixo cru -- nunca some do menu."""
        assert telas.grupo_da({"codigo": "XYZ_1.1"}) == "XYZ"

    def test_grupo_gravado_ganha_do_prefixo(self):
        assert telas.grupo_da({"codigo": "LIG_1.1", "grupo": "Atendimento"}) == "Atendimento"


class TestDeclaracaoDosGrupos:
    def test_todo_grupo_usado_esta_declarado(self):
        usados = {telas.grupo_da(t) for t in telas.TELAS}
        fora = usados - set(telas.GRUPOS)
        assert not fora, f"grupo usado e não declarado em GRUPOS: {fora}"

    def test_paineis_operacional_existe_e_nasce_vazio(self):
        """🔵 Decisão 3 dele: o grupo é criado, e só aparece quando tiver tela.

        Quem garante que ele não é desenhado é o `MenuLateral` (grupo sem item
        visível não vira linha). Aqui se garante o outro lado: que ele existe
        declarado e que nenhuma tela entrou nele por engano.
        """
        assert telas.GRUPOS["Painéis"] == ["Operacional"]
        assert not [t for t in telas.TELAS if telas.grupo_da(t) == "Painéis"]


class TestGrupoNaoMexeEmPermissao:
    def test_atendente_continua_vendo_o_mesmo_conjunto(self):
        """Apresentação não é permissão -- o conjunto é o de sempre."""
        usuario = {"owner": False, "permissoes": ["atendimento"]}
        vistas = {t["codigo"] for t in telas.do_usuario(usuario)}
        esperado = {
            t["codigo"]
            for t in telas.ativas()
            if t["permissao"] == "atendimento"
        }
        assert vistas == esperado

    def test_conta_sem_permissao_nao_ganha_tela_pelo_grupo(self):
        assert telas.do_usuario({"owner": False, "permissoes": []}) == []

    def test_inicio_continua_sendo_a_primeira(self):
        """🚨 A rota `/` redireciona para `sessao.telas[0].rota`.

        Agrupar não pode reordenar a lista: o menu é que agrupa, preservando a
        ordem do backend. Ordenar aqui mudaria o destino de todo login.
        """
        assert telas.do_usuario({"owner": True})[0]["codigo"] == "INI_1.1"
