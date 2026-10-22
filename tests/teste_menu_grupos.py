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
        """Antes de 21/10 `INI` e `EML` não estavam no mapa do menu e saíam crus.

        🔵 22/10: o E-mail passou a morar DENTRO de "Atendimento", abaixo do
        Chat interno (*"pessoal deu feedback que é melhor nessa ordem"*), e ele
        confirmou que é só visual -- o módulo continua `EML`, com rota, caixa e
        permissão próprias. Por isso o grupo esperado mudou e o resto não.

        🚨 A DEFESA ORIGINAL CONTINUA AQUI, e é a segunda linha de cada par:
        o que este teste existe para impedir é o grupo sair CRU ("EML", "INI").
        Trocar o destino do EML não pode levar essa garantia embora.
        """
        por_codigo = {t["codigo"]: t for t in telas.do_usuario({"owner": True})}
        assert por_codigo["INI_1.1"]["grupo"] == "Início"
        assert por_codigo["INI_1.1"]["grupo"] != "INI"
        assert por_codigo["EML_1.1"]["grupo"] == "Atendimento"
        assert por_codigo["EML_1.1"]["grupo"] != "EML"

    def test_o_fallback_do_EML_continua_apontando_para_E_mail(self):
        """⚠️ O grupo do EML_1.1 agora vem GRAVADO na tela, não do prefixo --
        mas o fallback tem de continuar correto. Tela sem `grupo` (backend um
        passo atrás da tela, que o `M16` diz que acontece) cai aqui, e cair
        em "E-mail" é degradar; cair em "EML" seria rótulo cru na tela."""
        assert telas.grupo_da({"codigo": "EML_1.1"}) == "E-mail"

    def test_o_grupo_E_mail_ficou_declarado_e_vazio(self):
        """🚨 TELA QUE MENTE É DEFEITO, e grupo vazio não mente: ele existe no
        registro e o `MenuLateral` não desenha grupo sem tela visível -- como
        "Painéis › Operacional" desde 19/10. Este teste é o que impede alguém
        "limpar" a entrada de GRUPOS e levar o fallback de cima com ela."""
        assert "E-mail" in telas.GRUPOS
        assert not [t for t in telas.ativas() if telas.grupo_da(t) == "E-mail"]


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

    def test_paineis_ganhou_o_primeiro_habitante(self):
        """🔵 19/10 o grupo nasceu declarado e VAZIO; 22/10 ele ganhou a
        PNL_1.1 (o painel da Operação), por decisão dele depois dos mockups.

        🚨 E O SUBGRUPO "Operacional" SAIU -- fecha a pendência 6 do plano
        (*"alinhar o nome do subgrupo com o painel"*). Ele nunca teve tela, e o
        painel chama-se "Operação": manter os dois faria o menu desenhar
        "Painéis › Operacional › Operação". Os quatro painéis são ITENS do
        grupo, sem subgrupo.

        ⚠️ Este teste mudou de nome junto com o comportamento. O antigo
        afirmava "nasce vazio", e deixá-lo verde com a tela dentro exigiria
        afrouxá-lo -- que é como um teste passa a mentir.
        """
        assert telas.GRUPOS["Painéis"] == []
        dentro = [t["codigo"] for t in telas.TELAS if telas.grupo_da(t) == "Painéis"]
        assert dentro == ["PNL_1.1"]


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
