"""As fixtures dos testes passam a ter ROTULO, porque a caixa agora depende dele.

🚨 POR QUE OS TESTES COBRAM, e por que corrigir a fixture e o certo. Ate agora
"mensagem na Entrada" era `NOT arquivada AND viva`, e uma linha sem rotulo
nenhum servia de fixture. Com a Entrada exigindo `INBOX` (22/10), essa mesma
linha passa a cair em **Arquivadas** -- e esta certo: mensagem sem `INBOX` e
sem `SENT` esta arquivada no Gmail.

A fixture e que estava irreal: mensagem de caixa de entrada SEMPRE tem o rotulo
`INBOX` no Gmail. Afrouxar o filtro para o teste passar seria escrever o
defeito no codigo para agradar a fixture.
"""
import shutil
import sys

# ---------------------------------------------------------------------------
# Um ajudante comum: criar o marcador da conta e pendurar na mensagem.
# ---------------------------------------------------------------------------
AJUDANTE = '''

def _rotular(conta: int, mensagem_id: int, *rotulos: str) -> None:
    """Pendura rótulos do Gmail na mensagem, criando o marcador se faltar.

    🚨 A CAIXA DA MENSAGEM DEPENDE DISTO desde 22/10: `INBOX` manda para a
    Entrada, `SENT` para Enviados, nenhum dos dois para Arquivadas (= está
    arquivada no Gmail). Fixture sem rótulo não representa mensagem de caixa
    de entrada nenhuma -- representa uma mensagem arquivada.
    """
    for rotulo in rotulos:
        mid = banco.um(
            """INSERT INTO email_marcador (conta_id, id_externo, nome, natureza)
               VALUES (%s, %s, %s, 'sistema')
               ON CONFLICT (conta_id, id_externo) DO UPDATE SET nome = EXCLUDED.nome
               RETURNING id""", (conta, rotulo, rotulo))["id"]
        banco.executar(
            """INSERT INTO email_mensagem_marcador (mensagem_id, marcador_id)
               VALUES (%s, %s) ON CONFLICT DO NOTHING""", (mensagem_id, mid))
'''

# ---------------------------------------------------------------------------
# teste_selo_email.py -- o `_mensagem` passa a nascer com INBOX.
# ---------------------------------------------------------------------------
SELO = "tests/teste_selo_email.py"

SELO_ANTES = '''def _mensagem(conta: int, chave: str, **campos) -> int:
    """Uma mensagem na caixa. Por padrão NÃO lida e na entrada."""
    dados = {"lida": False, "arquivada": False, "na_lixeira_desde": None}
    dados.update(campos)
    return banco.um(
        """INSERT INTO email_mensagem (conta_id, id_externo, remetente, assunto,
                                       lida, arquivada, na_lixeira_desde)
           VALUES (%s, %s, 'quem@fora.com', 'assunto', %s, %s, %s)
           RETURNING id""",
        (conta, chave, dados["lida"], dados["arquivada"],
         dados["na_lixeira_desde"]))["id"]'''

SELO_DEPOIS = '''def _mensagem(conta: int, chave: str, rotulos=("INBOX",), **campos) -> int:
    """Uma mensagem na caixa. Por padrão NÃO lida, na entrada, com `INBOX`.

    🚨 O `INBOX` NO PADRÃO NÃO É DETALHE. Desde 22/10 a Entrada exige esse
    rótulo: é a verdade do Gmail sobre onde a mensagem está, e foi a falta
    dela no filtro que fez o selo contar uma mensagem já arquivada no Gmail
    (dizia 1 onde o Gmail dizia 0). Fixture sem rótulo não é mensagem de
    caixa de entrada -- é mensagem arquivada, e os testes daqui falariam por
    motivo errado.
    """
    dados = {"lida": False, "arquivada": False, "na_lixeira_desde": None}
    dados.update(campos)
    mid = banco.um(
        """INSERT INTO email_mensagem (conta_id, id_externo, remetente, assunto,
                                       lida, arquivada, na_lixeira_desde)
           VALUES (%s, %s, 'quem@fora.com', 'assunto', %s, %s, %s)
           RETURNING id""",
        (conta, chave, dados["lida"], dados["arquivada"],
         dados["na_lixeira_desde"]))["id"]
    if rotulos:
        _rotular(conta, mid, *rotulos)
    return mid'''

