# -*- coding: utf-8 -*-
"""Aponta o FPSL_BASE_URL do MoviZap para a aplicacao, e nao para o nginx.

Medido em 21/10: o `fpsl-weso.service` escuta em 127.0.0.1:8004; a porta 8005
e um `server` do nginx (`fpsl.conf:116`) que escuta em 0.0.0.0 e repassa para
a 8004. A ponte e chamada entre dois servicos da mesma maquina -- nao precisa
atravessar um servidor web que escuta em todas as interfaces.

Troca so a linha do FPSL_BASE_URL, e nao imprime nenhum outro valor do .env.
"""
from pathlib import Path

ENV = Path("/home/claude/movizap_painel/.env")
CHAVE = "FPSL_BASE_URL"
NOVO = "http://127.0.0.1:8004"

linhas = ENV.read_text(encoding="utf-8").splitlines()
saida, antes = [], None
for l in linhas:
    if l.strip().startswith(f"{CHAVE}="):
        antes = l.partition("=")[2].strip()
        saida.append(f"{CHAVE}={NOVO}")
    else:
        saida.append(l)

if antes is None:
    raise SystemExit(f"{CHAVE} nao esta no .env -- nao invento linha nova aqui")
if antes == NOVO:
    print(f"{CHAVE} ja aponta para a aplicacao -- nada a fazer")
    raise SystemExit(0)

ENV.write_text("\n".join(saida) + "\n", encoding="utf-8")
print(f"{CHAVE}: {antes} -> {NOVO}")
