"""Preenche `tem_whatsapp` perguntando ao Evolution quais números existem.

🚨 POR QUE ISTO É O CAMINHO, E NÃO PUXAR HISTÓRICO

Não se descobre quem é quem lendo conversa antiga -- o `syncFullHistory` está
desligado de propósito e o WhatsApp nem garante o que entrega. O caminho é o
sentido inverso: pega-se o CADASTRO e pergunta-se ao WhatsApp quais daqueles
números existem lá.

Isso resolve três coisas de uma vez:
  1. `tem_whatsapp` deixa de ser NULL em 100% da base (metodologia §2: "é um
     campo, não uma suposição");
  2. destrava o informativo -- §4 proíbe enviar para `tem_whatsapp = false`;
  3. quando um desses números escrever, já chega identificado.

🚨 RITMO, NÃO RAJADA (metodologia §4). Consultar mil números de uma vez é
exatamente o padrão que faz o WhatsApp derrubar o número. O lote é pequeno e
tem intervalo, e os dois são regra de CÓDIGO, não disciplina de quem roda.

🚨 NULL É "NÃO VERIFICADO", E É DIFERENTE DE FALSE. Só se grava `false` quando
o Evolution respondeu que o número não existe -- nunca por timeout, nunca por
erro de rede. Errar isso silenciaria o cliente para sempre.

Uso:
    verificar_whatsapp.py                 # simulação, não grava
    verificar_whatsapp.py --limite 10 --aplicar
    verificar_whatsapp.py --aplicar       # a base toda, em ritmo
"""
import argparse
import sys
import time

sys.path.insert(0, "/home/claude/movizap_painel")

from movizap import banco, evolution  # noqa: E402

INSTANCIA = "atendimento"
LOTE = 20          # números por chamada
INTERVALO = 2.0    # segundos entre lotes


def pendentes(limite: int | None) -> list[dict]:
    """Só quem nunca foi verificado. Rodar de novo não repete o que já sabe."""
    sql = ("SELECT id, e164 FROM contato_telefone "
           "WHERE tem_whatsapp IS NULL AND e164 IS NOT NULL "
           "ORDER BY id")
    if limite:
        sql += f" LIMIT {int(limite)}"
    return banco.varios(sql)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--aplicar", action="store_true")
    p.add_argument("--limite", type=int, default=None)
    p.add_argument("--lote", type=int, default=LOTE)
    p.add_argument("--intervalo", type=float, default=INTERVALO)
    args = p.parse_args()

    banco.abrir()
    total_base = banco.um("SELECT COUNT(*) AS n FROM contato_telefone")["n"]
    fila = pendentes(args.limite)
    print(f"base: {total_base} telefones | sem verificação: "
          f"{len(pendentes(None))} | nesta rodada: {len(fila)}")
    print(f"ritmo: {args.lote} por chamada, {args.intervalo}s entre lotes\n")

    if not args.aplicar:
        print("(simulação -- nada foi consultado nem gravado. Use --aplicar.)")
        return 0

    existem, nao_existem, falharam = 0, 0, 0

    # 🚨 UM NÚMERO PODE ESTAR EM VÁRIAS LINHAS -- são as centrais de empresa,
    # que o Harmonit repete no cadastro de cada filial (uma delas em 8
    # contatos). Mandar o mesmo número duas vezes no mesmo lote faz o Evolution
    # recusar o LOTE INTEIRO com HTTP 400 `numbers contains duplicate item`.
    #
    # Foi o que derrubou 180 verificações na primeira rodada -- e o sintoma
    # enganava: parecia limite de chamadas, porque falhava sempre por volta da
    # mesma altura (que era quando o primeiro número repetido aparecia).
    #
    # Agrupa por número, pergunta UMA vez, aplica a resposta a todas as linhas.
    por_e164: dict[str, list[int]] = {}
    for t in fila:
        por_e164.setdefault(t["e164"], []).append(t["id"])
    distintos = sorted(por_e164)
    if len(distintos) != len(fila):
        print(f"  ({len(fila)} linhas -> {len(distintos)} números distintos; "
              f"{len(fila) - len(distintos)} são o mesmo número repetido)\n")

    for inicio in range(0, len(distintos), args.lote):
        pedaco = [{"e164": e, "ids": por_e164[e]}
                  for e in distintos[inicio:inicio + args.lote]]
        numeros = [t["e164"].lstrip("+") for t in pedaco]

        try:
            resposta = evolution._pedir(
                "POST", f"/chat/whatsappNumbers/{INSTANCIA}", {"numbers": numeros})
        except Exception as e:                      # noqa: BLE001
            # ⚠️ Falha de rede NÃO vira `false`. Fica NULL para a próxima
            # rodada: "não verificado" é a verdade aqui.
            # A mensagem entra no log: em 07/08 ela dizia `numbers contains
            # duplicate item`, e sem ela o sintoma parecia limite de chamadas.
            falharam += sum(len(t["ids"]) for t in pedaco)
            print(f"  lote {inicio // args.lote + 1}: FALHOU -- {e}")
            time.sleep(args.intervalo)
            continue

        por_numero = {str(r.get("number") or "").lstrip("+"): r
                      for r in (resposta or [])}

        with banco.cursor() as cur:
            for t in pedaco:
                bruto = t["e164"].lstrip("+")
                achado = por_numero.get(bruto)
                if achado is None:
                    # O Evolution não falou deste número: não se inventa
                    # resposta. Continua NULL.
                    continue
                existe = bool(achado.get("exists"))
                existem += int(existe)
                nao_existem += int(not existe)
                # A resposta vale para TODAS as linhas com aquele número.
                cur.execute(
                    "UPDATE contato_telefone SET tem_whatsapp = %s, "
                    "verificado_em = now() WHERE id = ANY(%s)",
                    (existe, t["ids"]))

        print(f"  lote {inicio // args.lote + 1}: {len(pedaco)} números "
              f"({existem} com, {nao_existem} sem)")
        time.sleep(args.intervalo)

    # A única prova é reler o estado.
    print("\nConferência, relendo o banco:")
    for rotulo, sql in (
            ("com WhatsApp ", "tem_whatsapp IS TRUE"),
            ("sem WhatsApp ", "tem_whatsapp IS FALSE"),
            ("não verificado", "tem_whatsapp IS NULL")):
        n = banco.um(f"SELECT COUNT(*) AS n FROM contato_telefone WHERE {sql}")["n"]
        print(f"  {rotulo}: {n}")
    if falharam:
        print(f"  ⚠️ {falharam} ficaram NULL por falha de consulta -- rodar de novo")
    return 0


if __name__ == "__main__":
    sys.exit(main())
