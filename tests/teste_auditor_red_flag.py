# -*- coding: utf-8 -*-
"""A RED FLAG DO AUDITOR AVISA UMA VEZ, NÃO TODO DIA — 23/11 (item A2).

🚨 **O DEFEITO, E COMO ELE FOI REPRODUZIDO.** Não foi por teste: foi **medido no
sistema vivo**, na auto-análise de 23/11. O `scripts/auditor_os.py` **nunca
chamava** `auditoria_os.marcar_avisadas`. A função existia, escrita e
documentada, e **nenhum chamador a invocava** — então o `avisada_em` ficava
`NULL` e a `para_a_red_flag()`, que filtra justamente por ele, devolvia as
mesmas linhas em toda rodada.

📏 **Os números medidos antes do conserto:**
  · `logs/os_auditor.log`: **8 red flags** enviadas, em 4 rodadas;
  · OS 17054 avisada **8 vezes**, OS 17114 **8 vezes**, OS 17128 **9 vezes**;
  · `avisada_em` **NULL nas 6 linhas** da `auditoria_os`.

⚠️ **ESTE ARQUIVO NÃO REPRODUZ O DEFEITO: ele TRANCA o conserto.** A reprodução
é a medição acima, e está no `231126.md`. O que as travas abaixo impedem é a
volta — e, principalmente, que alguém "conserte" o ruído afrouxando a régua.

🚨 **O QUE EU IA FAZER DE ERRADO, e a medição impediu.** Na auto-análise eu
escrevi que a `para_a_red_flag()` devia passar a filtrar `fechada_em IS NULL`,
porque a linha da OS 17128 estava fechada e seguia avisando. **Errado:** o
`_desistir()` grava `fechada_em = now()` junto com o veredito, então esse filtro
**calaria todo aviso de `desistiu`** — que é exatamente o aviso que mais importa
(*"não consegui acertar a situação em 3 tentativas"*). A trava
`test_desistiu_e_avisado_AINDA_QUE_a_linha_esteja_fechada` existe para isso.

🚨 **FAIXA DE OS RESERVADA, 997600+.** Esta suíte fala com o Postgres de
PRODUÇÃO (medido em 19/11, e é a lição daquele dia), então o que se isola aqui é
a CHAVE, não o banco — o molde é o do `teste_auditoria_os.py` (997300) e do
`teste_fila_das_passagens.py` (997400). A fixture apaga a faixa **antes e
depois**, para a 2ª rodada não herdar a 1ª.
"""
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

pytest.importorskip("psycopg")

from movizap import auditoria_os, banco  # noqa: E402

OS_BASE = 997600
FAIXA = list(range(OS_BASE, OS_BASE + 20))


@pytest.fixture(autouse=True)
def limpo():
    banco.abrir()
    _limpar()
    yield
    banco.abrir()
    _limpar()


def _limpar():
    banco.executar("DELETE FROM auditoria_os WHERE numero_os = ANY(%s)",
                   (FAIXA,))


def _linha(numero_os, veredito, *, fechada=False, erro=None):
    """Uma linha da auditoria no estado que interessa. Devolve o id."""
    r = banco.um(
        "INSERT INTO auditoria_os "
        "  (rodada, numero_os, coluna_nossa, situacao_do_erp, lido_em, "
        "   veredito, tentativas, grupos, ultimo_erro, fechada_em, "
        "   fechada_como, avisada_em) "
        "VALUES (now(), %s, 251, 16490, now(), %s, 3, 1, %s, "
        "        CASE WHEN %s THEN now() ELSE NULL END, "
        "        CASE WHEN %s THEN 'ainda_diferente' ELSE NULL END, NULL) "
        "RETURNING id",
        (numero_os, veredito, erro, fechada, fechada))
    return r["id"]


def _da_faixa(lista):
    return [d for d in lista if d["numero_os"] in FAIXA]


def _avisada_em(numero_os):
    r = banco.um("SELECT avisada_em FROM auditoria_os WHERE numero_os = %s",
                 (numero_os,))
    return (r or {}).get("avisada_em")


