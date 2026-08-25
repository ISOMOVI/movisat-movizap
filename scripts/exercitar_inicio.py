"""Exercita /api/inicio de verdade, como owner e como atendente comum.

🚨 EXISTE PORQUE PLACAR VERDE NÃO PROVA QUE A TELA ABRE. A suíte cobre as
funções; isto cobre a ROTA -- autenticação, serialização e o formato que a
tela consome. Já aconteceu de tudo passar com a tela derrubada.

⚠️ O token é criado e usado DENTRO do processo, nunca em linha de comando:
segredo em argv vai para o `auditd`. Nada de token é impresso.
"""
import sys

sys.path.insert(0, "/home/claude/movizap_painel")

from fastapi.testclient import TestClient  # noqa: E402

from movizap import auth, banco, main  # noqa: E402

banco.abrir()
cliente = TestClient(main.app)

for rotulo, condicao in (("owner", "owner"), ("atendente comum", "NOT owner")):
    linha = banco.um(
        f"SELECT login FROM atendente WHERE ativo AND {condicao} "
        f"  AND email IS NOT NULL LIMIT 1")
    if not linha:
        print(f"{rotulo}: nenhuma conta para testar")
        continue

    r = cliente.get("/api/inicio",
                    headers={"Authorization":
                             f"Bearer {auth.criar_token(linha['login'])}"})
    print(f"\n--- {rotulo} · HTTP {r.status_code}")
    if r.status_code != 200:
        print("   corpo:", r.text[:200])
        continue
    d = r.json()
    print("   chaves:", sorted(d))
    print("   meu_dia:", [(i["chave"], i["valor"]) for i in d["meu_dia"]])
    print("   operacao:", [(i["chave"], i["valor"]) for i in d["atencao"]])
    print("   desfecho minhas:", d["desfecho"]["minhas"],
          "| equipe:", d["desfecho"]["equipe"])
    print("   canais no JSON?", "canais" in d)
    if "configuracao" in d and d["configuracao"]:
        c = d["configuracao"]
        print("   config:", c["perfil"], "| times:", c["times"],
              "| fila inteira:", c["ve_a_fila_inteira"],
              "| jornada hoje:", len(c["jornada_hoje"]), "faixa(s)")

banco.fechar()
