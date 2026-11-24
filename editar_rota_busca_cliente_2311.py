# -*- coding: utf-8 -*-
"""23/11 — o elo que faltava: a ROTA pública não levava o `busca_cliente`.

🚨 O DEFEITO, MEDIDO AO VIVO depois do build. O `definicao()` passou a devolver
a coluna, a suíte ficou verde, e a internet recebeu `busca_cliente` AUSENTE —
porque `_publico_do_formulario` monta o payload dela campo por campo, de
propósito (nomes internos não saem). Com a chave ausente, `def.busca_cliente
=== true` é falso, e o botão *Buscar* desapareceu **também dos 6 contratuais**,
que devem mantê-lo.

É o [[feedback_campo_novo_nao_entra_sozinho]] inteiro: quem devolve, quem
grava, quem lê. E a trava que eu escrevi media a FUNÇÃO, não a ROTA —
[[feedback_rota_nova_pede_teste_http]]. As duas coisas se consertam aqui.
"""
import pathlib

ALVOS = {}


def abrir(rel):
    p = pathlib.Path(rel)
    bruto = p.read_bytes()
    ALVOS[rel] = {"p": p, "crlf": b"\r\n" in bruto,
                  "t": bruto.decode("utf-8").replace("\r\n", "\n")}
    return rel


def troca(rel, velho, novo, rotulo):
    d = ALVOS[rel]
    assert velho in d["t"], "NAO ACHOU (%s)" % rotulo
    assert d["t"].count(velho) == 1, "AMBIGUO %dx (%s)" % (
        d["t"].count(velho), rotulo)
    d["t"] = d["t"].replace(velho, novo, 1)
    print("  ok:", rotulo)


MN = abrir("movizap/main.py")

troca(MN,
      '''        "formato": d.get("formato") or "classico",
        "etapas": _etapas_publicas(d),''',
      '''        "formato": d.get("formato") or "classico",
        "etapas": _etapas_publicas(d),
        # 🚨 ESTA LINHA É O ELO QUE FALTOU EM 23/11, e o defeito foi medido ao
        # vivo: a coluna existia, a carga a escrevia, o `definicao()` a
        # devolvia, a suíte estava verde -- e a internet recebia a chave
        # AUSENTE, porque este payload é montado campo por campo. Resultado:
        # `def.busca_cliente === true` falso em todos, e o botão *Buscar*
        # sumiu também dos 6 que devem tê-lo.
        #
        # ⚠️ `bool()` de propósito: a tela decide com `=== true`, e chave
        # ausente ou nula mentiria dizendo "não procura" num formulário que
        # procura. Aqui a resposta é sempre sim ou não, nunca silêncio.
        "busca_cliente": bool(d.get("busca_cliente")),''',
      "1. a rota publica leva busca_cliente")


# ---------------------------------------------------------------------------
# A trava refeita: pela ROTA, que é o que a internet pede
# ---------------------------------------------------------------------------
TS = abrir("tests/teste_etapas_dos_formularios.py")

troca(TS,
      '''    def test_a_definicao_publica_leva_o_busca_cliente(self):
        """🚨 O ELO QUE NENHUMA DAS DUAS TRAVAS ACIMA VE.

        A coluna pode estar certa no banco e certa no script, e a internet
        continuar sem saber: quem leva o dado a tela e o `SELECT` do
        `definicao()`. Campo novo nao entra sozinho na cadeia -- quem devolve,
        quem grava, quem le ([[feedback_campo_novo_nao_entra_sozinho]]).
        """
        from movizap import formularios
        assert formularios.definicao("suporte", so_ativo=False)[
            "busca_cliente"] is True
        assert formularios.definicao("pagamento-tecnicos", so_ativo=False)[
            "busca_cliente"] is False''',
      '''    def test_a_definicao_publica_leva_o_busca_cliente(self):
        """🚨 O ELO QUE NENHUMA DAS DUAS TRAVAS ACIMA VE, E ELE QUEBROU.

        A coluna pode estar certa no banco e certa no script, e a internet
        continuar sem saber. Campo novo nao entra sozinho na cadeia -- quem
        devolve, quem grava, quem le
        ([[feedback_campo_novo_nao_entra_sozinho]]).

        🚨 ESTA TRAVA NASCEU MEDINDO A FUNCAO E ISSO NAO BASTOU. Em 23/11 ela
        passou verde com `formularios.definicao(...)` enquanto a INTERNET
        recebia a chave ausente: `_publico_do_formulario` monta o payload dela
        campo por campo, e a chave nova nao entrou. O botao sumiu dos 6
        contratuais, no ar, com a suite verde.
        ⚠️ Rota se mede PEDINDO A ROTA ([[feedback_rota_nova_pede_teste_http]]).
        """
        from fastapi.testclient import TestClient
        from movizap.main import app
        with TestClient(app) as c:
            assert c.get("/api/publico/formulario/suporte").json()[
                "busca_cliente"] is True
            assert c.get("/api/publico/formulario/pagamento-tecnicos").json()[
                "busca_cliente"] is False''',
      "2. a trava passa a pedir a rota, nao a funcao")


for rel, d in ALVOS.items():
    saida = d["t"].replace("\n", "\r\n") if d["crlf"] else d["t"]
    d["p"].write_bytes(saida.encode("utf-8"))
    print("gravado:", rel, len(saida), "bytes")
