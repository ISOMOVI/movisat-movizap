"""Confere cada número e cada afirmação do MIOLO contra o sistema ao vivo.

🚨 Existe porque o MIOLO é escrito à mão e envelhece em horas. Número em prosa
não tem teste -- foi assim que a contagem de linhas do registro de telas ficou
errada por semanas sem ninguém notar.
"""
import sys
from pathlib import Path

sys.path.insert(0, "/home/claude/movizap_painel")

from movizap import banco  # noqa: E402

RAIZ = Path("/home/claude/movizap_painel")
banco.abrir()

n = lambda sql, p=(): banco.um(sql, p)["n"]  # noqa: E731

print("== ESTADO MEDIDO ==")
print(f"conversas            : {n('SELECT count(*) n FROM conversa')}")
print(f"mensagens            : {n('SELECT count(*) n FROM mensagem')}")
midia = banco.um("SELECT count(*) n, pg_size_pretty(sum(tamanho)) t FROM midia")
print(f"midias               : {midia['n']} ({midia['t']})")
print(f"e-mails              : {n('SELECT count(*) n FROM email_mensagem')}")
print(f"  com anexo          : {n('SELECT count(*) n FROM email_mensagem WHERE tem_anexo')}")
print(f"clientes ativos      : {n('SELECT count(*) n FROM cliente WHERE ativo')}")
print(f"contatos             : {n('SELECT count(*) n FROM contato')}")
print(f"alcance por WhatsApp : "
      f"{n('''SELECT count(DISTINCT ct.cliente_id) n FROM contato_telefone t
              JOIN contato ct ON ct.id = t.contato_id
             WHERE t.tem_whatsapp IS TRUE AND ct.cliente_id IS NOT NULL''')}")
print(f"tabelas              : "
      f"{n('''SELECT count(*) n FROM information_schema.tables
              WHERE table_schema = 'public' ''')}")
ultima = banco.um("SELECT max(versao) v FROM schema_migracao")["v"]
print(f"ultima migracao      : {ultima}")

print("\n== SALAS DE CHAT ==")
print(f"salas                : {n('SELECT count(*) n FROM chat_sala')}")
print(f"mensagens de chat    : {n('SELECT count(*) n FROM chat_mensagem')}")

print("\n== AFIRMACOES QUE O MIOLO FAZ ==")
login = banco.um("SELECT login, perfil, owner FROM atendente WHERE owner")
print(f"login do owner e 'owner'      : {login and login['login'] == 'owner'}")
grupo = n("SELECT count(*) n FROM webhook_evento WHERE motivo_ignorado LIKE %s",
          ("grupo%",))
print(f"eventos de grupo descartados  : {grupo} (MIOLO diz que nenhum chega)")
rel = banco.varios("SELECT relacao, count(*) n FROM contato GROUP BY 1 ORDER BY 2 DESC")
print(f"relacao dos contatos          : {[(r['relacao'], r['n']) for r in rel]}")
sem_dono_nome = n(
    """SELECT count(*) n FROM contato ct
        JOIN cliente cl ON cl.id = ct.cliente_id
       WHERE ct.origem = 'bitrix'""")
print(f"contatos bitrix ligados       : {sem_dono_nome}")

print("\n== ARQUIVOS QUE O MIOLO CITA ==")
for caminho in ("docs/14_Avanco_2026-08-12.md",
                "docs/13_Avanco_2026-08-11.md",
                "docs/12_Bitrix_para_o_Cadastro.md",
                "docs/02_Modelo_Dados.md",
                "docs/03_Registro_Telas.md",
                "docs/06_Conteudo_das_Telas.md",
                "docs/11_Identidade_e_Cruzamento.md",
                "scripts/rotacionar_webhook.py",
                "scripts/auditar_segredo_em_log.py"):
    print(f"  {'OK ' if (RAIZ / caminho).exists() else 'FALTA'} {caminho}")
op = Path("/home/claude/movisat-operacao/docs/04_Segredo_em_Log.md")
print(f"  {'OK ' if op.exists() else 'FALTA'} movisat-operacao/docs/04_Segredo_em_Log.md")
print(f"  {'FALTA (bom)' if not (RAIZ / 'revisao').exists() else 'AINDA EXISTE'} revisao/")

banco.fechar()
