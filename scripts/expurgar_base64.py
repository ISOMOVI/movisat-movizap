"""Tira o binário do log de eventos, mantendo o log.

O `webhook_evento` guarda o corpo cru de tudo que o Evolution manda -- e é essa
decisão que permitiu, em 10/08, recuperar 57 mídias, 30 nomes de WhatsApp e 32
citações que os parsers da época jogavam fora. O log cru fica.

O que sai é só o `base64`: 25 MB de foto e áudio dentro de uma tabela do banco,
que agora têm cópia própria em `/home/claude/movizap_midia/`. Guardar o mesmo
byte duas vezes, sendo que um dos lugares é o banco (que vai para backup),
infla o backup com o que a decisão do usuário mandou deixar fora dele.

🚨 A REGRA DE SEGURANÇA: só apaga o base64 de uma mensagem cujo arquivo esteja
no disco E cujo SHA256 confira. Se qualquer uma das duas falhar, o payload fica
intacto. Nunca se apaga a única cópia -- é a mesma regra do "validar 1 antes do
lote", aplicada por linha em vez de por execução.

⚠️ O campo é trocado por um MARCADOR, não removido. Campo ausente e campo
esvaziado de propósito são coisas diferentes na hora de conferir o formato do
Evolution -- e conferir formato é a razão desta tabela existir. É o mesmo
padrão que o `webhook.py` já usa para a `apikey`.

Uso:
    python scripts/expurgar_base64.py            # só relata, não escreve
    python scripts/expurgar_base64.py --uma      # faz UMA e confere
    python scripts/expurgar_base64.py --confirmar
"""
import hashlib
import json
import os
import pathlib
import sys

import psycopg
from psycopg.rows import dict_row

MARCADOR = "[movido para /home/claude/movizap_midia -- ver tabela midia]"

# 🚨 O OUTRO base64 QUE O EVOLUTION MANDA É O QR CODE DE PAREAMENTO. Medido em
# 10/08: 37 eventos `qrcode.updated`, 13,6 KB de PNG cada.
#
# Este NÃO tem cópia em disco e não precisa ter. Um QR code do WhatsApp vale
# poucos segundos: os guardados estão todos vencidos e não pareiam nada. Mas
# enquanto valem são CREDENCIAL -- quem lê o QR vincula um aparelho à conta.
# Guardar credencial vencida no banco e no backup não tem ganho nenhum e tem
# risco não-zero, pela mesma régua que tirou a `apikey` do payload em 07/08.
MARCADOR_QR = "[QR de pareamento -- descartado, vale segundos e é credencial]"

ENV = pathlib.Path("/home/claude/movizap_painel/.env")


def conectar():
    cfg = {}
    for linha in ENV.read_text(encoding="utf-8").splitlines():
        if "=" in linha and not linha.strip().startswith("#"):
            k, v = linha.split("=", 1)
            cfg[k.strip()] = v.strip()
    return psycopg.connect(
        host=cfg["MOVIZAP_DB_HOST"], port=cfg["MOVIZAP_DB_PORTA"],
        dbname=cfg["MOVIZAP_DB_NOME"], user=cfg["MOVIZAP_DB_USUARIO"],
        password=cfg["MOVIZAP_DB_SENHA"], row_factory=dict_row)


def midia_confirmada(cur, id_externo):
    """A mídia desta mensagem está no disco e íntegra? Devolve (ok, motivo)."""
    if not id_externo:
        return False, "evento sem id_externo"

    cur.execute(
        """SELECT md.id, md.caminho, md.hash, md.tamanho
             FROM mensagem m JOIN midia md ON md.id = m.midia_id
            WHERE m.id_externo = %s""", (id_externo,))
    linha = cur.fetchone()
    if not linha:
        return False, "mensagem sem mídia ligada"

    caminho = pathlib.Path(linha["caminho"])
    if not caminho.is_file():
        return False, f"arquivo não está no disco: {caminho}"

    # 🚨 Existir não é bastar. Confere o conteúdo antes de apagar a outra cópia.
    digest = hashlib.sha256(caminho.read_bytes()).hexdigest()
    if digest != linha["hash"]:
        return False, "SHA256 do arquivo não confere com o guardado"

    return True, f"mídia {linha['id']} íntegra ({linha['tamanho']} bytes)"


def candidatos(cur):
    """Eventos que ainda têm BINÁRIO -- não apenas a chave `base64`.

    🚨 A chave sobrevive à limpeza, com o marcador no lugar do conteúdo (é de
    propósito: campo ausente e campo esvaziado dizem coisas diferentes na hora
    de conferir o formato). Procurar pela CHAVE devolveria as mesmas linhas
    para sempre, e cada UPDATE deixa uma versão morta atrás -- o script que
    existe para encolher a tabela passaria a inchá-la todo dia.
    """
    cur.execute(
        """SELECT id, id_externo, payload
             FROM webhook_evento
            WHERE processado
              AND payload::text LIKE '%%"base64"%%'
              AND payload::text NOT LIKE %s
              AND payload::text NOT LIKE %s
            ORDER BY id""",
        (f"%{MARCADOR}%", f"%{MARCADOR_QR}%"))
    return cur.fetchall()


