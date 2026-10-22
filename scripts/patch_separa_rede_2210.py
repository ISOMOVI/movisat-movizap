"""Separa a CHAMADA DE REDE do ESPELHO LOCAL, para o duplo dos testes poder
substituir so a rede.

🚨 O DUPLO FICOU IRREAL NO MOMENTO EM QUE EU MUDEI A FUNCAO. Os dois arquivos
de teste trocam `gmail._mexer_rotulo` inteiro por um falso que devolve
`{"ok": True}` -- e a docstring deles explica a intencao com clareza:

  *"Nenhum teste fala com o Gmail. `_mexer_rotulo` e o ponto unico por onde
  estrela, nao-lida e arquivar passam -- mockar aqui cobre os tres."*

A intencao e **nao falar com a rede**. Enquanto `_mexer_rotulo` era so rede,
trocar a funcao inteira cumpria isso. Depois do espelho local entrar nela, o
duplo passou a desligar tambem um efeito que acontece de verdade em producao --
e o teste de restaurar reprovou por isso, nao por defeito do codigo.

🚨 A LICAO: duplo se poe na BORDA (a rede), nunca no meio da regra. Quando o
duplo cobre regra, ele para de provar a regra -- e o sintoma e o pior que
existe, porque o teste fica verde em producao quebrada ou vermelho em producao
boa, sem distinguir os dois.

Depois desta separacao, os testes passam a exercitar o espelho local DE VERDADE
e continuam sem tocar a rede. Ganham cobertura em vez de perder.
"""
import shutil
import sys

GMAIL = "movizap/gmail.py"

# ---------------------------------------------------------------------------
# gmail.py: a rede sai para uma funcao propria.
# ---------------------------------------------------------------------------
GMAIL_ANTES = '''    token = _token_de_acesso(linha)
    corpo = {}
    if poe:
        corpo["addLabelIds"] = poe
    if tira:
        corpo["removeLabelIds"] = tira
    r = httpx.post(
        f"{API}/messages/{linha['id_externo']}/modify",
        headers={"Authorization": f"Bearer {token}"},
        json=corpo, timeout=30)
    if r.status_code != 200:
        raise GmailIndisponivel(
            f"O Gmail recusou {o_que} ({r.status_code}).")

    _espelhar_rotulos(mensagem_id, linha["conta_id"], poe, tira)
    return {"ok": True}'''

GMAIL_DEPOIS = '''    _modificar_no_gmail(linha, poe, tira, o_que)
    _espelhar_rotulos(mensagem_id, linha["conta_id"], poe, tira)
    return {"ok": True}


def _modificar_no_gmail(linha: dict, poe: list[str], tira: list[str],
                        o_que: str) -> None:
    """A CHAMADA DE REDE, e só ela. É aqui que os testes põem o duplo.

    🚨 ESTA FUNÇÃO EXISTE PARA O DUPLO TER ONDE ENCOSTAR. Até 22/10 os testes
    trocavam o `_mexer_rotulo` inteiro, o que cumpria a intenção deles ("nenhum
    teste fala com o Gmail") enquanto aquela função era só rede. Quando o
    espelho local entrou nela, o duplo passou a desligar **regra**, não só
    rede: o teste de restaurar reprovou por causa do duplo, com o código certo.

    Duplo se põe na BORDA. Duplo que cobre regra para de provar a regra, e
    fica verde em produção quebrada ou vermelho em produção boa sem distinguir
    os dois.
    """
    token = _token_de_acesso(linha)
    corpo = {}
    if poe:
        corpo["addLabelIds"] = poe
    if tira:
        corpo["removeLabelIds"] = tira
    r = httpx.post(
        f"{API}/messages/{linha['id_externo']}/modify",
        headers={"Authorization": f"Bearer {token}"},
        json=corpo, timeout=30)
    if r.status_code != 200:
        raise GmailIndisponivel(
            f"O Gmail recusou {o_que} ({r.status_code}).")'''

# ---------------------------------------------------------------------------
# Os duplos passam a trocar a rede. A primeira posicao vira a LINHA da
# mensagem (um dict), nao o id -- e os testes continuam afirmando `poe`/`tira`.
# ---------------------------------------------------------------------------
ACOES = "tests/teste_email_acoes.py"
LIXEIRA = "tests/teste_lixeira_email.py"

ACOES_DOC_ANTES = '''    """🚨 Nenhum teste fala com o Gmail. `_mexer_rotulo` é o ponto único por
    onde estrela, não-lida e arquivar passam -- mockar aqui cobre os três."""
    chamadas = []

    def falso(mensagem_id, poe, tira, o_que):
        chamadas.append({"id": mensagem_id, "poe": poe, "tira": tira})
        return {"ok": True}

    monkeypatch.setattr(gmail, "_mexer_rotulo", falso)
    yield chamadas'''