SELO_EXTRA = '''

class TestOSeloEhSoDaENTRADA:
    """🔵 22/10, segunda correção: *"siga com a 2"* -- a Entrada e o selo
    passam a exigir o rótulo `INBOX`, que é o que o Gmail usa para dizer "está
    na caixa de entrada". Antes disso o selo contava o que o Gmail já tinha
    arquivado."""

    def test_sem_rotulo_INBOX_nao_conta(self, cena):
        """🚨 ERA O DEFEITO RESTANTE, e era UMA mensagem na caixa real: um
        "Alerta de segurança" do Google, não lido desde 22/04 e **arquivado no
        Gmail** (sem `INBOX` desde a importação). O selo dizia 1, o Gmail 0."""
        _mensagem(cena["conta"], "zz-sem-inbox", rotulos=())
        assert _contador() == 0

    def test_a_enviada_nao_conta(self, cena):
        """Enviada é lugar próprio desde 22/10, e nunca foi "não lida da
        caixa de entrada" -- mesmo que o Gmail a marque como não lida."""
        _mensagem(cena["conta"], "zz-enviada", rotulos=("SENT",))
        assert _contador() == 0

    def test_com_INBOX_conta(self, cena):
        _mensagem(cena["conta"], "zz-na-caixa", rotulos=("INBOX",))
        assert _contador() == 1
'''

# ---------------------------------------------------------------------------
# teste_filtro_sumida.py -- o `_msg` ganha rotulos e entram as caixas novas.
# ---------------------------------------------------------------------------
SUMIDA = "tests/teste_filtro_sumida.py"

SUMIDA_ANTES = '''def _msg(conta, chave, *, lida=False, arquivada=False,
         lixeira=False, sumida=False):
    """Uma mensagem num dos estados que a varredura do Gmail produz."""
    mid = banco.um(
        """INSERT INTO email_mensagem (conta_id, id_externo, remetente, assunto,
                                       lida, arquivada)
           VALUES (%s, %s, 'quem@fora.com', %s, %s, %s) RETURNING id""",
        (conta, chave, chave, lida, arquivada))["id"]'''

SUMIDA_DEPOIS = '''def _msg(conta, chave, *, lida=False, arquivada=False,
         lixeira=False, sumida=False, rotulos=("INBOX",)):
    """Uma mensagem num dos estados que a varredura do Gmail produz.

    ⚠️ `rotulos` padrão `("INBOX",)`: desde 22/10 a caixa da mensagem sai do
    rótulo do Gmail, e sem ele a fixture representaria uma mensagem arquivada.
    """
    mid = banco.um(
        """INSERT INTO email_mensagem (conta_id, id_externo, remetente, assunto,
                                       lida, arquivada)
           VALUES (%s, %s, 'quem@fora.com', %s, %s, %s) RETURNING id""",
        (conta, chave, chave, lida, arquivada))["id"]
    if rotulos:
        _rotular(conta, mid, *rotulos)'''

SUMIDA_IDS_ANTES = '''def _ids(caixa):
    r = _cliente().get(f"/api/email/mensagens?caixa={caixa}&limite=500")
    assert r.status_code == 200, r.text
    return {m["id"] for m in r.json()["mensagens"]}'''

SUMIDA_IDS_DEPOIS = '''def _ids(caixa):
    r = _cliente().get(f"/api/email/mensagens?caixa={caixa}&limite=500")
    assert r.status_code == 200, r.text
    return {m["id"] for m in r.json()["mensagens"]}


CAIXAS = ("entrada", "enviados", "arquivadas", "lixeira")


def _onde(mensagem_id):
    """Em que caixas esta mensagem aparece. Tem de ser exatamente uma."""
    return [c for c in CAIXAS if mensagem_id in _ids(c)]'''

