# -*- coding: utf-8 -*-
"""Patch 29/10 (parte 10b): a suite do painel passa a guardar a regra NOVA.

🚨 Os 10 testes vermelhos nao eram defeito: eles guardavam o desenho de 22/10
(13 colunas, "Sem OS" primeiro, "Sem situacao" recebendo os tres casos, a frase
do `porque_nao_move`, a lista de formularios na resposta). Ele mudou o desenho
em 29/10, e teste que guarda regra morta nao se apaga -- se REESCREVE, dizendo
o que passou a valer e POR QUE a regra antiga caiu. Apagar deixaria o painel
sem trava nenhuma na distribuicao dos cards.
"""
import pathlib
import sys

MOVI = pathlib.Path("/home/claude/movizap_painel")


def trocar(caminho: pathlib.Path, velho: str, novo: str, rotulo: str) -> None:
    texto = caminho.read_text(encoding="utf-8")
    if novo and novo in texto:
        print(f"  = {rotulo}: ja aplicado")
        return
    if texto.count(velho) != 1:
        sys.exit(f"  ! {rotulo}: achei {texto.count(velho)} ocorrencias, "
                 f"esperava 1 -- PAREI sem gravar nada")
    caminho.write_text(texto.replace(velho, novo), encoding="utf-8")
    print(f"  + {rotulo}")


t = MOVI / "tests" / "teste_paineis.py"
print(t.name)

trocar(t, '''  · 🚨 **a coluna "Sem situação" existe e recebe os três casos** que não são
    uma das 11 situações: `situacao_id` nulo, zero, e um número que não está na
    lista. Em 22/10, **164 das 574 OS** do cache do FPSL estavam em `0` ou
    `NULL` -- sem essa coluna, desapareceriam da tela;''',
       '''  · 🚨 **as colunas são EXATAMENTE as 17 situações dele, na ordem dele**
    (29/10: *"qualquer aba fora dessas não deve estar no painel"* e *"as
    situações já estão na Ordem"*). ⚠️ Até 28/10 eram 13 -- as 11 situações de
    então mais "Sem OS" e "Sem situação" --, e as duas saíram porque o motivo
    de cada uma caiu no mesmo dia: a OS passou a nascer **automática no envio**
    (antes era por botão), e as 164 OS com situação 0/nula são de outras
    origens, não solicitações deste painel;
  · 🚨 **e o que não tem coluna é CONTADO, não escondido** (`fora_do_quadro`):
    solicitação sem OS ou com situação fora das 17 não cabe em coluna nenhuma,
    e sumir da tela é `M12`;''',
       "teste_paineis: cabecalho")

trocar(t, '''  · `pode_mover` é FALSO e traz o porquê: a rota que escreve `situacaoId` no
    Harmonit ainda não existe, e oferecer o gesto sem gravar seria pior.''',
       '''  · `pode_mover` é FALSO: a rota que escreve `situacaoId` no Harmonit ainda
    não existe, e oferecer o gesto sem gravar seria pior. ⚠️ A FRASE que
    explicava isso na tela saiu em 29/10, a pedido dele (*"os comentários tbm
    devem sumir dali"*) -- o comportamento não mudou, e é o que este teste
    guarda.''',
       "teste_paineis: cabecalho do pode_mover")

trocar(t, '''def teste_os_quatro_da_operacao_sao_os_que_ele_nomeou():
    codigos = [f["codigo"] for f in paineis.quadro("operacao")["formularios"]]
    assert set(codigos) == {"SUPORTE", "DEMONSTRACAO", "TESTE_GRATUITO",
                            "CREDENCIAMENTO"}''',
       '''def teste_os_quatro_da_operacao_sao_os_que_ele_nomeou():
    """⚠️ Lido do BANCO, não da resposta do painel: a lista de formulários saiu
    do quadro em 29/10 (ele mandou tirar da tela), mas o mapa continua sendo o
    dele e continua tendo de ser estes quatro."""
    codigos = {r["codigo"] for r in banco.varios(
        "SELECT codigo FROM formulario WHERE painel = 'operacao'")}
    assert codigos == {"SUPORTE", "DEMONSTRACAO", "TESTE_GRATUITO",
                       "CREDENCIAMENTO"}


def teste_a_resposta_do_painel_nao_traz_mais_a_lista_de_formularios():
    """🔵 29/10: *"os comentários tbm devem sumir dali"* -- a lista com a
    contagem de campos saiu da tela, e o backend parou de mandá-la."""
    assert "formularios" not in paineis.quadro("operacao")''',
       "teste_paineis: os quatro, lidos do banco")

