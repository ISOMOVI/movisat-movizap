"""Aviso de nota interna (28/10) — a régua de QUEM é avisado, e o corte.

🔵 Pedido dele: *"verifique se as notas internas tbm estao gerando notificacoes
como mensagens novas no movizap, se nao tiver - proponha para que sejam tbm"* e,
depois da proposta, *"somente daqui para frente, pode ajustar notific para
notas"*.

🚨 O QUE ESTE ARQUIVO EXISTE PARA PRENDER:
  · o AUTOR não é avisado da própria nota -- avisar a pessoa do que ela acabou
    de escrever é o jeito mais rápido de a equipe aprender a ignorar o selo;
  · **só daqui para frente**: nota anterior ao corte não avisa. Sem isso, as 310
    notas que já existiam virariam 310 avisos no primeiro ciclo de 8 s;
  · os TRÊS destinatários (dono · convidado ativo · quem já anotou ali), e o
    terceiro não é enfeite: medido em 28/10, **207 das 310 notas estão em
    conversa SEM DONO**, e sem ele dois terços seguiriam mudos;
  · quem não é nenhum dos três **não** recebe -- selo não é mural;
  · o EVENTO (log de ações) não avisa: são 530 dos 840 registros `tipo='nota'`;
  · o aviso morre quando a pessoa VÊ a nota, e "ver" é a linha de
    `nota_leitura` que a tela já grava sozinha -- é o que dispensa migração.

🚨 Escreve em `atendente`, `conversa`, `mensagem`, `nota_leitura` e
`conversa_participante`, tabelas de PRODUÇÃO. Login `zz_teste_an_` e números
`+5518977774xxx`; tudo apagado no fim.
"""
import sys
from datetime import timedelta
from pathlib import Path

import pytest

sys.path.insert(0, "/home/claude/movizap_painel")
pytest.importorskip("psycopg")

from fastapi.testclient import TestClient  # noqa: E402

from movizap import auth, banco, conversas, main, operacao, preferencia  # noqa: E402

ENV = Path("/home/claude/movizap_painel/.env")
pytestmark = pytest.mark.skipif(
    not ENV.exists() or "MOVIZAP_DB_SENHA" not in ENV.read_text(encoding="utf-8"),
    reason="banco nao configurado no .env")

LOGIN = "zz_teste_an_"
COM_DONO = "+5518977774001"
SEM_DONO = "+5518977774002"
NUMEROS = [COM_DONO, SEM_DONO]

DEPOIS = conversas.NOTIFICA_NOTA_DESDE + timedelta(minutes=5)
ANTES = conversas.NOTIFICA_NOTA_DESDE - timedelta(days=30)


def limpar():
    banco.executar(
        """DELETE FROM nota_leitura WHERE mensagem_id IN
            (SELECT id FROM mensagem WHERE conversa_id IN
              (SELECT id FROM conversa WHERE telefone_e164 = ANY(%s)))""", (NUMEROS,))
    banco.executar(
        """DELETE FROM conversa_participante WHERE conversa_id IN
            (SELECT id FROM conversa WHERE telefone_e164 = ANY(%s))""", (NUMEROS,))
    banco.executar(
        """DELETE FROM mensagem WHERE conversa_id IN
            (SELECT id FROM conversa WHERE telefone_e164 = ANY(%s))""", (NUMEROS,))
    banco.executar("DELETE FROM conversa WHERE telefone_e164 = ANY(%s)", (NUMEROS,))
    banco.executar("DELETE FROM atendente WHERE login LIKE %s", (LOGIN + "%",))


@pytest.fixture(scope="module", autouse=True)
def cena():
    banco.abrir()
    limpar()
    dono = operacao.criar_atendente("Zz Aviso Dono", LOGIN + "d",
                                    LOGIN + "d@teste.invalid")
    outro = operacao.criar_atendente("Zz Aviso Outro", LOGIN + "o",
                                     LOGIN + "o@teste.invalid")
    terceiro = operacao.criar_atendente("Zz Aviso Terceiro", LOGIN + "t",
                                        LOGIN + "t@teste.invalid")
    canal = banco.um("SELECT id FROM canal ORDER BY id LIMIT 1")
    com_dono = banco.um(
        """INSERT INTO conversa (canal_id, telefone_e164, estado, atendente_id)
           VALUES (%s, %s, 'humano', %s) RETURNING id""",
        (canal["id"], COM_DONO, dono["id"]))["id"]
    sem_dono = banco.um(
        """INSERT INTO conversa (canal_id, telefone_e164, estado)
           VALUES (%s, %s, 'nova') RETURNING id""", (canal["id"], SEM_DONO))["id"]
    yield {"dono": dono["id"], "outro": outro["id"], "terceiro": terceiro["id"],
           "com_dono": com_dono, "sem_dono": sem_dono}
    limpar()
    banco.fechar()


