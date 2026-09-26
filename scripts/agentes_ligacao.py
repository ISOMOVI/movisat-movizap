"""Os atendentes e os agentes de ligação deles -- SÓ LEITURA (Plano 5.2, 25/09).

🔵 *"o procedimento para que eu replique a Claudia e aos demais"*. É a consulta
das ferramentas do kit (`Desktop\\MoviZap-Ligacoes-Kit\\2-PC-DO-IAGO`):
  · achar o id do atendente pelo nome, ao preparar um PC;
  · a prova final de cada instalação -- o banco, não a tela.

Uso:
  ./venv/bin/python scripts/agentes_ligacao.py                 tabela de todos os ativos
  ./venv/bin/python scripts/agentes_ligacao.py --buscar Clau   só quem tem "Clau" no nome
  ./venv/bin/python scripts/agentes_ligacao.py --json          o mesmo, em JSON
Nada aqui é segredo: nem a chave nem o hash dela saem.
"""
import argparse
import json
import sys
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import logging  # noqa: E402
logging.disable(logging.CRITICAL)

from movizap import banco  # noqa: E402

p = argparse.ArgumentParser()
p.add_argument("--buscar", default="")
p.add_argument("--json", action="store_true")
a = p.parse_args()

banco.abrir()
linhas = banco.varios(
    """SELECT t.id, t.nome, t.ramal,
              g.id AS agente_id, g.ultima_versao AS versao, g.ultimo_contato_em AS contato,
              g.ultimo_ip AS ip, g.ultimo_pc AS pc, g.pendentes,
              g.cert_validade, (g.cert_sha256 IS NOT NULL) AS tem_cert,
              g.ultimo_erro AS erro, g.ultimo_aviso AS aviso
         FROM atendente t
         LEFT JOIN agente_ligacao g ON g.atendente_id = t.id AND g.revogado_em IS NULL
        WHERE t.ativo AND (t.login NOT LIKE 'zz%%' OR t.login LIKE 'zz_teste_kit%%')
        ORDER BY t.nome""")
if a.buscar:
    b = a.buscar.casefold()
    linhas = [l for l in linhas if b in l["nome"].casefold()]

br = ZoneInfo("America/Sao_Paulo")


def data(v, fmt="%d/%m %H:%M"):
    return v.astimezone(br).strftime(fmt) if v else ""


if a.json:
    print(json.dumps([{
        "id": l["id"], "nome": l["nome"], "ramal": l["ramal"], "agente_id": l["agente_id"],
        "versao": l["versao"], "contato": data(l["contato"], "%d/%m/%Y %H:%M"),
        "ip": l["ip"], "pc": l["pc"], "pendentes": l["pendentes"],
        "tem_cert": bool(l["tem_cert"]), "cert_validade": data(l["cert_validade"], "%d/%m/%Y"),
        "erro": l["erro"], "aviso": l["aviso"]} for l in linhas], ensure_ascii=False))
    sys.exit(0)

print(f"{'id':>6}  {'nome':<18} {'ramal':<6} {'agente':<7} {'versão':<6} {'último contato':<12} "
      f"{'IP':<16} {'PC':<16} {'pend':>4}  {'cert até':<10}  situação")
for l in linhas:
    if not l["agente_id"]:
        situacao = "sem agente"
    elif not l["contato"]:
        situacao = "chave gerada, nunca falou"
    elif not l["tem_cert"]:
        situacao = "passo 1 feito (falta o certificado)"
    elif not l["ip"]:
        situacao = "certificado emitido (falta o Concluir)"
    else:
        situacao = "OK"
    if l["erro"] or l["aviso"]:
        situacao += " | " + " | ".join(x for x in (l["erro"], l["aviso"]) if x)
    print(f"{l['id']:>6}  {l['nome'][:18]:<18} {l['ramal'] or '':<6} {l['agente_id'] or '':<7} "
          f"{l['versao'] or '':<6} {data(l['contato']):<12} {l['ip'] or '':<16} "
          f"{(l['pc'] or '')[:16]:<16} {l['pendentes'] if l['pendentes'] is not None else '':>4}  "
          f"{data(l['cert_validade'], '%d/%m/%Y'):<10}  {situacao}")
if not linhas:
    print("(ninguém encontrado)")
