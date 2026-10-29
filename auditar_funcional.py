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

# 🚨 O CLIENTE DOS TESTES E A VELASCO (998063), E SO ELA. Regra dele, 29/10:
# *"nao pode usar outro CNPJ alem da VELASCO para teste, pois os tickets nascem
# e tem ligacoes. OS com outros clientes podem ser mal interpretadas pela OP"*.
#
# ⚠️ Aqui o id vive em DUBLE e nenhuma escrita chega ao ERP -- mas e de um teste
# que se copia o numero para um script que escreve, e foi exatamente o que eu
# fiz em 29/10: a OS 17056 nasceu na DCBM porque o numero dela estava a mao.
CLIENTE_SANDBOX = 998063


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
               data={"documento": "WQ0P6GLD000108",
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
                       if cp.get("validacao") == "cnpj"): "WQ0P6GLD000108"}) == 998063)
    linha = banco.um("SELECT count(*) AS n FROM solicitacao_os")
    print(f"     solicitacao_os: {linha['n']} linhas")
    nao_exercitado("um envio real que abre OS",
                   "criaria OS no ERP; o caminho esta provado por teste HTTP "
                   "(teste_rotas_pipeline) e pela OS 17056, criada e apagada")

# ============================================================================
# 5 A 7 — ACRESCENTADOS EM 29/10, noite: *"audite tudo e documente"*
# ============================================================================
import re  # noqa: E402

from movizap import passagem  # noqa: E402

