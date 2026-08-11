"""Procura lixo no banco do MoviZap. LEITURA PURA -- nao apaga nada.

Lixo aqui e qualquer linha que ninguem usa, que contradiz outra, ou que so
existe porque alguem testou alguma coisa e nao limpou. Cada achado vem com o
numero, porque 'tem sujeira' nao e diagnostico.
"""
import sys

sys.path.insert(0, "/home/claude/movizap_painel")
from movizap import banco  # noqa: E402


def t(txt):
    print("\n" + "=" * 70)
    print(txt)
    print("=" * 70)


def n(sql, args=()):
    return banco.um(sql, args)["n"]


banco.abrir()
try:
    t("1. VOLUME DE CADA TABELA")
    for r in banco.varios("""
        SELECT relname t, n_live_tup n, pg_size_pretty(
                 pg_total_relation_size(relid)) tam
          FROM pg_stat_user_tables ORDER BY n_live_tup DESC"""):
        print(f"   {r['n']:9}  {r['tam']:>10}  {r['t']}")

    t("2. DADOS DE TESTE")
    # 🚨 padrao de LIKE vai como PARAMETRO: '%IAGO%' dentro do SQL faz o
    # psycopg ler '%I' como placeholder e estourar antes de consultar.
    for rot, sql, args in (
        ("conversas com o número da Pastelaria Velasco",
         "SELECT count(*) n FROM conversa WHERE telefone_e164 = %s",
         ("+5518998116168",)),
        ("clientes com IAGO SANTOS no nome",
         "SELECT count(*) n FROM cliente WHERE nome ILIKE %s", ("%IAGO SANTOS%",)),
        ("clientes com nome de 1 palavra minúscula",
         "SELECT count(*) n FROM cliente WHERE ativo AND nome ~ %s", ("^[a-z]+$",)),
        ("clientes marcados [NÃO USAR] / (INATIVADO)",
         "SELECT count(*) n FROM cliente WHERE ativo AND (nome ILIKE %s "
         "OR nome ILIKE %s OR nome ILIKE %s)",
         ("%NAO USAR%", "%NÃO USAR%", "%INATIVADO%")),
        ("clientes sem documento",
         "SELECT count(*) n FROM cliente WHERE ativo AND coalesce(documento,'') = ''", ()),
        ("clientes com documento de dígito único (0000…)",
         "SELECT count(*) n FROM cliente WHERE ativo AND documento IS NOT NULL "
         "AND length(replace(documento, substr(documento,1,1), '')) = 0", ()),
    ):
        print(f"   {n(sql, args):6}  {rot}")

    t("3. ÓRFÃOS E VÍNCULOS QUEBRADOS")
    for rot, sql in (
        ("conversas sem nenhuma mensagem",
         "SELECT count(*) n FROM conversa c WHERE NOT EXISTS "
         "(SELECT 1 FROM mensagem m WHERE m.conversa_id = c.id)"),
        ("mensagens sem conversa",
         "SELECT count(*) n FROM mensagem m WHERE NOT EXISTS "
         "(SELECT 1 FROM conversa c WHERE c.id = m.conversa_id)"),
        ("contatos sem cliente",
         "SELECT count(*) n FROM contato WHERE cliente_id IS NULL"),
        ("telefones sem contato",
         "SELECT count(*) n FROM contato_telefone t WHERE NOT EXISTS "
         "(SELECT 1 FROM contato c WHERE c.id = t.contato_id)"),
        ("contatos inativos ainda com telefone",
         "SELECT count(*) n FROM contato_telefone t JOIN contato c ON c.id=t.contato_id "
         "WHERE NOT c.ativo"),
        ("telefones de cliente INATIVO",
         "SELECT count(*) n FROM contato_telefone t JOIN contato c ON c.id=t.contato_id "
         "JOIN cliente cl ON cl.id=c.cliente_id WHERE NOT cl.ativo"),
        ("mídia sem mensagem",
         "SELECT count(*) n FROM midia m WHERE NOT EXISTS "
         "(SELECT 1 FROM mensagem x WHERE x.id = m.mensagem_id)"),
    ):
        try:
            print(f"   {n(sql):6}  {rot}")
        except Exception as e:                       # noqa: BLE001
            print(f"      (pulei '{rot}': {str(e)[:50]})")

    t("4. DUPLICATAS NO CADASTRO")
    dup = banco.varios("""
        SELECT documento, count(*) n, string_agg(id::text, ',') ids
          FROM cliente WHERE ativo AND documento IS NOT NULL
           AND length(replace(documento, substr(documento,1,1), '')) > 0
         GROUP BY documento HAVING count(*) > 1 ORDER BY n DESC""")
    print(f"   {len(dup)} documentos repetidos entre clientes ativos "
          f"({sum(r['n']-1 for r in dup)} linhas a mais)")
    for r in dup[:8]:
        nomes = banco.varios("SELECT nome FROM cliente WHERE documento=%s AND ativo",
                             (r["documento"],))
        print(f"      {r['documento']}  ×{r['n']}  {nomes[0]['nome'][:40]}")

    t("5. WEBHOOK_EVENTO — o gargalo conhecido")
    print(f"   linhas          : {n('SELECT count(*) n FROM webhook_evento')}")
    for r in banco.varios("""
        SELECT min(recebido_em)::date ini, max(recebido_em)::date fim
          FROM webhook_evento"""):
        print(f"   período         : {r['ini']} a {r['fim']}")
    for r in banco.varios("""
        SELECT coalesce(motivo_ignorado, '(processado)') m, count(*) n
          FROM webhook_evento GROUP BY 1 ORDER BY n DESC LIMIT 8"""):
        print(f"      {r['n']:7}  {r['m'][:52]}")
    print(f"   com erro        : {n('SELECT count(*) n FROM webhook_evento WHERE erro IS NOT NULL')}")

    t("6. ESTRUTURA CRIADA E NUNCA USADA")
    for rot, sql in (
        ("prompt_versao", "SELECT count(*) n FROM prompt_versao"),
        ("classificacao", "SELECT count(*) n FROM classificacao"),
        ("conversas classificadas",
         "SELECT count(*) n FROM conversa WHERE classificacao_id IS NOT NULL"),
        ("disparo", "SELECT count(*) n FROM disparo"),
        ("disparo_destino", "SELECT count(*) n FROM disparo_destino"),
        ("transferencia", "SELECT count(*) n FROM transferencia"),
        ("atendente", "SELECT count(*) n FROM atendente"),
        ("atendente_jornada", "SELECT count(*) n FROM atendente_jornada"),
        ("contato_papel", "SELECT count(*) n FROM contato_papel"),
        ("conversas com avaliação", "SELECT count(*) n FROM conversa WHERE avaliacao IS NOT NULL"),
        ("times sem nenhum membro",
         "SELECT count(*) n FROM time t WHERE NOT EXISTS "
         "(SELECT 1 FROM atendente_time a WHERE a.time_id = t.id)"),
    ):
        try:
            print(f"   {n(sql):6}  {rot}")
        except Exception as e:                        # noqa: BLE001
            print(f"      (pulei '{rot}': {str(e)[:40]})")

    t("7. E-MAIL")
    for rot, sql, args in (
        ("mensagens guardadas", "SELECT count(*) n FROM email_mensagem", ()),
        ("sem cliente vinculado",
         "SELECT count(*) n FROM email_mensagem WHERE cliente_id IS NULL", ()),
        ("remetente do próprio domínio",
         "SELECT count(*) n FROM email_mensagem WHERE remetente ILIKE %s",
         ("%@movisat.com.br",)),
        ("com bruto guardado (pesa)",
         "SELECT count(*) n FROM email_mensagem WHERE bruto IS NOT NULL", ()),
        ("noreply / automáticos",
         "SELECT count(*) n FROM email_mensagem WHERE remetente ~* %s",
         ("(noreply|no-reply|nao-responda|mailer-daemon|notificacao)",)),
    ):
        print(f"   {n(sql, args):6}  {rot}")

    t("8. CONVERSAS")
    for r in banco.varios("SELECT estado, count(*) n FROM conversa GROUP BY 1 ORDER BY n DESC"):
        print(f"   {r['n']:6}  estado = {r['estado']}")
    print(f"   {n('SELECT count(*) n FROM conversa WHERE contato_id IS NULL'):6}  sem vínculo")
    print(f"   {n('SELECT count(*) n FROM conversa WHERE nome_whatsapp IS NULL'):6}  sem nome do WhatsApp")
finally:
    banco.fechar()
