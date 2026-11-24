# -*- coding: utf-8 -*-
"""N1, a trava: o card de aba DIZ as respostas, não só o nome do formulário."""
import pathlib

q = pathlib.Path("tests/teste_pipeline.py")
bq = q.read_bytes()
CRLF = b"\r\n" in bq
u = bq.decode("utf-8").replace("\r\n", "\n")

VELHO = '''            achado = next(x for x in pipeline.cards_da_aba(aba["id"])
                          if x["id"] == c["id"])
            assert achado["observacoes"] == 1
            assert achado["formulario"] == "Suporte"
        finally:
            banco.executar("DELETE FROM formulario_solicitacao WHERE id = %s",
                           (s["id"],))'''

NOVO = '''            achado = next(x for x in pipeline.cards_da_aba(aba["id"])
                          if x["id"] == c["id"])
            assert achado["observacoes"] == 1
            assert achado["formulario"] == "Suporte"
        finally:
            banco.executar("DELETE FROM formulario_solicitacao WHERE id = %s",
                           (s["id"],))

    def test_o_card_de_aba_DIZ_as_respostas_e_nao_so_o_formulario(self, aba):
        """🔵 ELE, 23/11, sobre o formulario de pagamento: *"deveria estar
        gerando ja os dados"*.

        🚨 MEDIDO ENVIANDO UM TESTE DE VERDADE pela internet em 23/11
        (solicitacao 5990, card 4051 na etapa 875): o card nasce em 14 ms e as
        13 respostas chegam no payload -- e a tela nao mostrava NENHUMA, porque
        `cards_da_aba` nunca devolvia `resumo` e e `card.resumo` que o
        `CorpoDoCard` desenha. Card mudo com dado na mao.

        ⚠️ A REGRA E A MESMA DOS OUTROS PAINEIS (`paineis._resumo`): as duas
        primeiras respostas de texto, porque *"card nao e ficha"*. Esta trava
        prende o ELO (o campo chega no card), nao a regra -- se ele escolher
        campos a dedo depois, a regra muda num lugar so.
        """
        f = banco.um("SELECT id FROM formulario WHERE slug = 'suporte'")
        s = banco.um(
            """INSERT INTO formulario_solicitacao (formulario_id, valores)
               VALUES (%s, %s::jsonb) RETURNING id""",
            (f["id"], '{"a": "zz primeira resposta",'
                      ' "b": "zz segunda resposta", "c": 7}'))
        try:
            c = pipeline.criar(aba["id"], aba["etapas"][0],
                               solicitacao_id=s["id"])
            achado = next(x for x in pipeline.cards_da_aba(aba["id"])
                          if x["id"] == c["id"])
            assert achado["resumo"], "card mudo: o defeito de 23/11"
            assert "zz primeira resposta" in achado["resumo"]
            assert "zz segunda resposta" in achado["resumo"]
            # ⚠️ So TEXTO entra, e o numero fica fora: e a regra do `_resumo`,
            # e cita-la aqui prende que esta funcao e a usada -- nao uma copia.
            assert "7" not in achado["resumo"]
        finally:
            banco.executar("DELETE FROM formulario_solicitacao WHERE id = %s",
                           (s["id"],))

    def test_card_SEM_solicitacao_nao_inventa_resumo(self, aba):
        """⚠️ Card nascido de OS ou criado a mao nao tem respostas, e ali o
        resumo e `None` -- nunca string vazia: o `v-if` do card nao desenha o
        paragrafo, em vez de desenhar um paragrafo vazio."""
        c = pipeline.criar(aba["id"], aba["etapas"][0])
        achado = next(x for x in pipeline.cards_da_aba(aba["id"])
                      if x["id"] == c["id"])
        assert achado["resumo"] is None'''

assert VELHO in u, "NAO ACHOU o teste de observacoes"
assert u.count(VELHO) == 1
u = u.replace(VELHO, NOVO, 1)
print("  ok: as 2 travas do card que fala")

saida = u.replace("\n", "\r\n") if CRLF else u
q.write_bytes(saida.encode("utf-8"))
print("gravado:", q, len(saida), "bytes")
