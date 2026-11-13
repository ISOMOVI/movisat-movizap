#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""O ressarcimento vira card de chamado na Operação.

🔵 11/11, dele: *"ressarcimento gera card de chamado com a OBS dos dados do
termo"*. Em 12/11, sobre a fonte: *"os dados devem vir da OS, o que o FPSL
criar na OS é problema dele. Aqui seguimos pelo caminho de que o card-OS nasce
por conta da OS. No caso do ressarcimento, a OS nasce no financeiro, então um
card normal como chamado, vira com os mesmos dados da descrição da OS no corpo
do card"*. E sobre o atraso: *"pode seguir a partir do card-OS, delay de 2min
é suficiente"*.

===========================================================================
COMO ELE SABE QUE É RESSARCIMENTO, SEM CUSTAR NADA
===========================================================================
📏 Medido em 12/11, nas 19 OS da situação 15746: o campo `problema` separa as
duas famílias sem erro --

    problema 7524  -> "RESSARCIMENTO: placas: ... | O.S: ...."
    problema 11701 -> "FINANCEIRO — TERMO 8948 | placas: ... | itens: ..."

🚨 E `problema` JÁ VEM na leitura barata do painel (`os_por_situacao`), a
mesma que o quadro faz. Então a triagem não custa uma chamada sequer. A ficha
completa -- que é cara, ~15,5 s por leitura com o pool do Harmonit esgotado --
só é pedida para quem passou na triagem, que são 2 de 19.

⚠️ Procurar a palavra "RESSARCIMENTO" no texto seria mais frágil: texto muda,
id de problema é cadastro. O texto entra só como conferência, nunca como
critério.

===========================================================================
POR QUE NÃO PRECISA DE MARCA DE "JÁ EXAMINEI"
===========================================================================
O próprio card da Operação é a marca: se ele existe, esta rotina pula a OS e
nunca mais pede a ficha dela. 🚨 A conferência olha TAMBÉM o card já
finalizado -- senão um ressarcimento tratado e fechado renasceria a cada dois
minutos, que é o defeito que o semeador já teve em 11/11.

