"""Patch dos dois achados da conferência de documentação (22/10).

🚨 **ACHADO 1, o sério: a pasta de anexos dos formulários não estava em backup
nenhum.** `backup_midia.sh` espelha `/home/claude/movizap_midia`; o anexo de
formulário mora em `/home/claude/movizap_formularios_anexos` e ficou de fora --
exatamente o buraco que o próprio script foi criado para fechar em 22/09, agora
repetido com uma pasta nova. E o conteúdo dela é pior de perder: **é a ÚNICA
cópia** de documento que o cliente mandou (contrato social, comprovante de
endereço) -- o banco guarda o CAMINHO, não o arquivo, e no e-mail o Gmail tem a
cópia, aqui ninguém tem.

🚨 **ACHADO 2: o `.env` de um install novo não teria o segredo dos formulários.**
`gerar_env.py` não o gera, então uma máquina nova nasceria com o segredo
derivado do `jwt_secret` -- que está escrito como *fallback*, não como normal.

Os dois achados vieram de procurar o que NÃO está documentado, depois de ele
perguntar duas vezes *"tudo documentado?"*.
"""
import sys
from pathlib import Path

RAIZ = Path("/home/claude/movizap_painel")


def trocar(caminho, velho, novo, marca):
    t = caminho.read_text(encoding="utf-8")
    if marca in t:
        print(f"{caminho.name}: {marca!r} ja estava")
        return
    if t.count(velho) != 1:
        sys.exit(f"{caminho.name}: ancora de {marca!r} aparece {t.count(velho)}x")
    caminho.write_text(t.replace(velho, novo, 1), encoding="utf-8")
    print(f"{caminho.name}: {marca!r} emendado")


# ===================================================== 1) backup dos anexos
BK = RAIZ / "scripts" / "backup_midia.sh"

trocar(BK,
       """# Espelho da pasta de mídia do MoviZap — instantâneos datados, 14 dias.""",
       """# Espelho das pastas de ARQUIVO do MoviZap — instantâneos datados, 14 dias.
#
# 🔵 22/10/2026: passou a espelhar DUAS pastas. A segunda é
# `/home/claude/movizap_formularios_anexos`, o anexo que chega pelos
# formulários públicos -- e ela estava fora de backup nenhum, o MESMO buraco
# que este script foi escrito para fechar em 22/09, repetido com uma pasta
# nova.
#
# 🚨 E ESSA É A PIOR DE PERDER: o anexo de formulário é a ÚNICA cópia de um
# documento que o cliente mandou (contrato social, comprovante de endereço). No
# e-mail o Gmail guarda a cópia; aqui, ninguém guarda. O banco grava o CAMINHO
# do arquivo, nunca o arquivo.""",
       "passou a espelhar DUAS pastas")

trocar(BK,
       '''ORIGEM="/home/claude/movizap_midia"
DESTINO="/home/claude/backups/midia"
RETER_DIAS=14
HOJE="$(date +%F)"
ALVO="$DESTINO/$HOJE"

echo "=== $(date '+%F %T') backup da mídia do MoviZap ==="

if [ ! -d "$ORIGEM" ]; then
    echo "  ERRO: origem não existe: $ORIGEM"
    exit 1
fi''',
       '''# As pastas espelhadas, "origem:destino". ⚠️ A ordem importa só para o log.
PASTAS=(
    "/home/claude/movizap_midia:/home/claude/backups/midia"
    "/home/claude/movizap_formularios_anexos:/home/claude/backups/formularios_anexos"
)
RETER_DIAS=14
HOJE="$(date +%F)"

echo "=== $(date '+%F %T') backup dos arquivos do MoviZap ==="

falhou=0
for par in "${PASTAS[@]}"; do
ORIGEM="${par%%:*}"
DESTINO="${par##*:}"
ALVO="$DESTINO/$HOJE"

echo "-- $ORIGEM"

# ⚠️ ORIGEM QUE NÃO EXISTE NÃO É ERRO AQUI, e a diferença é deliberada: a
# pasta de anexos só nasce no primeiro upload, e um dia sem anexo nenhum não
# pode fazer o cron gritar. ⚠️ Mas ela também não é ignorada em silêncio: o
# log diz que não existe, para "sem backup" e "sem arquivo" não se
# confundirem.
if [ ! -d "$ORIGEM" ]; then
    echo "  pulada: a pasta ainda não existe"
    continue
fi''',
       "PASTAS=(")

