"""O rotulo que mexemos no Gmail passa a ser espelhado AQUI tambem.

🚨 DEFEITO DE PRODUCAO QUE A MINHA MUDANCA DE 22/10 IA INTRODUZIR, e que a
suite pegou. Com a Entrada passando a exigir o rotulo `INBOX`, a funcao
`restaurar` virou mentira: ela poe `INBOX` **no Gmail** e limpa
`na_lixeira_desde` **aqui**, mas nunca gravou o marcador local. Restaurar
mandaria a mensagem para **Arquivadas** em vez da Entrada.

E a ironia esta escrita no corpo da propria `restaurar`, desde 17/09:

  *"O `untrash` SOZINHO NAO DEVOLVE O `INBOX` (...) sem ele a pessoa clicaria
  'restaurar' e o e-mail sumiria de vez visualmente, mesmo sem ter sido
  apagado."*

Era verdade do lado do Gmail, e virou verdade do lado de ca. Mesmo defeito,
mesma frase, outro lado da casa.

🚨 O CONSERTO E NO PONTO UNICO, NAO EM CADA CHAMADOR. `_mexer_rotulo` e a
funcao por onde estrela, nao-lida, arquivar, excluir e restaurar passam -- o
proprio cabecalho dela diz "UMA FUNCAO, NAO TRES COPIAS", pela licao do
`_condicao_busca`. Entao o espelho local vai aqui: o que mandamos o Gmail
ligar/desligar, ligamos/desligamos aqui. Consertar so a `restaurar` deixaria
`arquivar`, `excluir` e `marcar_nao_lida` com o mesmo buraco esperando.

O que isto corrige de passagem, sem ninguem ter pedido:

  - `arquivar(True)` tirava `INBOX` no Gmail e deixava o marcador local --
    hoje mascarado porque a coluna `arquivada` tem precedencia no filtro, mas
    era estado local mentindo;
  - `marcar_nao_lida` punha `UNREAD` no Gmail e nao aqui -- gravava
    `lida = false` sem o marcador, exatamente a divergencia que eu medi em
    zero (zero porque ninguem tinha usado o botao nesta conta);
  - `excluir` nao gravava `TRASH` localmente.

⚠️ `marcar_lida` NAO passa por aqui: ela tem caminho proprio, com um `DELETE`
explicito do `UNREAD` (gmail.py:316). Fica como esta -- era o unico espelho que
existia, e e o que mantinha `lida` e `UNREAD` de acordo nas 826 mensagens.
"""
import shutil
import sys

ALVO = "movizap/gmail.py"

ANTES = '''    r = httpx.post(
        f"{API}/messages/{linha['id_externo']}/modify",
        headers={"Authorization": f"Bearer {token}"},
        json=corpo, timeout=30)
    if r.status_code != 200:
        raise GmailIndisponivel(
            f"O Gmail recusou {o_que} ({r.status_code}).")
    return {"ok": True}'''

DEPOIS = '''    r = httpx.post(
        f"{API}/messages/{linha['id_externo']}/modify",
        headers={"Authorization": f"Bearer {token}"},
        json=corpo, timeout=30)
    if r.status_code != 200:
        raise GmailIndisponivel(
            f"O Gmail recusou {o_que} ({r.status_code}).")

    _espelhar_rotulos(mensagem_id, linha["conta_id"], poe, tira)
    return {"ok": True}


def _espelhar_rotulos(mensagem_id: int, conta_id: int,
                      poe: list[str], tira: list[str]) -> None:
    """Repete AQUI o que acabamos de mandar o Gmail fazer com os rótulos.

    🚨 SEM ISTO O ESTADO LOCAL MENTE, e desde 22/10 ele decide em que CAIXA a
    mensagem aparece (a Entrada exige o rótulo `INBOX`). O caso que a suíte
    pegou: `restaurar` punha `INBOX` no Gmail, limpava `na_lixeira_desde`
    aqui, e **não gravava o marcador** -- a mensagem restaurada ia para
    Arquivadas em vez da Entrada.

    É a mesma lição que o corpo da `restaurar` já carregava sobre o lado do
    Gmail (*"o `untrash` sozinho não devolve o `INBOX`"*), agora do lado de
    cá: operação que mexe em rótulo tem de mexer nos DOIS lugares, ou os dois
    divergem e ninguém sabe qual é a verdade.

    ⚠️ Fica num ponto único de propósito -- `_mexer_rotulo` é por onde
    estrela, não-lida, arquivar, excluir e restaurar passam. Espelhar em cada
    chamador é o defeito que o cabeçalho daquela função já proíbe.
    """
    for rotulo in poe or []:
        marcador = banco.um(
            """INSERT INTO email_marcador (conta_id, id_externo, nome, natureza)
               VALUES (%s, %s, %s, 'sistema')
               ON CONFLICT (conta_id, id_externo)
               DO UPDATE SET nome = email_marcador.nome
               RETURNING id""", (conta_id, rotulo, rotulo))["id"]
        banco.executar(
            """INSERT INTO email_mensagem_marcador (mensagem_id, marcador_id)
               VALUES (%s, %s) ON CONFLICT DO NOTHING""",
            (mensagem_id, marcador))
    for rotulo in tira or []:
        banco.executar(
            """DELETE FROM email_mensagem_marcador mm
                USING email_marcador mk
                WHERE mk.id = mm.marcador_id AND mm.mensagem_id = %s
                  AND mk.conta_id = %s AND mk.id_externo = %s""",
            (mensagem_id, conta_id, rotulo))'''


def main() -> int:
    texto = open(ALVO, encoding="utf-8").read()
    if "_espelhar_rotulos" in texto:
        raise SystemExit("ja aplicado")
    if texto.count(ANTES) != 1:
        raise SystemExit(f"ancora com {texto.count(ANTES)} ocorrencias, esperava 1")
    shutil.copyfile(ALVO, ALVO + ".bak_2026-10-22_espelho")
    open(ALVO, "w", encoding="utf-8").write(texto.replace(ANTES, DEPOIS, 1))
    print("ok  movizap/gmail.py (com .bak_2026-10-22_espelho)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