def nota(conversa_id, autor, quando=DEPOIS, texto="zz nota"):
    return banco.um(
        """INSERT INTO mensagem (conversa_id, direcao, autor, tipo, conteudo,
                                 atendente_id, criada_em)
           VALUES (%s, 'interna', 'atendente', 'nota', %s, %s, %s)
           RETURNING id""", (conversa_id, texto, autor, quando))["id"]


def apagar(*ids):
    banco.executar("DELETE FROM nota_leitura WHERE mensagem_id = ANY(%s)", (list(ids),))
    banco.executar("DELETE FROM mensagem WHERE id = ANY(%s)", (list(ids),))


def quantas(eu, conversa_id):
    for r in conversas.notas_novas_para(eu):
        if r["conversa_id"] == conversa_id:
            return r["quantas"]
    return 0


# ---------------------------------------------------------- quem é avisado

def test_dono_e_avisado_da_nota_de_outro(cena):
    m = nota(cena["com_dono"], cena["outro"])
    try:
        assert quantas(cena["dono"], cena["com_dono"]) == 1
    finally:
        apagar(m)


def test_o_autor_nao_e_avisado_da_propria_nota(cena):
    m = nota(cena["com_dono"], cena["dono"])
    try:
        assert quantas(cena["dono"], cena["com_dono"]) == 0
    finally:
        apagar(m)


def test_estranho_nao_e_avisado(cena):
    """Selo não é mural: quem não é dono, não foi convidado e nunca anotou
    naquela conversa não recebe nada."""
    m = nota(cena["com_dono"], cena["outro"])
    try:
        assert quantas(cena["terceiro"], cena["com_dono"]) == 0
    finally:
        apagar(m)


def test_convidado_ativo_e_avisado(cena):
    banco.executar(
        """INSERT INTO conversa_participante (conversa_id, atendente_id, convidado_por)
           VALUES (%s, %s, %s)""",
        (cena["com_dono"], cena["terceiro"], cena["dono"]))
    m = nota(cena["com_dono"], cena["outro"])
    try:
        assert quantas(cena["terceiro"], cena["com_dono"]) == 1
    finally:
        apagar(m)
        banco.executar(
            "DELETE FROM conversa_participante WHERE conversa_id = %s AND atendente_id = %s",
            (cena["com_dono"], cena["terceiro"]))


def test_quem_ja_anotou_e_avisado_mesmo_sem_dono(cena):
    """🚨 É ESTA REGRA QUE SALVA DOIS TERÇOS DAS NOTAS. Medido em 28/10: 207 das
    310 notas estão em conversa SEM DONO -- com a régua do dono sozinha, a
    maioria do recurso seguiria muda."""
    a = nota(cena["sem_dono"], cena["outro"], texto="zz primeira")
    b = nota(cena["sem_dono"], cena["terceiro"], texto="zz segunda")
    try:
        assert quantas(cena["outro"], cena["sem_dono"]) == 1
        assert quantas(cena["terceiro"], cena["sem_dono"]) == 1
        # e o dono de OUTRA conversa continua fora
        assert quantas(cena["dono"], cena["sem_dono"]) == 0
    finally:
        apagar(a, b)


# ---------------------------------------------------------- o corte do tempo

def test_so_daqui_para_frente(cena):
    """🚨 ORDEM DELE: *"somente daqui para frente"*."""
    velha = nota(cena["com_dono"], cena["outro"], quando=ANTES)
    try:
        assert quantas(cena["dono"], cena["com_dono"]) == 0
        nova = nota(cena["com_dono"], cena["outro"], quando=DEPOIS)
        try:
            assert quantas(cena["dono"], cena["com_dono"]) == 1
        finally:
            apagar(nova)
    finally:
        apagar(velha)


# ---------------------------------------------------------- o que apaga o aviso

def test_visto_por_zera_o_aviso(cena):
    """O contador é a AUSÊNCIA de linha em `nota_leitura` -- a tabela do "visto
    por" (15/10), que a tela já preenche ao rolar a nota. É o que faz este
    recurso entrar sem migração nenhuma."""
    m = nota(cena["com_dono"], cena["outro"])
    try:
        assert quantas(cena["dono"], cena["com_dono"]) == 1
        conversas.marcar_notas_vistas(cena["com_dono"], [m], cena["dono"])
        assert quantas(cena["dono"], cena["com_dono"]) == 0
    finally:
        apagar(m)


def test_evento_nao_avisa(cena):
    """🚨 530 dos 840 registros `tipo='nota'` são o LOG DE AÇÕES. Avisar isso
    encheria o selo com o que a própria pessoa acabou de fazer."""
    m = nota(cena["com_dono"], cena["outro"])
    banco.executar("UPDATE mensagem SET evento = 'transferiu' WHERE id = %s", (m,))
    try:
        assert quantas(cena["dono"], cena["com_dono"]) == 0
    finally:
        apagar(m)


def test_nota_apagada_nao_avisa(cena):
    m = nota(cena["com_dono"], cena["outro"])
    banco.executar("UPDATE mensagem SET apagada_em = now() WHERE id = %s", (m,))
    try:
        assert quantas(cena["dono"], cena["com_dono"]) == 0
    finally:
        apagar(m)