===========================================================================
O QUE ELE NÃO FAZ
===========================================================================
🚨 Não manda mensagem nenhuma, para ninguém. Cria card e escreve a observação
de origem. Quem fala com cliente é gente.
⚠️ Não mexe no Harmonit: só lê.
"""
import argparse
import logging
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from movizap import banco, fpsl_ponte  # noqa: E402

log = logging.getLogger("ressarcimento")

# 🔵 A situação em que a OS de ressarcimento nasce, decisão dele de 11/11.
SITUACAO_FINANCEIRO = 15746
# 📏 O id do problema, medido em 12/11 nas 19 OS da situação.
PROBLEMA_RESSARCIMENTO = 7524
# 🔵 *"delay de 2min é suficiente"*.
ESPERA_SEGUNDOS = 120
# ⚠️ Teto por rodada: cada ficha custa caro com o pool do Harmonit esgotado,
# e uma rodada que demora mais que o intervalo do cron empilha processo.
TETO_POR_RODADA = 5


def _aba_e_etapa_dos_chamados() -> tuple[int, int] | None:
    """A coluna `Chamados` da Operação -- onde nasce card que não é de OS.

    ⚠️ Lido do banco, não fixo no código: a etapa tem id 1 hoje, mas quem
    garante isso é a migração, não esta rotina.
    """
    linha = banco.um(
        """SELECT e.id AS etapa_id, e.aba_id
             FROM pipeline_etapa e
             JOIN painel_aba a ON a.id = e.aba_id
            WHERE a.codigo_tela = 'PNL_1.1' AND e.ativo
            ORDER BY e.ordem
            LIMIT 1""")
    if not linha:
        return None
    return linha["aba_id"], linha["etapa_id"]


def _ja_tem_card(aba_id: int, numero_os: int) -> bool:
    """🚨 Inclusive o FINALIZADO. O índice único só vale para `desfecho IS
    NULL`; sem esta conferência, um ressarcimento tratado renasceria a cada
    rodada."""
    return banco.um(
        """SELECT 1 FROM pipeline_card
            WHERE aba_id = %s AND numero_os = %s LIMIT 1""",
        (int(aba_id), int(numero_os))) is not None


def _card_do_financeiro(numero_os: int) -> dict | None:
    """O card-OS do Financeiro, que é de onde este card nasce.

    🔵 *"pode seguir a partir do card-OS"* -- sem ele, não há de onde seguir,
    e a rotina espera a próxima rodada em vez de inventar um começo.
    """
    return banco.um(
        """SELECT c.id, c.cliente_id, c.criado_em,
                  EXTRACT(EPOCH FROM (now() - c.criado_em)) AS idade
             FROM pipeline_card c
             JOIN painel_aba a ON a.id = c.aba_id
            WHERE a.codigo_tela = 'PNL_1.4' AND c.numero_os = %s
            ORDER BY c.id
            LIMIT 1""", (int(numero_os),))


def _texto_da_origem(numero_os: int, descricao: str) -> str:
    """A observação que explica de onde o card veio.

    ⚠️ Em linhas rotuladas e não em texto corrido: quem abrir o card seis
    meses depois precisa achar o número da OS sem ler parágrafo.
    """
    return (f"[ressarcimento] Card aberto a partir da O.S. {numero_os}, "
            f"que nasceu no Financeiro.\n{descricao}")


def rodar(aplicar: bool = False, desde_dias: int = 60) -> dict:
    import datetime
    desde = (datetime.date.today()
             - datetime.timedelta(days=int(desde_dias))).isoformat()

    destino = _aba_e_etapa_dos_chamados()
    if destino is None:
        log.error("nao achei a coluna de chamados da Operacao; nada a fazer")
        return {"erro": "sem coluna de chamados"}
    aba_chamados, etapa_chamados = destino

    resposta = fpsl_ponte.os_por_situacao(desde)
    lista = resposta.get("os") if isinstance(resposta, dict) else resposta
    lista = lista or []

    # A triagem barata: situação do Financeiro + problema de ressarcimento.
    candidatas = [o for o in lista
                  if o.get("situacao_id") == SITUACAO_FINANCEIRO
                  and o.get("problema") == PROBLEMA_RESSARCIMENTO]

    conta = {"vistas": len(lista), "ressarcimentos": len(candidatas),
             "ja_tinham_card": 0, "sem_card_no_financeiro": 0,
             "novas_demais": 0, "criados": 0, "falhas": 0}

    for o in candidatas:
        numero = o.get("numero_os")
        if not numero:
            continue
        if _ja_tem_card(aba_chamados, numero):
            conta["ja_tinham_card"] += 1
            continue

        financeiro = _card_do_financeiro(numero)
        if financeiro is None:
            # Ainda não semeado: o quadro do Financeiro é quem cria aquele
            # card, e ninguém o abriu desde que a OS nasceu.
            conta["sem_card_no_financeiro"] += 1
            continue
        if float(financeiro["idade"] or 0) < ESPERA_SEGUNDOS:
            conta["novas_demais"] += 1
            continue

        if conta["criados"] >= TETO_POR_RODADA:
            break

        try:
            ficha = fpsl_ponte.ficha_da_os(numero)
        except Exception:
            log.exception("OS %s: nao consegui ler a ficha", numero)
            conta["falhas"] += 1
            continue
        descricao = (ficha.get("descricao") or "").strip()
        if not descricao:
            # ⚠️ Card sem a descrição seria um card que não explica nada --
            # e o pedido dele é exatamente a descrição no corpo. Espera.
            log.warning("OS %s: ficha sem descricao; deixo para a proxima",
                        numero)
            conta["falhas"] += 1
            continue

        if not aplicar:
            log.info("[ENSAIO] criaria card para a OS %s: %s",
                     numero, descricao[:90])
            conta["criados"] += 1
            continue

        try:
            with banco.cursor() as cur:
                cur.execute(
                    """INSERT INTO pipeline_card
                           (aba_id, etapa_id, numero_os, cliente_id, criado_por)
                       VALUES (%s, %s, %s, %s, NULL)
                       ON CONFLICT DO NOTHING
                       RETURNING id""",
                    (aba_chamados, etapa_chamados, int(numero),
                     financeiro.get("cliente_id") or o.get("cliente_id")))
                linha = cur.fetchone()
                if not linha:
                    # O índice único pegou: outra rodada criou primeiro.
                    conta["ja_tinham_card"] += 1
                    continue
                cur.execute(
                    """INSERT INTO os_observacao (numero_os, texto, atendente_id)
                       VALUES (%s, %s, NULL)""",
                    (int(numero), _texto_da_origem(numero, descricao)))
                cur.connection.commit()
            conta["criados"] += 1
            log.info("OS %s: card de ressarcimento criado na Operacao", numero)
        except Exception:
            log.exception("OS %s: falhei ao criar o card", numero)
            conta["falhas"] += 1

    return conta


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--aplicar", action="store_true",
                   help="cria de verdade; sem isto e so ensaio")
    p.add_argument("--dias", type=int, default=60)
    args = p.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s")

    banco.abrir()
    try:
        conta = rodar(aplicar=args.aplicar, desde_dias=args.dias)
    finally:
        banco.fechar()
    log.info("fim: %s", conta)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
