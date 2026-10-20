"""Restaura a configuracao da distribuicao que um TESTE MEU apagou em 19/10.

O que aconteceu: o teste `test_a_tela_diz_painel_fechado_e_nao_offline`, que eu
escrevi hoje em `tests/teste_distribuicao.py`, chamou
`distribuicao.definir_config(True, a, b, 10)` com atendentes DE TESTE -- e
`definir_config` grava na tabela `config` DE PRODUCAO. O cabecalho do proprio
arquivo de teste avisa: "a suite roda em producao e nao pode ligar a
distribuicao de verdade". Os testes antigos usam `cfg(a, b)` + `passar(...)`
com `forcar` exatamente para nao tocar na config. Eu ignorei o padrao.

Estrago medido: `distribuicao_ligada` virou false (estava true),
`primeiro`/`reserva` passaram a apontar para atendentes de teste ja apagados,
`minutos` virou 10 (era 30) e `ligada_em` virou 19/10 10:11 (era 25/09 11:38).
Nenhuma conversa foi afetada -- zero transferencias por inatividade hoje e zero
conversas apontando para atendente inexistente.

Os valores abaixo NAO sao de memoria: saem do dump das 02:40 de hoje
(`/home/claude/backups/db/movizap_20261019_0240.sql.gz`), que e anterior ao
estrago.

NAO uso `definir_config` para restaurar, de proposito: ela reescreveria
`ligada_em` para agora, e `ligada_em` e o MARCO -- conversa com mensagem
anterior a ele nao entra na fila. Reescrever o marco faria a distribuicao
ignorar tudo que esperava desde 25/09.

Tambem devolvo o `atualizado_em` original: a decisao e de 25/09 e ninguem a
mudou. Deixar "agora" ali faria a tabela dizer que ele mexeu nisto hoje.

Uso:  ./venv/bin/python scripts/restaurar_distribuicao.py            # so mostra
      ./venv/bin/python scripts/restaurar_distribuicao.py --aplicar
"""
import sys

sys.path.insert(0, "/home/claude/movizap_painel")
from movizap import banco  # noqa: E402

APLICAR = "--aplicar" in sys.argv

# chave -> (valor, descricao) exatamente como no dump das 02:40
ORIGINAL = {
    "distribuicao_ligada": ("true", "Distribuição automática da fila. Nasce desligada."),
    "distribuicao_primeiro": ("28581", "Quem recebe a conversa parada."),
    "distribuicao_reserva": ("123", "Quem recebe se o primeiro estiver offline."),
    "distribuicao_minutos": ("30", "Minutos sem ninguém assumir."),
    "distribuicao_ligada_em": (
        "2026-09-25 11:38:31.06036-03",
        "Quando a distribuição foi ligada: só entra mensagem depois disto."),
}
QUANDO = "2026-09-25 11:38:31.06036-03"

banco.abrir()

print("ANTES:")
for chave in ORIGINAL:
    linha = banco.um("SELECT valor, atualizado_em FROM config WHERE chave = %s", (chave,))
    print(f"  {chave} = {linha and linha['valor']}  ({linha and linha['atualizado_em']})")

# As duas pessoas ainda existem e recebem conversa? Restaurar apontando para
# quem foi apagado seria trocar um defeito por outro.
for chave in ("distribuicao_primeiro", "distribuicao_reserva"):
    aid = int(ORIGINAL[chave][0])
    quem = banco.um(
        "SELECT id, nome, ativo, transferivel FROM atendente WHERE id = %s", (aid,))
    print(f"  {chave} -> {quem}")
    assert quem and quem["ativo"] and quem["transferivel"], f"{aid} nao serve mais"

if not APLICAR:
    print("\nNada feito. Rode com --aplicar.")
    banco.fechar()
    sys.exit()

with banco.cursor() as cur:
    for chave, (valor, descricao) in ORIGINAL.items():
        cur.execute(
            """INSERT INTO config (chave, valor, descricao, atualizado_em)
               VALUES (%s, %s, %s, %s::timestamptz)
               ON CONFLICT (chave) DO UPDATE
                  SET valor = EXCLUDED.valor,
                      descricao = EXCLUDED.descricao,
                      atualizado_em = EXCLUDED.atualizado_em""",
            (chave, valor, descricao, QUANDO))

# A prova e RELER, nunca o retorno do comando.
print("\nDEPOIS (relido do banco):")
for chave in ORIGINAL:
    linha = banco.um("SELECT valor, atualizado_em FROM config WHERE chave = %s", (chave,))
    print(f"  {chave} = {linha['valor']}  ({linha['atualizado_em']})")

from movizap import distribuicao  # noqa: E402
print("\ndistribuicao.config():", distribuicao.config())
print("distribuicao.situacao():", distribuicao.situacao())
banco.fechar()