# ---------------------------------------------------------- a forma da resposta

def test_duas_notas_contam_duas_e_trazem_autor_e_trecho(cena):
    """O balão diz QUEM anotou: sem o autor, o aviso parece mensagem do
    cliente, que é exatamente o que ele não é."""
    a = nota(cena["com_dono"], cena["outro"], texto="zz confere o boleto")
    b = nota(cena["com_dono"], cena["outro"], texto="zz e o endereco tambem")
    try:
        linha = next(r for r in conversas.notas_novas_para(cena["dono"])
                     if r["conversa_id"] == cena["com_dono"])
        assert linha["quantas"] == 2
        assert (linha["autor"] or "").startswith("Zz Aviso")
        assert "endereco" in linha["trecho"]        # o trecho é o da MAIS NOVA
        assert len(linha["mensagem_ids"]) == 2
        assert linha["nome"]                        # a tela precisa de um rótulo
    finally:
        apagar(a, b)


def test_sem_atendente_nao_estoura(cena):
    """Quem não tem vínculo de atendente recebe lista vazia, não erro."""
    assert conversas.notas_novas_para(None) == []


# ---------------------------------------------------------- o interruptor

def test_interruptor_nasce_ligado_e_desliga(cena):
    """🚨 NASCE LIGADO porque ele PEDIU o aviso -- o oposto do atalho de teclado,
    que nasceu desligado porque ninguém pediu."""
    eu = cena["terceiro"]
    assert preferencia.aviso_nota(eu) is True
    preferencia.definir_aviso_nota(eu, False)
    assert preferencia.aviso_nota(eu) is False
    preferencia.definir_aviso_nota(eu, True)
    assert preferencia.aviso_nota(eu) is True


# ---------------------------------------------------------- a ROTA, de verdade
#
# 🚨 POR QUE ISTO EXISTE: a régua acima pode estar perfeita e o campo não
# chegar na tela. Foi exatamente o que aconteceu em 22/10 com o selo do e-mail
# -- a rota devolvia o número, o menu o lia, e nada no meio copiava; as duas
# suítes verdes. A auditoria de 22/10 também achou "10 rotas novas sem teste
# HTTP". Então o campo `notas` da rota tem trava própria.

def _cliente(login):
    c = TestClient(main.app)
    c.headers.update({"Authorization": f"Bearer {auth.criar_token(login)}"})
    return c


class TestARota:
    def test_a_rota_devolve_o_campo_notas(self, cena):
        m = nota(cena["com_dono"], cena["outro"], texto="zz pela rota")
        try:
            r = _cliente(LOGIN + "d").get("/api/eu/notificacoes")
            assert r.status_code == 200, r.text
            corpo = r.json()
            assert "notas" in corpo, \
                "a rota parou de devolver `notas` -- o selo e o som somem calados"
            minhas = [x for x in corpo["notas"]
                      if x["conversa_id"] == cena["com_dono"]]
            assert len(minhas) == 1, corpo["notas"]
            assert minhas[0]["quantas"] == 1
            assert minhas[0]["autor"].startswith("Zz Aviso")
            assert "pela rota" in minhas[0]["trecho"]
        finally:
            apagar(m)

    def test_a_rota_nao_mistura_nota_com_assumidas(self, cena):
        """🚨 `assumidas` alimenta o toque de MENSAGEM DO CLIENTE. Nota ali faria
        o balão dizer "Nova mensagem" quando foi um colega anotando."""
        m = nota(cena["com_dono"], cena["outro"])
        try:
            corpo = _cliente(LOGIN + "d").get("/api/eu/notificacoes").json()
            ids = [x["id"] for x in corpo.get("assumidas", [])]
            assert cena["com_dono"] not in ids, \
                "a conversa entrou em `assumidas` por causa de uma NOTA"
        finally:
            apagar(m)

    def test_desligar_o_interruptor_zera_a_rota(self, cena):
        m = nota(cena["com_dono"], cena["outro"])
        try:
            cli = _cliente(LOGIN + "d")
            assert cli.get("/api/eu/notificacoes").json()["notas"]
            r = cli.put("/api/eu/aviso-nota", json={"ligado": False})
            assert r.status_code == 200, r.text
            assert r.json()["aviso_nota"] is False
            assert cli.get("/api/eu/notificacoes").json()["notas"] == []
            # e a tela consegue LER o estado, para não mostrar "Avisar" a quem desligou
            avisos = cli.get("/api/eu/avisos").json()
            assert avisos["aviso_nota"] is False
        finally:
            _cliente(LOGIN + "d").put("/api/eu/aviso-nota", json={"ligado": True})
            apagar(m)

    def test_o_autor_nao_ve_a_propria_nota_na_rota(self, cena):
        m = nota(cena["com_dono"], cena["outro"])
        try:
            corpo = _cliente(LOGIN + "o").get("/api/eu/notificacoes").json()
            assert [x for x in corpo["notas"]
                    if x["conversa_id"] == cena["com_dono"]] == []
        finally:
            apagar(m)