class _Carteiro:
    """Um envio injetado. 🚨 Nada de rede, nada de Evolution."""

    def __init__(self, falha=False):
        self.enviados = []
        self.falha = falha

    def __call__(self, texto):
        if self.falha:
            raise RuntimeError("o WhatsApp caiu")
        self.enviados.append(texto)


# ===========================================================================
class TestAvisaUmaVez:
    """🔵 *"aviso que aparece todo dia vira aviso que ninguém lê"* — o
    comentário da própria `para_a_red_flag`."""

    def test_depois_de_avisar_a_linha_SAI_da_lista(self):
        """🚨 A trava central do A2: era isto que não acontecia."""
        _linha(OS_BASE + 1, "mudou_no_erp")
        a_avisar = _da_faixa(auditoria_os.para_a_red_flag())
        assert len(a_avisar) == 1

        carteiro = _Carteiro()
        r = auditoria_os.avisar("zz teste", a_avisar, enviar=carteiro)
        assert r == {"enviado": True, "marcadas": 1, "erro": ""}
        assert carteiro.enviados == ["zz teste"]

        # 🚨 E A SEGUNDA RODADA NÃO TEM O QUE DIZER.
        assert _da_faixa(auditoria_os.para_a_red_flag()) == []
        assert _avisada_em(OS_BASE + 1) is not None

    def test_tres_linhas_de_uma_vez_saem_todas(self):
        """📏 Três é o número do caso real: 17054, 17114 e 17128."""
        for n, v in ((2, "mudou_no_erp"), (3, "mudou_no_erp"), (4, "desistiu")):
            _linha(OS_BASE + n, v, fechada=(v == "desistiu"))
        a_avisar = _da_faixa(auditoria_os.para_a_red_flag())
        assert len(a_avisar) == 3
        r = auditoria_os.avisar("zz", a_avisar, enviar=_Carteiro())
        assert r["marcadas"] == 3
        assert _da_faixa(auditoria_os.para_a_red_flag()) == []

    def test_rodar_DUAS_VEZES_nao_avisa_de_novo(self):
        """⚠️ Trava-que-conta em banco compartilhado reprova na 2ª rodada se a
        chave não for isolada. Esta roda o ciclo duas vezes de propósito."""
        _linha(OS_BASE + 5, "mudou_no_erp")
        for volta in (1, 2):
            a_avisar = _da_faixa(auditoria_os.para_a_red_flag())
            carteiro = _Carteiro()
            auditoria_os.avisar("zz", a_avisar, enviar=carteiro)
            esperado = 1 if volta == 1 else 0
            assert len(carteiro.enviados) == (1 if volta == 1 else 1), volta
            assert len(a_avisar) == esperado, (
                "na volta %d a lista tinha de ter %d" % (volta, esperado))


class TestEnvioQueFalha:
    """🚨 **MARCA DEPOIS DE ENVIAR, NUNCA ANTES.** Marcar antes perderia o
    aviso se o envio falhasse, e ninguém nota a ausência de um aviso."""

    def test_envio_que_falha_NAO_marca_nada(self):
        _linha(OS_BASE + 6, "mudou_no_erp")
        a_avisar = _da_faixa(auditoria_os.para_a_red_flag())
        r = auditoria_os.avisar("zz", a_avisar, enviar=_Carteiro(falha=True))
        assert r["enviado"] is False
        assert r["marcadas"] == 0
        assert "o WhatsApp caiu" in r["erro"]
        # 🚨 E a linha VOLTA na próxima rodada, que é o ponto.
        assert len(_da_faixa(auditoria_os.para_a_red_flag())) == 1
        assert _avisada_em(OS_BASE + 6) is None

    def test_envio_que_falha_NAO_estoura(self):
        """⚠️ O alerta já foi impresso pelo script; perder o aviso é o dano,
        não perder o processo. Vigia que morre calado é pior que vigia nenhum."""
        _linha(OS_BASE + 7, "desistiu", fechada=True)
        a_avisar = _da_faixa(auditoria_os.para_a_red_flag())
        r = auditoria_os.avisar("zz", a_avisar, enviar=_Carteiro(falha=True))
        assert r["enviado"] is False


