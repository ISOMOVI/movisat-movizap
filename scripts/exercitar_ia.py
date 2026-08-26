#!/usr/bin/env python3
"""Prova que o motor da IA responde de verdade — sem tocar em conversa nenhuma.

🚨 FONTE NÃO É COMPORTAMENTO. `py_compile` aprova comentário, e a suíte roda
contra mock. Este script é o que exercita o caminho INTEIRO: chave do `.env`
-> `httpx` -> DeepSeek -> `tool_calls` -> a nossa ferramenta -> texto final.

Ele NÃO usa `movizap.ia.responder`: não lê conversa, não escreve mensagem, não
transfere e não publica versão de prompt nenhuma. Monta um contexto de mentira
em memória e chama o gateway direto. Custa alguns centavos de dólar.

Uso:  ./venv/bin/python scripts/exercitar_ia.py
"""
import sys

sys.path.insert(0, "/home/claude/movizap_painel")

from movizap import banco, config, ia            # noqa: E402
from movizap.llm import Params, obter            # noqa: E402

config.silenciar_clientes_http()

# Um contexto que não existe no banco: contato conhecido, empresa conhecida.
CTX = {"id": 0, "contato_id": 1, "cliente_id": 1,
       "contato_nome": "Fulano da Pastelaria", "relacao": "cliente",
       "cliente_nome": "Pastelaria Velasco", "nome_fantasia": "Velasco",
       "cliente_ativo": True, "nome_whatsapp": None}

SISTEMA_DE_ENSAIO = """\
Você atende no WhatsApp da Movisat, que trabalha com rastreamento de frotas.
Fale em português do Brasil, por você, com frases curtas.

# TIMES DISPONÍVEIS
- Suporte: problema técnico com rastreador
- Financeiro: boleto, fatura, pagamento
- Geral: quando não souber para onde mandar
"""

CASOS = [
    ("olá, tudo bem?", "conversa simples: NÃO deve chamar ferramenta"),
    ("quero saber onde está o meu caminhão placa ABC1D23 agora",
     "pede posição -- ela NÃO consegue consultar: tem de transferir"),
    ("qual o valor da minha fatura desse mês?",
     "pede fatura -- tem de transferir, sem falar de sistema"),
    ("quem sou eu no cadastro de vocês?",
     "deve chamar identificar_contato"),
]


def main() -> int:
    banco.abrir()
    g = obter()
    e = g.estado()
    print(f"provedor={e['provedor']} modelo={e['modelo']} chave={e['chave']}")
    if not e["disponivel"]:
        print("motor indisponível — nada a exercitar.")
        return 1

    total = 0
    reprovou = 0
    for pergunta, esperado in CASOS:
        acoes: list = []
        mensagens = [
            {"role": "system",
             "content": SISTEMA_DE_ENSAIO + "\n" + ia.CONDUTA + "\n" +
                        "VOCÊ NÃO CONSEGUE CONSULTAR, DE JEITO NENHUM:\n" +
                        "\n".join(f"- {s}" for s in ia.SEM_ACESSO) +
                        "\nQuando pedirem isso, transfira. Não diga que não "
                        "encontrou nem que não tem acesso."},
            {"role": "user", "content": pergunta},
        ]
        # ⚠️ `ensaio=True`: as ferramentas de escrita viram registro em
        # `acoes` e não tocam no banco. `CTX["id"] = 0` não existe.
        r = g.conversar(mensagens, ia.FERRAMENTAS,
                        ia._executor(CTX, True, acoes), Params())
        total += r["tokens"]
        print("\n" + "=" * 70)
        print(f"PERGUNTA : {pergunta}")
        print(f"ESPERADO : {esperado}")
        print(f"FERRAMENTAS: {r['ferramentas_usadas'] or 'nenhuma'}")
        print(f"AÇÕES    : {acoes or 'nenhuma'}")
        print(f"RESPOSTA : {r['texto']}")
        if not r["texto"]:
            print("🚨 REPROVOU: resposta vazia")
            reprovou += 1
        # A regra que mais custou caro no MoviChat: falar do mecanismo.
        for proibida in ("sistema", "não consegui", "erro", "api", "cadastro",
                         "consulta", "base de dados"):
            if proibida in r["texto"].lower():
                print(f"⚠️  a resposta contém {proibida!r} — conferir se expõe mecanismo")

    print("\n" + "=" * 70)
    print(f"{len(CASOS)} casos, {total} tokens, {reprovou} reprovações")
    return 1 if reprovou else 0


if __name__ == "__main__":
    raise SystemExit(main())
