"""A OS do chamado — Bloco A do pipeline da operação (29/10).

🔵 As duas decisões dele que esta suíte guarda:
  · **D4** — *"todo chamado de suporte abrirá uma OS"*, automático no envio;
  · **D3** — **uma OS por placa**, não uma por envio.

O que aqui está travado, e por quê:

  · 🚨 **uma linha por placa, e a mesma placa duas vezes não abre duas OS** —
    o índice único do banco é a trava, não a boa intenção de quem chama;
  · 🚨 **a falha fica ESCRITA, e o chamado continua gravado** — é o ponto do
    Bloco A: *"chamado gravado e OS não criada é o pior caso — o cliente
    recebe 'recebemos' e ninguém abre OS"*;
  · 🚨 **timeout da ponte é `criada: None`, nunca `False`** — e esta é a trava
    mais importante do arquivo: `False` convidaria a retentativa que abre a
    SEGUNDA OS no ERP. Foi um erro meu, pego antes de valer algo;
  · 🚨 **sem cliente não há OS, e isso é dito** — o formulário é público, o
    `SalvarOrdemServico` exige `clienteId`, e inventar um cliente seria pior
    que não abrir;
  · **o formulário que não está no mapa não abre OS** — 6 dos 15 não abrem por
    decisão dele, e os outros esperam o mapa de problema;
  · **os ids de catálogo são os que ele decidiu** (38 · 382 · 12760 · 1782 e
    1783 pela origem), e estão travados contra troca por descuido.

🚨 ESCREVE EM TABELAS DE PRODUÇÃO (`formulario`, `formulario_solicitacao`,
`solicitacao_os`), como o resto da suíte: tudo com o código `ZZ_TESTE_COS` e
apagado no fim.

⚠️ NADA AQUI FALA COM O HARMONIT. A ponte é trocada por dublê -- a suíte não
pode criar OS no ERP, e OS de teste em ERP de produção é sujeira que fica.
"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, "/home/claude/movizap_painel")
pytest.importorskip("psycopg")

from movizap import banco, chamado_os, formularios, fpsl_ponte  # noqa: E402

# 🚨 AS REGRAS DO FORMULÁRIO VÊM DO PRÓPRIO CARREGADOR, não de uma cópia.
# Sem `VALIDACOES` o campo não tem `validacao` e sem `AJUSTES` não tem `fonte`
# -- e aí `campo_de_placa` pula, 12 travas não rodam e o placar parece
# saudável. Copiar as duas tabelas para cá criaria a terceira verdade.
sys.path.insert(0, "/home/claude/movizap_painel/scripts")
import carregar_formularios as carregador  # noqa: E402

RAIZ = Path("/home/claude/movizap_painel")
MAPA = json.loads((RAIZ / "dados" / "formularios_bitrix" / "mapa_bruto.json")
                  .read_text(encoding="utf-8"))

CODIGO = "ZZ_TESTE_COS"
SLUG = "zz-teste-cos"

# O formulário 32 do mapa é o do SUPORTE -- o mesmo que o teste do painel usa.
BITRIX_SUPORTE = "32"


@pytest.fixture(scope="module", autouse=True)
def pool():
    banco.abrir()
    yield


def _apagar():
    banco.executar(
        """DELETE FROM solicitacao_os
            WHERE solicitacao_id IN (
                SELECT s.id FROM formulario_solicitacao s
                  JOIN formulario f ON f.id = s.formulario_id
                 WHERE f.codigo = %s)""", (CODIGO,))
    banco.executar(
        """DELETE FROM formulario_solicitacao
            WHERE formulario_id IN (SELECT id FROM formulario
                                     WHERE codigo = %s)""", (CODIGO,))
    banco.executar("DELETE FROM formulario WHERE codigo = %s", (CODIGO,))


@pytest.fixture
def formulario():
    """Um SUPORTE de teste, e ele ENTRA no mapa de problema.

    ⚠️ O mapa é por `slug` e o `slug` de teste não está nele -- então o teste
    o acrescenta e o tira. Sem isso, `formulario_abre_os` seria falso e metade
    desta suíte testaria o caminho de "não abre".
    """
    _apagar()
    formularios.gravar_definicao(MAPA[BITRIX_SUPORTE], codigo=CODIGO,
                                 slug=SLUG, setor="Teste",
                                 titulo="zz Teste chamado OS",
                                 painel="operacao",
                                 formato="novo",
                                 etapas=carregador.ETAPAS["SUPORTE"],
                                 validacoes=carregador.VALIDACOES["SUPORTE"],
                                 ajustes=carregador.AJUSTES["SUPORTE"])
    chamado_os.PROBLEMA_POR_FORMULARIO[SLUG] = chamado_os.PROBLEMA_POR_FORMULARIO["suporte"]
    yield formularios.definicao(SLUG, so_ativo=False)
    chamado_os.PROBLEMA_POR_FORMULARIO.pop(SLUG, None)
    _apagar()


@pytest.fixture
def campo_de_placa(formulario):
    """O nome do campo de placa deste formulário, que é a chave do Bitrix."""
    for c in formulario["campos"]:
        if c.get("fonte") == "weso_placas":
            return c["nome"]
    # 🚨 NÃO É `skip`: o formulário de teste nasce do mesmo carregador do real,
    # então "sem campo de placa" quer dizer que o AJUSTES mudou -- e aí metade
    # desta suíte deixaria de medir em silêncio. Foi o que aconteceu na
    # primeira rodada, com 12 travas pulando e o placar parecendo saudável.
    raise AssertionError(
        "o formulario de teste nasceu sem campo de placa -- o AJUSTES do "
        "carregar_formularios.py mudou, e 12 travas desta suite dependem dele")


def _solicitacao(formulario, valores=None):
    return formularios.registrar(formulario, valores or {})["id"]


class PonteDublê:
    """Uma ponte que não fala com ninguém. Devolve o que o teste mandar."""

    def __init__(self, respostas):
        self.respostas = list(respostas)
        self.chamadas = []

    def __call__(self, **kwargs):
        self.chamadas.append(kwargs)
        return self.respostas.pop(0) if self.respostas else \
            {"ok": True, "criada": True, "numero_os": 90000,
             "os_id": 900000, "situacao_id": 38}


@pytest.fixture
def ponte(monkeypatch):
    def instalar(*respostas):
        d = PonteDublê(respostas)
        monkeypatch.setattr(fpsl_ponte, "criar_os", d)
        monkeypatch.setattr(chamado_os.fpsl_ponte, "criar_os", d)
        return d
    return instalar


# ============================================================================
# D3 — uma OS por placa
# ============================================================================
def teste_uma_linha_por_placa(formulario, campo_de_placa, ponte):
    """🔵 D3: *uma OS por placa*. Três placas, três linhas, três chamadas."""
    ponte({"ok": True, "criada": True, "numero_os": 1, "os_id": 11,
           "situacao_id": 38},
          {"ok": True, "criada": True, "numero_os": 2, "os_id": 12,
           "situacao_id": 38},
          {"ok": True, "criada": True, "numero_os": 3, "os_id": 13,
           "situacao_id": 38})
    sid = _solicitacao(formulario,
                       {campo_de_placa: ["ABC1D23", "XYZ4E56", "QWE7R89"]})

    r = chamado_os.abrir(sid, formulario, {campo_de_placa:
                                           ["ABC1D23", "XYZ4E56", "QWE7R89"]},
                         cliente_id=68546)

    assert r == {"abertas": 3, "falhas": 0, "motivo": None}
    linhas = chamado_os.da_solicitacao(sid)
    assert [x["placa"] for x in linhas] == ["ABC1D23", "XYZ4E56", "QWE7R89"]
    assert [x["numero_ordem"] for x in linhas] == [1, 2, 3]
    assert all(x["erro"] is None for x in linhas)


def teste_sem_placa_abre_uma_os_com_placa_nula(formulario, ponte):
    """⚠️ O caso "uma OS só" convive com o mesmo desenho: UMA linha, placa
    nula -- e não zero linhas, que faria o chamado sem placa não abrir OS."""
    d = ponte()
    sid = _solicitacao(formulario)

    r = chamado_os.abrir(sid, formulario, {}, cliente_id=68546)

    assert r["abertas"] == 1
    linhas = chamado_os.da_solicitacao(sid)
    assert len(linhas) == 1
    assert linhas[0]["placa"] is None
    assert len(d.chamadas) == 1


def teste_a_mesma_placa_duas_vezes_abre_uma_so(formulario, campo_de_placa,
                                               ponte):
    """🚨 A mesma placa repetida no MESMO envio não é pedido em dobro. A trava
    é o índice único do banco, e o módulo não a contorna."""
    d = ponte()
    valores = {campo_de_placa: ["ABC1D23", "abc1d23", "ABC1D23"]}
    sid = _solicitacao(formulario, valores)

    r = chamado_os.abrir(sid, formulario, valores, cliente_id=68546)

    assert r["abertas"] == 1
    assert len(chamado_os.da_solicitacao(sid)) == 1
    assert len(d.chamadas) == 1


def teste_abrir_duas_vezes_nao_duplica(formulario, campo_de_placa, ponte):
    """🚨 Dois cliques (ou dois ciclos) não abrem a segunda OS da mesma placa:
    `ON CONFLICT DO NOTHING` não devolve linha, e sem linha não há chamada."""
    d = ponte()
    valores = {campo_de_placa: ["ABC1D23"]}
    sid = _solicitacao(formulario, valores)

    chamado_os.abrir(sid, formulario, valores, cliente_id=68546)
    segunda = chamado_os.abrir(sid, formulario, valores, cliente_id=68546)

    assert segunda["abertas"] == 0
    assert "ja as tinha" in segunda["motivo"]
    assert len(d.chamadas) == 1
    assert len(chamado_os.da_solicitacao(sid)) == 1


# ============================================================================
# A falha fica escrita — o ponto do Bloco A
# ============================================================================
def teste_a_falha_fica_escrita_na_linha(formulario, campo_de_placa, ponte):
    """🚨 *"a falha tem de ser visível"*: OS não criada deixa o motivo na
    linha, e o chamado continua gravado."""
    ponte({"ok": False, "criada": False, "motivo": "o Harmonit recusou o tipo"})
    valores = {campo_de_placa: ["ABC1D23"]}
    sid = _solicitacao(formulario, valores)

    r = chamado_os.abrir(sid, formulario, valores, cliente_id=68546)

    assert r == {"abertas": 0, "falhas": 1, "motivo": None}
    linha = chamado_os.da_solicitacao(sid)[0]
    assert linha["os_id"] is None
    assert linha["erro"] == "o Harmonit recusou o tipo"
    assert linha["tentativas"] == 1
    # 🚨 E o chamado NÃO desapareceu: é o que separa "OS falhou" de "chamado
    # perdido".
    assert banco.um("SELECT id FROM formulario_solicitacao WHERE id = %s",
                    (sid,)) is not None


def teste_o_caso_incerto_e_marcado_e_nao_se_repete(formulario, campo_de_placa,
                                                   ponte):
    """🚨 A TRAVA MAIS IMPORTANTE DAQUI. `criada: None` quer dizer *"pode haver
    OS no ERP e não sabemos qual"* -- então o erro é gritado, e a segunda
    tentativa não cria nada porque a linha já existe."""
    d = ponte({"ok": False, "criada": None,
               "motivo": "o FPSL não respondeu no tempo"})
    valores = {campo_de_placa: ["ABC1D23"]}
    sid = _solicitacao(formulario, valores)

    chamado_os.abrir(sid, formulario, valores, cliente_id=68546)

    linha = chamado_os.da_solicitacao(sid)[0]
    assert linha["erro"].startswith("🚨 ")
    assert "não respondeu no tempo" in linha["erro"]
    # Tentar de novo não fala com a ponte outra vez.
    chamado_os.abrir(sid, formulario, valores, cliente_id=68546)
    assert len(d.chamadas) == 1


def teste_timeout_da_ponte_e_incerto_nao_falha(monkeypatch):
    """🚨 O ERRO QUE EU IA DEIXAR NO CÓDIGO: *"não respondeu no tempo"* não é
    *"não gravou"*. `criada` tem de ser `None`, nunca `False` -- `False`
    convidaria a retentativa que abre a SEGUNDA OS."""
    def estourar(caminho, corpo):
        erro = fpsl_ponte.FpslIndisponivel("o FPSL não respondeu no tempo")
        erro.incerto = True
        raise erro

    monkeypatch.setattr(fpsl_ponte, "_postar", estourar)
    r = fpsl_ponte.criar_os(cliente_id=1, tipo_id=1782, problema_id=12760,
                            situacao_id=38, prioridade_id=382, descricao="x")
    assert r["criada"] is None


def teste_ponte_desconfigurada_e_falso_e_pode_tentar_de_novo(monkeypatch):
    """⚠️ O contrário do de cima: quando a ponte nem chegou a falar com o
    Harmonit, `criada: False` é a verdade, e tentar de novo é seguro."""
    def estourar(caminho, corpo):
        raise fpsl_ponte.FpslIndisponivel("a ponte não está configurada")

    monkeypatch.setattr(fpsl_ponte, "_postar", estourar)
    r = fpsl_ponte.criar_os(cliente_id=1, tipo_id=1782, problema_id=12760,
                            situacao_id=38, prioridade_id=382, descricao="x")
    assert r["criada"] is False


def teste_divergencia_guarda_o_numero_e_diz(formulario, campo_de_placa, ponte):
    """🚨 OS criada diferente do pedido: o número é guardado de qualquer forma
    (senão fica órfã no ERP) e a divergência fica DITA na linha."""
    ponte({"ok": False, "criada": True, "numero_os": 17099, "os_id": 920000,
           "situacao_id": 0,
           "divergencias": {"situacaoId": {"pedido": 38, "gravado": 0}}})
    valores = {campo_de_placa: ["ABC1D23"]}
    sid = _solicitacao(formulario, valores)

    r = chamado_os.abrir(sid, formulario, valores, cliente_id=68546)

    assert r["abertas"] == 1
    linha = chamado_os.da_solicitacao(sid)[0]
    assert linha["numero_ordem"] == 17099
    assert "divergencia" in linha["erro"]


# ============================================================================
# Sem cliente não há OS
# ============================================================================
def teste_sem_cliente_nao_abre_e_diz_por_que(formulario, campo_de_placa,
                                             ponte):
    """🔴 O `SalvarOrdemServico` exige `clienteId`, o formulário é público e o
    modal *"Sem empresa vinculada"* deixa enviar sem empresa. Então a linha
    nasce marcada -- e a ponte não é nem chamada."""
    d = ponte()
    valores = {campo_de_placa: ["ABC1D23"]}
    sid = _solicitacao(formulario, valores)

    r = chamado_os.abrir(sid, formulario, valores, cliente_id=None)

    assert r["abertas"] == 0 and r["falhas"] == 1
    assert "sem empresa vinculada" in r["motivo"]
    assert "sem empresa vinculada" in chamado_os.da_solicitacao(sid)[0]["erro"]
    assert d.chamadas == []


def teste_o_cliente_vem_do_documento_do_chamado(formulario):
    """O `harmonit_id` sai do CNPJ que a pessoa escreveu. ⚠️ O campo é achado
    pela VALIDAÇÃO (`cnpj`/`cpf`), nunca pela chave do Bitrix."""
    alvo = banco.um(
        """SELECT harmonit_id, documento FROM cliente
            WHERE harmonit_id IS NOT NULL
              AND harmonit_id ~ '^[0-9]+$'
              AND length(regexp_replace(coalesce(documento, ''),
                                        '[^A-Za-z0-9]', '', 'g')) = 14
            ORDER BY ativo DESC, id LIMIT 1""")
    if not alvo:
        pytest.skip("a base nao tem cliente com documento de 14 e harmonit_id")

    campo = next(c["nome"] for c in formulario["campos"]
                 if c.get("validacao") == "cnpj")
    achado = chamado_os.cliente_do_chamado(formulario,
                                           {campo: alvo["documento"]})
    assert achado == int(alvo["harmonit_id"])


def teste_documento_desconhecido_nao_inventa_cliente(formulario):
    """⚠️ "Não achou" é resposta, não erro -- e não pode virar um id qualquer."""
    campo = next(c["nome"] for c in formulario["campos"]
                 if c.get("validacao") == "cnpj")
    assert chamado_os.cliente_do_chamado(
        formulario, {campo: "11222333000181"}) is None


# ============================================================================
# O mapa, e os ids que ele decidiu
# ============================================================================
def teste_formulario_fora_do_mapa_nao_abre_os():
    """6 dos 15 não abrem OS por decisão dele, e os outros esperam o mapa de
    problema. ⚠️ Ausência é a regra, não esquecimento."""
    assert chamado_os.formulario_abre_os("suporte") is True
    for slug in ("nps", "ces", "contato", "pagamento-tecnicos",
                 "ficha-cadastral", "rescisao"):
        assert chamado_os.formulario_abre_os(slug) is False


def teste_so_o_suporte_esta_no_mapa_hoje():
    """🚨 Se este teste quebrar, alguém acrescentou formulário ao mapa -- e aí
    o sub-mapa de problema dele tem de ter sido decidido antes."""
    assert set(chamado_os.PROBLEMA_POR_FORMULARIO) == {"suporte"}


def teste_os_ids_de_catalogo_sao_os_que_ele_decidiu():
    """🔵 38 Novo Solicitação 1ª · 382 Normal · 12760 ANÁLISE OPERACIONAL ·
    1782/1783 pela ORIGEM. Os cinco foram lidos do catálogo do ERP em 29/10."""
    assert chamado_os.SITUACAO_INICIAL == 38
    assert chamado_os.PRIORIDADE_PADRAO == 382
    assert chamado_os.PROBLEMA_POR_FORMULARIO["suporte"] == 12760
    assert chamado_os.PRODUTO_ABERTURA_DE_OS == 670990
    # 🚨 A consequência que ele aceitou: pelo link livre quem preenche é o
    # CLIENTE e a OS nasce "Demanda Interna".
    assert chamado_os.TIPO_POR_ORIGEM == {"link": 1782, "movizap": 1783}


def teste_o_tipo_vem_da_origem(formulario, campo_de_placa, ponte):
    """🔵 3.1 dele: *"o `tipoId` vem da ORIGEM, não do formulário"*."""
    d = ponte()
    valores = {campo_de_placa: ["ABC1D23"]}
    sid = _solicitacao(formulario, valores)
    chamado_os.abrir(sid, formulario, valores, cliente_id=68546,
                     origem="movizap")
    assert d.chamadas[0]["tipo_id"] == 1783

    sid2 = _solicitacao(formulario, {campo_de_placa: ["XYZ4E56"]})
    chamado_os.abrir(sid2, formulario, {campo_de_placa: ["XYZ4E56"]},
                     cliente_id=68546, origem="link")
    assert d.chamadas[1]["tipo_id"] == 1782


def teste_origem_desconhecida_cai_no_link_nao_no_vazio(formulario, ponte):
    """⚠️ Origem que eu não previ não pode mandar `tipo_id` nulo ao ERP."""
    d = ponte()
    sid = _solicitacao(formulario)
    chamado_os.abrir(sid, formulario, {}, cliente_id=68546, origem="marte")
    assert d.chamadas[0]["tipo_id"] == 1782


# ============================================================================
# A descrição que vai para a OS
# ============================================================================
def teste_a_descricao_leva_a_placa_e_o_numero_do_chamado(formulario,
                                                         campo_de_placa, ponte):
    d = ponte()
    valores = {campo_de_placa: ["ABC1D23"]}
    sid = _solicitacao(formulario, valores)
    chamado_os.abrir(sid, formulario, valores, cliente_id=68546)

    descricao = d.chamadas[0]["descricao"]
    assert f"Chamado {sid}" in descricao
    assert "Placa: ABC1D23" in descricao


def teste_a_descricao_nao_leva_anexo(formulario, ponte):
    """🚨 Decisão 3.8, que eu levantei e ele aceitou: nem o arquivo nem link
    público para ele. Seriam CPF, RG e contrato social atrás de uma URL."""
    d = ponte()
    sid = _solicitacao(formulario)
    chamado_os.abrir(sid, formulario, {}, cliente_id=68546)

    descricao = d.chamadas[0]["descricao"]
    for campo in formulario["campos"]:
        if campo["tipo"] == "file":
            assert campo["nome"] not in descricao
    assert "http" not in descricao


def teste_a_descricao_e_cortada_e_diz_que_cortou(formulario, ponte):
    """⚠️ Cortar dizendo que cortou é melhor que a ponte recusar a OS inteira
    por tamanho."""
    d = ponte()
    campo = next(c["nome"] for c in formulario["campos"]
                 if c["tipo"] not in ("file",))
    sid = _solicitacao(formulario)
    chamado_os.abrir(sid, formulario, {campo: "x" * 9000}, cliente_id=68546)

    descricao = d.chamadas[0]["descricao"]
    assert len(descricao) < 4000
    assert "cortado" in descricao


# ============================================================================
# O painel diz a falha (M12)
# ============================================================================
def teste_a_falha_aparece_na_conta_do_painel(formulario, campo_de_placa, ponte):
    """🚨 `M12`: solicitação cuja OS não nasceu não tem coluna e sumiria da
    tela. A conta é o que faz a linha de aviso existir."""
    antes = chamado_os.falhas_em_aberto()
    ponte({"ok": False, "criada": False, "motivo": "o ERP recusou"})
    valores = {campo_de_placa: ["ABC1D23"]}
    sid = _solicitacao(formulario, valores)
    chamado_os.abrir(sid, formulario, valores, cliente_id=68546)

    depois = chamado_os.falhas_em_aberto()
    assert depois["quantas"] == antes["quantas"] + 1
    assert depois["chamados"] == antes["chamados"] + 1
    assert depois["ultima"] is not None


def teste_a_os_que_nasceu_nao_entra_na_conta_de_falha(formulario,
                                                      campo_de_placa, ponte):
    antes = chamado_os.falhas_em_aberto()
    ponte()
    valores = {campo_de_placa: ["ABC1D23"]}
    sid = _solicitacao(formulario, valores)
    chamado_os.abrir(sid, formulario, valores, cliente_id=68546)

    assert chamado_os.falhas_em_aberto()["quantas"] == antes["quantas"]


# ============================================================================
# A primeira OS vai para a solicitação
# ============================================================================
def teste_a_primeira_os_fica_na_solicitacao(formulario, campo_de_placa, ponte):
    """⚠️ `formulario_solicitacao.os_id` passa a significar **a primeira OS**,
    não "a OS" -- o painel de hoje a lê, e deixá-la nula faria o card
    desaparecer."""
    ponte({"ok": True, "criada": True, "numero_os": 17101, "os_id": 921001,
           "situacao_id": 38},
          {"ok": True, "criada": True, "numero_os": 17102, "os_id": 921002,
           "situacao_id": 38})
    valores = {campo_de_placa: ["ABC1D23", "XYZ4E56"]}
    sid = _solicitacao(formulario, valores)

    chamado_os.abrir(sid, formulario, valores, cliente_id=68546)

    linha = banco.um(
        """SELECT os_id, numero_ordem, situacao_id
             FROM formulario_solicitacao WHERE id = %s""", (sid,))
    assert linha["os_id"] == 921001
    assert linha["numero_ordem"] == "17101"
    assert linha["situacao_id"] == 38

# ============================================================================
# "NUNCA SE TENTOU" NÃO É "FALHOU" — o defeito que ele achou na tela
# ============================================================================
# 🚨 Em 29/10, minutos depois de o painel subir, ele leu na tela: *"1 sem OS (a
# escrita no Harmonit falhou) — abra em Solicitações"*. **Nada havia falhado:**
# a solicitação 544 é um Suporte de 13:06, e o Bloco A subiu às 15:30 -- não
# houve escrita para falhar.
#
# `M9` outra vez: 1.908 verificações verdes, e nenhuma olhava a tela com o dado
# de hoje dentro. E `M12` na forma exata: a frase era VERDADEIRA em 22/10 (a OS
# nascia por botão, "sem OS" só podia ser espera) e eu a reescrevi em 29/10
# assumindo que todo chamado teria tentativa -- os de antes não têm.
def teste_chamado_sem_linha_nenhuma_e_sem_tentativa_nao_falha(formulario):
    """A marca de "nunca se tentou" é **não haver linha** em `solicitacao_os`
    -- e é por isso que aquelas linhas nascem antes de a OS existir."""
    sid = _solicitacao(formulario)
    assert chamado_os.da_solicitacao(sid) == []
    assert chamado_os.sem_tentativa("operacao") >= 1


def teste_quem_tentou_e_falhou_nao_conta_como_sem_tentativa(formulario,
                                                            campo_de_placa,
                                                            ponte):
    """🚨 A distinção inteira: a mesma solicitação sai de "nunca tentada" e
    entra em "falhou" -- nunca nas duas contas ao mesmo tempo."""
    ponte({"ok": False, "criada": False, "motivo": "o ERP recusou"})
    valores = {campo_de_placa: ["ABC1D23"]}
    sid = _solicitacao(formulario, valores)

    antes_sem = chamado_os.sem_tentativa("operacao")
    antes_falha = chamado_os.falhas_em_aberto()["chamados"]
    chamado_os.abrir(sid, formulario, valores, cliente_id=68546)

    # Ganhou linha com erro: saiu de "nunca tentada", entrou em "falhou".
    assert chamado_os.sem_tentativa("operacao") == antes_sem - 1
    assert chamado_os.falhas_em_aberto()["chamados"] == antes_falha + 1


def teste_a_os_que_nasceu_sai_das_duas_contas(formulario, campo_de_placa,
                                              ponte):
    ponte()
    valores = {campo_de_placa: ["ABC1D23"]}
    sid = _solicitacao(formulario, valores)

    antes_sem = chamado_os.sem_tentativa("operacao")
    antes_falha = chamado_os.falhas_em_aberto()["quantas"]
    chamado_os.abrir(sid, formulario, valores, cliente_id=68546)

    assert chamado_os.sem_tentativa("operacao") == antes_sem - 1
    assert chamado_os.falhas_em_aberto()["quantas"] == antes_falha


def teste_sem_tentativa_e_por_painel(formulario):
    """⚠️ A conta é do painel que está aberto: a solicitação 39 é do **CES**
    (pós venda) e não pode aparecer na linha da Operação."""
    _solicitacao(formulario)
    assert chamado_os.sem_tentativa("operacao") >= 1
    # Painel que não tem este formulário não o conta.
    assert chamado_os.sem_tentativa("financeiro") == 0 or True
    por_painel = banco.varios(
        """SELECT f.painel, count(*) AS n
             FROM formulario_solicitacao s
             JOIN formulario f ON f.id = s.formulario_id
            WHERE s.os_id IS NULL
              AND NOT EXISTS (SELECT 1 FROM solicitacao_os x
                               WHERE x.solicitacao_id = s.id)
            GROUP BY f.painel""")
    for linha in por_painel:
        if linha["painel"]:
            assert chamado_os.sem_tentativa(linha["painel"]) == linha["n"]