trocar(t, '''def teste_as_colunas_sao_as_11_situacoes_mais_duas():
    q = paineis.quadro("operacao")
    assert len(q["colunas"]) == len(paineis.SITUACOES) + 2
    # 🚨 A ORDEM É O DESENHO: "Sem OS" primeiro, porque é de onde a OS nasce.
    assert q["colunas"][0]["chave"] == "sem_os"
    assert q["colunas"][1]["chave"] == "sem_situacao"
    assert q["colunas"][2]["situacao_id"] == 38''',
       '''def teste_as_colunas_sao_exatamente_as_dezessete_dele():
    """🔵 29/10: *"qualquer aba fora dessas não deve estar no painel"*."""
    q = paineis.quadro("operacao")
    assert len(paineis.SITUACOES) == 17
    assert len(q["colunas"]) == 17
    # 🚨 Toda coluna É uma situação -- não há mais coluna sem `situacao_id`.
    assert all(c["situacao_id"] for c in q["colunas"])


def teste_a_ordem_das_colunas_e_a_dele_e_nao_alfabetica_nem_por_id():
    """🔵 *"as situações já estão na Ordem"* -- a ordem é o FLUXO da operação.

    🚨 Este teste existe porque ordem é a coisa mais fácil de perder: qualquer
    `sorted()` bem-intencionado em cima de `SITUACOES` destruiria o desenho sem
    quebrar nada visível.
    """
    q = paineis.quadro("operacao")
    titulos = [c["titulo"] for c in q["colunas"]]
    assert titulos[0] == "Novo Solicitação 1ª"
    assert titulos[1] == "Pendente de ação da Movisat"
    assert titulos[-1] == "Contratual"
    assert titulos != sorted(titulos)
    ids = [c["situacao_id"] for c in q["colunas"]]
    assert ids != sorted(ids)
    # E o começo do fluxo é a situação em que a OS nasce.
    assert ids[0] == 38


def teste_a_solicitacao_sem_os_e_contada_em_vez_de_escondida(formulario_de_operacao):
    """🚨 `M12`: a coluna "Sem OS" saiu, e o card não tem onde cair -- mas o
    número aparece. Sumir em silêncio seria o defeito."""
    ident = solicitar(formulario_de_operacao)
    q = paineis.quadro("operacao")
    nos_cards = [c["id"] for coluna in q["colunas"] for c in coluna["cards"]]
    assert ident not in nos_cards
    assert q["fora_do_quadro"]["sem_os"] >= 1


@pytest.mark.parametrize("situacao", [None, 0, 99999])
def teste_situacao_fora_das_dezessete_e_contada_com_o_numero_cru(
        formulario_de_operacao, situacao):
    """Nulo (nunca lida), zero (o Harmonit respondeu 0) e um número que não
    está na lista. ⚠️ O número cru aparece, nunca um rótulo inventado -- é a
    régua do grid do FPSL."""
    solicitar(formulario_de_operacao, os_id=99901, situacao_id=situacao)
    fora = paineis.quadro("operacao")["fora_do_quadro"]
    assert fora["situacao_fora"] >= 1
    if situacao is not None:
        assert situacao in fora["situacoes"]''',
       "teste_paineis: as 17, a ordem e o que fica fora")

