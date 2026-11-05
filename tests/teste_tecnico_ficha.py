"""A ficha do técnico, os dez serviços e o credenciamento — `TEC_1.1` (04/11).

🚨 ESCREVE EM TABELAS DE PRODUÇÃO (`contato`, `contato_telefone`,
`tecnico_ficha`, `tecnico_preco`, `servico_tecnico`, `atendente`) e apaga tudo
no fim. Marcas deste teste: contatos cujo nome começa com `Zz Teste Tecnico`,
login `zz_teste_tec_`, serviço `Zz Servico De Teste`, telefone
`+5518977770001`.

🚨 **O CATÁLOGO DOS DEZ NÃO É TOCADO.** Ele é dado de produção (migração 085), e
um teste que renomeasse ou desativasse "Instalação" mudaria a ficha de todos os
técnicos. Para exercitar criar/atualizar serviço, o teste cria um **décimo
primeiro**, com nome marcado, e o apaga.

O que estes testes guardam:
  · técnico SEM ficha continua aparecendo na lista (eram 303 contatos e 0
    fichas em 04/11 — listar só os fichados abriria a tela vazia);
  · `None` de booleano NÃO vira `False`: "não respondeu se tem ponto fixo" e
    "disse que não tem" são fatos diferentes;
  · preço ausente e preço nulo são "não oferece"; **zero é zero**, e continua
    diferente de ausente;
  · `definir_precos` NÃO apaga o que não veio na chamada;
  · credenciar EXIGE endereço e pelo menos um preço — senão a tela de KM e a de
    orçamento recebem um técnico marcado como pronto e falham;
  · a ficha NÃO muda o tipo do contato: contato que não é técnico é recusado;
  · telefone que já é de outro cadastro RECUSA (a trava de 02/10);
  · `uf` só aceita sigla: "São Paulo" não vira "Sã";
  · **escrever sem a chave `TEC_1.2` é 403, e ler com só `atendimento` é 200.**
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, "/home/claude/movizap_painel")
pytest.importorskip("psycopg")

from fastapi.testclient import TestClient  # noqa: E402

from movizap import auth, banco, main, operacao, tecnico_ficha  # noqa: E402
from movizap.config import settings  # noqa: E402
from movizap.operacao import DadoInvalido  # noqa: E402

ENV = Path("/home/claude/movizap_painel/.env")
pytestmark = pytest.mark.skipif(
    not ENV.exists() or "MOVIZAP_DB_SENHA" not in ENV.read_text(encoding="utf-8"),
    reason="banco nao configurado no .env")

LOGIN = "zz_teste_tec_"
NOME = "Zz Teste Tecnico"
SERVICO = "Zz Servico De Teste"
TEL = "+5518977770001"


def limpar():
    banco.executar(
        """DELETE FROM tecnico_preco WHERE contato_id IN
            (SELECT id FROM contato WHERE nome LIKE %s)""", (NOME + "%",))
    banco.executar(
        """DELETE FROM tecnico_ficha WHERE contato_id IN
            (SELECT id FROM contato WHERE nome LIKE %s)""", (NOME + "%",))
    banco.executar(
        """DELETE FROM contato_telefone WHERE contato_id IN
            (SELECT id FROM contato WHERE nome LIKE %s)""", (NOME + "%",))
    banco.executar("DELETE FROM contato WHERE nome LIKE %s", (NOME + "%",))
    banco.executar("DELETE FROM tecnico_preco WHERE servico_id IN "
                   "(SELECT id FROM servico_tecnico WHERE nome LIKE %s)",
                   (SERVICO + "%",))
    banco.executar("DELETE FROM servico_tecnico WHERE nome LIKE %s", (SERVICO + "%",))
    banco.executar("DELETE FROM atendente WHERE login LIKE %s", (LOGIN + "%",))


def _contato(nome: str, relacao: str = "tecnico") -> int:
    with banco.cursor() as cur:
        cur.execute(
            """INSERT INTO contato (nome, relacao, origem, ativo)
               VALUES (%s, %s, 'movizap', true) RETURNING id""", (nome, relacao))
        return cur.fetchone()["id"]


@pytest.fixture(scope="module", autouse=True)
def base():
    banco.abrir()
    limpar()
    pessoa = operacao.criar_atendente(NOME + " Validador", LOGIN + "1",
                                      LOGIN + "1@teste.invalid")
    tecnico = _contato(NOME + " Um")
    outro = _contato(NOME + " Dois")
    nao_tecnico = _contato(NOME + " Cliente", relacao="cliente")
    yield {"pessoa": pessoa, "tecnico": tecnico, "outro": outro,
           "nao_tecnico": nao_tecnico}
    # Reabre antes de limpar: o `TestClient` roda o lifespan e fecha o pool.
    # Não se chama `fechar()` aqui — ver o aviso no `teste_orcamento_consulta`.
    banco.abrir()
    limpar()


# ---------------------------------------------------------------------------
# O CATÁLOGO
# ---------------------------------------------------------------------------

class TestCatalogo:
    def test_os_dez_estao_no_ar_na_ordem_dele(self):
        """🔵 A lista e a ordem são dele (04/11), com `Substituição R.` e
        `Substituição I.` escritas por extenso como ele confirmou."""
        nomes = [s["nome"] for s in tecnico_ficha.servicos()]
        for esperado in ("Instalação", "Retirada", "Manutenção Local",
                         "Manutenção Troca", "Substituição Retirada",
                         "Substituição Instalação", "Socorro", "Laudo Técnico",
                         "Treinamento", "Acompanhamento"):
            assert esperado in nomes, f"{esperado} saiu do catálogo"
        dele = [n for n in nomes if n.startswith(("Instalação", "Retirada",
                                                  "Manutenção", "Substituição",
                                                  "Socorro", "Laudo",
                                                  "Treinamento",
                                                  "Acompanhamento"))]
        assert dele[:10] == ["Instalação", "Retirada", "Manutenção Local",
                             "Manutenção Troca", "Substituição Retirada",
                             "Substituição Instalação", "Socorro",
                             "Laudo Técnico", "Treinamento", "Acompanhamento"]

    def test_nome_repetido_recusa_com_frase(self):
        assert tecnico_ficha.criar_servico(SERVICO + " A")["nome"] == SERVICO + " A"
        with pytest.raises(DadoInvalido) as e:
            tecnico_ficha.criar_servico(SERVICO + " A")
        assert "Já existe" in str(e.value)

    def test_desativar_nao_apaga_o_preco(self, base):
        """⚠️ Serviço aposentado sai da ficha de quem ainda não precificou e
        continua explicando os preços antigos."""
        servico = tecnico_ficha.criar_servico(SERVICO + " B")
        tecnico_ficha.definir_precos(base["tecnico"], {str(servico["id"]): 5000})
        tecnico_ficha.atualizar_servico(servico["id"], servico["nome"],
                                        servico["ordem"], False)
        guardado = banco.um(
            "SELECT custo_centavos FROM tecnico_preco "
            " WHERE contato_id = %s AND servico_id = %s",
            (base["tecnico"], servico["id"]))
        assert guardado["custo_centavos"] == 5000
        # E continua visível na ficha de quem tem preço nele, mesmo inativo.
        precos = tecnico_ficha.ficha(base["tecnico"])["precos"]
        assert servico["id"] in [p["servico_id"] for p in precos]


# ---------------------------------------------------------------------------
# A LISTA
# ---------------------------------------------------------------------------

class TestLista:
    def test_tecnico_sem_ficha_aparece(self, base):
        """🚨 O defeito que isto impede: 303 contatos de técnico e 0 fichas em
        04/11. Listar só os fichados abriria a tela vazia e pareceria quebrada."""
        achados = tecnico_ficha.listar(busca=NOME + " Dois")["itens"]
        assert [i["contato_id"] for i in achados] == [base["outro"]]
        assert achados[0]["tem_ficha"] is False
        assert achados[0]["estado"] is None

    def test_sem_ficha_conta_o_filtro_inteiro(self, base):
        r = tecnico_ficha.listar(busca=NOME)
        assert r["sem_ficha"] >= 1
        assert r["total"] >= 2

    def test_contato_que_nao_e_tecnico_nunca_entra(self, base):
        achados = tecnico_ficha.listar(busca=NOME + " Cliente")["itens"]
        assert achados == []

    def test_filtro_de_estado_invalido_recusa_com_frase(self):
        with pytest.raises(DadoInvalido):
            tecnico_ficha.listar(estado="aprovadissimo")


# ---------------------------------------------------------------------------
# A FICHA
# ---------------------------------------------------------------------------

class TestFicha:
    def test_ficha_nova_traz_o_catalogo_inteiro_sem_preco(self, base):
        """🚨 As dez linhas vêm sempre. Devolver só as preenchidas faria a
        ficha nova nascer sem onde digitar."""
        achado = tecnico_ficha.ficha(base["outro"])
        assert achado["ficha"] is None
        assert len(achado["precos"]) >= 10
        assert all(p["custo_centavos"] is None for p in achado["precos"]
                   if p["nome"] in ("Socorro", "Treinamento"))

    def test_booleano_nao_respondido_continua_nulo(self, base):
        """🚨 `None` não pode virar `False`. Achatar faria a ficha afirmar o
        que ninguém respondeu — o mesmo defeito do `0` ≠ `NULL` da situação."""
        tecnico_ficha.salvar(base["tecnico"], {"nome_fantasia": NOME + " Ltda"})
        ficha = tecnico_ficha.ficha(base["tecnico"])["ficha"]
        assert ficha["ponto_fixo"] is None
        assert ficha["vai_ao_cliente"] is None
        tecnico_ficha.salvar(base["tecnico"], {"ponto_fixo": False})
        assert tecnico_ficha.ficha(base["tecnico"])["ficha"]["ponto_fixo"] is False

    def test_preenche_os_tem_tres_estados(self, base):
        """🔵 04/11, no fechamento: *"crie um campo de flag, junto com os do
        deslocamento chamado 'Preenche OS'"* (migração 088).

        🚨 Nasce NULO, e isso é o ponto: `false` por default diria, das 287
        fichas, que nenhum técnico preenche OS — afirmação que ninguém fez.
        """
        contato = _contato(NOME + " Treze")
        tecnico_ficha.salvar(contato, {"nome_fantasia": NOME + " Treze Ltda"})
        assert tecnico_ficha.ficha(contato)["ficha"]["preenche_os"] is None
        tecnico_ficha.salvar(contato, {"preenche_os": True})
        assert tecnico_ficha.ficha(contato)["ficha"]["preenche_os"] is True
        tecnico_ficha.salvar(contato, {"preenche_os": False})
        assert tecnico_ficha.ficha(contato)["ficha"]["preenche_os"] is False

    def test_vazio_vira_nulo_e_nao_string_vazia(self, base):
        tecnico_ficha.salvar(base["tecnico"], {"bairro": "   "})
        assert tecnico_ficha.ficha(base["tecnico"])["ficha"]["bairro"] is None

    def test_documento_guarda_so_digitos(self, base):
        tecnico_ficha.salvar(base["tecnico"], {"cnpj": "12.345.678/0001-95"})
        assert tecnico_ficha.ficha(base["tecnico"])["ficha"]["cnpj"] == "12345678000195"

    def test_documento_longo_recusa_com_frase_e_nao_trunca(self, base):
        with pytest.raises(DadoInvalido) as e:
            tecnico_ficha.salvar(base["tecnico"], {"cnpj": "1" * 20})
        assert "dígitos" in str(e.value)

    def test_uf_sobe_para_maiuscula(self, base):
        tecnico_ficha.salvar(base["tecnico"], {"uf": "sp"})
        assert tecnico_ficha.ficha(base["tecnico"])["ficha"]["uf"] == "SP"

    def test_uf_por_extenso_recusa_em_vez_de_truncar(self, base):
        """🚨 `uf` é `varchar(2)`. Truncar "São Paulo" em "Sã" gravaria lixo
        com cara de dado."""
        with pytest.raises(DadoInvalido):
            tecnico_ficha.salvar(base["tecnico"], {"uf": "São Paulo"})

    def test_a_forma_de_pagamento_so_aceita_as_tres(self, base):
        """🔵 04/11: *"Banco ajuste para dados de pagamento, pode ser TED, PIX,
        ou boleto"*. Era aqui que vivia o teste do titular PF/PJ, que saiu com
        o bloco antigo (migração 086).

        🚨 OS TRÊS VALORES SÃO OS MESMOS DO FORMULÁRIO, e é isso que ele quis
        com *"ajuste no formulario tbm, o mesmo formato. ai amarra eles"*."""
        tecnico_ficha.salvar(base["tecnico"], {"pagamento_forma": "PIX"})
        assert tecnico_ficha.ficha(base["tecnico"])["ficha"]["pagamento_forma"] == "pix"
        with pytest.raises(DadoInvalido) as e:
            tecnico_ficha.salvar(base["tecnico"], {"pagamento_forma": "cheque"})
        assert "TED, PIX ou boleto" in str(e.value)

    def test_os_dados_de_pagamento_sao_texto_livre(self, base):
        """⚠️ Chave PIX é CPF, CNPJ, telefone, e-mail ou chave aleatória, e
        conta é banco + agência + conta. Validar formato recusaria o que o
        técnico mandou do jeito que ele tem."""
        tecnico_ficha.salvar(base["tecnico"], {
            "pagamento_forma": "ted",
            "pagamento_dados": "Banco 237, ag. 1234, cc 56789-0, titular Zz Ltda"})
        ficha = tecnico_ficha.ficha(base["tecnico"])["ficha"]
        assert "ag. 1234" in ficha["pagamento_dados"]

    def test_a_forma_do_formulario_bate_com_a_da_ficha(self):
        """🚨 O ELO QUE "AMARRA ELES": os `value` que o formulário grava têm de
        ser exatamente os que a coluna aceita. Se alguém mexer nas opções do
        formulário e esquecer a ficha, a solicitação chegaria com um valor que
        `salvar()` recusa — e o credenciamento pararia no meio, sem causa
        aparente."""
        formulario = banco.um("SELECT id FROM formulario WHERE codigo = %s",
                              (tecnico_ficha.CODIGO_DO_FORMULARIO,))
        if not formulario:
            pytest.skip("o formulário CREDENCIAMENTO não está neste banco")
        campo = banco.um(
            "SELECT opcoes, rotulo FROM formulario_campo "
            " WHERE formulario_id = %s AND nosso_nome = %s",
            (formulario["id"], "titular-da-conta-e-pessoa-fisica-ou-juri"))
        assert campo, "o campo da forma de pagamento saiu do formulário"
        valores = {o["value"] for o in (campo["opcoes"] or [])}
        assert valores == set(tecnico_ficha.FORMAS_DE_PAGAMENTO), (
            f"o formulário oferece {sorted(valores)} e a ficha aceita "
            f"{sorted(tecnico_ficha.FORMAS_DE_PAGAMENTO)}")
        assert campo["rotulo"] == "Forma de pagamento"

    def test_a_ficha_nao_muda_o_tipo_do_contato(self, base):
        """🚨 Quem é técnico se decide na ficha da conversa, que tem travas
        próprias. Criar ficha em cima de um contato de cliente mudaria o tipo
        dele pela porta de trás."""
        with pytest.raises(DadoInvalido) as e:
            tecnico_ficha.salvar(base["nao_tecnico"], {"cidade": "Presidente Prudente"})
        assert "não é do tipo técnico" in str(e.value)
        assert banco.um("SELECT relacao FROM contato WHERE id = %s",
                        (base["nao_tecnico"],))["relacao"] == "cliente"

    def test_contato_inexistente_recusa(self):
        with pytest.raises(DadoInvalido):
            tecnico_ficha.salvar(0, {"cidade": "Lugar Nenhum"})

    def test_TODA_coluna_da_ficha_e_lida_e_gravada(self):
        """🚨 O ELO QUE SUÍTE VERDE NÃO VÊ — e que esta entrega já tropeçou.

        `km_valor_centavos` nasceu fora da tupla `CAMPOS`: `salvar()` o gravava
        (vem do dict de valores) e `ficha()` não o lia (vem da tupla). O valor
        entrava no banco e a tela nunca o via — nada falhava, nada no log.

        Este teste compara a tupla com as COLUNAS DE VERDADE, então coluna nova
        na migração que ninguém pendurar aqui reprova na hora.
        """
        reais_ = {c["column_name"] for c in banco.varios(
            "SELECT column_name FROM information_schema.columns "
            " WHERE table_name = 'tecnico_ficha'")}
        # Estas são do registro, não da ficha: ninguém as digita.
        de_dentro = {"contato_id", "estado", "estado_em", "estado_por",
                     "estado_nota", "solicitacao_id", "criado_em",
                     "atualizado_em"}
        esperadas = reais_ - de_dentro
        assert set(tecnico_ficha.CAMPOS) == esperadas, (
            "a tupla CAMPOS e as colunas de tecnico_ficha divergiram: "
            f"só no banco {sorted(esperadas - set(tecnico_ficha.CAMPOS))}, "
            f"só na tupla {sorted(set(tecnico_ficha.CAMPOS) - esperadas)}")

    def test_o_km_da_ficha_volta_escrito_e_em_centavos(self, base):
        """⚠️ Os dois: `km_valor_centavos` é o que o campo de edição manda de
        volta, e `km_valor_texto` é o que se lê. Dividir por 100 na tela é o
        que a aba de orçamentos já proibiu."""
        tecnico_ficha.salvar(base["tecnico"], {"km_valor_centavos": 150})
        ficha = tecnico_ficha.ficha(base["tecnico"])["ficha"]
        assert ficha["km_valor_centavos"] == 150
        assert ficha["km_valor_texto"] == "1,50"


# ---------------------------------------------------------------------------
# OS PREÇOS
# ---------------------------------------------------------------------------

class TestPrecos:
    def _id(self, nome: str) -> int:
        return next(s["id"] for s in tecnico_ficha.servicos() if s["nome"] == nome)

    def test_zero_e_diferente_de_nao_oferece(self, base):
        """⚠️ Serviço de cortesia é um FATO, não um vazio."""
        socorro = self._id("Socorro")
        tecnico_ficha.definir_precos(base["tecnico"], {str(socorro): 0})
        precos = {p["servico_id"]: p["custo_centavos"]
                  for p in tecnico_ficha.ficha(base["tecnico"])["precos"]}
        assert precos[socorro] == 0
        tecnico_ficha.definir_precos(base["tecnico"], {str(socorro): None})
        precos = {p["servico_id"]: p["custo_centavos"]
                  for p in tecnico_ficha.ficha(base["tecnico"])["precos"]}
        assert precos[socorro] is None

    def test_o_que_nao_veio_na_chamada_nao_e_apagado(self, base):
        """🚨 Enviar a ficha inteira para corrigir uma linha é o caminho mais
        curto para zerar nove preços sem perceber."""
        a, b = self._id("Instalação"), self._id("Retirada")
        tecnico_ficha.definir_precos(base["tecnico"], {str(a): 15000, str(b): 9000})
        tecnico_ficha.definir_precos(base["tecnico"], {str(a): 16000})
        precos = {p["servico_id"]: p["custo_centavos"]
                  for p in tecnico_ficha.ficha(base["tecnico"])["precos"]}
        assert precos[a] == 16000
        assert precos[b] == 9000

    def test_valor_negativo_recusa(self, base):
        with pytest.raises(DadoInvalido):
            tecnico_ficha.definir_precos(base["tecnico"],
                                         {str(self._id("Socorro")): -1})

    def test_servico_inexistente_recusa(self, base):
        with pytest.raises(DadoInvalido) as e:
            tecnico_ficha.definir_precos(base["tecnico"], {"999999": 100})
        assert "não existe" in str(e.value)

    def test_a_lista_conta_quantos_servicos_ele_oferece(self, base):
        achado = tecnico_ficha.listar(busca=NOME + " Um")["itens"][0]
        assert achado["servicos_com_preco"] >= 1


# ---------------------------------------------------------------------------
# O CREDENCIAMENTO
# ---------------------------------------------------------------------------

class TestCredenciamento:
    def test_ficha_nasce_candidata(self):
        """⚠️ Monta o próprio técnico, pelo mesmo motivo do
        `test_recusar_nao_apaga_a_ficha`: usando o compartilhado, passava só
        quando `TestFicha` rodava antes."""
        contato = _contato(NOME + " Doze")
        tecnico_ficha.salvar(contato, {"nome_fantasia": NOME + " Doze Ltda"})
        assert tecnico_ficha.ficha(contato)["ficha"]["estado"] == "candidato"

    def test_sem_ficha_nao_ha_o_que_validar(self, base):
        with pytest.raises(DadoInvalido) as e:
            tecnico_ficha.definir_estado(base["outro"], "credenciado")
        assert "ainda não tem ficha" in str(e.value)

    def test_credenciar_exige_endereco(self, base):
        """🚨 Sem rua e cidade não há cálculo de KM: credenciado assim, o
        técnico aparece pronto numa tela e falha na outra."""
        contato = _contato(NOME + " Tres")
        tecnico_ficha.salvar(contato, {"nome_fantasia": NOME + " Tres Ltda"})
        tecnico_ficha.definir_precos(
            contato, {str(next(s["id"] for s in tecnico_ficha.servicos()
                               if s["nome"] == "Instalação")): 10000})
        with pytest.raises(DadoInvalido) as e:
            tecnico_ficha.definir_estado(contato, "credenciado")
        assert "rua e cidade" in str(e.value)

    def test_credenciar_exige_pelo_menos_um_preco(self, base):
        contato = _contato(NOME + " Quatro")
        tecnico_ficha.salvar(contato, {"logradouro": "Rua Sem Preço",
                                       "cidade": "Presidente Prudente"})
        with pytest.raises(DadoInvalido) as e:
            tecnico_ficha.definir_estado(contato, "credenciado")
        assert "valor" in str(e.value)

    def test_credenciar_grava_quem_validou(self, base):
        """⚠️ Validação sem autor é afirmação sem responsável."""
        tecnico_ficha.salvar(base["tecnico"], {"logradouro": "Rua Teste",
                                               "cidade": "Presidente Prudente"})
        tecnico_ficha.definir_precos(
            base["tecnico"],
            {str(next(s["id"] for s in tecnico_ficha.servicos()
                      if s["nome"] == "Instalação")): 12000})
        depois = tecnico_ficha.definir_estado(
            base["tecnico"], "credenciado", nota="conferido no teste",
            atendente_id=base["pessoa"]["id"])
        assert depois["ficha"]["estado"] == "credenciado"
        assert depois["ficha"]["estado_por"] == base["pessoa"]["id"]
        assert depois["ficha"]["estado_nota"] == "conferido no teste"

    def test_recusar_nao_apaga_a_ficha(self):
        """⚠️ Mesmo CNPJ volta amanhã; sem o registro ninguém lembra por que
        saiu.

        ⚠️ ESTE TESTE MONTA O PRÓPRIO TÉCNICO, e isso não é verbosidade: na
        primeira escrita ele usava o técnico compartilhado da fixture e passava
        só porque outro teste, antes dele, tinha criado a ficha. Rodado
        isolado, estourava. Teste que depende da ordem de coleta é teste que
        um dia reprova sem nada ter mudado.
        """
        contato = _contato(NOME + " Onze")
        tecnico_ficha.salvar(contato, {"nome_fantasia": NOME + " Onze Ltda",
                                       "cnpj": "12345678000195"})
        tecnico_ficha.definir_estado(contato, "recusado", nota="só teste")
        ficha = tecnico_ficha.ficha(contato)["ficha"]
        assert ficha["estado"] == "recusado"
        assert ficha["estado_nota"] == "só teste"
        assert ficha["nome_fantasia"] == NOME + " Onze Ltda"
        assert ficha["cnpj"] == "12345678000195"  # continua tudo lá

    def test_estado_invalido_recusa(self, base):
        with pytest.raises(DadoInvalido):
            tecnico_ficha.definir_estado(base["tecnico"], "aprovado")


# ---------------------------------------------------------------------------
# CRIAR À MÃO (D3: o formulário não é exclusivo)
# ---------------------------------------------------------------------------

class TestCriarAMao:
    def test_cria_contato_tecnico_com_ficha_vazia(self):
        novo = tecnico_ficha.criar_tecnico(NOME + " Cinco", TEL)
        assert novo["contato"]["relacao"] == "tecnico"
        assert novo["ficha"]["estado"] == "candidato"
        assert [t["e164"] for t in novo["contato"]["telefones"]] == [TEL]

    def test_telefone_de_outro_cadastro_recusa_com_quem_e(self):
        """🚨 A trava de 02/10: dois cadastros com o mesmo número fazem a
        conversa escolher um deles sozinha."""
        with pytest.raises(DadoInvalido) as e:
            tecnico_ficha.criar_tecnico(NOME + " Seis", TEL)
        assert NOME + " Cinco" in str(e.value)

    def test_telefone_impossivel_recusa(self):
        with pytest.raises(DadoInvalido) as e:
            tecnico_ficha.criar_tecnico(NOME + " Sete", "abc")
        assert "telefone" in str(e.value)

    def test_nome_vazio_recusa(self):
        with pytest.raises(DadoInvalido):
            tecnico_ficha.criar_tecnico("   ")

    def test_tecnico_sem_telefone_e_permitido(self):
        novo = tecnico_ficha.criar_tecnico(NOME + " Oito")
        assert novo["contato"]["telefones"] == []


# ---------------------------------------------------------------------------
# A PORTA DO FORMULÁRIO
# ---------------------------------------------------------------------------

class TestCandidatos:
    def test_a_lista_de_candidatos_sabe_qual_formulario_e(self):
        achado = tecnico_ficha.candidatos()
        assert achado["formulario"] is not None, (
            "o formulário CREDENCIAMENTO saiu do banco — a tela precisa dizer "
            "isso, e não mostrar 'nenhum candidato' e parecer em dia")
        assert achado["formulario"]["codigo"] == "CREDENCIAMENTO"

    def test_solicitacao_inexistente_recusa(self):
        with pytest.raises(DadoInvalido):
            tecnico_ficha.sugestao_da_solicitacao(0)

    def test_a_uf_so_sai_quando_e_sigla(self):
        """🚨 O formulário pergunta "Estado" em TEXTO LIVRE e `uf` é
        `varchar(2)`. Vazio é honesto; "Sã" é lixo com cara de dado."""
        assert tecnico_ficha._uf_de("sp") == "SP"
        assert tecnico_ficha._uf_de("SP") == "SP"
        assert tecnico_ficha._uf_de("São Paulo") is None
        assert tecnico_ficha._uf_de("") is None
        assert tecnico_ficha._uf_de("XX") is None

    def test_as_seis_perguntas_de_preco_continuam_nomeadas(self):
        """⚠️ Elas NÃO são os dez serviços da ficha, e é por isso que ficam
        listadas: sem isso, quem credencia digitaria no escuro tendo a resposta
        a um clique."""
        assert len(tecnico_ficha.PRECOS_DO_FORMULARIO) == 7
        assert "Remoção" in tecnico_ficha.PRECOS_DO_FORMULARIO.values()

    def test_o_de_para_nao_cita_campo_que_o_formulario_nao_tem(self):
        """🚨 O elo que suíte verde não vê: campo renomeado no formulário faria
        o de-para apontar para o nada, e a sugestão viria vazia em silêncio."""
        formulario = banco.um("SELECT id FROM formulario WHERE codigo = %s",
                              (tecnico_ficha.CODIGO_DO_FORMULARIO,))
        if not formulario:
            pytest.skip("o formulário CREDENCIAMENTO não está neste banco")
        nossos = {c["nosso_nome"] for c in banco.varios(
            "SELECT nosso_nome FROM formulario_campo WHERE formulario_id = %s",
            (formulario["id"],))}
        citados = (set(tecnico_ficha.DE_PARA)
                   | set(tecnico_ficha.DE_PARA_LISTA)
                   | set(tecnico_ficha.PRECOS_DO_FORMULARIO)
                   | {"estado", "titular-da-conta-e-pessoa-fisica-ou-juri"})
        assert not (citados - nossos), (
            f"o de-para cita campos que o formulário não tem: "
            f"{sorted(citados - nossos)}")

    def test_todo_destino_do_de_para_e_coluna_da_ficha(self):
        colunas = set(tecnico_ficha.CAMPOS)
        destinos = set(tecnico_ficha.DE_PARA.values()) | set(
            tecnico_ficha.DE_PARA_LISTA.values())
        assert not (destinos - colunas), (
            f"o de-para grava em coluna que a ficha não tem: "
            f"{sorted(destinos - colunas)}")


# ---------------------------------------------------------------------------
# O QUE O ORÇAMENTO LÊ
#
# 🔵 04/11, e a premissa é dele: *"o orçamento não vai ao cliente, somente ao
# técnico."* Então o custo cadastrado pode preencher a linha do papel.
# ---------------------------------------------------------------------------

class TestPrecosParaOOrcamento:
    def _id(self, nome: str) -> int:
        return next(s["id"] for s in tecnico_ficha.servicos() if s["nome"] == nome)

    def test_tecnico_sem_preco_nao_oferece_nada(self):
        contato = _contato(NOME + " Catorze")
        assert tecnico_ficha.precos_para_orcamento(contato) == []

    def test_so_o_que_tem_preco_aparece(self, base):
        """🚨 Linha ausente ou nula é *"não oferece"*, e oferecer no `<select>`
        um serviço que ele não faz é convidar ao erro."""
        contato = _contato(NOME + " Quinze")
        tecnico_ficha.definir_precos(contato, {
            str(self._id("Instalação")): 18000,
            str(self._id("Socorro")): None,
        })
        oferece = {i["servico"] for i in tecnico_ficha.precos_para_orcamento(contato)}
        assert oferece == {"Instalação"}

    def test_ZERO_aparece_porque_e_cortesia(self, base):
        """🔵 Decisão dele em 04/11: *"zero pode ir ao orçamento"*. Na ficha,
        zero é cobrar zero e é um fato diferente de ausente — se o catálogo o
        escondesse, a cortesia cadastrada ficaria invisível na hora do papel."""
        contato = _contato(NOME + " Dezesseis")
        tecnico_ficha.definir_precos(contato, {str(self._id("Treinamento")): 0})
        itens = tecnico_ficha.precos_para_orcamento(contato)
        assert [i["servico"] for i in itens] == ["Treinamento"]
        assert itens[0]["preco_unit_centavos"] == 0

    def test_o_formato_e_o_do_CATALOGO_do_orcamento(self, base):
        """⚠️ `servico`/`unidade`/`preco_unit_centavos` — o que o modal já sabe
        consumir. Traduzir num lugar só evita que o `orcamento.py` aprenda o
        esquema da ficha."""
        contato = _contato(NOME + " Dezessete")
        tecnico_ficha.definir_precos(contato, {str(self._id("Retirada")): 9000})
        item = tecnico_ficha.precos_para_orcamento(contato)[0]
        assert set(item) == {"servico", "unidade", "preco_unit_centavos"}
        assert item["unidade"] == "un"

    def test_servico_desativado_nao_e_oferecido_de_novo(self, base):
        """⚠️ Mas o preço continua gravado, explicando os orçamentos antigos."""
        servico = tecnico_ficha.criar_servico(SERVICO + " C")
        contato = _contato(NOME + " Dezoito")
        tecnico_ficha.definir_precos(contato, {str(servico["id"]): 5000})
        assert tecnico_ficha.precos_para_orcamento(contato)
        tecnico_ficha.atualizar_servico(servico["id"], servico["nome"],
                                        servico["ordem"], False)
        assert tecnico_ficha.precos_para_orcamento(contato) == []
        guardado = banco.um(
            "SELECT custo_centavos FROM tecnico_preco "
            " WHERE contato_id = %s AND servico_id = %s",
            (contato, servico["id"]))
        assert guardado["custo_centavos"] == 5000

    def test_a_ordem_e_a_do_catalogo(self, base):
        contato = _contato(NOME + " Dezenove")
        tecnico_ficha.definir_precos(contato, {
            str(self._id("Acompanhamento")): 1000,   # ordem 10
            str(self._id("Instalação")): 2000,       # ordem 1
        })
        nomes = [i["servico"] for i in tecnico_ficha.precos_para_orcamento(contato)]
        assert nomes == ["Instalação", "Acompanhamento"]

    def test_o_catalogo_do_orcamento_junta_as_duas_fixas_com_a_ficha(self, base):
        """🚨 O ELO ENTRE OS DOIS MÓDULOS, e o que ele pediu: *"os da ficha + as
        duas de sempre"*."""
        from movizap import orcamento
        contato = _contato(NOME + " Vinte")
        tecnico_ficha.definir_precos(contato, {str(self._id("Socorro")): 25000})
        nomes = [i["servico"] for i in orcamento.catalogo(contato)]
        assert nomes[:2] == ["KM DESLOCAMENTO", "PAGAMENTO DE TECNICO"]
        assert "Socorro" in nomes

    def test_o_item_da_ficha_NAO_traz_harmonit_id(self, base):
        """🚨 Estes dez não têm id de produto no Harmonit. Devolver o campo
        vazio sugeriria que alguém o lê — e ninguém lê: o `harmonit_id` morre no
        `<select>` do modal, medido em 04/11."""
        from movizap import orcamento
        contato = _contato(NOME + " Vinte e Um")
        tecnico_ficha.definir_precos(contato, {str(self._id("Laudo Técnico")): 7000})
        item = next(i for i in orcamento.catalogo(contato)
                    if i["servico"] == "Laudo Técnico")
        assert "harmonit_id" not in item
        assert item["da_ficha"] is True
        # O valor vai ESCRITO, pela régua da casa (nunca dividir por 100 na tela)
        assert item["preco_unit"] == "70,00"
        assert item["preco_unit_centavos"] == 7000

    def test_nome_igual_a_uma_linha_fixa_nao_duplica_a_opcao(self, monkeypatch):
        """⚠️ O `<select>` casa por NOME: duas opções iguais fariam a escolha
        depender da ordem. A fixa ganha, porque é a que tem procedência.

        🚨 AQUI A FONTE É DUBLADA, e de propósito: provar isto com dado real
        exigiria criar no catálogo de produção um serviço chamado
        `PAGAMENTO DE TECNICO`, que apareceria na ficha dos 303 técnicos. O
        duplo substitui **de onde vêm os preços**; a regra sob teste — a
        deduplicação em `orcamento.catalogo()` — é a de verdade.
        """
        from movizap import orcamento
        monkeypatch.setattr(
            tecnico_ficha, "precos_para_orcamento",
            lambda _id: [{"servico": "PAGAMENTO DE TECNICO", "unidade": "un",
                          "preco_unit_centavos": 1234},
                         {"servico": "Socorro", "unidade": "un",
                          "preco_unit_centavos": 25000}])
        itens = orcamento.catalogo(999_999)
        nomes = [i["servico"] for i in itens]
        assert len(nomes) == len(set(nomes)), f"opção repetida: {nomes}"
        # A fixa venceu: continua com o id e SEM preço sugerido da ficha.
        fixa = next(i for i in itens if i["servico"] == "PAGAMENTO DE TECNICO")
        assert fixa["harmonit_id"] == 653939
        assert "preco_unit" not in fixa
        # E o que não colide entrou.
        assert "Socorro" in nomes

    def test_falha_ao_ler_a_ficha_NAO_derruba_o_catalogo(self, monkeypatch):
        """🚨 Perder o atalho é aceitável; não poder emitir não é."""
        from movizap import orcamento

        def estoura(_id):
            raise RuntimeError("banco fora")

        monkeypatch.setattr(tecnico_ficha, "precos_para_orcamento", estoura)
        nomes = [i["servico"] for i in orcamento.catalogo(999_999)]
        assert nomes == ["KM DESLOCAMENTO", "PAGAMENTO DE TECNICO"]


