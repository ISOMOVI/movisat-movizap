# -*- coding: utf-8 -*-
"""A guarda que impede a SUÍTE de deixar card de produção para trás (11/11).

🚨 **O DEFEITO, MEDIDO E CONFIRMADO DUAS VEZES.** Depois da migração 106, ler
um quadro passou a ter um **efeito de escrita**: `pipeline.semear_os` cria o
card das OS cuja situação foi reendereçada para outro painel. E esta suíte roda
**contra a base de produção**.

📏 O resultado: o painel Financeiro apareceu com **12 cards** quando a ponte só
tinha **2** OS naquela situação. Os outros **10** (17052, 17055, 17058, 17066,
17068, 17071, 17084, 17087, 17102, 17112) são OS **reais e antigas** — e
entraram porque `teste_definir_data_matriz_grava_e_rele` recua a data matriz
para **2026-10-20** para provar que gravar e reler funciona. Com a janela
aberta, o quadro lê muito mais OS, e o semeador grava o que vê.

⚠️ **Os testes da data matriz estão CERTOS:** eles devolvem a data no `finally`.
Quem não se desfazia era o **efeito colateral novo** — e nenhum deles podia
saber disso, porque o efeito não existia quando foram escritos.

## Por que a guarda é aqui, e não um "modo de teste" no código

🚨 Desligar o semeador quando a suíte roda seria **deixar de exercitar o
caminho que importa**: as travas de `teste_destino_do_card.py` provam que
semear não duplica, não ressuscita card finalizado e põe a OS no painel certo.
Com um `if TESTE: return`, todas elas passariam a medir nada.

Então o caminho continua rodando de verdade, e o que esta guarda faz é
**desfazer a escrita** quando o teste acaba — a régua de
*"prove em cópia antes da produção"* aplicada ao único lugar onde isso não era
possível.

⚠️ **Só os cards de OS** (`numero_os IS NOT NULL`) são desfeitos: é essa a
escrita que a leitura passou a causar. Card de solicitação nasce de um envio
que o próprio teste faz, e quem o cria já cuida dele.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from movizap import banco  # noqa: E402


def _ultimo_card() -> int:
    linha = banco.um(
        "SELECT coalesce(max(id), 0) AS ultimo FROM pipeline_card")
    return (linha or {}).get("ultimo") or 0


@pytest.fixture(autouse=True)
def nenhum_card_de_os_sobra_da_suite():
    """Desfaz os cards de OS que a leitura de um quadro semeou no teste.

    🚨 Pelo `id`, e não por uma lista de números: o teste pode recuar a data
    matriz e trazer OS que eu não teria como prever. O que se sabe é que
    qualquer `pipeline_card` com `id` acima do último de antes **nasceu
    durante este teste**.

    ⚠️ A guarda não pode derrubar a suíte: se o banco não estiver aberto (há
    testes que não tocam nele), ela simplesmente não faz nada.
    """
    try:
        banco.abrir()
        antes = _ultimo_card()
    except Exception:  # noqa: BLE001 -- ver o docstring
        yield
        return

    yield

    try:
        quantos = banco.executar(
            """DELETE FROM pipeline_card
                WHERE id > %s AND numero_os IS NOT NULL""", (antes,))
        if quantos:
            # ⚠️ Em `stderr`, para aparecer sem `-s`: resíduo que se limpa em
            # silêncio é resíduo que ninguém sabe que existiu.
            print(f"[conftest] {quantos} card(s) de OS semeado(s) pela leitura "
                  f"do quadro foram desfeitos", file=sys.stderr)
    except Exception:  # noqa: BLE001
        pass
