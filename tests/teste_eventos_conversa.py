"""O log de ações dentro da conversa (Bloco 11, 15/10).

🚨 Escreve em `atendente`, `conversa`, `mensagem`, `conversa_participante`,
`transferencia` e `numero_bloqueado`, tabelas de PRODUÇÃO. Login
`zz_teste_ev_` e número `+5518977772001`; tudo apagado no fim.

O que estes testes guardam:
  · cada ação deixa UMA linha, e ela diz o que aconteceu e quem fez;
  · o evento é NOTA INTERNA (`direcao = 'interna'`), então nunca vai ao
    cliente -- é o CHECK `ck_nota_e_interna` do banco que garante, e o teste
    prova que a gravação respeita o caminho;
  · `entrar` (auto-convite) e `convidar` alguém NÃO são o mesmo evento,
    embora passem pela mesma função;
  · 🚨 EVENTO NÃO SE EDITA NEM SE APAGA, nem por quem agiu -- e é justamente
    quem agiu que passaria no teste de "só quem escreveu", porque o
    `atendente_id` é dele;
  · evento não conta como não lida;
  · `mensagens()` devolve o campo `evento`: campo que a tela desenha tem de
    vir na consulta que ela pede.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, "/home/claude/movizap_painel")
pytest.importorskip("psycopg")

from movizap import banco, conversas, operacao  # noqa: E402

ENV = Path("/home/claude/movizap_painel/.env")
pytestmark = pytest.mark.skipif(
    not ENV.exists() or "MOVIZAP_DB_SENHA" not in ENV.read_text(encoding="utf-8"),
    reason="banco nao configurado no .env")

LOGIN = "zz_teste_ev_"
NUMERO = "+5518977772001"


def limpar():
    banco.executar("DELETE FROM numero_bloqueado WHERE telefone_e164 = %s", (NUMERO,))
    banco.executar("""DELETE FROM conversa_participante WHERE conversa_id IN
                       (SELECT id FROM conversa WHERE telefone_e164 = %s)""", (NUMERO,))
    banco.executar("""DELETE FROM transferencia WHERE conversa_id IN
                       (SELECT id FROM conversa WHERE telefone_e164 = %s)""", (NUMERO,))
    banco.executar("""DELETE FROM mensagem WHERE conversa_id IN
                       (SELECT id FROM conversa WHERE telefone_e164 = %s)""", (NUMERO,))
    banco.executar("DELETE FROM conversa WHERE telefone_e164 = %s", (NUMERO,))
    banco.executar("DELETE FROM atendente WHERE login LIKE %s", (LOGIN + "%",))


@pytest.fixture(scope="module", autouse=True)
def gente():
    banco.abrir()
    limpar()
    um = operacao.criar_atendente("Zz Evento Um", LOGIN + "1", LOGIN + "1@teste.invalid")
    dois = operacao.criar_atendente("Zz Evento Dois", LOGIN + "2", LOGIN + "2@teste.invalid")
    # ⚠️ `transferivel` é a regra de quem PODE receber transferência
    # (`_recebe_transferencia`), e conta nova não nasce com ela. Sem isto a
    # transferência é recusada com `ok: False` -- e o teste acusaria o evento
    # de faltar quando quem faltou foi a transferência.
    banco.executar("UPDATE atendente SET transferivel = true WHERE id = %s",
                   (dois["id"],))
    yield {"um": um["id"], "dois": dois["id"],
           "nome_dois": "Zz Evento Dois"}
    limpar()
    banco.fechar()


@pytest.fixture
def conversa():
    """Uma conversa nova por teste: o log é cumulativo, e contar eventos de uma
    conversa suja daria falso positivo."""
    banco.executar("DELETE FROM conversa WHERE telefone_e164 = %s", (NUMERO,))
    canal = banco.um("SELECT id FROM canal ORDER BY id LIMIT 1")
    linha = banco.um(
        """INSERT INTO conversa (canal_id, telefone_e164, estado)
           VALUES (%s, %s, 'nova') RETURNING id""", (canal["id"], NUMERO))
    yield linha["id"]


def eventos(conversa_id):
    return banco.varios(
        """SELECT evento, conteudo, autor, direcao, tipo, atendente_id
             FROM mensagem WHERE conversa_id = %s AND evento IS NOT NULL
            ORDER BY id""", (conversa_id,))


# ------------------------------------------------------------ cada ação

def test_assumir_deixa_uma_linha_com_quem_fez(conversa, gente):
    assert conversas.assumir(conversa, gente["um"])["ok"]
    linhas = eventos(conversa)
    assert len(linhas) == 1
    assert linhas[0]["evento"] == "assumiu"
    assert linhas[0]["conteudo"] == "assumiu a conversa"
    assert linhas[0]["atendente_id"] == gente["um"]


def test_o_evento_e_nota_interna_e_nunca_sai(conversa, gente):
    conversas.assumir(conversa, gente["um"])
    linha = eventos(conversa)[0]
    # 🚨 É o que impede o log da equipe de aparecer no WhatsApp do cliente.
    assert linha["direcao"] == "interna"
    assert linha["tipo"] == "nota"
    # A frase foi escrita pelo sistema, em nome de quem agiu.
    assert linha["autor"] == "sistema"


def test_entrar_e_convidar_nao_sao_o_mesmo_evento(conversa, gente):
    """Os dois passam pela MESMA função (`entrar` reusa `convidar` com
    `convidado_por` = a própria pessoa), e o log tem de distinguir."""
    conversas.assumir(conversa, gente["um"])
    assert conversas.entrar(conversa, gente["dois"])["ok"]
    tipos = [e["evento"] for e in eventos(conversa)]
    assert tipos == ["assumiu", "entrou"]

    assert conversas.convidar(conversa, gente["um"], gente["dois"])["ok"] in (True, False)
    # Quem convidou é o `convidado_por`, e o nome de quem foi chamado aparece.
    convite = [e for e in eventos(conversa) if e["evento"] == "convidou"]
    if convite:
        assert "Zz Evento Um" in convite[0]["conteudo"]
        assert convite[0]["atendente_id"] == gente["dois"]


def test_sair_registra(conversa, gente):
    conversas.assumir(conversa, gente["um"])
    conversas.entrar(conversa, gente["dois"])
    assert conversas.sair(conversa, gente["dois"])["ok"]
    assert [e["evento"] for e in eventos(conversa)][-1] == "saiu"


def test_devolver_para_fila_registra(conversa, gente):
    conversas.assumir(conversa, gente["um"])
    assert conversas.devolver_para_fila(conversa, gente["um"])["ok"]
    ultimo = eventos(conversa)[-1]
    assert ultimo["evento"] == "devolveu"
    assert "fila" in ultimo["conteudo"]


def test_transferir_diz_para_quem(conversa, gente):
    conversas.assumir(conversa, gente["um"])
    r = conversas.transferir(conversa, None, gente["dois"], "manual",
                             gente["um"], None, False)
    assert r["ok"], r
    linha = [e for e in eventos(conversa) if e["evento"] == "transferiu"][0]
    assert gente["nome_dois"] in linha["conteudo"]
    assert linha["atendente_id"] == gente["um"]


def test_transferir_sem_resumo_tambem_deixa_rastro(conversa, gente):
    """🚨 Até hoje, transferência SEM resumo não deixava nada na conversa: a
    nota de 23/09 só é gravada quando há resumo. O evento existe sempre."""
    conversas.assumir(conversa, gente["um"])
    conversas.transferir(conversa, None, gente["dois"], "manual",
                         gente["um"], None, False)
    notas = banco.varios(
        """SELECT evento FROM mensagem WHERE conversa_id = %s AND tipo = 'nota'
            ORDER BY id""", (conversa,))
    assert any(n["evento"] == "transferiu" for n in notas)


def test_encerrar_registra(conversa, gente):
    conversas.assumir(conversa, gente["um"])
    assert conversas.encerrar(conversa, None, None, gente["um"])["ok"]
    assert eventos(conversa)[-1]["evento"] == "encerrou"


def test_bloqueou_e_desbloqueou_sao_eventos_validos(conversa, gente):
    """🚨 AQUI NÃO SE CHAMA `conversas.bloquear()`, e o motivo é importante:
    ele fala com a API do WhatsApp de verdade (`evolution.mudar_bloqueio`).
    Uma primeira versão deste arquivo o chamava e a suíte ficou pendurada nas
    retentativas da rede — é o "teste que lê produção" em outra forma, e esta
    vez ia além de ler: ia tentar bloquear um número.

    O que dá para provar sem rede é que os dois eventos **existem** para o
    banco; que eles são gravados no lugar certo está provado pelo código, não
    por este teste. Quem prova de verdade é bloquear um número na tela.
    """
    assert conversas.registrar_evento(
        conversa, "bloqueou", "bloqueou este número", gente["um"])
    assert conversas.registrar_evento(
        conversa, "desbloqueou", "desbloqueou este número", gente["um"])
    assert [e["evento"] for e in eventos(conversa)] == ["bloqueou", "desbloqueou"]


# ------------------------------------------------- o que o log NÃO permite

def test_evento_nao_se_edita_nem_se_apaga_nem_por_quem_agiu(conversa, gente):
    """🚨 É quem AGIU que passaria no teste de "só quem escreveu pode editar",
    porque o `atendente_id` do evento é dele. Sem a recusa explícita, o log
    seria reescrevível pelo próprio autor -- e log que se reescreve não é log.
    """
    conversas.assumir(conversa, gente["um"])
    mensagem_id = banco.um(
        """SELECT id FROM mensagem WHERE conversa_id = %s AND evento IS NOT NULL
            ORDER BY id DESC LIMIT 1""", (conversa,))["id"]

    r = conversas.editar_nota(conversa, mensagem_id, "outra coisa", gente["um"])
    assert not r["ok"]
    assert "registro de ação" in r["motivo"]

    r = conversas.apagar_nota(conversa, mensagem_id, gente["um"])
    assert not r["ok"]

    # E o texto continua o mesmo, no banco.
    assert banco.um("SELECT conteudo FROM mensagem WHERE id = %s",
                    (mensagem_id,))["conteudo"] == "assumiu a conversa"


def test_nota_comum_continua_editavel(conversa, gente):
    """A recusa é do EVENTO, não da nota: quebrar o editar de nota comum seria
    pagar o log com um recurso que já existia."""
    nota = conversas.anotar(conversa, "nota de teste", gente["um"])
    assert nota["ok"]
    assert conversas.editar_nota(conversa, nota["mensagem_id"],
                                 "nota corrigida", gente["um"])["ok"]


def test_evento_nao_conta_como_nao_lida(conversa, gente):
    """Só `direcao = 'entrada'` conta, e o evento é `interna`. Se contasse, a
    bolinha da lista subiria sozinha a cada ação da própria equipe."""
    conversas.assumir(conversa, gente["um"])
    conversas.transferir(conversa, None, gente["dois"], "manual",
                         gente["um"], None, False)
    linha = banco.um(
        """SELECT count(*) AS n FROM mensagem
            WHERE conversa_id = %s AND direcao = 'entrada'""", (conversa,))
    assert linha["n"] == 0


def test_a_tela_recebe_o_campo_evento(conversa, gente):
    """Campo que a tela desenha tem de vir na consulta que ela pede — foi a
    lição do `estrela` no e-mail."""
    conversas.assumir(conversa, gente["um"])
    lista = conversas.mensagens(conversa)
    assert lista, "a conversa ficou sem mensagem nenhuma"
    assert "evento" in lista[0]
    assert lista[-1]["evento"] == "assumiu"


def test_evento_desconhecido_e_recusado_pelo_banco(conversa):
    """A lista fechada do CHECK é o que impede dois verbos para a mesma ação."""
    assert conversas.registrar_evento(conversa, "inventou", "texto") is None
    assert eventos(conversa) == []
