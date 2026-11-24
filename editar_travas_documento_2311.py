# -*- coding: utf-8 -*-
"""23/11 — as travas banco x script do documento do parceiro e da busca.

🚨 POR QUE AQUI DENTRO, na `TestACargaNaoApagaOQueEstaNoAr`: as duas mudanças
de hoje são **dado reescrito pela carga**. Uma vive no `AJUSTES`
(`obrigatorio: False`) e a outra no `BUSCA_CLIENTE`. Se amanhã alguém
consertar no banco em vez do script, a próxima carga desfaz -- em silêncio,
porque o estado no ar estaria certo. É a bomba de 11/11, e estas travas são o
mesmo tipo de guarda que a resolveu.
"""
import pathlib

p = pathlib.Path("tests/teste_etapas_dos_formularios.py")
bruto = p.read_bytes()
CRLF = b"\r\n" in bruto
t = bruto.decode("utf-8").replace("\r\n", "\n")


def troca(velho, novo, rotulo):
    global t
    assert velho in t, "NAO ACHOU (%s)" % rotulo
    assert t.count(velho) == 1, "AMBIGUO %dx (%s)" % (t.count(velho), rotulo)
    t = t.replace(velho, novo, 1)
    print("  ok:", rotulo)


troca('''    def test_o_derivador_de_etapas_pode_ser_IMPORTADO(self):''',
      '''    def test_o_documento_do_PARCEIRO_nao_e_obrigatorio(self):
        """🔵 23/11, dele: *"formulario de pagamento de parceiros esta errado,
        ele nao precisa de cpf e cnpj, obviamente pois nao puxa de base
        alguma, devem ser somente preencheiveis"*.

        🚨 O QUE ESTAVA ERRADO, MEDIDO EM 23/11: nos DOIS formularios de
        parceiro tecnico, CPF e CNPJ visiveis, os dois `obrigatorio = True` e
        NENHUMA regra condicional. Pessoa fisica tinha de inventar um CNPJ
        para o botao Enviar funcionar; pessoa juridica, um CPF. No
        CREDENCIAMENTO isso fechava a porta de entrada do parceiro.

        ⚠️ A trava mede os DOIS lados de proposito: o `AJUSTES` (que a carga
        aplica) e o banco (o que a internet le agora). Um sem o outro e meia
        verdade -- foi assim que 55 validacoes quase morreram em 11/11.
        """
        mod = _carregador()
        for codigo in ("PAGAMENTO_TECNICOS", "CREDENCIAMENTO"):
            ajuste = (mod.AJUSTES.get(codigo) or {}).get("campos") or {}
            for campo in ("cpf", "cnpj"):
                assert ajuste.get(campo, {}).get("obrigatorio") is False, (
                    "%s/%s: o ajuste nao desobriga, e a carga devolveria o "
                    "obrigatorio do Bitrix" % (codigo, campo))

        linhas = banco.varios(
            """SELECT f.codigo, c.nosso_nome, c.obrigatorio, c.validacao
                 FROM formulario_campo c
                 JOIN formulario f ON f.id = c.formulario_id
                WHERE f.codigo IN ('PAGAMENTO_TECNICOS', 'CREDENCIAMENTO')
                  AND c.nosso_nome IN ('cpf', 'cnpj')""")
        assert len(linhas) == 4, (
            "esperava os 4 documentos dos 2 formularios, achei %d" % len(linhas))
        for r in linhas:
            assert r["obrigatorio"] is False, (
                "%s/%s continua obrigatorio" % (r["codigo"], r["nosso_nome"]))
            # ⚠️ O CAMPO FICA INTEIRO, e isto e o pedido dele ao pe da letra:
            # *"somente preencheiveis"*. A validacao de FORMATO continua, e nao
            # ha contradicao -- ela so fala quando a pessoa escreve algo. Campo
            # vazio passa; CPF pela metade, nao. Tirar as duas coisas juntas
            # seria aceitar documento quebrado, que ele nao pediu.
            assert r["validacao"] == r["nosso_nome"], (
                "%s/%s perdeu a validacao de formato" % (r["codigo"],
                                                         r["nosso_nome"]))

    def test_quem_busca_cliente_bate_banco_x_script(self):
        """🔵 23/11, dele, sobre o botao Buscar: **tirar onde nao ha base**.

        🚨 O DEFEITO: `temBusca` era `ehNovo && validacao === 'cnpj'`, e
        `FORMATO_NOVO = None` poe os 16 em `novo` -- entao todo formulario com
        CNPJ ganhou o botao. O `cliente_por_documento` varre a tabela
        `cliente` (os clientes NOSSOS): parceiro tecnico, fornecedor e
        interessado em teste gratuito nunca estao la. O botao aparecia e a
        resposta certa era sempre "nao achou".

        ⚠️ A `FICHA_CADASTRAL` fica FORA de proposito: e a ficha de clientes
        NOVOS -- quem preenche, por definicao, ainda nao esta na base.
        """
        mod = _carregador()
        assert mod.BUSCA_CLIENTE == {
            "SUPORTE", "ADITIVO", "ADMINISTRATIVO", "FINANCEIRO", "RESCISAO",
            "SUBSTITUICAO",
        }
        no_banco = {
            r["codigo"]
            for r in banco.varios(
                "SELECT codigo FROM formulario WHERE busca_cliente")
        }
        assert no_banco == mod.BUSCA_CLIENTE, (
            "banco x script divergem: so no banco %s / so no script %s"
            % (sorted(no_banco - mod.BUSCA_CLIENTE),
               sorted(mod.BUSCA_CLIENTE - no_banco)))

    def test_a_definicao_publica_leva_o_busca_cliente(self):
        """🚨 O ELO QUE NENHUMA DAS DUAS TRAVAS ACIMA VE.

        A coluna pode estar certa no banco e certa no script, e a internet
        continuar sem saber: quem leva o dado a tela e o `SELECT` do
        `definicao()`. Campo novo nao entra sozinho na cadeia -- quem devolve,
        quem grava, quem le ([[feedback_campo_novo_nao_entra_sozinho]]).
        """
        from movizap import formularios
        assert formularios.definicao("suporte", so_ativo=False)[
            "busca_cliente"] is True
        assert formularios.definicao("pagamento-tecnicos", so_ativo=False)[
            "busca_cliente"] is False

    def test_o_derivador_de_etapas_pode_ser_IMPORTADO(self):''',
      "as 3 travas novas, dentro da TestACargaNaoApagaOQueEstaNoAr")

saida = t.replace("\n", "\r\n") if CRLF else t
p.write_bytes(saida.encode("utf-8"))
print("gravado:", p, len(saida), "bytes")
