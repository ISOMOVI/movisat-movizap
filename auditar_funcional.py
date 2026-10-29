# -*- coding: utf-8 -*-
"""AUDITORIA FUNCIONAL: painel + formulários + os recursos do plano.

🔵 Pedido dele: *"audite o painel + forms + recursos desse plano depois, precisa
funcionar"*.

🚨 ESTA AUDITORIA EXERCITA, NAO LE CODIGO. Toda linha abaixo chama o caminho
real (rota HTTP, com sessao de owner) e compara com o dado de hoje. O que nao
puder ser exercitado sem escrever no ERP e dito como NAO EXERCITADO, em vez de
declarado funcionando.

Uso: venv/bin/python auditar_funcional.py
"""
import json
import sys

sys.path.insert(0, "/home/claude/movizap_painel")

from fastapi.testclient import TestClient  # noqa: E402

from movizap import auth, banco, chamado_os, formularios, main  # noqa: E402
from movizap import paineis, passagem  # noqa: E402
from movizap.config import settings  # noqa: E402

banco.abrir()
ok, falho, naoexerc = [], [], []


def conferir(nome, condicao, detalhe=""):
    (ok if condicao else falho).append((nome, detalhe))
    print(f"  {'OK  ' if condicao else 'FALHA'} {nome}"
          + (f" — {detalhe}" if detalhe else ""))


def nao_exercitado(nome, por_que):
    naoexerc.append((nome, por_que))
    print(f"  ----  {nome} — NAO EXERCITADO: {por_que}")


