"""Limpa as mensagens falsas que o ramo de "tipo ainda nao tratado" gravou.

🚨 O PADRAO E O DO `migrar_reacoes.py` (26/08), e nao e detalhe: RECUPERA
PRIMEIRO, APAGA DEPOIS, e o que nao puder ser recuperado NAO E APAGADO. Ali
159 das 161 foram para o lugar certo e as 2 orfas ficaram intactas.

Cada linha falsa e casada com o evento cru pelo `id_externo`. Sem evento, a
linha nao e tocada -- nao da para saber o que ela era.

Uso:
    python scripts/migrar_tipos_falsos.py             # SECO: so relata
    python scripts/migrar_tipos_falsos.py --aplicar
"""
import sys

sys.path.insert(0, "/home/claude/movizap_painel")

from movizap import banco, conversas

ALVO = "%tipo ainda n_o tratado%"


def plano() -> dict:
    """O que aconteceria com cada linha falsa, sem escrever nada."""
    linhas = banco.varios(
        """SELECT m.id, m.conversa_id, m.id_externo, m.conteudo, m.criada_em,
                  e.payload
             FROM mensagem m
             LEFT JOIN LATERAL (
                 SELECT payload FROM webhook_evento w
                  WHERE w.id_externo = m.id_externo
                  ORDER BY w.id DESC LIMIT 1
             ) e ON true
            WHERE m.conteudo LIKE %s
            ORDER BY m.criada_em""", (ALVO,))

    virar_texto, apagar, intocadas = [], [], []
    for m in linhas:
        msg = ((m["payload"] or {}).get("data") or {}).get("message")
        if not isinstance(msg, dict):
            # 🚨 SEM O CRU, NAO SE MEXE. E a regra que deixou 2 reacoes de pe.
            intocadas.append((m, "evento cru nao encontrado pelo id_externo"))
            continue
        if conversas.motivo_de_descarte(msg):
            apagar.append(m)
            continue
        _, texto = conversas._tipo_e_texto(msg)
        if texto:
            virar_texto.append((m, texto))
        else:
            intocadas.append((m, "o parser novo nao produziu texto"))
    return {"virar_texto": virar_texto, "apagar": apagar, "intocadas": intocadas}


def main() -> None:
    aplicar = "--aplicar" in sys.argv
    banco.abrir()
    p = plano()

    print(f"=== VIRAM TEXTO LEGIVEL: {len(p['virar_texto'])} ===")
    for m, texto in p["virar_texto"]:
        print(f'  msg {m["id"]} (conversa {m["conversa_id"]}, {m["criada_em"]:%d/%m %H:%M})')
        print(f'      de : {m["conteudo"][:70]}')
        print(f'      por: {texto[:150]}')
    print(f"\n=== APAGADAS: {len(p['apagar'])} ===")
    porq = {}
    for m in p["apagar"]:
        chave = m["conteudo"].split(" ")[0].lstrip("[")
        porq[chave] = porq.get(chave, 0) + 1
    for k, n in sorted(porq.items(), key=lambda x: -x[1]):
        print(f"  {n:4}  {k}")
    print(f"\n=== INTOCADAS: {len(p['intocadas'])} ===")
    for m, motivo in p["intocadas"]:
        print(f'  msg {m["id"]}: {m["conteudo"][:45]} -- {motivo}')

    if not aplicar:
        print("\nSECO. Nada foi escrito. Para aplicar: --aplicar")
        return

    # 🚨 RECUPERA PRIMEIRO. Se algo estourar no meio, o que ja virou texto
    # esta salvo e nada foi apagado ainda.
    for m, texto in p["virar_texto"]:
        banco.executar("UPDATE mensagem SET conteudo = %s WHERE id = %s",
                       (texto, m["id"]))
    print(f"\n{len(p['virar_texto'])} recuperadas.")
    if p["apagar"]:
        banco.executar("DELETE FROM mensagem WHERE id = ANY(%s)",
                       ([m["id"] for m in p["apagar"]],))
    print(f"{len(p['apagar'])} apagadas.")

    r = banco.um("SELECT COUNT(*) n FROM mensagem WHERE conteudo LIKE %s", (ALVO,))
    print(f"\nESTADO RELIDO: restam {r['n']} linhas falsas "
          f"(esperado: {len(p['intocadas'])})")


if __name__ == "__main__":
    main()
