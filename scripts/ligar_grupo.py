"""Liga (ou desliga) o recebimento de mensagens de GRUPO numa instância.

🚨 SÓ NA `atendimento`, por decisão do usuário em 12/08. A `informativos` é
disparo: um grupo virando atendimento ali seria resposta num canal que ninguém
lê. O padrão de pareamento (`evolution.SETTINGS_PADRAO`) continua
`groupsIgnore = True`, para instância nova não começar recebendo tudo.

⚠️ LIGAR NÃO IMPORTA GRUPO NENHUM. A conversa só nasce quando CHEGA MENSAGEM,
então dos 62 grupos de que o número participa só aparecem os que falarem.
Grupo parado nunca vira conversa (migração 028).

🚨 A CONFIRMAÇÃO É RELER DO EVOLUTION, não o código de retorno do POST.

Uso:  ./venv/bin/python scripts/ligar_grupo.py            (confere)
      ./venv/bin/python scripts/ligar_grupo.py --ligar
      ./venv/bin/python scripts/ligar_grupo.py --desligar
"""
import sys

import httpx

sys.path.insert(0, "/home/claude/movizap_painel")

from movizap.config import settings  # noqa: E402

INSTANCIA = "atendimento"


def ler(c: httpx.Client) -> dict:
    r = c.get(f"/settings/find/{INSTANCIA}")
    if r.status_code != 200:
        raise SystemExit(f"Evolution respondeu {r.status_code} ao ler settings.")
    return r.json() or {}


def main() -> None:
    if "--ligar" in sys.argv:
        alvo = False          # groupsIgnore = False significa RECEBER grupo
    elif "--desligar" in sys.argv:
        alvo = True
    else:
        alvo = None

    cabecalhos = {"apikey": settings.evolution_api_key}
    with httpx.Client(base_url=settings.evolution_base_url, timeout=30,
                      headers=cabecalhos) as c:
        antes = ler(c)
        print(f"instância        : {INSTANCIA}")
        print(f"groupsIgnore     : {antes.get('groupsIgnore')}  "
              f"({'IGNORA grupo' if antes.get('groupsIgnore') else 'RECEBE grupo'})")

        if alvo is None:
            print("\n(leitura) nada alterado. Use --ligar ou --desligar.")
            return
        if antes.get("groupsIgnore") == alvo:
            print(f"\njá está como se pede. Nada a fazer.")
            return

        # ⚠️ O POST de settings SUBSTITUI o conjunto. Mandar só o campo que
        # muda apagaria os outros -- é a mesma armadilha do PUT do Harmonit,
        # onde campo omitido não é preservado, é apagado. Por isso relê,
        # troca um campo e devolve o conjunto inteiro.
        corpo = {k: v for k, v in antes.items()
                 if k not in ("id", "instanceId", "createdAt", "updatedAt")}
        corpo["groupsIgnore"] = alvo

        r = c.post(f"/settings/set/{INSTANCIA}", json=corpo)
        print(f"\nPOST /settings/set -> HTTP {r.status_code}")

        depois = ler(c)
        print(f"relido           : groupsIgnore = {depois.get('groupsIgnore')}")
        if depois.get("groupsIgnore") != alvo:
            raise SystemExit("ABORTADO: o Evolution não aplicou a mudança.")

        # Conferir que nada mais foi perdido no caminho.
        perdidos = [k for k in corpo
                    if k != "groupsIgnore" and k in antes
                    and depois.get(k) != antes.get(k)]
        if perdidos:
            print(f"⚠️ MUDARAM TAMBÉM: {perdidos} — conferir se era esperado.")
        else:
            print("nenhum outro campo mudou.")

        print()
        print("RECEBE grupo agora." if not alvo else "VOLTOU a ignorar grupo.")
        if not alvo:
            print("Grupo entra na MESMA lista da conversa direta, como no "
                  "WhatsApp. Não há importação: só vira conversa o grupo que "
                  "MANDAR MENSAGEM (migração 028).")


if __name__ == "__main__":
    main()