ACOES_DOC_DEPOIS = '''    """🚨 Nenhum teste fala com o Gmail, e o duplo fica na BORDA.

    ⚠️ 22/10: o duplo era no `_mexer_rotulo`, que era só rede. Depois que o
    espelho dos rótulos locais entrou nessa função, trocá-la inteira passou a
    desligar **regra** junto com a rede -- e o teste de restaurar reprovou com
    o código certo. Agora o duplo é no `_modificar_no_gmail`, que é só a
    chamada HTTP: o espelho local roda de verdade, e nada fala com o Google.
    """
    chamadas = []

    def falso(linha, poe, tira, o_que):
        chamadas.append({"id": linha["id"], "poe": poe, "tira": tira})

    monkeypatch.setattr(gmail, "_modificar_no_gmail", falso)
    yield chamadas'''

ACOES_FALHA_ANTES = '''        def as_vezes_falha(mensagem_id, poe, tira, o_que):
            chamadas["n"] += 1
            if chamadas["n"] == 2:
                raise gmail.GmailIndisponivel("caiu")
            return {"ok": True}

        monkeypatch.setattr(gmail, "_mexer_rotulo", as_vezes_falha)'''

ACOES_FALHA_DEPOIS = '''        def as_vezes_falha(linha, poe, tira, o_que):
            chamadas["n"] += 1
            if chamadas["n"] == 2:
                raise gmail.GmailIndisponivel("caiu")

        monkeypatch.setattr(gmail, "_modificar_no_gmail", as_vezes_falha)'''

LIXEIRA_DOC_ANTES = '''    def falso(mensagem_id, poe, tira, o_que):
        chamadas.append({"id": mensagem_id, "poe": poe, "tira": tira, "o_que": o_que})
        return {"ok": True}

    monkeypatch.setattr(gmail, "_mexer_rotulo", falso)'''

LIXEIRA_DOC_DEPOIS = '''    # ⚠️ 22/10: o duplo desceu de `_mexer_rotulo` para `_modificar_no_gmail`.
    # O primeiro deixou de ser só rede quando o espelho dos rótulos locais
    # entrou nele -- e este teste foi justamente o que reprovou por isso, com
    # o código certo. Duplo na borda; a regra roda.
    def falso(linha, poe, tira, o_que):
        chamadas.append({"id": linha["id"], "poe": poe, "tira": tira, "o_que": o_que})

    monkeypatch.setattr(gmail, "_modificar_no_gmail", falso)'''

LIXEIRA_CAB_ANTES = '''🚨 O GMAIL É MOCKADO, mesma regra do teste_email_acoes.py: `_mexer_rotulo`
é o ponto único por onde estrela, não-lida, arquivar, excluir e restaurar
passam -- mockar aqui cobre os cinco sem falar com a rede.'''

LIXEIRA_CAB_DEPOIS = '''🚨 O GMAIL É MOCKADO, mesma regra do teste_email_acoes.py: o duplo fica em
`_modificar_no_gmail`, a chamada HTTP por onde estrela, não-lida, arquivar,
excluir e restaurar passam -- cobre os cinco sem falar com a rede, e deixa o
espelho dos rótulos LOCAIS rodar de verdade (22/10).'''


def aplicar(caminho, passos, marca):
    texto = open(caminho, encoding="utf-8").read()
    if marca in texto:
        raise SystemExit(f"{caminho}: ja aplicado")
    for antes, depois, rotulo in passos:
        n = texto.count(antes)
        if n != 1:
            raise SystemExit(f"FALHOU {caminho} / {rotulo}: {n} ocorrencias")
        texto = texto.replace(antes, depois, 1)
        print(f"ok  {caminho}: {rotulo}")
    shutil.copyfile(caminho, caminho + ".bak_2026-10-22_borda")
    open(caminho, "w", encoding="utf-8").write(texto)


def main() -> int:
    aplicar(GMAIL, [(GMAIL_ANTES, GMAIL_DEPOIS, "a rede sai para funcao propria")],
            "_modificar_no_gmail")
    aplicar(ACOES, [(ACOES_DOC_ANTES, ACOES_DOC_DEPOIS, "o duplo vai para a borda"),
                    (ACOES_FALHA_ANTES, ACOES_FALHA_DEPOIS, "o duplo que falha")],
            "_modificar_no_gmail")
    aplicar(LIXEIRA, [(LIXEIRA_CAB_ANTES, LIXEIRA_CAB_DEPOIS, "o cabecalho"),
                      (LIXEIRA_DOC_ANTES, LIXEIRA_DOC_DEPOIS, "o duplo vai para a borda")],
            "_modificar_no_gmail")
    return 0


if __name__ == "__main__":
    sys.exit(main())
