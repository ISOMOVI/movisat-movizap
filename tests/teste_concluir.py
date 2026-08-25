"""Concluir atendimento — o que mudou em 25/08, e o que não pode quebrar junto.

Decisões do usuário: "encerrar" vira CONCLUIR ATENDIMENTO, a conversa volta
para "sem dono", concluir vale mesmo com outras pessoas dentro, e os
convidados saem junto.

🚨 O RISCO DA MUDANÇA NÃO É CONCLUIR -- É O QUE LÊ `atendente_id` DEPOIS.
Soltar o dono apaga a única pista de quem atendeu naquela conversa. Por isso
metade destes testes não olha para o fechamento: olha para o HISTÓRICO e para
a contagem de desfecho, que são os dois lugares onde o apagamento apareceria
como "—" sem ninguém notar.

🚨 Escreve em `conversa`, `conversa_participante` e `atendente`, tabelas de
PRODUÇÃO. Telefone de DDD inexistente e login com prefixo `zz`.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, "/home/claude/movizap_painel")
pytest.importorskip("psycopg")

from movizap import banco, conversas, inicio  # noqa: E402

ENV = Path("/home/claude/movizap_painel/.env")
pytestmark = pytest.mark.skipif(
    not ENV.exists() or "MOVIZAP_DB_SENHA" not in ENV.read_text(encoding="utf-8"),
    reason="banco nao configurado no .env")

FONE = "+5599933330000"
# ⚠️ A limpeza varre pelo PREFIXO, não pelo número exato: um dos testes cria
# uma segunda conversa (`...0001`) para provar ordenação, e assert que falha
# antes do delete deixaria lixo em produção para sempre.
PREFIXO = "+559993333%"
LOGIN = "zz_teste_concluir_"


def limpar():
    banco.executar(
        """DELETE FROM conversa_participante WHERE conversa_id IN
           (SELECT id FROM conversa WHERE telefone_e164 LIKE %s)""", (PREFIXO,))
    banco.executar(
        """DELETE FROM transferencia WHERE conversa_id IN
           (SELECT id FROM conversa WHERE telefone_e164 LIKE %s)""", (PREFIXO,))
    banco.executar(
        """DELETE FROM mensagem WHERE conversa_id IN
           (SELECT id FROM conversa WHERE telefone_e164 LIKE %s)""", (PREFIXO,))
    banco.executar("DELETE FROM conversa WHERE telefone_e164 LIKE %s", (PREFIXO,))
    banco.executar("DELETE FROM atendente WHERE login LIKE %s", (LOGIN + "%",))


@pytest.fixture(scope="module", autouse=True)
def pool():
    banco.abrir()
    limpar()
    yield
    limpar()
    banco.fechar()


@pytest.fixture()
def cena():
    """Conversa com dono e um convidado acompanhando."""
    limpar()
    canal = banco.um("SELECT id FROM canal WHERE instancia = 'atendimento'")
    if not canal:
        pytest.skip("canal atendimento não cadastrado")
    ids = {}
    for papel in ("dono", "convidado"):
        ids[papel] = banco.um(
            """INSERT INTO atendente (nome, login, email, senha_hash, perfil, ativo)
               VALUES (%s, %s, %s, 'x', 'atendimento', true) RETURNING id""",
            (f"Teste {papel}", LOGIN + papel,
             f"{LOGIN}{papel}@movisat.com.br"))["id"]
    conversa = banco.um(
        """INSERT INTO conversa (canal_id, telefone_e164, estado, atendente_id)
           VALUES (%s, %s, 'humano', %s) RETURNING id""",
        (canal["id"], FONE, ids["dono"]))["id"]
    banco.executar(
        """INSERT INTO conversa_participante (conversa_id, atendente_id, convidado_por)
           VALUES (%s, %s, %s)""",
        (conversa, ids["convidado"], ids["dono"]))
    yield {"conversa": conversa, **ids}
    limpar()


def _linha(conversa_id):
    return banco.um(
        "SELECT estado, atendente_id, resolvida_por, resolvida_em "
        "  FROM conversa WHERE id = %s", (conversa_id,))


class TestConcluirSoltaODono:
    def test_a_conversa_volta_para_sem_dono(self, cena):
        """A decisão de 25/08: concluído é conclusão do ATENDIMENTO, não posse
        do assunto. Sem isto, conversa fechada continuava contando como
        'minha' e o painel de quem atende nunca esvaziava."""
        conversas.encerrar(cena["conversa"], atendente_id=cena["dono"])
        assert _linha(cena["conversa"])["atendente_id"] is None

    def test_quem_concluiu_fica_gravado(self, cena):
        """🚨 A CONDIÇÃO DE SOLTAR O DONO. `atendente_id` era o único lugar
        onde o autor do fechamento aparecia -- soltar sem gravar apagaria o
        desfecho, e é ele que a tela inicial conta."""
        conversas.encerrar(cena["conversa"], atendente_id=cena["dono"])
        assert _linha(cena["conversa"])["resolvida_por"] == cena["dono"]

    def test_sem_autor_explicito_cai_no_dono_de_entao(self, cena):
        """Chamada de rotina ou de teste não sabe quem clicou. O dono da hora
        é a melhor resposta disponível -- e é melhor que NULL."""
        conversas.encerrar(cena["conversa"])
        assert _linha(cena["conversa"])["resolvida_por"] == cena["dono"]

    def test_quem_conclui_ganha_de_quem_era_dono(self, cena):
        """O convidado que conclui é quem concluiu. Nunca o contrário."""
        conversas.encerrar(cena["conversa"], atendente_id=cena["convidado"])
        assert _linha(cena["conversa"])["resolvida_por"] == cena["convidado"]

    def test_concluir_duas_vezes_e_recusado(self, cena):
        conversas.encerrar(cena["conversa"], atendente_id=cena["dono"])
        segundo = conversas.encerrar(cena["conversa"], atendente_id=cena["dono"])
        assert segundo["ok"] is False
        assert "concluído" in segundo["motivo"].lower()


class TestOsConvidadosSaemJunto:
    def test_participante_recebe_saiu_em(self, cena):
        """Conversa concluída não fica na lista de ninguém (decisão 25/08)."""
        conversas.encerrar(cena["conversa"], atendente_id=cena["dono"])
        aberto = banco.um(
            """SELECT count(*) AS n FROM conversa_participante
                WHERE conversa_id = %s AND saiu_em IS NULL""",
            (cena["conversa"],))["n"]
        assert aberto == 0

    def test_o_retorno_diz_quantos_sairam(self, cena):
        """A tela avisa quem foi tirado. Tirar gente em silêncio é o tipo de
        efeito que só aparece quando o outro reclama que a conversa sumiu."""
        r = conversas.encerrar(cena["conversa"], atendente_id=cena["dono"])
        assert r["participantes_saidos"] == 1

    def test_concluir_funciona_COM_gente_dentro(self, cena):
        """🚨 Concluir é conclusão, mesmo com outros acompanhando. Quem quer
        apenas se retirar usa `sair()`, que é outra ação."""
        assert conversas.encerrar(
            cena["conversa"], atendente_id=cena["dono"])["ok"] is True


class TestOQueLiaAtendenteIdContinuaSabendo:
    def test_o_historico_ainda_mostra_quem_atendeu(self, cena):
        """🚨 O JOIN antigo era em `c.atendente_id`. Com o dono solto, ele
        daria '—' em toda conversa concluída a partir de 25/08 -- o histórico
        pararia de saber quem atendeu justo quando a regra melhorou."""
        conversas.encerrar(cena["conversa"], atendente_id=cena["dono"])
        achada = [c for c in conversas.historico(busca=FONE)
                  if c["id"] == cena["conversa"]]
        assert achada, "a conversa concluída sumiu do histórico"
        assert achada[0]["atendente_nome"] == "Teste dono"

    def test_a_tela_inicial_conta_o_desfecho_por_pessoa(self, cena):
        """É o mini-CRM: sem `resolvida_por` este número seria sempre zero."""
        antes = inicio.resumo(cena["dono"])["desfecho"]["minhas"]["hoje"]
        conversas.encerrar(cena["conversa"], atendente_id=cena["dono"])
        depois = inicio.resumo(cena["dono"])["desfecho"]["minhas"]["hoje"]
        assert depois == antes + 1

    def test_conversa_concluida_nao_conta_como_minha_em_aberto(self, cena):
        """O outro lado do mesmo: ela sai de 'esperando sua resposta'."""
        conversas.encerrar(cena["conversa"], atendente_id=cena["dono"])
        meu_dia = inicio.resumo(cena["dono"])["meu_dia"]
        minhas = next(i for i in meu_dia if i["chave"] == "minhas")
        assert cena["conversa"] not in [
            c["id"] for c in conversas.listar(atendente_id=cena["dono"])]
        assert minhas["valor"] == 0


class TestReabrirDesfazODesfecho:
    def test_reabrir_limpa_resolvida_por(self, cena):
        """🚨 Conversa reaberta que continuasse com o autor do fechamento
        seria contada como desfecho sem ter desfecho -- e o número subiria
        sozinho a cada reabrir/concluir do mesmo atendimento."""
        conversas.encerrar(cena["conversa"], atendente_id=cena["dono"])
        assert conversas.assumir(cena["conversa"], cena["convidado"])["ok"] is True
        linha = _linha(cena["conversa"])
        assert linha["resolvida_por"] is None
        assert linha["resolvida_em"] is None
        assert linha["atendente_id"] == cena["convidado"]


class TestOwnerNaTelaInicial:
    def test_quem_nao_e_owner_nao_recebe_canais(self, cena):
        """🚨 A CFG_1.1 é tela de owner desde sempre, e até 25/08 a tela
        inicial entregava o mesmo dado para qualquer perfil pela porta da
        frente. A trava é no JSON, não no `v-if`."""
        r = inicio.resumo(cena["dono"], owner=False)
        assert "canais" not in r
        assert "saude" not in r
        assert "alcance" not in r

    def test_owner_continua_recebendo(self, cena):
        r = inicio.resumo(cena["dono"], owner=True)
        assert "canais" in r and "saude" in r and "alcance" in r

    def test_quem_nao_e_owner_recebe_a_propria_configuracao(self, cena):
        """No lugar do bloco de infraestrutura: em que times está, que filas
        vê, e por que. Sem isto a conclusão natural é 'está quebrado'."""
        config = inicio.resumo(cena["dono"], owner=False)["configuracao"]
        assert config["perfil"] == "atendimento"
        # Sem linha em `atendente_time_permissao` a pessoa vê a fila INTEIRA:
        # é o padrão permissivo da migração 001, e a leitura oposta da lista
        # vazia é exatamente o que este campo existe para impedir.
        assert config["ve_a_fila_inteira"] is True


class TestConcluidaVaiParaOFimDaFila:
    """🚨 A LISTA É A FILA DE QUEM ESPERA. Ordenar só por
    `ultima_atividade_em` punha a conversa concluída logo após a última
    mensagem do cliente no TOPO de "Sem dono", acima de quem ainda espera --
    porque concluir não toca nesse campo, e nem deve: ele mede atividade do
    cliente, não do atendente.
    """

    def test_concluida_fica_abaixo_de_uma_aberta_mais_antiga(self, cena):
        canal = banco.um("SELECT canal_id FROM conversa WHERE id = %s",
                         (cena["conversa"],))["canal_id"]
        # A aberta é MAIS VELHA de propósito: pela data, ela perderia.
        antiga = banco.um(
            """INSERT INTO conversa (canal_id, telefone_e164, estado,
                                     ultima_atividade_em)
               VALUES (%s, %s, 'nova', now() - interval '3 days')
               RETURNING id""", (canal, FONE.replace("0000", "0001")))["id"]
        banco.executar(
            "UPDATE conversa SET ultima_atividade_em = now() WHERE id = %s",
            (cena["conversa"],))
        conversas.encerrar(cena["conversa"], atendente_id=cena["dono"])

        ordem = [c["id"] for c in conversas.listar(sem_dono=True, limite=500)]
        assert ordem.index(antiga) < ordem.index(cena["conversa"])
        banco.executar("DELETE FROM conversa WHERE id = %s", (antiga,))

    def test_na_BUSCA_a_concluida_nao_e_empurrada(self, cena):
        """Quem digita um termo procura UMA conversa. Empurrar a concluída
        para depois de 300 abertas é escondê-la de quem sabe que existe."""
        conversas.encerrar(cena["conversa"], atendente_id=cena["dono"])
        achadas = [c["id"] for c in conversas.listar(busca=FONE)]
        assert cena["conversa"] in achadas
