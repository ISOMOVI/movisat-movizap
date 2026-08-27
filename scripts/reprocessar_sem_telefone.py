"""Recupera os eventos que foram recusados por telefone nao reconhecido.

🚨 O DEFEITO ERA INVISIVEL, e por isso este script existe. Ate 27/08 o 0800 e
o estrangeiro sem "+" caiam em `telefone = NULL` e o evento morria ali: sem
conversa, sem contato, sem mensagem. Ninguem viu porque nada estourou.

Com o `telefone.py` corrigido, os eventos antigos continuam com o campo nulo
gravado NA CHEGADA -- corrigir o parser nao volta no tempo. Este script releva
o telefone e devolve o evento para a fila.

⚠️ ISSO CRIA CONVERSA COM DATA ANTIGA. As mensagens sao de dias atras e vao
aparecer na caixa de entrada. E por isso que o `--aplicar` e do usuario.

⚠️ GRUPO NAO ENTRA: `telefone` nulo em grupo e o esperado -- a identidade
deles e o `grupo_jid`. Sao 1.172 dos 1.342, e mexer neles seria estrago.

Uso:
    python scripts/reprocessar_sem_telefone.py             # SECO
    python scripts/reprocessar_sem_telefone.py --aplicar
"""
import collections
import sys

sys.path.insert(0, "/home/claude/movizap_painel")

from movizap import banco, telefone


def plano() -> list[dict]:
    eventos = banco.varios(
        "SELECT id, payload, recebido_em, de_mim FROM webhook_evento "
        " WHERE evento = 'messages.upsert' AND telefone IS NULL ORDER BY id")
    recuperaveis = []
    for e in eventos:
        jid = (((e["payload"].get("data") or {}).get("key") or {})
               .get("remoteJid") or "")
        if not jid or jid.endswith("@g.us"):
            continue
        a = telefone.analisar(jid)
        if a.e164:
            recuperaveis.append({**e, "jid": jid, "e164": a.e164, "tipo": a.tipo})
    return recuperaveis


def main() -> None:
    aplicar = "--aplicar" in sys.argv
    banco.abrir()
    recuperaveis = plano()

    por_numero = collections.Counter(r["e164"] for r in recuperaveis)
    print(f"=== EVENTOS RECUPERAVEIS: {len(recuperaveis)} ===")
    for num, n in por_numero.most_common():
        tipo = next(r["tipo"] for r in recuperaveis if r["e164"] == num)
        datas = [r["recebido_em"] for r in recuperaveis if r["e164"] == num]
        ja = banco.um("SELECT id FROM conversa WHERE telefone_e164 = %s LIMIT 1", (num,))
        print(f"  {n:5}  {num:16} {tipo:14} "
              f"{min(datas):%d/%m} a {max(datas):%d/%m}  "
              f"{'JA TEM CONVERSA' if ja else 'CONVERSA NOVA'}")

    print(f"\n=== O QUE ACONTECE ===")
    print(f"  {len(por_numero)} conversas apareceriam na caixa de entrada,")
    print(f"  com mensagens datadas de quando chegaram (nao de hoje).")

    if not aplicar:
        print("\nSECO. Nada foi escrito. Para aplicar: --aplicar")
        return

    for r in recuperaveis:
        banco.executar(
            "UPDATE webhook_evento SET telefone = %s, processado = false, "
            "       processado_em = NULL, motivo_ignorado = NULL "
            " WHERE id = %s", (r["e164"], r["id"]))
    print(f"\n{len(recuperaveis)} eventos devolvidos para a fila.")
    print("O processador roda a cada 5 s -- confira relendo o estado.")


if __name__ == "__main__":
    main()