trocar(BK,
       '''    rm -rf "$ALVO"
    mv "$ALVO.parcial" "$ALVO"
    echo "  ok: $n_copia arquivos em $ALVO ($(du -sh "$ALVO" | cut -f1) aparentes)"
else
    echo "  ERRO: rsync falhou; o .parcial fica para análise"
    exit 1
fi''',
       '''    rm -rf "$ALVO"
    mv "$ALVO.parcial" "$ALVO"
    echo "  ok: $n_copia arquivos em $ALVO ($(du -sh "$ALVO" | cut -f1) aparentes)"
else
    echo "  ERRO: rsync falhou; o .parcial fica para análise"
    falhou=1
    continue
fi''',
       'falhou=1')

trocar(BK,
       '''        echo "  ERRO: origem tem $n_origem arquivos e a cópia tem $n_copia"
        echo "  o instantâneo fica como .parcial para análise"
        exit 1
    fi''',
       '''        echo "  ERRO: origem tem $n_origem arquivos e a cópia tem $n_copia"
        echo "  o instantâneo fica como .parcial para análise"
        # 🚨 UMA PASTA QUE FALHA NÃO IMPEDE A OUTRA DE SER SALVA, e o script
        # ainda sai diferente de zero no fim -- senão o cron ficaria calado.
        falhou=1
        continue
    fi''',
       'UMA PASTA QUE FALHA NÃO IMPEDE A OUTRA')

trocar(BK,
       '''echo "  podados: $podados instantâneo(s) com mais de $RETER_DIAS dias"
echo "  total em disco: $(du -sh "$DESTINO" | cut -f1)"''',
       '''echo "  podados: $podados instantâneo(s) com mais de $RETER_DIAS dias"
echo "  total em disco: $(du -sh "$DESTINO" | cut -f1)"

done

if [ "$falhou" -ne 0 ]; then
    echo "=== terminou COM FALHA em pelo menos uma pasta ==="
    exit 1
fi
echo "=== ok ==="''',
       "terminou COM FALHA em pelo menos uma pasta")

# ===================================================== 2) o .env de um install novo
trocar(RAIZ / "scripts" / "gerar_env.py",
       'conteudo = f"""# MoviZap -- gerado automaticamente. NUNCA versionar.',
       '''# 🔵 22/10/2026: o segredo dos tokens dos formularios publicos. Assina a
# abertura do formulario (o tempo minimo de preenchimento) e o desafio -- e
# NENHUM dos dois e credencial de ninguem.
#
# 🚨 SEGREDO PROPRIO, NUNCA O `jwt_secret`: os dois tokens saem para a
# internet. O `movizap/formularios.py` deriva um do jwt_secret quando este
# falta, e AVISA no log -- mas derivacao e fallback, nao o normal. Sem esta
# linha, maquina nova nasceria no fallback em silencio.
FORMULARIOS_SEGREDO = secrets.token_hex(32)

conteudo = f"""# MoviZap -- gerado automaticamente. NUNCA versionar.''',
       "FORMULARIOS_SEGREDO = secrets.token_hex(32)")

# e a chave entra no conteudo do .env
trocar(RAIZ / "scripts" / "gerar_env.py",
       """FPSL_BASE_URL=http://127.0.0.1:8005
\"\"\"""",
       """FPSL_BASE_URL=http://127.0.0.1:8005

# ---- formularios publicos (Etapa 1, 2026-10-22) ----
# Assina a abertura do formulario e o desafio. NAO e credencial.
MOVIZAP_FORMULARIOS_SEGREDO={FORMULARIOS_SEGREDO}
\"\"\"""",
       "MOVIZAP_FORMULARIOS_SEGREDO={FORMULARIOS_SEGREDO}")
