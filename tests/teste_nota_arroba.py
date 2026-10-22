"""O `@` na nota interna: chama gente NOSSA, e o aviso sai pelo chat interno.

🚨 Escreve em `atendente`, `conversa`, `conversa_participante`, `mensagem` e
nas tabelas do chat interno, que são de PRODUÇÃO. Login `zz_teste_na_` e
número `+5518977774001`; tudo apagado no fim, e a limpeza é por esses dois
prefixos -- nunca por tabela inteira.

O que estes testes guardam:
  · quem pode ser chamado é o DONO + os convidados ATIVOS, pela mesma régua de
    `esta_na_conversa`: quem saiu da conversa e quem está inativo saem da lista;
  · 🚨 chamar quem NÃO está na conversa é RECUSA, e a nota NÃO é gravada -- a
    conferência vem antes do INSERT, senão a pessoa reescreveria a nota e a
    conversa ficaria com duas;
  · o aviso vai pelo CHAT INTERNO, com menção gravada em `chat_mencao` (que é o
    que acende o contador separado e o selo) e com o link `/atendimento/<id>`;
  · 🚨 NOTA NÃO VAI AO WHATSAPP nem quando chama alguém: o Evolution não é
    sequer tocado, e a linha gravada é `tipo='nota'` com `direcao='interna'`;
  · falha no aviso NÃO desfaz a nota -- ela volta com `avisos_falhos`, porque
    perder o texto escrito para punir uma falha de aviso seria pior;
  · chamar a si mesmo sai da lista em silêncio, e não é erro.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, "/home/claude/movizap_painel")
pytest.importorskip("psycopg")

from movizap import banco, chat, conversas, operacao  # noqa: E402

ENV = Path("/home/claude/movizap_painel/.env")
pytestmark = pytest.mark.skipif(
    not ENV.exists() or "MOVIZAP_DB_SENHA" not in ENV.read_text(encoding="utf-8"),
    reason="banco nao configurado no .env")

LOGIN = "zz_teste_na_"
NUMERO = "+5518977774001"


def limpar():
    """🚨 SÓ O QUE ESTE TESTE CRIOU, e por ID -- nunca por janela de tempo.

    Uma versão anterior disto apagaria "sala direta vazia criada na última
    hora", que é uma rede capaz de pegar sala de gente de verdade. O alvo são
    as salas que têm um atendente `zz_teste_na_` como membro, lidas ANTES de
    apagar os membros (depois delas não haveria como achar as salas).
    """
    meus = [r["id"] for r in banco.varios(
        "SELECT id FROM atendente WHERE login LIKE %s", (LOGIN + "%",))]
    if meus:
        salas = [r["sala_id"] for r in banco.varios(
            "SELECT DISTINCT sala_id FROM chat_membro WHERE atendente_id = ANY(%s)",
            (meus,))]
        if salas:
            # A ordem é a das chaves: reação e menção, mensagem, membro, sala.
            for sql in (
                """DELETE FROM chat_reacao WHERE mensagem_id IN
                    (SELECT id FROM chat_mensagem WHERE sala_id = ANY(%s))""",
                """DELETE FROM chat_mencao WHERE mensagem_id IN
                    (SELECT id FROM chat_mensagem WHERE sala_id = ANY(%s))""",
                "DELETE FROM chat_mensagem WHERE sala_id = ANY(%s)",
                "DELETE FROM chat_membro WHERE sala_id = ANY(%s)",
                "DELETE FROM chat_sala WHERE id = ANY(%s)",
            ):
                banco.executar(sql, (salas,))
    banco.executar("""DELETE FROM mensagem WHERE conversa_id IN
                       (SELECT id FROM conversa WHERE telefone_e164 = %s)""",
                   (NUMERO,))
    banco.executar("""DELETE FROM conversa_participante WHERE conversa_id IN
                       (SELECT id FROM conversa WHERE telefone_e164 = %s)""",
                   (NUMERO,))
    banco.executar("DELETE FROM conversa WHERE telefone_e164 = %s", (NUMERO,))
    banco.executar("DELETE FROM atendente WHERE login LIKE %s", (LOGIN + "%",))


@pytest.fixture(scope="module", autouse=True)
def cena():
    banco.abrir()
    limpar()
    dono = operacao.criar_atendente("Zz Nota Dona", LOGIN + "1",
                                    LOGIN + "1@teste.invalid")
    dentro = operacao.criar_atendente("Zz Nota Dentro", LOGIN + "2",
                                      LOGIN + "2@teste.invalid")
    saiu = operacao.criar_atendente("Zz Nota Saiu", LOGIN + "3",
                                    LOGIN + "3@teste.invalid")
    fora = operacao.criar_atendente("Zz Nota Fora", LOGIN + "4",
                                    LOGIN + "4@teste.invalid")
    inativo = operacao.criar_atendente("Zz Nota Inativo", LOGIN + "5",
                                       LOGIN + "5@teste.invalid")
    banco.executar("UPDATE atendente SET ativo = false WHERE id = %s",
                   (inativo["id"],))

    canal = banco.um("SELECT id FROM canal ORDER BY id LIMIT 1")
    contato = banco.um(
        """INSERT INTO contato (nome, origem) VALUES ('Zz Cliente da Nota',
                                                   'movizap')
           RETURNING id""")["id"]
    conversa = banco.um(
        """INSERT INTO conversa (canal_id, telefone_e164, estado, atendente_id,
                                 contato_id)
           VALUES (%s, %s, 'humano', %s, %s) RETURNING id""",
        (canal["id"], NUMERO, dono["id"], contato))["id"]
    # Um convidado ativo, um que saiu, e o inativo convidado (para provar que
    # ativo é condição, não detalhe).
    banco.executar(
        """INSERT INTO conversa_participante (conversa_id, atendente_id,
                                              convidado_por, entrou_em)
           VALUES (%s, %s, %s, now())""",
        (conversa, dentro["id"], dono["id"]))
    banco.executar(
        """INSERT INTO conversa_participante (conversa_id, atendente_id,
                                              convidado_por, entrou_em, saiu_em)
           VALUES (%s, %s, %s, now(), now())""",
        (conversa, saiu["id"], dono["id"]))
    banco.executar(
        """INSERT INTO conversa_participante (conversa_id, atendente_id,
                                              convidado_por, entrou_em)
           VALUES (%s, %s, %s, now())""",
        (conversa, inativo["id"], dono["id"]))

    yield {"conversa": conversa, "dono": dono["id"], "dentro": dentro["id"],
           "saiu": saiu["id"], "fora": fora["id"], "inativo": inativo["id"],
           "contato": contato}

    limpar()
    banco.executar("DELETE FROM contato WHERE id = %s", (contato,))


def notas(conversa_id):
    return banco.um("SELECT count(*) n FROM mensagem WHERE conversa_id = %s "
                    "AND tipo = 'nota'", (conversa_id,))["n"]


def avisos_para(quem):
    """As mensagens do chat em que `quem` foi chamado."""
    return banco.varios(
        """SELECT cm.texto FROM chat_mencao mc
             JOIN chat_mensagem cm ON cm.id = mc.mensagem_id
            WHERE mc.atendente_id = %s ORDER BY cm.id""", (quem,))


class TesteQuemPodeSerChamado:
    def teste_e_o_dono_e_o_convidado_ativo(self, cena):
        ids = [p["id"] for p in conversas.quem_esta_na_conversa(cena["conversa"])]
        assert cena["dono"] in ids
        assert cena["dentro"] in ids

    def teste_quem_saiu_e_quem_esta_inativo_ficam_fora(self, cena):
        ids = [p["id"] for p in conversas.quem_esta_na_conversa(cena["conversa"])]
        assert cena["saiu"] not in ids
        assert cena["inativo"] not in ids
        assert cena["fora"] not in ids

    def teste_o_dono_vem_primeiro_e_marcado(self, cena):
        lista = conversas.quem_esta_na_conversa(cena["conversa"])
        assert lista[0]["id"] == cena["dono"]
        assert lista[0]["dono"] is True

    def teste_a_regua_e_a_mesma_de_quem_pode_agir(self, cena):
        """🚨 Oferecer na tela quem a rota recusa seria o defeito."""
        for p in conversas.quem_esta_na_conversa(cena["conversa"]):
            assert conversas.esta_na_conversa(cena["conversa"], p["id"])


class TesteChamarNaNota:
    def teste_chama_quem_esta_e_o_aviso_sai_pelo_chat(self, cena):
        antes = len(avisos_para(cena["dentro"]))
        r = conversas.anotar(cena["conversa"], "o cliente cobrou o retorno",
                             cena["dono"], chamar=[cena["dentro"]])
        assert r["ok"] is True
        assert [c["id"] for c in r["chamados"]] == [cena["dentro"]]
        assert r["avisos_falhos"] == []
        depois = avisos_para(cena["dentro"])
        assert len(depois) == antes + 1

    def teste_o_aviso_leva_o_link_da_conversa_o_nome_e_o_trecho(self, cena):
        conversas.anotar(cena["conversa"], "confere a nota fiscal dele",
                         cena["dono"], chamar=[cena["dentro"]])
        texto = avisos_para(cena["dentro"])[-1]["texto"]
        assert f"/atendimento/{cena['conversa']}" in texto
        # O título vem do CADASTRO, não do telefone.
        assert "Zz Cliente da Nota" in texto
        assert "confere a nota fiscal dele" in texto
        assert "@Zz Nota Dentro" in texto

    def teste_trecho_longo_e_cortado_com_reticencia(self, cena):
        longo = "x" * (conversas.TRECHO_NO_AVISO + 50)
        conversas.anotar(cena["conversa"], longo, cena["dono"],
                         chamar=[cena["dentro"]])
        texto = avisos_para(cena["dentro"])[-1]["texto"]
        assert "…" in texto
        assert "x" * (conversas.TRECHO_NO_AVISO + 1) not in texto

    def teste_chamar_quem_nao_esta_recusa_e_NAO_grava_a_nota(self, cena):
        """🚨 A conferência vem antes do INSERT."""
        antes = notas(cena["conversa"])
        r = conversas.anotar(cena["conversa"], "nota que nao deve existir",
                             cena["dono"], chamar=[cena["fora"]])
        assert r["ok"] is False
        assert "Zz Nota Fora" in r["motivo"]
        assert "convide" in r["motivo"]
        assert notas(cena["conversa"]) == antes

    def teste_quem_saiu_da_conversa_tambem_e_recusado(self, cena):
        r = conversas.anotar(cena["conversa"], "nota", cena["dono"],
                             chamar=[cena["saiu"]])
        assert r["ok"] is False
        assert "Zz Nota Saiu" in r["motivo"]

    def teste_chamar_a_si_mesmo_sai_da_lista_sem_recusar(self, cena):
        antes = notas(cena["conversa"])
        r = conversas.anotar(cena["conversa"], "anotando para mim",
                             cena["dono"], chamar=[cena["dono"]])
        assert r["ok"] is True
        assert r["chamados"] == []
        assert notas(cena["conversa"]) == antes + 1

    def teste_teto_recusa_antes_de_olhar_quem_e(self, cena):
        demais = list(range(900001, 900001 + chat.TETO_MENCOES + 1))
        r = conversas.anotar(cena["conversa"], "nota", cena["dono"],
                             chamar=demais)
        assert r["ok"] is False
        assert str(chat.TETO_MENCOES) in r["motivo"]

    def teste_nota_sem_chamar_segue_como_sempre(self, cena):
        r = conversas.anotar(cena["conversa"], "nota simples", cena["dono"])
        assert r["ok"] is True
        assert r["chamados"] == []
        assert r["avisos_falhos"] == []


class TesteNotaNaoVazaNemQuandoChama:
    def teste_a_linha_gravada_e_interna(self, cena):
        r = conversas.anotar(cena["conversa"], "interna mesmo", cena["dono"],
                             chamar=[cena["dentro"]])
        linha = banco.um("SELECT tipo, direcao FROM mensagem WHERE id = %s",
                         (r["mensagem_id"],))
        assert linha["tipo"] == "nota"
        assert linha["direcao"] == "interna"

    def teste_o_evolution_nao_e_tocado(self, cena, monkeypatch):
        """🚨 Nota com menção continua não indo ao WhatsApp."""
        from movizap import evolution

        def recusar(*a, **k):
            raise AssertionError("a nota tentou falar com o WhatsApp")

        monkeypatch.setattr(evolution, "enviar_texto", recusar)
        r = conversas.anotar(cena["conversa"], "sem WhatsApp", cena["dono"],
                             chamar=[cena["dentro"]])
        assert r["ok"] is True


class TesteFalhaNoAviso:
    def teste_aviso_recusado_nao_desfaz_a_nota(self, cena, monkeypatch):
        monkeypatch.setattr(chat, "escrever",
                            lambda *a, **k: {"ok": False, "motivo": "sala cheia"})
        antes = notas(cena["conversa"])
        r = conversas.anotar(cena["conversa"], "a nota tem de ficar",
                             cena["dono"], chamar=[cena["dentro"]])
        assert r["ok"] is True
        assert notas(cena["conversa"]) == antes + 1
        assert [f["nome"] for f in r["avisos_falhos"]] == ["Zz Nota Dentro"]
        assert r["chamados"] == []

    def teste_erro_no_chat_nao_derruba_a_nota(self, cena, monkeypatch):
        def explodir(*a, **k):
            raise RuntimeError("chat fora do ar")

        monkeypatch.setattr(chat, "abrir_direta", explodir)
        r = conversas.anotar(cena["conversa"], "nota com chat fora",
                             cena["dono"], chamar=[cena["dentro"]])
        assert r["ok"] is True
        assert r["avisos_falhos"][0]["motivo"].startswith("não consegui avisar")
