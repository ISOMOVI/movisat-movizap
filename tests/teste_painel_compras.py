# -*- coding: utf-8 -*-
"""O PAINEL DE COMPRAS NO BANCO — a migração 122 medida, 27/11.

🔵 Ele, 27/11: *"proponha um novo de compras, sem vinculo de OS somente por
formularios"*, *"nao precisa propor colunas alem da primeira: nova
solicitacoes"*, *"sera somente interno"*.

🚨 **A COLUNA É UMA, E ESTE TESTE PRENDE A LISTA INTEIRA, POSIÇÃO POR
POSIÇÃO** -- o molde é o `teste_painel_contratual.py`. Afirmar *"tem a coluna
Nova solicitação"* deixaria passar uma segunda coluna que ninguém pediu, e
coluna a mais num painel de uma coluna muda o gesto: o `<select>` de mover
passa a ter destino.

⚠️ Nenhum teste aqui escreve. Todos leem o estado que a 122 deixou.

Roda:  venv/bin/python -m pytest tests/teste_painel_compras.py
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, "/home/claude/movizap_painel")
pytest.importorskip("psycopg")

from movizap import banco, paineis  # noqa: E402

ENV = Path("/home/claude/movizap_painel/.env")
pytestmark = pytest.mark.skipif(
    not ENV.exists() or "MOVIZAP_DB_SENHA" not in ENV.read_text(encoding="utf-8"),
    reason="banco nao configurado no .env")


@pytest.fixture(scope="module", autouse=True)
def base():
    banco.abrir()
    yield


class TestAAba:
    def test_a_aba_existe_ligada_e_no_painel_compras(self):
        linha = banco.um(
            """SELECT painel, titulo, ordem, ativo FROM painel_aba
                WHERE codigo_tela = 'PNL_1.7'""")
        assert linha, "a aba da PNL_1.7 não está no banco (migração 122)"
        assert linha["painel"] == "compras"
        assert linha["titulo"] == "Compras"
        assert linha["ativo"] is True

    def test_e_ela_e_a_UNICA_aba_do_painel_compras(self):
        """⚠️ Ele pediu uma. Aba a mais desenharia uma tira de abas num painel
        que não tem para onde ir."""
        quantas = banco.um(
            "SELECT count(*) n FROM painel_aba WHERE painel = 'compras'")["n"]
        assert quantas == 1


class TestAColunaUnica:
    def test_a_lista_de_colunas_INTEIRA(self):
        colunas = banco.varios(
            """SELECT e.titulo, e.ordem, e.ativo, e.final,
                      e.depois_da_situacao, e.recebe_situacao
                 FROM pipeline_etapa e
                 JOIN painel_aba a ON a.id = e.aba_id
                WHERE a.codigo_tela = 'PNL_1.7'
                ORDER BY e.ordem, e.id""")
        # 🔵 27/11, DEPOIS DO MOCKUP: ele escolheu as três seguintes --
        # *"Em cotação + Aprovado + Comprado"* (migração 123).
        # 🚨 A LISTA INTEIRA, POSIÇÃO POR POSIÇÃO, e eu a ESTENDI em vez de
        # afrouxar: afirmar *"tem a coluna Em cotação"* deixaria passar uma
        # quinta que ninguém pediu, e coluna a mais muda o GESTO -- o
        # `<select>` de mover ganha um destino que não existe no desenho dele.
        assert [c["titulo"] for c in colunas] == [
            "Nova solicitação", "Em cotação", "Aprovado", "Comprado"]
        assert all(c["ativo"] for c in colunas)
        # 🚨 `final` SÓ NA ÚLTIMA. As três primeiras não são desfecho -- a
        # primeira é onde o card nasce, e as duas do meio são caminho. É o
        # `final` que diz ao quadro onde o card termina: marcar `Em cotação`
        # como final faria o contador de *"parado nesta etapa"* fechar no
        # meio do caminho.
        assert [c["final"] for c in colunas] == [False, False, False, True]
        # ⚠️ E as duas colunas de situação do ERP ficam NULAS nas quatro:
        # preencher qualquer uma ligaria o semeador de OS a este painel, que
        # é justamente o *"sem vínculo de OS"* dele.
        assert all(c["depois_da_situacao"] is None for c in colunas)
        assert all(c["recebe_situacao"] is None for c in colunas)

    def test_o_quadro_monta_e_diz_Compras(self):
        """🚨 Pela função que a rota usa, não pela tabela.

        Medido em 27/11: `paineis.PAINEIS` **não** precisou de `'compras'` --
        aquele dicionário serve só a rota antiga `/api/paineis/{painel}`, e
        este painel usa `/api/paineis/aba/{codigo}`. Este teste é o que prova
        que a decisão de não tocá-lo está certa.
        """
        q = paineis.quadro_da_aba("PNL_1.7")
        assert q["painel"] == "compras"
        assert q["titulo"] == "Compras"
        # 🔵 27/11: as quatro, pela função que a rota usa.
        assert [c["titulo"] for c in q["colunas"]] == [
            "Nova solicitação", "Em cotação", "Aprovado", "Comprado"]
        # 🚨 E O `<select>` DE MOVER PASSA A TER DESTINO: a tela só o desenha
        # com mais de uma etapa (`etapas.length > 1`). Com uma só ele não
        # aparecia -- e é por isso que a ajuda da tela, que prometia
        # *"arraste o card"*, mentia em Compras até hoje.
        assert len(q["etapas"]) == 4
        assert q["abas"] == [{"codigo_tela": "PNL_1.7", "titulo": "Compras"}]


class TestOFormulario:
    def test_o_COMPRAS_nasceu_desligado_interno_e_sem_OS(self):
        f = banco.um(
            """SELECT codigo, slug, titulo, setor, ativo, gera_os, painel,
                      interno, formato, bitrix_id, etapa_destino_id
                 FROM formulario WHERE codigo = 'COMPRAS'""")
        assert f, "o formulário COMPRAS não está no banco (migração 122)"
        assert f["slug"] == "compras"
        # ⚠️ O título é a palavra DELE: *"Sugestão de compras"*.
        assert f["titulo"] == "Sugestão de compras"
        assert f["painel"] == "compras"
        assert f["interno"] is True
        # 🚨 O *"sem vínculo de OS"* dele, escrito no banco.
        assert f["gera_os"] is False
        # 🚨 NASCE DESLIGADO. Quem liga formulário é ele, pela FRM_1.1 -- e um
        # teste que aceitasse `ativo = true` deixaria de acusar o dia em que
        # alguém ligasse um formulário no lugar dele.
        assert f["ativo"] is False
        # ⚠️ Não vem do Bitrix: foi `INSERT` direto, e não
        # `gravar_definicao()`, que é idempotente pelo `bitrix_id`.
        assert f["bitrix_id"] is None

    def test_o_destino_aponta_para_a_coluna_de_compras(self):
        """🚨 `etapa_destino_id` é a ÚNICA coluna que faz o envio virar card.

        Sem ela o envio grava a solicitação e o painel fica vazio para sempre
        -- e foi exatamente o que ele viu em 11/11 com o aditivo.
        """
        destino = banco.um(
            """SELECT a.codigo_tela, e.titulo
                 FROM formulario f
                 JOIN pipeline_etapa e ON e.id = f.etapa_destino_id
                 JOIN painel_aba a ON a.id = e.aba_id
                WHERE f.codigo = 'COMPRAS'""")
        assert destino, "o COMPRAS não tem etapa de destino"
        assert destino["codigo_tela"] == "PNL_1.7"
        assert destino["titulo"] == "Nova solicitação"

    def test_os_quatro_campos_na_ordem_e_o_VALOR_logo_depois(self):
        """🚨 **DOIS CAMPOS PARA PREENCHER**, decisão dele depois de eu propor
        oito: *"não precisa de setor, só de um campo de justificativa e um
        campo com anexo para Sugestão de compras - por enquanto"*. O terceiro é
        o solicitante, que a rota injeta.

        🚨 **E A CHAVE É `SUGESTAO`, NÃO `JUSTIFICATIVA`.** `valores` é `jsonb`
        e ordena a chave por TAMANHO: com 13 letras, `JUSTIFICATIVA` perdia
        para `CONTACT_NAME` (12) e o resumo do card repetia o nome que já é o
        título. O rótulo na tela continua "Justificativa".
        """
        campos = banco.varios(
            """SELECT nome, rotulo, tipo, obrigatorio, visivel
                 FROM formulario_campo
                WHERE formulario_id = (SELECT id FROM formulario
                                        WHERE codigo = 'COMPRAS')
                ORDER BY ordem, id""")
        # 🔵 27/11, DEPOIS DO MOCKUP: ele pediu o valor estimado, e **só o
        # campo** -- o painel não soma nem ordena por ele (migração 123).
        assert [c["nome"] for c in campos] == ["SUGESTAO", "VALOR", "ANEXO",
                                               "CONTACT_NAME"]
        assert [c["rotulo"] for c in campos] == ["Justificativa",
                                                 "Valor estimado", "Anexo",
                                                 "Solicitante"]
        # ⚠️ `string`, NÃO `double`: o `double` da casa é CNPJ, CPF, RG e
        # quantidade, e valida como número -- *"R$ 184,00"* seria recusado.
        assert [c["tipo"] for c in campos] == ["text", "string", "file",
                                               "string"]
        # ⚠️ O valor NÃO é obrigatório: quem pede nem sempre sabe o preço, e
        # campo obrigatório que ninguém consegue preencher vira número
        # inventado -- pior que vazio, porque tem cara de dado.
        assert [c["obrigatorio"] for c in campos] == [True, False, False, True]
        # 🚨 E A ORDEM DAS CHAVES É O QUE DECIDE O RESUMO, não a coluna
        # `ordem`: `valores` é `jsonb` e ordena por TAMANHO de chave.
        # `VALOR` (5) < `SUGESTAO` (8) < `CONTACT_NAME` (12), então o resumo
        # lidera com o preço. 📏 Provado na cópia em 27/11:
        #   'R$ 184,00 · Cabo de rede cat6, 20 metros, para o rack da sala 2'
        assert len("VALOR") < len("SUGESTAO") < len("CONTACT_NAME")
        # 🚨 TODOS VISÍVEIS. Campo invisível SOME no `validar` -- *"escondido
        # some, não vira vazio"* --, e o solicitante invisível faria o card
        # fechado escrever `cliente ?, fora do nosso cadastro`.
        assert all(c["visivel"] for c in campos)


class TestOVocabularioDoBanco:
    def test_os_DOIS_CHECK_conhecem_compras(self):
        """🚨 São dois, e eram dois desde a 075/092: `painel_aba` e
        `formulario`. Alargar só um deixaria metade da migração falhando."""
        for nome in ("painel_aba_painel_conhecido", "formulario_painel_check"):
            bruto = banco.um(
                "SELECT pg_get_constraintdef(oid) d FROM pg_constraint "
                "WHERE conname = %s", (nome,))
            assert bruto, f"o CHECK {nome} não existe"
            assert "'compras'" in bruto["d"], f"{nome} não conhece 'compras'"
