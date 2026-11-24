# -*- coding: utf-8 -*-
"""Tarefa 3.1, as travas: a fila ganha, e esperar não é desistir."""
import pathlib

q = pathlib.Path("tests/teste_auditoria_os.py")
bq = q.read_bytes()
CRLF = b"\r\n" in bq
u = bq.decode("utf-8").replace("\r\n", "\n")

# O helper da fila, ao lado do `_moveu` que ja existe.
VELHO_H = '''def _leitor(mapa, contador=None):'''
NOVO_H = '''def _na_fila(numero_os, de, para, *, resolvida=False):
    """Uma passagem PENDENTE: a fila ainda insistindo nesta OS (migracao 115).

    🚨 E o estado que a OS 17137 tinha as 15:01 de 23/11, quando o escritor
    mirou a mesma OS com outro valor.
    """
    banco.executar(
        "INSERT INTO os_passagem (numero_os, de_situacao, para_situacao, ok, "
        "                         em, pendente_desde, tentativas, resolvida_em) "
        "VALUES (%s, %s, %s, false, now(), now(), 1, "
        "        CASE WHEN %s THEN now() ELSE NULL END)",
        (numero_os, de, para, resolvida))


def _leitor(mapa, contador=None):'''

assert VELHO_H in u and u.count(VELHO_H) == 1
u = u.replace(VELHO_H, NOVO_H, 1)
print("  ok: o helper _na_fila")

VELHO = '''    def test_o_escritor_NAO_decide_a_lista(self):'''
NOVO = '''    def test_A_FILA_GANHA_a_OS_com_passagem_pendente_fica_FORA(self):
        """🔵 D3 DELE, 23/11: *a fila ganha*.

        🚨 REPRODUZIDO NO BANCO, OS 17137: `251 -> 16488` as 14:50 (a fila, da
        passagem do operador) e `251 -> 1316` as 15:01 (o escritor), mesma
        origem e DOIS destinos em 11 minutos. A fila venceu por sorte de
        ordem -- ninguem arbitrava.

        ⚠️ A trava mede a LISTA, que e a unica coisa que o escritor le: e ali
        que a arbitragem mora, e nao dentro dele.
        """
        _moveu(OS_BASE + 40, 38, 251, ha_segundos=86400)
        _moveu(OS_BASE + 40, 251, 16488, ha_segundos=7200)
        auditoria_os.auditar(ler=_leitor({OS_BASE + 40: 251}))
        # Sem fila, a OS ESTA na lista -- senao a trava provaria nada.
        assert [d for d in auditoria_os.abertas()
                if d["numero_os"] == OS_BASE + 40], "a linha nem entrou"
        _na_fila(OS_BASE + 40, 251, 1316)
        assert [d for d in auditoria_os.abertas()
                if d["numero_os"] == OS_BASE + 40] == [], (
            "o escritor ainda pegaria a OS que a fila esta tentando")

    def test_ESPERAR_NAO_E_DESISTIR_a_linha_continua_aberta(self):
        """⚠️ Fechar a linha por causa de um conflito temporario descartaria
        uma divergencia REAL. A OS so sai da lista enquanto a fila insiste."""
        _moveu(OS_BASE + 41, 38, 251, ha_segundos=86400)
        _moveu(OS_BASE + 41, 251, 16488, ha_segundos=7200)
        auditoria_os.auditar(ler=_leitor({OS_BASE + 41: 251}))
        _na_fila(OS_BASE + 41, 251, 1316)
        linha = _linha(OS_BASE + 41)
        assert linha["fechada_em"] is None, linha
        assert linha["veredito"] == "escrita_perdida", linha

    def test_fila_RESOLVIDA_devolve_a_OS_para_o_escritor(self):
        """🚨 E a outra metade: resolvido o conflito, o escritor volta a pegar
        a OS na rodada seguinte. Senao a divergencia ficaria presa para
        sempre."""
        _moveu(OS_BASE + 42, 38, 251, ha_segundos=86400)
        _moveu(OS_BASE + 42, 251, 16488, ha_segundos=7200)
        auditoria_os.auditar(ler=_leitor({OS_BASE + 42: 251}))
        _na_fila(OS_BASE + 42, 251, 1316, resolvida=True)
        assert [d for d in auditoria_os.abertas()
                if d["numero_os"] == OS_BASE + 42], (
            "fila resolvida e a OS continua escondida do escritor")

    def test_o_escritor_NAO_decide_a_lista(self):'''

assert VELHO in u and u.count(VELHO) == 1
u = u.replace(VELHO, NOVO, 1)
print("  ok: as 3 travas da D3")

saida = u.replace("\n", "\r\n") if CRLF else u
q.write_bytes(saida.encode("utf-8"))
print("gravado:", q, len(saida), "bytes")
