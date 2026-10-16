"""docs/ligacoes.md: a seção do vigia (Bloco 2, 15/10/2026).

Idempotente, com âncora conferida.
Uso: ./venv/bin/python scripts/patch_docs_vigia.py [--conferir]
"""
import sys
from pathlib import Path

ALVO = Path(__file__).resolve().parent.parent / "docs/ligacoes.md"
SO_CONFERIR = "--conferir" in sys.argv

# A promessa antiga ficou desatualizada: o gancho da sessão não é mais o único
# gatilho.
ALERTA_DE = """- **Alerta:** o gancho `SessionStart` do Claude Code roda
  `scripts/agentes_mudos.py`. Ele fica mudo quando está tudo em dia e acusa:
  PC sem contato há mais de 24 h, PC vivo com erro ou aviso, e certificado
  vencendo em menos de 30 dias."""
ALERTA_PARA = """- **Alerta:** `scripts/agentes_mudos.py` fica mudo quando está tudo em dia e
  acusa: PC sem contato há mais de 24 h, PC vivo com erro ou aviso, e
  certificado vencendo em menos de 30 dias. **Dois gatilhos** (desde 15/10): o
  gancho `SessionStart` do Claude Code, que imprime na sessão, e o **cron da
  VPS às 08:10 e 18:10** com `--avisar-whatsapp`, que manda uma mensagem.
  Detalhe na seção "O vigia"."""

SECAO = """
## O vigia (Bloco 2, 15/10/2026)

🔵 *"Rotina da VPS verifica se os envios estão sendo feito corretamente e mesmo
que não tenha arquivos novos para enviar, um ping no servidor valida o usuario
e a conexão"*.

O ping já existia e não mudou: é o `batimento`, que o agente dá a cada passada
mesmo sem nada para enviar. O que faltava era **alguém olhando** — até 15/10 o
único gatilho do `agentes_mudos.py` era o `SessionStart` da sessão do Claude,
ou seja: se eu não abrisse sessão, ninguém era avisado. Com um PC isso passava;
com oito, não.

```
cron da VPS (claude), 08:10 e 18:10
  └─ scripts/agentes_mudos.py --avisar-whatsapp
        PC sem contato há mais de 24 h  (agentes_mudos)
        PC vivo com erro ou aviso       (agentes_com_aviso)
        certificado vencendo em 30 dias (certs_vencendo)
        │
        ├─ imprime (vai para o log /home/claude/logs/movizap_ligacoes_vigia.log)
        └─ UMA mensagem para MOVIZAP_LIGACOES_AVISO_NUMERO, pelo Evolution
```

- **Horário:** 08:10 e 18:10, depois das passadas dos PCs (logon+5min de manhã
  e 17:30), para não acusar quem ainda ia falar.
- 🚨 **Fala direto com o Evolution**, não pela rota do painel: o vigia tem de
  funcionar inclusive com o painel fora do ar — que é justamente um dos motivos
  de um PC parecer mudo.
- 🚨 **Mudo quando está tudo em dia:** nenhuma linha impressa, nenhuma mensagem
  enviada, log vazio. Aviso que chega todo dia vira aviso que ninguém lê.
- **Se o envio falhar**, o alerta não se perde: ele já foi impresso (e vai para
  o log) antes da tentativa de mandar.
- `MOVIZAP_LIGACOES_AVISO_NUMERO` vazio no `.env` = só imprime. É o que mantém
  o gancho da sessão funcionando sem mandar mensagem para ninguém.
- ⚠️ **Por que não existe alerta de "ramal revogado sem substituto"** (eu havia
  proposto): a revogação acontece junto do alistamento do PC novo, na mesma
  transação, e fora disso só à mão — quando alguém sai da empresa. Avisar nesse
  caso seria cobrar a reinstalação de quem foi embora.

### Provado em 15/10

| O quê | Resultado |
|---|---|
| Tudo em dia, sem flag | silêncio total (é o gancho da sessão) |
| Tudo em dia, com `--avisar-whatsapp` | silêncio total, nada enviado |
| PC fingido mudo há 30 h | alerta impresso **e** mensagem entregue no número do `.env` |
| O estado forçado | devolvido ao valor exato (`finally`), conferido depois |
| A linha do cron, rodada literalmente | código 0, log vazio |
"""

texto = ALVO.read_text(encoding="utf-8")

if ALERTA_PARA in texto:
    print("já estava: nota do alerta")
elif ALERTA_DE not in texto:
    raise SystemExit("ÂNCORA NÃO ACHADA: nota do alerta")
else:
    texto = texto.replace(ALERTA_DE, ALERTA_PARA)
    print(f"{'conferido' if SO_CONFERIR else 'aplicado'}: nota do alerta")

if "## O vigia (Bloco 2" in texto:
    print("já estava: seção do vigia")
else:
    ancora = "## Achados do ensaio de 25/09 (antes de produção)"
    if ancora not in texto:
        raise SystemExit("ÂNCORA NÃO ACHADA: achados de 25/09")
    texto = texto.replace(ancora, SECAO.lstrip("\n") + "\n" + ancora)
    print(f"{'conferido' if SO_CONFERIR else 'aplicado'}: seção do vigia")

if not SO_CONFERIR:
    ALVO.write_text(texto, encoding="utf-8")
    print(f"gravado: {ALVO} ({len(texto.splitlines())} linhas)")