# A parametrizacao de "exatamente uma aba" ganha os casos de rotulo, e passa a
# conferir as QUATRO caixas.
PARAM_ANTES = '''    @pytest.mark.parametrize("estado", [
        {"lixeira": True},
        {"sumida": True},
        {"lixeira": True, "sumida": True},
        {"arquivada": True},
        {},
    ])
    def test_toda_mensagem_cai_em_EXATAMENTE_uma_aba(self, cena, estado):'''

PARAM_DEPOIS = '''    @pytest.mark.parametrize("estado", [
        {"lixeira": True},
        {"sumida": True},
        {"lixeira": True, "sumida": True},
        {"arquivada": True},
        {},
        # 🔵 22/10: os casos que as quatro caixas trouxeram. O penúltimo é a
        # mensagem com os DOIS rótulos (medida: 1 na caixa real) e o último é
        # a sem nenhum (medida: 1 -- o "Alerta de segurança" do Google, que
        # antes não caía em caixa nenhuma).
        {"rotulos": ("SENT",)},
        {"rotulos": ("SENT",), "lixeira": True},
        {"rotulos": ("INBOX", "SENT")},
        {"rotulos": ()},
    ])
    def test_toda_mensagem_cai_em_EXATAMENTE_uma_aba(self, cena, estado):'''

PARAM_CORPO_ANTES = '''        m = _msg(cena["conta"], "zz-uma-aba", **estado)
        onde = [c for c in ("entrada", "arquivadas", "lixeira") if m in _ids(c)]
        assert onde == [onde[0]] and len(onde) == 1, \\
            f"estado {estado} caiu em {onde}, deveria cair em exatamente uma"'''

PARAM_CORPO_DEPOIS = '''        m = _msg(cena["conta"], "zz-uma-aba", **estado)
        onde = _onde(m)
        assert len(onde) == 1, \\
            f"estado {estado} caiu em {onde}, deveria cair em exatamente uma"'''

SUMIDA_EXTRA = '''

class TestEnviadosEhLugar:
    """🔵 22/10: *"enviadas devem ter seu proprio grupo, igual no Gmail"*.

    🚨 ANTES DISSO "Entrada" EXISTIA EM DOIS CONTROLES -- a aba de caixa e a
    lista de marcadores -- e a tela mandava os dois ao servidor de uma vez
    (`caixa=lixeira&marcador=INBOX`, visto no log). Consequência medida: **11
    mensagens enviadas na lixeira ficavam invisíveis**, porque a Lixeira era
    filtrada pelo rótulo da Entrada. O conserto é de modelo: caixa é LUGAR,
    marcador é ETIQUETA.
    """

    def test_a_enviada_fica_em_Enviados(self, cena):
        m = _msg(cena["conta"], "zz-enviada", rotulos=("SENT",))
        assert _onde(m) == ["enviados"]

    def test_a_enviada_nao_aparece_na_Entrada(self, cena):
        m = _msg(cena["conta"], "zz-enviada", rotulos=("SENT",))
        assert m not in _ids("entrada")

    def test_a_enviada_na_lixeira_aparece_na_LIXEIRA(self, cena):
        """🚨 AS 11 INVISÍVEIS. A Lixeira não pode filtrar pelo rótulo da
        Entrada: o que está na lixeira está na lixeira, venha de onde vier."""
        m = _msg(cena["conta"], "zz-enviada-lixo", rotulos=("SENT",), lixeira=True)
        assert _onde(m) == ["lixeira"]

    def test_a_que_tem_os_DOIS_rotulos_fica_na_Entrada(self, cena):
        """Medido: 1 mensagem na caixa real tem `INBOX` e `SENT`. A Entrada
        ganha, por precedência explícita -- é o que mantém "exatamente uma
        caixa" verdadeiro, e a decisão está escrita no `main.py`."""
        m = _msg(cena["conta"], "zz-ambos", rotulos=("INBOX", "SENT"))
        assert _onde(m) == ["entrada"]

    def test_a_sem_rotulo_nenhum_fica_em_Arquivadas(self, cena):
        """🚨 ESTA É A QUE NÃO PODIA DESAPARECER. Sem `INBOX` e sem `SENT`, a
        mensagem está arquivada no Gmail -- e antes de 22/10 ela não caía em
        caixa nenhuma depois da Entrada passar a exigir `INBOX`. É o mesmo
        defeito das 73 sumidas, que custou a volta anterior deste mesmo dia."""
        m = _msg(cena["conta"], "zz-sem-rotulo", rotulos=())
        assert _onde(m) == ["arquivadas"]

    def test_arquivada_pelo_painel_fica_em_Arquivadas_mesmo_com_INBOX(self, cena):
        """⚠️ Arquivar pelo painel tira o `INBOX` no Gmail, mas NÃO apaga o
        marcador local (só o `UNREAD` é apagado, em `marcar_lida`). Sem a
        nossa coluna `arquivada` tendo precedência no filtro, a mensagem
        arquivada pelo painel voltaria para a Entrada."""
        m = _msg(cena["conta"], "zz-arq-com-inbox",
                 rotulos=("INBOX",), arquivada=True)
        assert _onde(m) == ["arquivadas"]
'''


