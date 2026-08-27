"""0800 e estrangeiro pelo WhatsApp — 27/08.

🚨 O QUE ISTO DEFENDE. O cabeçalho do `telefone.py` avisa como este defeito se
manifesta: *"o cliente escreve e o sistema responde que ele não é cliente. O
erro é invisível: nada quebra, nada estoura, nada aparece no log"*. Foi
exatamente o que aconteceu, e por semanas.

Medido em 27/08, varrendo os 1.342 eventos `messages.upsert` sem telefone:

  1.172  grupo -- esperado, a identidade deles é o `grupo_jid`
    146  0800 -- DOIS números de fornecedor, recusados como "DDD 80 não existe"
     24  estrangeiro -- Reino Unido e Índia, recusados por falta de um "+"
           que o WhatsApp nunca manda no JID

Ou seja: **170 mensagens de gente** que nunca viraram conversa, nunca viraram
contato e nunca puderam ser respondidas.

⚠️ OS NÚMEROS AQUI SÃO OS REAIS DA BASE. Caso inventado não teria achado que o
0800 chega SEM o zero inicial (`558008871599`), que é o detalhe que fazia o
"80" parecer DDD.
"""
import sys

import pytest

sys.path.insert(0, "/home/claude/movizap_painel")

from movizap import telefone  # noqa: E402


class TestNaoGeografico:
    """0800 e família não têm DDD. Lê-los como "DDD + assinante" é o defeito."""

    @pytest.mark.parametrize("bruto", [
        "558008871599@s.whatsapp.net",   # 71 eventos na base
        "558005916423@s.whatsapp.net",   # 75 eventos na base
    ])
    def test_0800_do_whatsapp_vira_telefone(self, bruto):
        a = telefone.analisar(bruto)
        assert a.e164, f"recusado: {a.motivo}"
        assert a.tipo == telefone.ESPECIAL

    def test_o_0800_converge_venha_como_vier(self):
        """As três grafias têm de dar a MESMA string, senão a busca por
        igualdade não encontra o contato que já existe."""
        formas = ["558008871599@s.whatsapp.net", "08008871599",
                  "0800 887 1599", "+558008871599"]
        saidas = {telefone.normalizar(f) for f in formas}
        assert saidas == {"+558008871599"}, saidas

    def test_4003_tambem_e_especial(self):
        """⚠️ Sem caso medido na base -- entra porque 8 dígitos soltos já eram
        recusados, então cobrir não tira nada de ninguém."""
        assert telefone.analisar("40031234").tipo == telefone.ESPECIAL

    def test_nenhum_DDD_valido_virou_especial(self):
        """🚨 A trava da trava: 80, 30, 50 e 90 não são DDDs, então nada que
        hoje passa pode mudar de destino. Mede os 67 DDDs, um por um."""
        for ddd in telefone.DDDS_VALIDOS:
            a = telefone.analisar(f"+55{ddd}998877665")
            assert a.tipo == telefone.MOVEL, f"DDD {ddd} deixou de ser celular"


class TestEstrangeiroPeloJid:
    """O JID é canônico; texto digitado não é. A exceção vale só para o JID."""

    @pytest.mark.parametrize("bruto,esperado", [
        ("447707805722@s.whatsapp.net", "+447707805722"),   # 23 eventos
        ("917283820406@s.whatsapp.net", "+917283820406"),   # 1 evento
    ])
    def test_estrangeiro_do_whatsapp_e_aceito(self, bruto, esperado):
        a = telefone.analisar(bruto)
        assert a.e164 == esperado
        assert a.tipo == telefone.INTERNACIONAL

    def test_estrangeiro_DIGITADO_sem_mais_continua_recusado(self):
        """🚨 A METADE QUE NÃO PODE CAIR. Sem o `+`, "441234567890" digitado é
        ambíguo, e chutar país é pior que recusar -- a regra original está
        certa. O que mudou é só que o JID não é digitado por ninguém."""
        assert telefone.analisar("447707805722").e164 is None


class TestNadaQuebrou:
    """O que já funcionava tem de continuar exatamente igual."""

    @pytest.mark.parametrize("bruto,esperado,tipo", [
        ("5518998116168@s.whatsapp.net", "+5518998116168", telefone.MOVEL),
        ("+5518998116168", "+5518998116168", telefone.MOVEL),
        ("551832214455@s.whatsapp.net", "+551832214455", telefone.FIXO),
        ("+551832214455", "+551832214455", telefone.FIXO),
        # Celular na grafia antiga: continua ganhando o nono dígito.
        ("+551898116168", "+5518998116168", telefone.MOVEL),
    ])
    def test_numero_normal_nao_mudou(self, bruto, esperado, tipo):
        a = telefone.analisar(bruto)
        assert a.e164 == esperado
        assert a.tipo == tipo

    def test_lixo_continua_recusado(self):
        assert telefone.analisar("").e164 is None
        assert telefone.analisar("abc").e164 is None
        assert telefone.analisar("+5511").e164 is None

    def test_variantes_do_especial_nao_inventa_nono_digito(self):
        """`variantes()` só duplica CELULAR. Um 0800 com um 9 enfiado no meio
        seria um número que não existe, indo parar em consulta a terceiro."""
        assert telefone.variantes("+558008871599") == {"+558008871599"}
