"""A fixture do `teste_email_acoes` passa a criar mensagem DE CAIXA DE ENTRADA.

As tres mensagens nasciam sem rotulo nenhum. Ate 22/10 isso bastava, porque
"estar na Entrada" era `NOT arquivada AND viva`. Com a Entrada exigindo `INBOX`
(decisao dele: *"siga com a 2"*), mensagem sem rotulo esta **arquivada no
Gmail** -- e o `GET /api/email/mensagens`, que abre na Entrada, vinha vazio.

🚨 CORRIGIR A FIXTURE, E NAO O FILTRO. A fixture e que era irreal: mensagem de
caixa de entrada sempre tem `INBOX` no Gmail. Afrouxar o filtro para a fixture
passar seria escrever o defeito no codigo para agradar o teste -- e o defeito
era justamente o selo contar uma mensagem arquivada.
"""
import shutil
import sys

ALVO = "tests/teste_email_acoes.py"

ANTES = '''    msgs = []
    for i in range(3):
        msgs.append(banco.um(
            """INSERT INTO email_mensagem (conta_id, id_externo, remetente,
                                           assunto, lida)
               VALUES (%s, %s, 'quem@fora.com', %s, true) RETURNING id""",
            (conta, f"zz-acoes-{i}", f"assunto {i}"))["id"])'''

DEPOIS = '''    # 🚨 O `INBOX` NASCE COM A MENSAGEM desde 22/10: a Entrada passou a exigir
    # esse rótulo, que é como o Gmail diz "está na caixa de entrada". Sem ele
    # estas três seriam mensagens ARQUIVADAS, e o `GET /api/email/mensagens`
    # (que abre na Entrada) vinha vazio -- foi assim que estes testes
    # reprovaram, por fixture irreal e não por defeito do código.
    rotulo_inbox = banco.um(
        """INSERT INTO email_marcador (conta_id, id_externo, nome, natureza)
           VALUES (%s, 'INBOX', 'INBOX', 'sistema')
           ON CONFLICT (conta_id, id_externo)
           DO UPDATE SET nome = email_marcador.nome RETURNING id""",
        (conta,))["id"]
    msgs = []
    for i in range(3):
        mid = banco.um(
            """INSERT INTO email_mensagem (conta_id, id_externo, remetente,
                                           assunto, lida)
               VALUES (%s, %s, 'quem@fora.com', %s, true) RETURNING id""",
            (conta, f"zz-acoes-{i}", f"assunto {i}"))["id"]
        banco.executar(
            """INSERT INTO email_mensagem_marcador (mensagem_id, marcador_id)
               VALUES (%s, %s) ON CONFLICT DO NOTHING""", (mid, rotulo_inbox))
        msgs.append(mid)'''


def main() -> int:
    texto = open(ALVO, encoding="utf-8").read()
    if "rotulo_inbox" in texto:
        raise SystemExit("ja aplicado")
    if texto.count(ANTES) != 1:
        raise SystemExit(f"ancora com {texto.count(ANTES)} ocorrencias")
    shutil.copyfile(ALVO, ALVO + ".bak_2026-10-22_fixture")
    open(ALVO, "w", encoding="utf-8").write(texto.replace(ANTES, DEPOIS, 1))
    print(f"ok  {ALVO}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
