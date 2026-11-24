# -*- coding: utf-8 -*-
"""Tarefa 3.1 — a FILA GANHA: o escritor não toca OS com passagem pendente.

🔵 DECISÃO DELE (D3, 23/11): *a fila ganha*.

🚨 O DEFEITO, REPRODUZIDO NO BANCO EM 23/11. A OS 17137 teve a mesma origem e
DOIS destinos em 11 minutos:

    14:50   251 -> 16488     (a fila, da passagem do operador)
    15:01   251 -> 1316      (o escritor do auditor)

`pendente_desde 15:01`, 2 tentativas, `resolvida_em 16:30` -- a fila venceu
sozinha, por sorte de ordem. Ninguém arbitrava: dois processos miravam a mesma
OS com valores diferentes.

🚨 E O PONTO DE CONSERTO É ESTE, e só ele: `abertas()` é a ÚNICA lista que o
escritor lê. Ele não decide nada -- pega o que a lista dá. Então a arbitragem
mora na lista, não no escritor, e não há um segundo lugar para esquecer.

⚠️ NÃO FECHA A LINHA, SÓ ESPERA. A linha do auditor continua aberta: quando a
fila resolver, a OS sai do bloqueio e o escritor a pega na rodada seguinte (o
cron é */5 para a fila, 03:20 para o escritor). Fechar aqui seria desistir de
uma divergência real por causa de um conflito temporário.
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


AU = abrir("movizap/auditoria_os.py")

troca(AU,
      '''    🚨 **SÓ `escrita_perdida`**, e isto é o conserto que o ensaio a seco de
    18/11 obrigou. `mudou_no_erp` NÃO entra: ali o ERP mostra um valor que nós
    nunca escrevemos, ou seja alguém mexeu na OS dentro do Harmonit -- e
    reescrever a nossa coluna por cima desfaria o trabalho dessa pessoa. Foi o
    que teria acontecido com as OS 17054 e 17114.
    """
    return banco.varios(
        "SELECT id, numero_os, coluna_nossa, situacao_do_erp, tentativas, "
        "       grupos FROM auditoria_os "
        " WHERE fechada_em IS NULL AND veredito = 'escrita_perdida' "
        " ORDER BY numero_os")''',
      '''    🚨 **SÓ `escrita_perdida`**, e isto é o conserto que o ensaio a seco de
    18/11 obrigou. `mudou_no_erp` NÃO entra: ali o ERP mostra um valor que nós
    nunca escrevemos, ou seja alguém mexeu na OS dentro do Harmonit -- e
    reescrever a nossa coluna por cima desfaria o trabalho dessa pessoa. Foi o
    que teria acontecido com as OS 17054 e 17114.

    🚨 **E A FILA GANHA (🔵 D3 dele, 23/11): OS com passagem PENDENTE fica
    fora.** Reproduzido no banco em 23/11, na OS 17137: `251 -> 16488` às
    14:50 (a fila, da passagem do operador) e `251 -> 1316` às 15:01 (este
    escritor), mesma origem e dois destinos em 11 minutos. A fila venceu por
    sorte de ordem -- ninguém arbitrava.

    ⚠️ **A ARBITRAGEM MORA AQUI, e é de propósito:** esta é a ÚNICA lista que o
    escritor lê, e ele não decide nada -- escreve o que a lista der. Pôr a
    regra no escritor abriria um segundo lugar para esquecer dela.

    ⚠️ **ESPERAR NÃO É DESISTIR:** a linha do auditor continua ABERTA. Quando a
    fila resolver (`resolvida_em`), a OS volta à lista e o escritor a pega na
    rodada seguinte. Fechar aqui descartaria uma divergência real por causa de
    um conflito temporário.
    """
    return banco.varios(
        "SELECT id, numero_os, coluna_nossa, situacao_do_erp, tentativas, "
        "       grupos FROM auditoria_os "
        " WHERE fechada_em IS NULL AND veredito = 'escrita_perdida' "
        # 🔵 D3: a fila ganha. `pendente_desde IS NOT NULL AND resolvida_em IS
        # NULL` é a definição de "a fila ainda está insistindo nesta OS"
        # (migração 115) -- a mesma que a própria fila usa para escolher o que
        # retentar.
        "   AND NOT EXISTS (SELECT 1 FROM os_passagem p "
        "                    WHERE p.numero_os = auditoria_os.numero_os "
        "                      AND p.pendente_desde IS NOT NULL "
        "                      AND p.resolvida_em IS NULL) "
        " ORDER BY numero_os")''',
      "3.1: a fila ganha, dentro da unica lista que o escritor le")


for rel, d in ALVOS.items():
    saida = d["t"].replace("\n", "\r\n") if d["crlf"] else d["t"]
    d["p"].write_bytes(saida.encode("utf-8"))
    print("gravado:", rel, len(saida), "bytes")
