#!/usr/bin/env python3
"""Copia a chave do modelo do `.env` do MoviChat para o do MoviZap.

🚨 O VALOR NUNCA APARECE. Nem em `argv`, nem na saída, nem em log. Este script
existe exatamente por isso: `grep`/`cut`/`echo` com o segredo põem o valor em
`argv`, e o `auditd` grava `argv` -- foi assim que, em 12/08, o comando que
procurava o segredo nos logs escreveu o segredo num log. Ele é lido e escrito
DENTRO do processo. Mesma razão de `scripts/auditar_segredo_em_log.py`.

Por que copiar em vez de gerar chave nova: `docs/04_Contrato_IA.md` decide que
*"a montagem usa a chave atual; a chave própria do MoviZap entra depois -- é
uma linha no `.env`, sem tocar em código"*. Este script é essa linha.

⚠️ ENQUANTO A CHAVE FOR COMPARTILHADA, O CUSTO É COMPARTILHADO. Trocar pela
chave própria do MoviZap é editar `MOVIZAP_DEEPSEEK_API_KEY` no `.env` e
reiniciar -- nenhum código muda.

Uso:  ./venv/bin/python scripts/copiar_chave_llm.py [--forcar]
"""
import sys
from pathlib import Path

ORIGEM = Path("/home/claude/IA_agente_Movichat/.env")
DESTINO = Path("/home/claude/movizap_painel/.env")

# De qual chave da origem sai qual chave do destino. O prefixo `MOVIZAP_` é o
# que impede uma variável de ambiente do MoviChat de alimentar este painel sem
# ninguém pedir.
DE_PARA = {
    "DEEPSEEK_API_KEY": "MOVIZAP_DEEPSEEK_API_KEY",
    "GROQ_API_KEY": "MOVIZAP_GROQ_API_KEY",
}


def ler(arquivo: Path) -> dict[str, str]:
    valores: dict[str, str] = {}
    if not arquivo.exists():
        return valores
    for linha in arquivo.read_text(encoding="utf-8").splitlines():
        linha = linha.strip()
        if not linha or linha.startswith("#") or "=" not in linha:
            continue
        chave, _, valor = linha.partition("=")
        valores[chave.strip()] = valor.strip().strip('"').strip("'")
    return valores


def main() -> int:
    forcar = "--forcar" in sys.argv

    if not ORIGEM.exists():
        print(f"ERRO: {ORIGEM} não existe.")
        return 1
    origem = ler(ORIGEM)
    destino_txt = DESTINO.read_text(encoding="utf-8") if DESTINO.exists() else ""
    destino = ler(DESTINO)

    novas: list[str] = []
    for de, para in DE_PARA.items():
        valor = origem.get(de, "")
        if not valor:
            print(f"  {de}: ausente na origem, pulando")
            continue
        if destino.get(para) and not forcar:
            # ⚠️ Não sobrescreve: se o MoviZap já tem chave PRÓPRIA, copiar a
            # do MoviChat por cima desfaria em silêncio a separação de custo.
            print(f"  {para}: já existe no destino, mantido (--forcar troca)")
            continue
        novas.append(f"{para}={valor}")
        print(f"  {para}: será gravada ({len(valor)} caracteres)")

    if not novas:
        print("nada a fazer.")
        return 0

    # Monta o texto novo em memória e confere ANTES de gravar (regra 8 da
    # abertura do Proximos_Passos: validar antes, nunca depois).
    cabecalho = ("\n# ---- IA (passo 8, 2026-08-26) ----\n"
                 "# Copiadas do .env do MoviChat por scripts/copiar_chave_llm.py.\n"
                 "# Trocar pela chave PRÓPRIA do MoviZap é editar aqui e reiniciar.\n")
    candidato = destino_txt.rstrip("\n") + "\n" + cabecalho + "\n".join(novas) + "\n"

    conferencia = ler_texto(candidato)
    for de, para in DE_PARA.items():
        if para in [n.split("=", 1)[0] for n in novas]:
            if conferencia.get(para) != origem.get(de):
                print(f"ERRO: {para} não sobreviveu à montagem. Nada foi gravado.")
                return 1

    DESTINO.write_text(candidato, encoding="utf-8")
    DESTINO.chmod(0o600)
    print(f"gravado em {DESTINO}. Reinicie: systemctl --user restart movizap")
    return 0


def ler_texto(texto: str) -> dict[str, str]:
    valores: dict[str, str] = {}
    for linha in texto.splitlines():
        linha = linha.strip()
        if not linha or linha.startswith("#") or "=" not in linha:
            continue
        chave, _, valor = linha.partition("=")
        valores[chave.strip()] = valor.strip().strip('"').strip("'")
    return valores


if __name__ == "__main__":
    raise SystemExit(main())