class TestOQueNaoPodeSerCALADO:
    """🚨 O conserto do ruído NÃO pode virar silêncio sobre trabalho real."""

    def test_desistiu_e_avisado_AINDA_QUE_a_linha_esteja_fechada(self):
        """🚨 **A TRAVA QUE IMPEDIU MEU PRÓPRIO ERRO.** Na auto-análise eu
        propus filtrar `fechada_em IS NULL` na `para_a_red_flag`. O
        `_desistir()` grava `fechada_em = now()` junto com o veredito — então
        esse filtro calaria TODO aviso de `desistiu`, que é o *"não consegui
        acertar a situação em 3 tentativas"*, o mais importante de todos."""
        _linha(OS_BASE + 8, "desistiu", fechada=True, erro="recusa_do_erp")
        a_avisar = _da_faixa(auditoria_os.para_a_red_flag())
        assert len(a_avisar) == 1, (
            "linha fechada como `desistiu` TEM de ser avisada uma vez")
        assert a_avisar[0]["ultimo_erro"] == "recusa_do_erp"

    # 📏 Os 7 vereditos que a `CHECK auditoria_os_veredito` permite, medidos em
    # 23/11: `aberta`, `atraso`, `escrita_perdida`, `mudou_no_erp`,
    # `nao_confirmada`, `resolvida`, `desistiu`. ⚠️ Eu havia posto `igual` aqui
    # de memória — e o banco recusou com `CheckViolation`, que é o banco
    # ensinando. Os dois que AVISAM são `mudou_no_erp` e `desistiu`; estes
    # cinco são os que nunca avisam.
    @pytest.mark.parametrize("veredito", ["aberta", "atraso", "escrita_perdida",
                                          "nao_confirmada", "resolvida"])
    def test_o_que_nunca_vira_aviso_continua_nunca_virando(self, veredito):
        """⚠️ `atraso` e `nao_confirmada` são o ERP respondendo devagar, não
        trabalho para alguém — foi isso que produziu as 7 recusas falsas na OS
        17133 em 18/11. E `resolvida` é trabalho que terminou bem."""
        _linha(OS_BASE + 9, veredito)
        assert _da_faixa(auditoria_os.para_a_red_flag()) == []

    def test_lista_vazia_nao_envia_NADA(self):
        """🚨 Silêncio é o que faz o alerta ser alerta."""
        carteiro = _Carteiro()
        r = auditoria_os.avisar("zz", [], enviar=carteiro)
        assert r["marcadas"] == 0
        # ⚠️ A decisão de não chamar quando a lista é vazia é do SCRIPT (ele sai
        # antes, com `if not linhas: sys.exit(0)`). Aqui o que se cobra é que
        # chamar com vazio não marque nada nem estoure.
        assert carteiro.enviados == ["zz"]


class TestOScriptUsaACostura:
    """🚨 `M15`: ausência só se afirma lendo a definição. A costura só serve se
    o script a usa — foi exatamente o elo que faltava por 4 dias."""

    def test_o_auditor_chama_auditoria_os_avisar(self):
        fonte = (RAIZ / "scripts" / "auditor_os.py").read_text(encoding="utf-8")
        assert "auditoria_os.avisar(" in fonte, (
            "o auditor tem de usar a costura; era isto que faltava")

    def test_o_auditor_NAO_envia_mais_por_fora(self):
        """⚠️ Se alguém reintroduzir o `evolution.enviar_texto` direto no
        script, a marcação volta a ficar de fora — e o ruído volta."""
        fonte = (RAIZ / "scripts" / "auditor_os.py").read_text(encoding="utf-8")
        diretos = [l for l in fonte.split("\n")
                   if "evolution.enviar_texto" in l
                   and "enviar=lambda" not in l]
        assert diretos == [], diretos
