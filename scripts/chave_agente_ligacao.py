"""Gera a chave do agente de ligações de um operador (Plano 5, 25/09).

Uso:
  ./venv/bin/python scripts/chave_agente_ligacao.py --atendente <id> --ramal <ramal> --config <arquivo>
      (recomendado) grava a chave num config.json PRONTO para o PC (0600).
      O `instalar.ps1` acha esse arquivo na pasta dele, absorve e apaga.
      A chave não aparece na tela de ninguém.

  ./venv/bin/python scripts/chave_agente_ligacao.py --atendente <id> --ramal <ramal>
      mostra a chave UMA VEZ, para colar no `instalar.ps1`.

O banco guarda só o hash. Gerar de novo revoga a anterior daquele ramal.
"""
import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from movizap import banco, ligacoes  # noqa: E402

URL = "https://movizap.movisat.com.br"  # rota antiga até o passo 2 (-Concluir)

p = argparse.ArgumentParser()
p.add_argument("--atendente", type=int, required=True)
p.add_argument("--ramal", required=True)
p.add_argument("--config", type=Path, help="grava um config.json pronto em vez de mostrar a chave")
a = p.parse_args()
banco.abrir()
nome = banco.um("SELECT nome FROM atendente WHERE id = %s", (a.atendente,))
chave = ligacoes.gerar_chave(a.atendente, a.ramal)
print(f"Ramal {a.ramal} -> {nome['nome'] if nome else a.atendente}")
if a.config:
    fd = os.open(a.config, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump({"url": URL, "chave": chave}, f)
    print(f"config.json gravado em {a.config} (a chave NÃO foi mostrada).")
else:
    print(f"CHAVE (aparece só agora): {chave}")
