"""Preenche cidade e UF da ficha do técnico a partir do nome do contato.

🔵 Pedido dele em 04/11, à proposta P4: **"4 preencha e mantenha o nome"**.

🚨 O NOME NÃO É TOCADO. Nem aqui nem em lugar nenhum: `contato.nome` fica como
está, com o `| Cidade - UF` no fim. Ele decidiu manter -- e é esse pedaço que
distingue homônimos na conversa.

🚨 ISTO É DERIVAÇÃO, NÃO CADASTRO CONFERIDO, e o script diz isso de três
maneiras: a ficha nasce **candidata**, a `observacao` registra de onde o dado
veio, e **nada já preenchido é sobrescrito**. Cadastro preenchido por
adivinhação é pior que vazio; cadastro derivado e marcado como derivado é um
ponto de partida que alguém confere.

⚠️ SÓ CIDADE E UF. O resto do endereço (rua, número, bairro, CEP) continua
vazio, e é ele que a calculadora de KM precisa além da cidade -- credenciar
continua exigindo rua e cidade, como antes.

Uso:
    ./venv/bin/python scripts/cidade_do_nome_do_tecnico.py             # só relata
    ./venv/bin/python scripts/cidade_do_nome_do_tecnico.py --um        # faz 1
    ./venv/bin/python scripts/cidade_do_nome_do_tecnico.py --aplicar   # faz o lote
"""
import sys

sys.path.insert(0, "/home/claude/movizap_painel")

from movizap import banco  # noqa: E402

UFS = {"AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA", "MT", "MS",
       "MG", "PA", "PB", "PR", "PE", "PI", "RJ", "RN", "RS", "RO", "RR", "SC",
       "SP", "SE", "TO"}

PROCEDENCIA = ("Cidade e UF derivadas do nome do cadastro do Harmonit "
               "(04/11). Confira antes de credenciar.")


def partir(nome: str):
    """`"Ademir | Marília - SP"` -> `("Marília", "SP")`, ou `None`.

    ⚠️ DOIS FORMATOS, MEDIDOS: 286 dos 287 terminam em `" - UF"` e o resto usa
    barra (*"TÉC. Rogerio Marques | Araxá/MG"*). Qualquer outra coisa devolve
    `None` -- é melhor deixar 16 fichas sem cidade do que gravar 16 palpites.

    🚨 A UF TEM DE ESTAR NA LISTA. Sem isso, "Rua 7 - de Setembro" viraria UF
    `de`, e `uf` é `varchar(2)`: gravaria lixo com cara de dado.
    """
    if " | " not in (nome or ""):
        return None
    cauda = nome.rsplit(" | ", 1)[1].strip()

    for separador in (" - ", "/"):
        if separador in cauda:
            cidade, _, uf = cauda.rpartition(separador)
            cidade, uf = cidade.strip(), uf.strip().upper()
            if uf in UFS and cidade:
                return cidade[:50], uf
    return None


def main() -> None:
    aplicar = "--aplicar" in sys.argv
    so_um = "--um" in sys.argv

    banco.abrir()
    tecnicos = banco.varios(
        """SELECT c.id, c.nome, f.contato_id IS NOT NULL AS tem_ficha,
                  f.cidade, f.uf, f.observacao
             FROM contato c
             LEFT JOIN tecnico_ficha f ON f.contato_id = c.id
            WHERE c.relacao = 'tecnico'
            ORDER BY c.id""")

    casaram, sem_padrao, ja_tinham = [], [], []
    for t in tecnicos:
        achado = partir(t["nome"])
        if not achado:
            sem_padrao.append(t)
            continue
        # ⚠️ NÃO SOBRESCREVE o que alguém já preencheu, nem o que uma rodada
        # anterior deste script preencheu: rodar duas vezes não muda nada.
        if t["cidade"] or t["uf"]:
            ja_tinham.append(t)
            continue
        casaram.append((t, achado))

    print(f"técnicos                : {len(tecnicos)}")
    print(f"com cidade/UF no nome   : {len(casaram) + len(ja_tinham)}")
    print(f"  a preencher           : {len(casaram)}")
    print(f"  já tinham (intactos)  : {len(ja_tinham)}")
    print(f"sem o padrão no nome    : {len(sem_padrao)}")
    for t in sem_padrao[:5]:
        print(f"    - {t['id']} {t['nome']!r}")
    if len(sem_padrao) > 5:
        print(f"    ... e outros {len(sem_padrao) - 5}")

    if not casaram:
        print("\nnada a fazer.")
        return

    print("\namostra do que seria gravado:")
    for t, (cidade, uf) in casaram[:5]:
        print(f"    {t['id']:>7}  {cidade} - {uf}   <- {t['nome']!r}")

    if not (aplicar or so_um):
        print("\nnada foi gravado. Use --um para fazer o primeiro, "
              "ou --aplicar para o lote.")
        return

    alvo = casaram[:1] if so_um else casaram
    print(f"\ngravando {len(alvo)}...")
    with banco.cursor() as cur:
        for t, (cidade, uf) in alvo:
            if t["tem_ficha"]:
                # A observação só entra se não houver uma: o que alguém
                # escreveu vale mais que a minha nota de procedência.
                cur.execute(
                    """UPDATE tecnico_ficha
                          SET cidade = %s, uf = %s,
                              observacao = COALESCE(NULLIF(observacao, ''), %s),
                              atualizado_em = now()
                        WHERE contato_id = %s""",
                    (cidade, uf, PROCEDENCIA, t["id"]))
            else:
                cur.execute(
                    """INSERT INTO tecnico_ficha (contato_id, cidade, uf, observacao)
                       VALUES (%s, %s, %s, %s)
                       ON CONFLICT (contato_id) DO NOTHING""",
                    (t["id"], cidade, uf, PROCEDENCIA))

    # 🚨 RELÊ O ESTADO, não confia no que acabou de mandar.
    conferido = banco.um(
        """SELECT count(*) AS n FROM tecnico_ficha
            WHERE cidade IS NOT NULL AND uf IS NOT NULL""")["n"]
    estados = banco.varios(
        "SELECT estado, count(*) AS n FROM tecnico_ficha GROUP BY estado")
    print(f"fichas com cidade e UF agora: {conferido}")
    print("estados:", {e["estado"]: e["n"] for e in estados})

    nomes_mexidos = banco.um(
        """SELECT count(*) AS n FROM contato
            WHERE relacao = 'tecnico' AND nome NOT LIKE %s""", ("% | %",))["n"]
    print(f"nomes de técnico SEM o ' | ' (eram 16): {nomes_mexidos}"
          "  <- prova que o nome não foi tocado")


if __name__ == "__main__":
    main()