# ---------------------------------------------------------------------------
# O QUE O KM LÊ
# ---------------------------------------------------------------------------

class TestOrigemDoKm:
    def test_ficha_sem_endereco_devolve_None_e_nao_dict_de_vazios(self, base):
        """⚠️ A tela precisa distinguir "não tem endereço cadastrado" de "tem
        endereço em branco" — sete `None` desenhariam a segunda frase."""
        contato = _contato(NOME + " Nove")
        tecnico_ficha.salvar(contato, {"nome_fantasia": NOME + " Nove Ltda"})
        assert tecnico_ficha.origem_do_tecnico(contato) is None

    def test_o_endereco_da_ficha_e_a_origem(self, base):
        contato = _contato(NOME + " Dez")
        tecnico_ficha.salvar(contato, {
            "cep": "19010000", "logradouro": "Rua da Origem", "numero": "100",
            "bairro": "Centro", "cidade": "Presidente Prudente", "uf": "SP"})
        origem = tecnico_ficha.origem_do_tecnico(contato)
        assert origem["logradouro"] == "Rua da Origem"
        assert origem["cidade"] == "Presidente Prudente"
        assert set(tecnico_ficha.CAMPOS_DE_ENDERECO) <= set(origem)

    def test_os_sete_campos_sao_os_mesmos_do_compromisso(self):
        """🚨 Duas réguas para o mesmo endereço é uma delas mentindo.

        ⚠️ A comparação era contra `rotas.CAMPOS_DE_ORIGEM` TAMBÉM, e ela saiu
        junto com a memória da 077 em 04/11 — a ficha é a fonte agora. Ficou só
        a régua do compromisso, que é a que continua existindo.
        """
        from movizap import agendamento
        assert tecnico_ficha.CAMPOS_DE_ENDERECO == agendamento.CAMPOS_DE_ENDERECO


