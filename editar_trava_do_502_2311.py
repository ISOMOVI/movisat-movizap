# -*- coding: utf-8 -*-
"""Tarefa 3.4, a trava: 502 da ficha SEM rastro no log reprova.

🚨 Esta trava existe porque o defeito era A AUSENCIA de uma linha -- e ausencia
nenhuma suite ve por acidente. O `test_ponte_caida_vira_502_e_NAO_ficha_vazia`
ja existia e passava verde com o log faltando, nos quatro 502 de 19/11.
"""
import pathlib

q = pathlib.Path("tests/teste_obs_rota.py")
bq = q.read_bytes()
CRLF = b"\r\n" in bq
u = bq.decode("utf-8").replace("\r\n", "\n")

VELHO = '''        monkeypatch.setattr(main.fpsl_ponte, "ficha_da_os", estourar)
        r = cliente.get(f"/api/paineis/operacao/ficha?numero_os={OS_TESTE}",
                        headers=cab)
        assert r.status_code == 502
        assert "Harmonit" in r.json()["detail"]'''

NOVO = '''        monkeypatch.setattr(main.fpsl_ponte, "ficha_da_os", estourar)
        r = cliente.get(f"/api/paineis/operacao/ficha?numero_os={OS_TESTE}",
                        headers=cab)
        assert r.status_code == 502
        assert "Harmonit" in r.json()["detail"]

    def test_o_502_da_ficha_DEIXA_RASTRO_no_log(self, cliente, cab,
                                                monkeypatch, caplog):
        """🚨 TAREFA 3.4. O teste de 502 acima passava verde com o log
        FALTANDO.

        Em 19/11 a ficha devolveu 502 quatro vezes, todas na OS 17137, e
        nenhuma deixou vestigio: o `except Exception` levantava o 502 direto.
        A frase chegava na tela do operador e morria ali.

        ⚠️ E e o que destrava o A10 e o A16: as duas perguntam *"o valor que o
        ERP mostra e um que NOS escrevemos?"*, e responder exige saber QUANDO a
        ponte falhou e COM QUE. Ausencia de linha nenhuma suite ve por
        acidente -- por isso esta trava e separada da de cima.
        """
        import logging

        def estourar(numero_os):
            raise RuntimeError("zz ponte fora do ar")

        monkeypatch.setattr(main.fpsl_ponte, "ficha_da_os", estourar)
        with caplog.at_level(logging.WARNING, logger="movizap"):
            r = cliente.get(
                f"/api/paineis/operacao/ficha?numero_os={OS_TESTE}",
                headers=cab)
        assert r.status_code == 502
        linhas = [x for x in caplog.records
                  if str(OS_TESTE) in x.getMessage()]
        assert linhas, "502 da ficha sem uma linha de log -- o defeito de 3.4"
        # ⚠️ O TRACO TAMBEM E COBRADO: `str(e)` num erro de pool do Harmonit e
        # linha generica, e o traco e o que separa timeout de pool esgotado e
        # de 500 do ERP.
        assert linhas[0].exc_info, "sem exc_info nao da para distinguir a causa"'''

assert VELHO in u, "NAO ACHOU o teste de 502"
assert u.count(VELHO) == 1, "AMBIGUO %dx" % u.count(VELHO)
u = u.replace(VELHO, NOVO, 1)
print("  ok: a trava do log, junto do teste de 502 que ja existia")

saida = u.replace("\n", "\r\n") if CRLF else u
q.write_bytes(saida.encode("utf-8"))
print("gravado:", q, len(saida), "bytes")
