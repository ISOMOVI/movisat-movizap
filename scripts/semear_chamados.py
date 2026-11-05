# -*- coding: utf-8 -*-
"""Cria o card de chamado das solicitacoes que ja existem sem OS.

🚨 POR PADRAO SO RELATA. `--aplicar` grava.
⚠️ Idempotente: `pipeline.criar` devolve o card que ja existe se a solicitacao
ja tiver um (indice unico `ux_pipeline_card_solicitacao`).
"""
import sys
sys.path.insert(0, "/home/claude/movizap_painel")
from movizap import banco, paineis, pipeline
banco.abrir()

aplicar = "--aplicar" in sys.argv
etapa = paineis._etapa_dos_chamados()
if not etapa:
    sys.exit("a etapa Chamados nao existe -- a migracao 092 nao rodou?")
print(f"etapa Chamados: id={etapa['id']} aba={etapa['aba_id']}")

linhas = banco.varios("""
    SELECT s.id, s.criada_em, f.slug, f.titulo, f.painel,
           s.valores->>'COMPANY_TITLE' AS empresa,
           s.valores->>'CONTACT_NAME' AS pessoa
      FROM formulario_solicitacao s
      JOIN formulario f ON f.id = s.formulario_id
     WHERE s.os_id IS NULL AND f.painel = 'operacao'
     ORDER BY s.id""")
print(f"solicitacoes sem OS no painel operacao: {len(linhas)}")
for r in linhas:
    quem = r["empresa"] or r["pessoa"] or "(sem nome)"
    ja = pipeline.da_solicitacao(r["id"])
    marca = "JA TEM CARD" if ja else ("CRIA" if aplicar else "criaria")
    print(f"  solicitacao {r['id']} | {r['slug']:10} | {str(r['criada_em'])[:16]} | {quem[:34]} -> {marca}")
    if aplicar and not ja:
        pipeline.criar(etapa["aba_id"], etapa["id"], solicitacao_id=r["id"])

print()
print("cards na etapa Chamados agora:", len(
    [c for c in pipeline.cards_da_aba(etapa["aba_id"]) if c["etapa_id"] == etapa["id"]]))
if not aplicar:
    print("NADA FOI GRAVADO. Use --aplicar.")