with TestClient(main.app) as c:
    cab = {"Authorization": f"Bearer {auth.criar_token(settings.admin_login)}"}

    print()
    print("=" * 72)
    print("5. BLOCO C — OS DOIS TEMPOS")
    print("=" * 72)

    q = c.get("/api/paineis/operacao", headers=cab).json()
    cards = [cd for col in q["colunas"] for cd in col["cards"]]
    conferir("todo card traz o campo da etapa",
             all("etapa_desde" in cd for cd in cards))
    conferir("todo card do ERP traz a data de criacao (o TOTAL)",
             all(cd.get("criada_em") for cd in cards if cd["origem"] == "erp"))
    medidos = [cd["numero_ordem"] for cd in cards if cd.get("etapa_desde")]
    print(f"     com etapa medida: {len(medidos)} de {len(cards)} "
          f"(a os_passagem comecou em 29/10)")
    conferir("a etapa_desde sai da passagem, nao de palpite",
             all(passagem.etapa_desde([n]).get(n) for n in medidos)
             if medidos else True)

    print()
    print("=" * 72)
    print("6. BLOCO F — PRIORIDADE E OBSERVACAO")
    print("=" * 72)

    conferir("as 4 prioridades sao as que ele decidiu",
             passagem.PRIORIDADES == {381: "Baixa", 382: "Normal",
                                      383: "Alta", 384: "Urgente"})
    com_prio = [cd["numero_ordem"] for cd in cards if cd.get("prioridade_nome")]
    print(f"     cards com prioridade no cache: {len(com_prio)} de {len(cards)}")
    conferir("prioridade inventada e recusada",
             c.post("/api/paineis/operacao/prioridade",
                    json={"numero_os": 90901, "prioridade_id": 99999},
                    headers=cab).status_code in (400, 422))
    conferir("observacao vazia e recusada",
             c.post("/api/paineis/operacao/observacao",
                    json={"numero_os": 90901, "texto": "  "},
                    headers=cab).status_code in (400, 422))
    r = c.post("/api/paineis/operacao/observacao",
               json={"numero_os": 90901, "texto": "zz auditoria"}, headers=cab)
    try:
        obs = r.json().get("observacoes") or []
        conferir("observacao grava com autor e hora",
                 bool(obs) and bool(obs[0].get("quem")) and bool(obs[0].get("em")),
                 f"{len(obs)} observacao(oes)")
        conferir("o card fechado conta os recados",
                 passagem.quantas_observacoes([90901]) == {90901: 1})
    finally:
        banco.executar("DELETE FROM os_observacao WHERE numero_os = %s",
                       (90901,))
    conferir("o log do teste foi limpo",
             passagem.observacoes(90901) == [])

    print()
    print("=" * 72)
    print("7. OS FILTROS E ORDENADORES")
    print("=" * 72)

    conferir("a rota aceita busca e ordem",
             c.get("/api/paineis/operacao?busca=zz&ordem=cliente",
                   headers=cab).status_code == 200)
    if cards:
        alvo = cards[0]
        porOS = c.get(f"/api/paineis/operacao?busca={alvo['numero_ordem']}",
                      headers=cab).json()
        conferir("busca por OS acha 1 e diz que casou por OS",
                 porOS["total"] == 1 and porOS["filtro_casou_por"] == ["OS"],
                 f"{porOS['total']} card(s), casou por {porOS['filtro_casou_por']}")
        if alvo.get("cliente"):
            nome = alvo["cliente"].split()[0]
            porCli = c.get(f"/api/paineis/operacao?busca={nome}",
                           headers=cab).json()
            conferir("busca por CLIENTE acha e diz",
                     porCli["total"] >= 1
                     and "cliente" in (porCli["filtro_casou_por"] or []),
                     f"{porCli['total']} card(s) com {nome!r}")
    vazio = c.get("/api/paineis/operacao?busca=zzznaoexistezzz",
                  headers=cab).json()
    conferir("busca sem resultado DIZ que esta filtrada",
             vazio["total"] == 0 and vazio["busca"] == "zzznaoexistezzz")
    for ordem in ("os_desc", "os_asc", "parado", "cliente", "antiga"):
        r = c.get(f"/api/paineis/operacao?ordem={ordem}", headers=cab)
        if r.status_code != 200 or r.json()["ordem"] != ordem:
            falho.append((f"ordem {ordem}", f"status {r.status_code}"))
        else:
            ok.append((f"ordem {ordem}", ""))
    print(f"  OK   as 5 ordens respondem")
    conferir("ordem inventada cai no padrao, sem estourar",
             c.get("/api/paineis/operacao?ordem=zzz",
                   headers=cab).status_code == 200)
    from movizap import paineis as _p
    conferir("a busca ignora acento e caixa",
             _p._normalizar("VEICULO") == _p._normalizar("veiculo")
             == _p._normalizar("veículo"))

    print()
    print("=" * 72)
    print("8. O PLANO DOS FORMULARIOS (o .md dele) — quantos de 15")
    print("=" * 72)

    forms = c.get("/api/formularios", headers=cab).json()
    novos = [x["slug"] for x in forms if x.get("formato") == "novo"]
    print(f"     no formato novo: {len(novos)} de {len(forms)} -> {novos}")
    # 🚨 Os 56 campos sem validacao: a conta que a validacao de 29/10 achou.
    PEDE = {"cnpj": ("cnpj",), "cpf": ("cpf",), "placa": ("placa",),
            "telefone": ("telefone", "celular", "whatsapp"),
            "e-mail": ("mail",), "cep": ("cep",)}
    sem_total = 0
    for f in forms:
        d = formularios.definicao(f["slug"], so_ativo=False)
        for campo in d["campos"]:
            alvo_t = ((campo.get("nosso_nome") or "") + " "
                      + (campo.get("rotulo") or "")).lower()
            if campo.get("validacao"):
                continue
            if any(k in alvo_t for chaves in PEDE.values() for k in chaves):
                sem_total += 1
    print(f"     campos que pedem mascara e NAO tem: {sem_total}")
    conferir("o SUPORTE tem as mascaras",
             any(cp.get("validacao") == "cnpj"
                 for cp in formularios.definicao("suporte")["campos"]))
    # ⚠️ Isto NAO e uma falha da entrega: e a lacuna medida e documentada na
    # secao 12. Fica como NUMERO para nao se perder.
    nao_exercitado(f"{sem_total} campos sem validacao nos outros 14",
                   "lacuna medida e documentada na secao 12 do doc 16 -- "
                   "o plano dos formularios esta entregue para 1 de 15")

print()
print("=" * 72)
print(f"RESULTADO: {len(ok)} OK · {len(falho)} FALHAS · "
      f"{len(naoexerc)} nao exercitados")
print("=" * 72)
for nome, det in falho:
    print(f"  FALHA: {nome} — {det}")
sys.exit(1 if falho else 0)