trocar(t, '''def teste_solicitacao_sem_os_fica_na_primeira_coluna(formulario_de_operacao):
    ident = solicitar(formulario_de_operacao)
    q = paineis.quadro("operacao")
    sem_os = next(c for c in q["colunas"] if c["chave"] == "sem_os")
    assert ident in [c["id"] for c in sem_os["cards"]]


@pytest.mark.parametrize("situacao", [None, 0, 99999])
def teste_os_tres_casos_sem_situacao_caem_na_mesma_coluna(
        formulario_de_operacao, situacao):
    """🚨 Nulo (nunca lida), zero (o Harmonit respondeu 0) e um número fora da
    lista das 11. Em 22/10, 127 OS estavam em `0` e 37 em `NULL`."""
    ident = solicitar(formulario_de_operacao, os_id=99901, situacao_id=situacao)
    q = paineis.quadro("operacao")
    coluna = next(c for c in q["colunas"] if c["chave"] == "sem_situacao")
    assert ident in [c["id"] for c in coluna["cards"]]


''', '''''', "teste_paineis: saem os dois testes das colunas que morreram")

trocar(t, '''def teste_o_card_leva_a_os_e_a_situacao_crua(formulario_de_operacao):
    """A solicitação E a OS lado a lado, como ele pediu -- e a situação crua à
    vista, nunca um rótulo inventado."""
    ident = solicitar(formulario_de_operacao, os_id=99903, numero_ordem="17042",
                      situacao_id=0)''',
       '''def teste_o_card_leva_a_os_e_a_situacao_crua(formulario_de_operacao):
    """A solicitação E a OS lado a lado, como ele pediu -- e a situação à vista.

    ⚠️ Com uma situação DAS 17: até 28/10 este teste usava `situacao_id = 0`,
    que ia para a coluna "Sem situação". Ela não existe mais, e com zero o card
    não teria coluna nenhuma.
    """
    ident = solicitar(formulario_de_operacao, os_id=99903, numero_ordem="17042",
                      situacao_id=15746)''',
       "teste_paineis: o card com situacao das 17")

trocar(t, '''    assert card["numero_ordem"] == "17042"
    assert card["situacao_id"] == 0''',
       '''    assert card["numero_ordem"] == "17042"
    assert card["situacao_id"] == 15746''',
       "teste_paineis: a situacao do card")

trocar(t, '''def teste_solicitacao_de_outro_painel_nao_entra(formulario_de_operacao):
    """O CES é de Pós venda: não pode aparecer na Operação."""
    ces = formularios.definicao("ces", so_ativo=False)
    r = formularios.registrar(ces, {"CONTACT_NAME": "zz Painel outro"})
    try:
        ids = [c["id"] for coluna in paineis.quadro("operacao")["colunas"]
               for c in coluna["cards"]]
        assert r["id"] not in ids
    finally:''',
       '''def teste_solicitacao_de_outro_painel_nao_entra(formulario_de_operacao):
    """O CES é de Pós venda: não pode aparecer na Operação -- nem nos cards,
    nem na conta do que ficou fora."""
    ces = formularios.definicao("ces", so_ativo=False)
    antes = paineis.quadro("operacao")["fora_do_quadro"]["sem_os"]
    r = formularios.registrar(ces, {"CONTACT_NAME": "zz Painel outro"})
    try:
        q = paineis.quadro("operacao")
        ids = [c["id"] for coluna in q["colunas"] for c in coluna["cards"]]
        assert r["id"] not in ids
        # ⚠️ E nem na contagem: ela é só do painel, não do banco todo.
        assert q["fora_do_quadro"]["sem_os"] == antes
    finally:''',
       "teste_paineis: outro painel nem na contagem")

trocar(t, '''def teste_mover_ainda_nao_existe_e_o_painel_explica():
    q = paineis.quadro("operacao")
    assert q["pode_mover"] is False
    assert "Harmonit" in q["porque_nao_move"]''',
       '''def teste_mover_ainda_nao_existe_e_a_frase_saiu_da_tela():
    """⚠️ Duas coisas, e elas são diferentes: mover continua não existindo
    (`pode_mover` falso, e é o que impede o `draggable`), e a FRASE que
    explicava isso saiu em 29/10 a pedido dele."""
    q = paineis.quadro("operacao")
    assert q["pode_mover"] is False
    assert "porque_nao_move" not in q''',
       "teste_paineis: mover e a frase")

print()
print("ok")
