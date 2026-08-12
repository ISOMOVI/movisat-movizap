"""Mede o vínculo por NOME dos contatos vindos do Bitrix, e separa em três.

O cruzamento de 11/08 ligou contato do Bitrix a cliente do Harmonit por duas
regras, e a segunda é a que assusta:

  1. `via_nome`  -- o núcleo normalizado do nome da empresa BATE com o nome (ou
     nome fantasia) de um cliente ativo. Casamento direto.
  2. `grupo_alvo` -- **propagação pelo grupo do Bitrix**: se QUALQUER contato da
     mesma empresa Bitrix casou por nome, TODOS os contatos daquele grupo
     herdaram o mesmo cliente. Aqui um contato cujo nome não tem nada a ver
     pode ter entrado de carona.

🚨 SÓ LÊ. Nada é alterado sem `--eliminar`, e mesmo aí só a faixa "nada a ver".

Uso:  ./venv/bin/python scripts/auditar_vinculo_por_nome.py
      ./venv/bin/python scripts/auditar_vinculo_por_nome.py --eliminar
"""
import re
import sys
import unicodedata
from collections import Counter

sys.path.insert(0, "/home/claude/movizap_painel")

from movizap import banco  # noqa: E402

# As mesmas expressões do `01_extrair_clientes_ativos.py`: medir com régua
# diferente da que criou o vínculo daria número que não quer dizer nada.
MARCAS = re.compile(
    r"\b(LTDA|ME|EPP|EIRELI|S\s*/?\s*A|SA|MEI|CIA|COMPANHIA|"
    r"COMERCIO|COMERCIAL|INDUSTRIA|SERVICOS|TRANSPORTES?|LOGISTICA)\b")
RUIDO = re.compile(r"\b(DE|DA|DO|DAS|DOS|E|EM|A|O)\b")


def nucleo(nome: str) -> str:
    s = "".join(c for c in unicodedata.normalize("NFD", nome or "")
                if unicodedata.category(c) != "Mn")
    s = RUIDO.sub(" ", MARCAS.sub(" ", s.upper()))
    return " ".join(re.sub(r"[^A-Z0-9 ]", " ", s).split())


def parecenca(a: str, b: str) -> float:
    """Fração de palavras em comum, sobre o menor dos dois.

    ⚠️ Sobre o MENOR de propósito: 'WESO' dentro de 'WESO TRANSPORTES E
    LOGISTICA DO BRASIL' é o mesmo negócio, e dividir pelo maior daria 0,25 e
    jogaria um acerto bom na faixa duvidosa.
    """
    pa, pb = set(a.split()), set(b.split())
    if not pa or not pb:
        return 0.0
    return len(pa & pb) / min(len(pa), len(pb))


