"""Tira a chave do Evolution dos payloads já gravados.

🚨 Achado em 07/08, na conferência do primeiro payload real: o Evolution manda
a própria `apikey` dentro do corpo, e o `webhook_evento` guardava o corpo
inteiro. O código já não grava mais (`webhook._sem_segredo`); este script
cuida do que entrou antes.

⚠️ NÃO apaga evento nenhum e não mexe em mais nada do payload: troca o valor
de `apikey` pelo marcador, com `jsonb_set`. Tudo que a conferência de formato
usa continua lá.

Uso:  PYTHONPATH=. ./venv/bin/python scripts/limpar_apikey_webhook.py [--aplicar]
"""
import argparse
import sys

from movizap import banco, webhook


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--aplicar", action="store_true")
    args = parser.parse_args()

    banco.abrir()
    antes = banco.um(
        "SELECT COUNT(*) AS n FROM webhook_evento "
        "WHERE payload ? 'apikey' AND payload->>'apikey' <> %s", (webhook.MARCADOR,))
    print(f"payloads com a chave guardada: {antes['n']}")

    if not antes["n"]:
        print("nada a fazer.")
        return 0

    if not args.aplicar:
        print("(simulação -- rode com --aplicar)")
        return 0

    mexidos = banco.executar(
        "UPDATE webhook_evento SET payload = jsonb_set(payload, '{apikey}', %s::jsonb) "
        "WHERE payload ? 'apikey' AND payload->>'apikey' <> %s",
        (f'"{webhook.MARCADOR}"', webhook.MARCADOR))
    print(f"linhas atualizadas: {mexidos}")

    # A única prova é reler o estado.
    depois = banco.um(
        "SELECT COUNT(*) AS n FROM webhook_evento "
        "WHERE payload ? 'apikey' AND payload->>'apikey' <> %s", (webhook.MARCADOR,))
    print(f"payloads ainda com a chave: {depois['n']} (esperado 0)")

    total = banco.um("SELECT COUNT(*) AS n FROM webhook_evento")
    print(f"eventos na tabela: {total['n']} (nenhum foi apagado)")
    return 0 if depois["n"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
