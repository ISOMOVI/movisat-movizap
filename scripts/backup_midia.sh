#!/usr/bin/env bash
#
# Espelho da pasta de mídia do MoviZap — instantâneos datados, 14 dias.
#
# 🚨 POR QUE ESTE SCRIPT EXISTE (22/09/2026). A pasta `/home/claude/movizap_midia`
# NÃO ESTAVA EM BACKUP NENHUM, e ninguém tinha percebido:
#   - o `backup_projetos.sh` empacota seis diretórios NOMINAIS, e a pasta de
#     mídia fica FORA do diretório do projeto;
#   - o `backup_db.py` do MoviZap faz `pg_dump`, e o banco guarda o CAMINHO do
#     arquivo, não o arquivo.
# Pior: o `expurgar_base64.py` MOVEU as mídias do banco para o disco. Antes
# dele o conteúdo viajava dentro do `pg_dump`; depois, parou de viajar. O
# expurgo tirou 2.586 mídias do backup em silêncio. Medido em 22/09: 723 MB,
# incluindo a pasta `perfil/` com as fotos da tela Minha conta.
#
# 🚨 INSTANTÂNEO DATADO COM `--link-dest`, NÃO UM TAR POR DIA. Os arquivos já
# são comprimidos (jpg, ogg, pdf): 723 MB de `tar.gz` diário seria quase tudo
# recompressão inútil, crescendo para sempre. Com `--link-dest`, o dia novo
# aponta por hardlink para o arquivo idêntico do dia anterior — cada
# instantâneo PARECE completo e ocupa só o que mudou. Restaurar é `cp`, sem
# desempacotar nada.
#
# ⚠️ MESMA MÁQUINA, E ISSO É UM LIMITE, NÃO UM DESCUIDO. Protege contra apagar
# sem querer, contra o expurgo que levou junto o que não devia, contra o bug
# que renomeia em massa. NÃO protege contra perder a VPS. Levar para fora
# exige destino e credencial, e isso é decisão do usuário — registrada como
# escolha dele em 22/09, não como esquecimento.
#
# ⚠️ `--delete` É DE PROPÓSITO, e é seguro AQUI: ele só faz o instantâneo DE
# HOJE refletir a origem. Os instantâneos anteriores são diretórios próprios e
# não são tocados — arquivo apagado na origem continua nos 13 dias anteriores.

set -uo pipefail

ORIGEM="/home/claude/movizap_midia"
DESTINO="/home/claude/backups/midia"
RETER_DIAS=14
HOJE="$(date +%F)"
ALVO="$DESTINO/$HOJE"

echo "=== $(date '+%F %T') backup da mídia do MoviZap ==="

if [ ! -d "$ORIGEM" ]; then
    echo "  ERRO: origem não existe: $ORIGEM"
    exit 1
fi

mkdir -p "$DESTINO"

# O instantâneo mais recente que já existe vira a base dos hardlinks.
# Sem base, o primeiro dia copia tudo — é o esperado, e acontece uma vez.
# ⚠️ O INSTANTÂNEO DE HOJE TAMBÉM SERVE DE BASE. Rodar duas vezes no mesmo dia
# é comum (rodada à mão, conferência); sem esta linha a segunda rodada não
# acharia base — `$ALVO` seria descartado por ser "igual ao alvo" — e copiaria
# os 723 MB de novo à toa. Apontar para `$ALVO` é seguro porque a escrita vai
# para `$ALVO.parcial`, e a troca só acontece no fim.
ANTERIOR="$(ls -1d "$DESTINO"/20* 2>/dev/null | sort | tail -1)"
LINK=()
if [ -n "$ANTERIOR" ]; then
    LINK=(--link-dest="$ANTERIOR")
    echo "  base de hardlink: $(basename "$ANTERIOR")"
else
    echo "  sem base anterior: esta rodada copia tudo"
fi

# 🚨 ESCREVE EM `.parcial` E SÓ DEPOIS RENOMEIA. Instantâneo pela metade nunca
# fica com o nome definitivo — nem se o processo morrer no meio. É a mesma
# regra que o `midia.guardar` usa ao gravar cada arquivo.
rm -rf "$ALVO.parcial"
if rsync -a --delete "${LINK[@]}" "$ORIGEM/" "$ALVO.parcial/"; then
    # A conferência é CONTAR OS DOIS LADOS, não confiar no código de saída.
    # `rsync` devolve 0 em casos que ainda deixam o espelho curto.
    n_origem="$(find "$ORIGEM" -type f | wc -l)"
    n_copia="$(find "$ALVO.parcial" -type f | wc -l)"
    if [ "$n_origem" -ne "$n_copia" ]; then
        echo "  ERRO: origem tem $n_origem arquivos e a cópia tem $n_copia"
        echo "  o instantâneo fica como .parcial para análise"
        exit 1
    fi
    rm -rf "$ALVO"
    mv "$ALVO.parcial" "$ALVO"
    echo "  ok: $n_copia arquivos em $ALVO ($(du -sh "$ALVO" | cut -f1) aparentes)"
else
    echo "  ERRO: rsync falhou; o .parcial fica para análise"
    exit 1
fi

# Poda. ⚠️ NUNCA apaga o último que sobrou: se algo estiver errado com as
# datas, ficar sem backup nenhum é pior que guardar demais.
podados=0
for velho in $(ls -1d "$DESTINO"/20* 2>/dev/null | sort); do
    restantes="$(ls -1d "$DESTINO"/20* 2>/dev/null | wc -l)"
    [ "$restantes" -le 1 ] && break
    dias="$(( ( $(date +%s) - $(date -d "$(basename "$velho")" +%s) ) / 86400 ))"
    if [ "$dias" -gt "$RETER_DIAS" ]; then
        rm -rf "$velho"
        podados=$((podados + 1))
    fi
done
echo "  podados: $podados instantâneo(s) com mais de $RETER_DIAS dias"
echo "  total em disco: $(du -sh "$DESTINO" | cut -f1)"