def aplicar(caminho, passos, ajudante_depois_de=None, extra=None, marca=None):
    texto = open(caminho, encoding="utf-8").read()
    if marca and marca in texto:
        raise SystemExit(f"{caminho}: ja aplicado")
    for antes, depois, rotulo in passos:
        n = texto.count(antes)
        if n != 1:
            raise SystemExit(f"FALHOU {caminho} / {rotulo}: {n} ocorrencias")
        texto = texto.replace(antes, depois, 1)
        print(f"ok  {caminho}: {rotulo}")
    if ajudante_depois_de:
        n = texto.count(ajudante_depois_de)
        if n != 1:
            raise SystemExit(f"FALHOU {caminho}: ancora do ajudante ({n})")
        texto = texto.replace(ajudante_depois_de,
                              ajudante_depois_de + AJUDANTE, 1)
        print(f"ok  {caminho}: o ajudante `_rotular`")
    if extra:
        texto = texto.rstrip("\n") + "\n" + extra
        print(f"ok  {caminho}: testes novos")
    shutil.copyfile(caminho, caminho + ".bak_2026-10-22_caixas")
    open(caminho, "w", encoding="utf-8").write(texto)


def main() -> int:
    aplicar(
        SELO,
        [(SELO_ANTES, SELO_DEPOIS, "o `_mensagem` nasce com INBOX")],
        ajudante_depois_de='LOGIN = "zz_teste_selo_email_"\n'
                           'ENDERECO = "zz_teste_selo_email@movisat.com.br"\n',
        extra=SELO_EXTRA, marca="_rotular")
    aplicar(
        SUMIDA,
        [(SUMIDA_ANTES, SUMIDA_DEPOIS, "o `_msg` ganha rotulos"),
         (SUMIDA_IDS_ANTES, SUMIDA_IDS_DEPOIS, "o ajudante `_onde` e as 4 caixas"),
         (PARAM_ANTES, PARAM_DEPOIS, "os casos de rotulo na parametrizacao"),
         (PARAM_CORPO_ANTES, PARAM_CORPO_DEPOIS, "o corpo confere as 4")],
        ajudante_depois_de='LOGIN = "zz_teste_sumida_"\n'
                           'ENDERECO = "zz_teste_sumida@movisat.com.br"\n',
        extra=SUMIDA_EXTRA, marca="_rotular")
    return 0


if __name__ == "__main__":
    sys.exit(main())
