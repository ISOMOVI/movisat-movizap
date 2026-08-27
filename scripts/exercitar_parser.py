"""Exercita o parser de mensagens contra TODOS os payloads reais da base.

🚨 POR QUE ISTO EXISTE. Em 26/08 a suite do motor da IA passou verde com dois
defeitos que o cliente veria, porque rodava contra um duplo. O MIOLO registrou
isso como o QUARTO JEITO de achar o que falta: exercitar contra o mundo real.

Em 27/08 ele se pagou na primeira rodada. A trava de fixture estava verde com
35 verificacoes, e o exercicio contra os 14.209 eventos reais achou DOIS tipos
que o levantamento por consulta nao tinha visto -- `listMessage` e
`listResponseMessage`. O segundo e a pessoa RESPONDENDO a um menu: descarta-lo
teria apagado o que ela escolheu.

⚠️ NAO E TESTE, e nao deve virar um: le producao, e teste que le producao e
armadilha registrada. E ferramenta de conferencia, para rodar a mao depois de
mexer no parser.

Uso:
    ./venv/bin/python scripts/exercitar_parser.py
"""
import collections
import sys

sys.path.insert(0, "/home/claude/movizap_painel")

from movizap import banco, conversas


def main() -> None:
    banco.abrir()
    eventos = banco.varios(
        "SELECT id, payload FROM webhook_evento "
        " WHERE evento = 'messages.upsert' ORDER BY id")
    print(f"{len(eventos)} eventos reais\n")

    descartados = collections.Counter()
    textos = collections.Counter()
    vazios = collections.Counter()
    suspeitos = []

    for e in eventos:
        msg = (e["payload"].get("data") or {}).get("message")
        if not isinstance(msg, dict) or "reactionMessage" in msg:
            continue
        motivo = conversas.motivo_de_descarte(msg)
        if motivo:
            descartados[motivo.split(":")[0]] += 1
            continue
        tipo, texto = conversas._tipo_e_texto(msg)
        chaves = conversas._chaves_uteis(msg)
        if texto is None:
            vazios[chaves[0] if chaves else "?"] += 1
            continue
        textos[tipo] += 1
        # 🚨 O DEFEITO QUE ESTA RODADA FECHOU: o nome cru da chave indo para o
        # balao do atendente com cara de fala do cliente.
        if "tipo n" in texto or any(c in texto for c in chaves):
            suspeitos.append((e["id"], chaves[:1], texto[:70]))

    print("DESCARTADOS (nao viram mensagem):")
    for k, n in descartados.most_common():
        print(f"  {n:5}  {k}")
    print("\nVIRARAM MENSAGEM, por tipo:")
    for k, n in textos.most_common():
        print(f"  {n:5}  {k}")
    print("\nSEM TEXTO (midia sem legenda e normal):")
    for k, n in vazios.most_common(8):
        print(f"  {n:5}  {k}")
    print(f"\nSUSPEITOS (nome cru da chave no texto): {len(suspeitos)}")
    for s in suspeitos[:5]:
        print("  ", s)
    if suspeitos:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