def limpar(payload):
    """Devolve (novo_payload, bytes_liberados, especie) ou (None, 0, "").

    Duas espécies, com regras diferentes: mídia só sai com o arquivo conferido
    no disco; QR code sai sempre, porque não há o que preservar.
    """
    data = payload.get("data")
    if not isinstance(data, dict):
        return None, 0, ""

    msg = data.get("message")
    if (isinstance(msg, dict) and isinstance(msg.get("base64"), str)
            and msg["base64"] != MARCADOR):
        liberados = len(msg["base64"])
        novo = json.loads(json.dumps(payload))   # cópia, não muta o original
        novo["data"]["message"]["base64"] = MARCADOR
        return novo, liberados, "midia"

    qr = data.get("qrcode")
    if (isinstance(qr, dict) and isinstance(qr.get("base64"), str)
            and qr["base64"] != MARCADOR_QR):
        liberados = len(qr["base64"])
        novo = json.loads(json.dumps(payload))
        novo["data"]["qrcode"]["base64"] = MARCADOR_QR
        return novo, liberados, "qrcode"

    return None, 0, ""


def main():
    so_uma = "--uma" in sys.argv
    confirmar = "--confirmar" in sys.argv

    con = conectar()
    cur = con.cursor()

    linhas = candidatos(cur)
    print(f"eventos processados com base64 no payload: {len(linhas)}")

    prontos, travados, total_bytes = [], [], 0
    por_especie = {"midia": 0, "qrcode": 0}
    for linha in linhas:
        novo, liberados, especie = limpar(linha["payload"])
        if novo is None:
            travados.append((linha["id"], "base64 não está onde se espera"))
            continue

        if especie == "qrcode":
            # Não há cópia para conferir: não existe nada a preservar.
            prontos.append((linha["id"], novo, liberados, "QR vencido"))
            total_bytes += liberados
            por_especie["qrcode"] += 1
            continue

        ok, motivo = midia_confirmada(cur, linha["id_externo"])
        if ok:
            prontos.append((linha["id"], novo, liberados, motivo))
            total_bytes += liberados
            por_especie["midia"] += 1
        else:
            travados.append((linha["id"], motivo))

    print(f"  liberáveis: {len(prontos)}  ({total_bytes/1024/1024:.1f} MB) "
          f"-- mídia {por_especie['midia']}, QR {por_especie['qrcode']}")
    print(f"  TRAVADOS (payload fica intacto): {len(travados)}")
    for eid, motivo in travados[:10]:
        print(f"    evento {eid}: {motivo}")

    if not prontos:
        print("\nnada a fazer.")
        return

    if not (so_uma or confirmar):
        print("\n(relatório apenas -- rode com --uma, depois --confirmar)")
        return

    alvos = prontos[:1] if so_uma else prontos
    print(f"\nlimpando {len(alvos)} evento(s)...")
    for eid, novo, liberados, motivo in alvos:
        cur.execute("UPDATE webhook_evento SET payload = %s WHERE id = %s",
                    (json.dumps(novo, ensure_ascii=False), eid))
    con.commit()

    # ── RELER O ESTADO. O UPDATE dizer "1" não prova nada.
    print("\n=== CONFERINDO ===")
    ids = [a[0] for a in alvos]
    cur.execute(
        "SELECT id, payload FROM webhook_evento WHERE id = ANY(%s)", (ids,))
    ruins = 0
    for linha in cur.fetchall():
        data = linha["payload"].get("data") or {}
        b64 = ((data.get("message") or {}).get("base64")
               or (data.get("qrcode") or {}).get("base64"))
        if b64 not in (MARCADOR, MARCADOR_QR):
            print(f"  evento {linha['id']}: base64 NÃO virou marcador -> {str(b64)[:40]}")
            ruins += 1
    print(f"  {len(ids) - ruins}/{len(ids)} com o marcador no lugar")

    # o resto do payload continua legível?
    cur.execute("SELECT payload FROM webhook_evento WHERE id = %s", (ids[0],))
    p = cur.fetchone()["payload"]
    d = p.get("data") or {}
    print(f"  payload ainda íntegro: pushName={d.get('pushName')!r} "
          f"messageType={d.get('messageType')!r} "
          f"chaves de message={sorted((d.get('message') or {}).keys())}")

    # e o arquivo continua lá?
    cur.execute(
        """SELECT count(*) n FROM midia
            WHERE caminho IS NOT NULL""")
    print(f"  linhas em midia: {cur.fetchone()['n']}")
    raiz = pathlib.Path("/home/claude/movizap_midia")
    arqs = [x for x in raiz.rglob("*") if x.is_file()]
    print(f"  arquivos no disco: {len(arqs)} · "
          f"{sum(x.stat().st_size for x in arqs)/1024/1024:.1f} MB")

    cur.execute("SELECT pg_size_pretty(pg_total_relation_size('webhook_evento')) t")
    print(f"  tamanho da tabela webhook_evento: {cur.fetchone()['t']}")
    con.close()


if __name__ == "__main__":
    main()