def main() -> None:
    eliminar = "--eliminar" in sys.argv
    banco.abrir()

    linhas = banco.varios(
        """SELECT ct.id, ct.nome AS contato_nome, ct.bitrix_id,
                  cl.id AS cliente_id, cl.nome AS cliente_nome,
                  cl.nome_fantasia, cl.documento,
                  b.empresa_nome, b.empresa_id_externo,
                  (SELECT count(*) FROM contato_telefone t
                    WHERE t.contato_id = ct.id) AS fones,
                  EXISTS (SELECT 1 FROM conversa c
                           JOIN contato_telefone t2 ON t2.contato_id = ct.id
                          WHERE c.telefone_e164 = t2.e164) AS tem_conversa
             FROM contato ct
             JOIN cliente cl ON cl.id = ct.cliente_id
             LEFT JOIN bitrix_contato b
                    ON b.id_externo = split_part(ct.bitrix_id, ':', 1)
            WHERE ct.origem = 'bitrix' AND ct.cliente_id IS NOT NULL""")

    # Quais clientes têm documento? Documento é chave DURA -- esses vínculos
    # não dependem do nome e ficam fora desta auditoria.
    exato, quase, nada, sem_dado = [], [], [], []
    for r in linhas:
        alvo = nucleo(r["empresa_nome"])
        candidatos = [nucleo(r["cliente_nome"]), nucleo(r["nome_fantasia"])]
        candidatos = [c for c in candidatos if c]
        if not alvo or not candidatos:
            sem_dado.append(r)
            continue
        if alvo in candidatos:
            exato.append(r)
            continue
        melhor = max(parecenca(alvo, c) for c in candidatos)
        r["_parecenca"] = melhor
        (quase if melhor >= 0.5 else nada).append(r)

    total = len(linhas)
    print(f"contatos do Bitrix ligados a cliente: {total}\n")
    for rotulo, faixa in (("NOME IGUAL      ", exato),
                          ("QUASE PARECIDO  ", quase),
                          ("NADA A VER      ", nada),
                          ("sem nome de um dos lados", sem_dado)):
        pct = 100 * len(faixa) / total if total else 0
        print(f"  {rotulo} {len(faixa):5}  ({pct:5.1f}%)")

    print("\n--- NADA A VER: exemplos (contato -> cliente ligado) ---")
    for r in nada[:15]:
        print(f"  {r['empresa_nome'][:38]:38} -> {r['cliente_nome'][:38]:38} "
              f"| {r['fones']} fone(s)"
              f"{' | JÁ TEM CONVERSA' if r['tem_conversa'] else ''}")

    print("\n--- QUASE PARECIDO: exemplos ---")
    for r in sorted(quase, key=lambda x: x["_parecenca"])[:10]:
        print(f"  {r['_parecenca']:.2f}  {r['empresa_nome'][:34]:34} -> "
              f"{r['cliente_nome'][:34]}")

    com_conversa = sum(1 for r in nada if r["tem_conversa"])
    fones = sum(r["fones"] for r in nada)
    grupos = Counter(r["empresa_id_externo"] for r in nada)
    print(f"\nSe eliminar a faixa NADA A VER:")
    print(f"  contatos removidos    : {len(nada)}")
    print(f"  telefones que vão junto: {fones}")
    print(f"  🚨 desses, JÁ TÊM CONVERSA: {com_conversa}")
    print(f"  grupos Bitrix envolvidos: {len(grupos)}")

    alcance_antes = banco.um(
        """SELECT count(DISTINCT ct.cliente_id) n FROM contato_telefone t
             JOIN contato ct ON ct.id = t.contato_id
            WHERE t.tem_whatsapp IS TRUE AND ct.cliente_id IS NOT NULL""")["n"]
    print(f"  alcance por WhatsApp hoje: {alcance_antes} clientes")

    if not eliminar:
        print("\n(leitura) nada foi alterado. Use --eliminar para remover a "
              "faixa NADA A VER.")
        banco.fechar()
        return

    if not nada:
        print("\nnada a eliminar.")
        banco.fechar()
        return

    ids = [r["id"] for r in nada]

    # 🚨 `conversa.contato_id` REFERENCIA `contato` SEM CASCATA. Apagar direto
    # levantaria ForeignKeyViolation se alguma conversa estiver apontando --
    # e apagar em cascata seria pior, porque levaria a CONVERSA junto. O certo
    # é desfazer o vínculo: a conversa volta a ser "não identificado", que é a
    # verdade, já que o vínculo estava errado.
    soltas = banco.um(
        """UPDATE conversa SET contato_id = NULL, atualizada_em = now()
            WHERE contato_id = ANY(%s) RETURNING id""", (ids,))
    if soltas:
        print(f"\nconversa(s) desvinculada(s) antes de apagar: voltam a "
              f"'não identificado'")

    banco.executar("DELETE FROM contato WHERE id = ANY(%s)", (ids,))
    # 🚨 A prova é RELER, não o "delete deu certo".
    sobrou = banco.um("SELECT count(*) n FROM contato WHERE id = ANY(%s)",
                      (ids,))["n"]
    depois = banco.um(
        """SELECT count(DISTINCT ct.cliente_id) n FROM contato_telefone t
             JOIN contato ct ON ct.id = t.contato_id
            WHERE t.tem_whatsapp IS TRUE AND ct.cliente_id IS NOT NULL""")["n"]
    print(f"\nremovidos: {len(ids)}  ·  sobrou por engano: {sobrou}")
    print(f"alcance por WhatsApp: {alcance_antes} -> {depois} clientes")
    banco.fechar()


if __name__ == "__main__":
    main()
