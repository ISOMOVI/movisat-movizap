#!/usr/bin/env python3
"""Recupera as reações que viraram mensagem falsa, e só então apaga as falsas.

🚨 A ORDEM É A GARANTIA. Primeiro aplica cada reação no lugar certo
(`mensagem_reacao`), lendo o payload cru que o `webhook_evento` guardou;
**depois** apaga a linha `[reactionMessage — tipo ainda não tratado]`. Assim
nada se perde: o que for apagado já está guardado em outro lugar, e o que não
puder ser recuperado NÃO é apagado.

Medido em 26/08 antes de escrever: 161 eventos de reação, 159 apontando para
mensagem que temos, 161 linhas falsas no histórico (97 em conversa direta,
64 em grupo).

⚠️ É por isso que a migração 036 não faz isto: migração que apaga dado do
usuário tem de ser um passo separado, que se lê antes de rodar e que roda
seco primeiro.

Uso:
  ./venv/bin/python scripts/migrar_reacoes.py            # seco, não grava nada
  ./venv/bin/python scripts/migrar_reacoes.py --aplicar
"""
import sys

sys.path.insert(0, "/home/claude/movizap_painel")

from movizap import banco, conversas  # noqa: E402

MARCA = "[reactionMessage — tipo ainda não tratado]"


def main() -> int:
    aplicar = "--aplicar" in sys.argv
    banco.abrir()

    eventos = banco.varios(
        """SELECT id, payload FROM webhook_evento
            WHERE payload::text LIKE %s ORDER BY id""", ("%reactionMessage%",))
    print(f"eventos de reação guardados: {len(eventos)}")

    aplicadas = 0
    sem_alvo = 0
    with banco.cursor() as cur:
        for e in eventos:
            data = ((e["payload"] or {}).get("data") or {})
            chave = data.get("key") or {}
            e_grupo = str(chave.get("remoteJid") or "").endswith("@g.us")
            # O telefone que o webhook já normalizou fica no próprio evento;
            # aqui basta o JID, porque conversa direta usa o remetente.
            nota = conversas._aplicar_reacao(cur, data, e_grupo, None)
            if nota.startswith("reação a mensagem que não temos") or \
               nota.startswith("reação sem alvo"):
                sem_alvo += 1
            else:
                aplicadas += 1
        if not aplicar:
            # 🚨 SECO DE VERDADE: desfaz tudo o que este cursor escreveu.
            cur.connection.rollback()

    print(f"  reações aplicáveis : {aplicadas}")
    print(f"  sem alvo no banco  : {sem_alvo} (estas NÃO serão apagadas)")

    falsas = banco.um(
        "SELECT count(*) n FROM mensagem WHERE conteudo = %s", (MARCA,))["n"]
    print(f"linhas falsas no histórico: {falsas}")

    # ⚠️ Só apaga a linha falsa cujo evento correspondente PÔDE ser aplicado.
    # A ligação é o `id_externo` da mensagem falsa, que é o id do evento de
    # reação -- e o evento sabe qual mensagem ele reagia.
    apagaveis = banco.um(
        """SELECT count(*) n FROM mensagem m
            WHERE m.conteudo = %s
              AND EXISTS (
                  SELECT 1 FROM webhook_evento e
                   WHERE e.id_externo = m.id_externo
                     AND EXISTS (SELECT 1 FROM mensagem alvo
                                  WHERE alvo.id_externo =
                                        e.payload->'data'->'message'
                                         ->'reactionMessage'->'key'->>'id'))""",
        (MARCA,))["n"]
    print(f"  apagáveis com segurança  : {apagaveis}")
    print(f"  ficam (alvo desconhecido): {falsas - apagaveis}")

    if not aplicar:
        print("\nSECO — nada foi gravado. Rode com --aplicar.")
        return 0

    banco.executar(
        """DELETE FROM mensagem m
            WHERE m.conteudo = %s
              AND EXISTS (
                  SELECT 1 FROM webhook_evento e
                   WHERE e.id_externo = m.id_externo
                     AND EXISTS (SELECT 1 FROM mensagem alvo
                                  WHERE alvo.id_externo =
                                        e.payload->'data'->'message'
                                         ->'reactionMessage'->'key'->>'id'))""",
        (MARCA,))

    # 🚨 A CONFIRMAÇÃO É RELER O ESTADO, nunca o retorno do comando.
    print("\ndepois:")
    print("  reações gravadas :",
          banco.um("SELECT count(*) n FROM mensagem_reacao")["n"])
    print("  linhas falsas    :",
          banco.um("SELECT count(*) n FROM mensagem WHERE conteudo = %s",
                   (MARCA,))["n"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