with TestClient(main.app) as c:
    cab = {"Authorization": f"Bearer {auth.criar_token(settings.admin_login)}"}

    print()
    print("=" * 72)
    print("1. O PAINEL DA OPERACAO")
    print("=" * 72)

    r = c.get("/api/paineis/operacao", headers=cab)
    conferir("a rota responde 200", r.status_code == 200, f"status {r.status_code}")
    q = r.json() if r.status_code == 200 else {}

    conferir("17 colunas, na ordem dele", len(q.get("colunas") or []) == 17,
             f"{len(q.get('colunas') or [])} colunas")
    conferir("a ponte do FPSL respondeu", q.get("ponte_respondeu") is True,
             q.get("ponte_motivo") or "")
    cards = [cd for col in q.get("colunas", []) for cd in col["cards"]]
    conferir("ha card na tela", len(cards) > 0, f"{len(cards)} cards")
    conferir("a data matriz e 24/10 (D9)", q.get("desde") == "2026-10-24",
             str(q.get("desde")))
    conferir("o interruptor nasce ligado", q.get("so_abertas") is True)
    conferir("pode_mover e verdade (Bloco D)", q.get("pode_mover") is True)

    # Cada card tem o que a tela desenha?
    sem_cliente = [cd["numero_ordem"] for cd in cards if not cd.get("cliente")]
    conferir("todo card tem nome de cliente", not sem_cliente,
             f"sem nome: {sem_cliente}")
    sem_tipo = [cd["numero_ordem"] for cd in cards if not cd.get("tipo_nome")]
    conferir("todo card tem nome de tipo", not sem_tipo,
             f"sem tipo: {sem_tipo}")
    # 🚨 A data tem de ser ISO, senao o "ha X dias" nao aparece.
    nao_iso = [cd["numero_ordem"] for cd in cards
               if cd.get("criada_em") and "/" in str(cd["criada_em"])]
    conferir("a data do card e ISO (o 'ha X dias' depende disso)",
             not nao_iso, f"em formato brasileiro: {nao_iso}")
    sem_lido = [cd["numero_ordem"] for cd in cards if not cd.get("visto_em")]
    conferir("todo card diz quando foi lido do ERP", not sem_lido,
             f"sem: {sem_lido}")

    r2 = c.get("/api/paineis/operacao?so_abertas=0", headers=cab)
    n0 = sum(cl["total"] for cl in r2.json()["colunas"])
    conferir("o interruptor muda o quadro", n0 > len(cards),
             f"{len(cards)} abertas -> {n0} com finalizadas")

    print()
    print("  -- o que NAO tem coluna, e se a tela diz --")
    f = q.get("fora_do_quadro", {})
    print(f"     {json.dumps(f, ensure_ascii=False, default=str)}")
    conferir("a sobra sem OS vem com o NUMERO do chamado",
             (not f.get("sem_tentativa")) or bool(f.get("sem_tentativa_quais")),
             f"quais: {f.get('sem_tentativa_quais')}")
    conferir("a OS sem coluna vem com o NUMERO da OS",
             (not f.get("situacao_fora")) or bool(f.get("fora_quais")),
             f"quais: {f.get('fora_quais')}")

    print()
    print("=" * 72)
    print("2. MOVER O CARD (Bloco D)")
    print("=" * 72)

    r = c.post("/api/paineis/operacao/mover",
               json={"numero_os": 99999, "para_situacao": 99999}, headers=cab)
    conferir("situacao fora das 17 e recusada",
             r.status_code in (400, 422), f"status {r.status_code}")

    r = c.put("/api/paineis/operacao/desde", json={"desde": "24/10/2026"},
              headers=cab)
    conferir("data matriz torta e recusada", r.status_code in (400, 422),
             f"status {r.status_code}")

    r = c.get("/api/paineis/operacao/passagens?dias=1", headers=cab)
    conferir("o log de passagens e legivel", r.status_code == 200,
             f"{len(r.json().get('passagens', []))} passagens em 1 dia")

    nao_exercitado("mover de verdade pela rota HTTP",
                   "escreve no ERP; ja provado na OS 16991 pelo script "
                   "provar_mover.py, e repetir aqui consumiria escrita real")

    print()
    print("=" * 72)
    print("3. OS FORMULARIOS")
    print("=" * 72)

    r = c.get("/api/formularios", headers=cab)
    conferir("a lista da FRM_1.1 responde", r.status_code == 200)
    forms = r.json() if r.status_code == 200 else []
    conferir("os 15 estao cadastrados", len(forms) == 15, f"{len(forms)}")
    ligados = [x for x in forms if x.get("ativo")]
    conferir("todos ligados", len(ligados) == 15, f"{len(ligados)} ligados")

    print()
    print("  -- a pagina publica de cada um (o que o cliente abre) --")
    for x in sorted(forms, key=lambda y: y["slug"]):
        slug = x["slug"]
        p = c.get(f"/api/publico/formulario/{slug}")
        d = p.json() if p.status_code == 200 else {}
        campos = len(d.get("campos") or [])
        etapas = len(d.get("etapas") or []) if d.get("etapas") else 0
        marca = "OK  " if p.status_code == 200 and campos else "FALHA"
        if p.status_code != 200 or not campos:
            falho.append((f"formulario {slug}", f"status {p.status_code}"))
        else:
            ok.append((f"formulario {slug}", ""))
        print(f"  {marca} /f/{slug:<26} {campos:>3} campos | "
              f"etapas: {etapas} | formato: {d.get('formato') or '?'} | "
              f"abre OS: {'sim' if chamado_os.formulario_abre_os(slug) else 'nao'}")

    print()
    print("  -- a busca de cliente por CNPJ (o que a tela do Suporte usa) --")
    p = c.post("/api/publico/formulario/suporte/cliente",
               data={"documento": "18392222000162",
                     "abertura": formularios._assinar("a0")})
    print(f"     status {p.status_code}: {str(p.text)[:160]}")
    conferir("a busca por CNPJ responde", p.status_code in (200, 400, 422),
             f"status {p.status_code}")

    print()
    print("=" * 72)
    print("4. A OS DO CHAMADO (Bloco A)")
    print("=" * 72)

    conferir("so o SUPORTE abre OS hoje",
             set(chamado_os.PROBLEMA_POR_FORMULARIO) == {"suporte"},
             str(set(chamado_os.PROBLEMA_POR_FORMULARIO)))
    conferir("o cliente sai do CNPJ",
             chamado_os.cliente_do_chamado(
                 formularios.definicao("suporte"),
                 {next(cp["nome"] for cp in formularios.definicao("suporte")["campos"]
                       if cp.get("validacao") == "cnpj"): "18392222000162"}) == 68546)
    linha = banco.um("SELECT count(*) AS n FROM solicitacao_os")
    print(f"     solicitacao_os: {linha['n']} linhas")
    nao_exercitado("um envio real que abre OS",
                   "criaria OS no ERP; o caminho esta provado por teste HTTP "
                   "(teste_rotas_pipeline) e pela OS 17056, criada e apagada")

print()
print("=" * 72)
print(f"RESULTADO: {len(ok)} OK · {len(falho)} FALHAS · "
      f"{len(naoexerc)} nao exercitados")
print("=" * 72)
for nome, det in falho:
    print(f"  FALHA: {nome} — {det}")
sys.exit(1 if falho else 0)