# ---------------------------------------------------------------------------
# AS ROTAS E A PORTA
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def cliente():
    with TestClient(main.app) as c:
        yield c


@pytest.fixture(scope="module")
def token():
    return auth.criar_token(settings.admin_login)


@pytest.fixture(scope="module")
def token_atendente(base):
    """Uma conta de perfil `atendimento` — que tem a TEC_1.1 e NÃO a TEC_1.2."""
    return auth.criar_token(LOGIN + "1")


class TestRotas:
    def test_tudo_exige_token(self, cliente, base):
        for metodo, caminho in (
                ("get", "/api/tecnicos"),
                ("get", "/api/tecnicos/servicos"),
                ("get", "/api/tecnicos/candidatos"),
                ("get", f"/api/tecnicos/{base['tecnico']}"),
                ("post", "/api/tecnicos"),
                ("put", f"/api/tecnicos/{base['tecnico']}"),
                ("put", f"/api/tecnicos/{base['tecnico']}/precos"),
                ("put", f"/api/tecnicos/{base['tecnico']}/estado")):
            # `cliente.get(..., json=...)` não existe no httpx; `request` sim.
            resposta = cliente.request(metodo.upper(), caminho, json={})
            assert resposta.status_code in (401, 403), f"{metodo} {caminho}"

    def test_a_palavra_servicos_nao_e_lida_como_id(self, cliente, token):
        """🚨 Rota literal antes da paramétrica. Depois da `{contato_id}`, a
        palavra "servicos" viraria 422."""
        resposta = cliente.get("/api/tecnicos/servicos",
                               headers={"Authorization": f"Bearer {token}"})
        assert resposta.status_code == 200
        assert len(resposta.json()["servicos"]) >= 10

    def test_atendente_LE_a_lista(self, cliente, token_atendente):
        """🚨 Um 403 aqui derrubaria a tela de quem monta orçamento — foi
        exatamente o que a lista de classificações sofreu até 23/09."""
        resposta = cliente.get("/api/tecnicos",
                               headers={"Authorization": f"Bearer {token_atendente}"})
        assert resposta.status_code == 200
        assert "itens" in resposta.json()

    def test_atendente_LE_a_ficha(self, cliente, token_atendente, base):
        resposta = cliente.get(f"/api/tecnicos/{base['tecnico']}",
                               headers={"Authorization": f"Bearer {token_atendente}"})
        assert resposta.status_code == 200
        assert resposta.json()["precos"]

    @pytest.mark.parametrize("metodo,caminho,corpo", [
        ("post", "/api/tecnicos", {"nome": "Zz Teste Tecnico Intruso"}),
        ("put", "/api/tecnicos/{id}", {"cidade": "Lugar Nenhum"}),
        ("put", "/api/tecnicos/{id}/precos", {"precos": {}}),
        ("put", "/api/tecnicos/{id}/estado", {"estado": "credenciado"}),
        ("post", "/api/tecnicos/servicos", {"nome": "Zz Servico De Teste Intruso"}),
        # ⚠️ Id inexistente de propósito: a permissão é conferida ANTES do
        # corpo, então o 403 se prova sem apontar para um serviço real. Com
        # `1` aqui, este teste renomearia "Instalação" no dia em que a trava
        # falhasse — e um teste que estraga produção quando acha o defeito é
        # pior que não ter o teste.
        ("put", "/api/tecnicos/servicos/999999", {"nome": "Zz Servico De Teste Intruso",
                                                  "ordem": 1, "ativo": True}),
    ])
    def test_atendente_NAO_ESCREVE_nada(self, cliente, token_atendente, base,
                                        metodo, caminho, corpo):
        """🚨 A metade que decide. *"Ler todo atendente, escrever owner e
        admin"* — e é aqui que isso ou é verdade ou não é."""
        resposta = getattr(cliente, metodo)(
            caminho.format(id=base["tecnico"]), json=corpo,
            headers={"Authorization": f"Bearer {token_atendente}"})
        assert resposta.status_code == 403, f"{metodo} {caminho} passou!"

    def test_o_intruso_nao_deixou_rastro(self):
        """⚠️ 403 que grava é pior que 500: prova que nada entrou."""
        assert banco.um("SELECT count(*) AS n FROM contato WHERE nome = %s",
                        ("Zz Teste Tecnico Intruso",))["n"] == 0
        assert banco.um("SELECT count(*) AS n FROM servico_tecnico WHERE nome = %s",
                        ("Zz Servico De Teste Intruso",))["n"] == 0

    def test_estado_invalido_vira_400_e_nao_500(self, cliente, token, base):
        resposta = cliente.put(f"/api/tecnicos/{base['tecnico']}/estado",
                               json={"estado": "aprovadissimo"},
                               headers={"Authorization": f"Bearer {token}"})
        assert resposta.status_code == 400

    def test_contato_inexistente_e_404(self, cliente, token):
        resposta = cliente.get("/api/tecnicos/0",
                               headers={"Authorization": f"Bearer {token}"})
        assert resposta.status_code == 404

    def test_o_catalogo_do_orcamento_nao_aceita_tecnico_por_parametro(
            self, cliente, token, base):
        """🚨 DE QUEM É O PREÇO NÃO VEM DO NAVEGADOR — a mesma régua da
        calculadora de KM, onde aceitar o id no corpo deixava qualquer um
        sobrescrever a origem de outro técnico. Aqui o risco é ler a tabela de
        preço de um técnico pela tela de outro.
        """
        cab = {"Authorization": f"Bearer {token}"}
        # Mandar o contato como se fosse parâmetro: tem de ser ignorado.
        corpo = cliente.get(
            f"/api/orcamento/catalogo?tecnico_contato_id={base['tecnico']}",
            headers=cab).json()
        assert [i["servico"] for i in corpo["catalogo"]] == [
            "KM DESLOCAMENTO", "PAGAMENTO DE TECNICO"]
        assert corpo["tecnico_contato_id"] is None

    def test_sem_conversa_o_catalogo_responde_como_antes(self, cliente, token):
        corpo = cliente.get("/api/orcamento/catalogo",
                            headers={"Authorization": f"Bearer {token}"}).json()
        assert [i["servico"] for i in corpo["catalogo"]] == [
            "KM DESLOCAMENTO", "PAGAMENTO DE TECNICO"]
        assert "proximo_numero" in corpo

    def test_conversa_que_nao_e_de_tecnico_devolve_as_duas(self, cliente, token):
        """⚠️ `_tecnico_da_conversa` devolve `None` para conversa de cliente, de
        grupo e para conversa que não existe — e o catálogo volta ao de sempre."""
        corpo = cliente.get("/api/orcamento/catalogo?conversa_id=0",
                            headers={"Authorization": f"Bearer {token}"}).json()
        assert [i["servico"] for i in corpo["catalogo"]] == [
            "KM DESLOCAMENTO", "PAGAMENTO DE TECNICO"]
        assert corpo["tecnico_contato_id"] is None
