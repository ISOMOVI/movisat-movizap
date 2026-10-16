"""O vigia passa a dar um RESUMO DIARIO quando esta tudo em dia (15/10).

🔵 Pedido dele: *"se quer resumo diario do vigia quando esta tudo em dia (hoje
ele fica mudo)"* -> *"o 3 pode seguir"*.

⚠️ UMA VEZ POR DIA, NAO DUAS. O cron roda as 08:10 e as 18:10; mandar os dois
seria transformar um recurso de tranquilidade em duas notificacoes diarias para
sempre. O resumo sai so na passada da TARDE (`--resumo`), que e quando o dia
inteiro ja passou pelos dois horarios dos PCs.

🚨 E O SILENCIO CONTINUA SENDO A REGRA DO ALERTA. Isto nao afrouxa nada: se
houver alerta ou aviso, sai o alerta como antes. O resumo e so para o caso em
que antes nao saia nada.

Uso: ./venv/bin/python scripts/patch_vigia_resumo.py [--conferir]
"""
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
ALVO = RAIZ / "scripts" / "agentes_mudos.py"
SO_CONFERIR = "--conferir" in sys.argv

PASSOS = [
    ("a bandeira --resumo",
     """AVISAR = "--avisar-whatsapp" in sys.argv""",
     """AVISAR = "--avisar-whatsapp" in sys.argv
# 🔵 15/10: com `--resumo`, "tudo em dia" também fala -- uma linha dizendo
# quantos PCs estão enviando. Sem a bandeira, o comportamento é o de antes:
# silêncio total quando não há nada errado.
RESUMO = "--resumo" in sys.argv"""),

    ("tudo em dia deixa de ser silêncio quando ele pede resumo",
     """if not linhas:
    sys.exit(0)""",
     """if not linhas:
    if not RESUMO:
        # 🚨 O SILÊNCIO É A REGRA. Sem `--resumo`, nada errado = nada dito, que
        # é o que faz um alerta ser alerta.
        sys.exit(0)
    # 🔵 15/10: o resumo de "está tudo em dia". Ele diz o NÚMERO, não um
    # "tudo ok": a frase que não conta nada não distingue vigia funcionando de
    # vigia olhando para uma base vazia.
    try:
        vivos = ligacoes.agentes_vivos_resumo()
    except Exception as e:  # noqa: BLE001
        print(f"ALERTA MoviZap Ligações: não consegui montar o resumo "
              f"({e.__class__.__name__}).")
        sys.exit(0)
    linhas.append(
        f"MoviZap Ligações, {datetime.now(br):%d/%m}: tudo em dia. "
        f"{vivos['com_agente']} PC(s) enviando, "
        f"{vivos['ligacoes_hoje']} ligação(ões) hoje"
        + (f", {vivos['sem_agente']} atendente(s) ainda sem agente."
           if vivos["sem_agente"] else "."))"""),
]


def aplicar():
    texto = ALVO.read_text(encoding="utf-8")
    feitos, pulados = [], []
    for nome, velho, novo in PASSOS:
        if novo in texto:
            pulados.append(nome)
            continue
        n = texto.count(velho)
        if n != 1:
            raise SystemExit(f"ANCORA {n}x em '{nome}'")
        texto = texto.replace(velho, novo, 1)
        feitos.append(nome)
    compile(texto, str(ALVO), "exec")
    if not SO_CONFERIR and feitos:
        ALVO.write_text(texto, encoding="utf-8")
    for n in feitos:
        print(f"  {'conferido' if SO_CONFERIR else 'aplicado'}: {n}")
    for n in pulados:
        print(f"  ja aplicado: {n}")


aplicar()
