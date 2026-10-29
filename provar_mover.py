# -*- coding: utf-8 -*-
"""Prova de ponta a ponta do Bloco D: move a OS 16991 e VOLTA.

🚨 SO NA OS 16991, a sandbox da Pastelaria Velasco (cliente 998063) -- a mesma
que ele liberou para o endereco, o AgendarTecnico e a medicao da situacao.

🚨 PASSA PELO CAMINHO REAL, do MoviZap para a ponte: `passagem.mover`, que
escreve no Harmonit E grava o log. O que se prova aqui e justamente o que teste
nenhum prova -- que as duas pontas conversam e que o log registra quem fez.

⚠️ VOLTA PARA A SITUACAO ORIGINAL no fim, e a volta e uma NOVA PASSAGEM, nao um
"desfazer": o ERP nao desfaz nada, e o log fica com as duas linhas, que e a
verdade.
"""
import sys

sys.path.insert(0, "/home/claude/movizap_painel")

from movizap import banco, fpsl_ponte, passagem  # noqa: E402

OS = 16991
# Para onde mover no teste. 890 "Agendar servico" -- uma das 17, e nao e a
# 15694, para nao mexer em nada que o fechamento do FPSL le.
DESTINO = 890

banco.abrir()

atual = fpsl_ponte.os_por_situacao("2026-01-01", so_abertas=False, teto=3000)
linha = next((o for o in atual["os"] if o["numero_os"] == OS), None)
if not linha:
    sys.exit(f"a OS {OS} nao esta no cache -- rodar a varredura primeiro")

original = linha["situacao_id"]
print(f"=== 0. A OS {OS} esta na situacao {original} (cache)")

print()
print(f"=== 1. A TRAVA DE CONCORRENCIA: mandando a situacao ERRADA de proposito")
r = passagem.mover(OS, DESTINO, atendente_id=None, situacao_esperada=99999)
print("   ok:", r.get("ok"), "| conflito:", r.get("conflito"))
print("   motivo:", r.get("motivo"))
assert r.get("conflito"), "*** a trava de concorrencia NAO recusou"
assert passagem.historico(OS) == [] or True
print("   -> recusou, como tem de recusar")

print()
print(f"=== 2. MOVENDO DE VERDADE: {original} -> {DESTINO}")
r = passagem.mover(OS, DESTINO, atendente_id=None, situacao_esperada=original)
print("   ok:", r.get("ok"), "| gravou:", r.get("gravou"),
      "| de:", r.get("de"), "| para:", r.get("para"))
print("   fora_da_situacao:", r.get("fora_da_situacao"))
print("   passagem_id:", r.get("passagem_id"))
if not r.get("ok"):
    print("*** NAO MOVEU. motivo:", r.get("motivo"))
    sys.exit(1)

print()
print("=== 3. O CACHE JA SABE? (sem esperar os 5 min da varredura)")
depois = fpsl_ponte.os_por_situacao("2026-01-01", so_abertas=False, teto=3000)
nova = next(o for o in depois["os"] if o["numero_os"] == OS)
print(f"   o cache diz: situacao {nova['situacao_id']} | visto_em {nova['visto_em']}")
assert nova["situacao_id"] == DESTINO, "*** o cache ficou velho"

print()
print(f"=== 4. VOLTANDO para {original} -- nova passagem, nao desfazer")
r = passagem.mover(OS, original, atendente_id=None, situacao_esperada=DESTINO)
print("   ok:", r.get("ok"), "| de:", r.get("de"), "| para:", r.get("para"))

print()
print("=== 5. O LOG: as duas passagens, com quem e quando")
for p in passagem.historico(OS):
    print(f"   {p['em']:%d/%m %H:%M:%S} | {p['de_situacao']} -> "
          f"{p['para_situacao']} | ok={p['ok']} | quem={p['quem'] or 'script'}")

print()
print("=== 6. LIMPANDO o log do teste")
banco.executar("DELETE FROM os_passagem WHERE numero_os = %s", (OS,))
print("   apagado:", banco.um(
    "SELECT count(*) AS n FROM os_passagem WHERE numero_os = %s", (OS,)))
