"""Rotaciona o segredo do webhook do Evolution SEM JANELA DE RECUSA.

Por que não é só trocar o valor: segredo errado devolve **404**, e o Evolution
trata 404 como falha. Trocar e reiniciar deixaria todo evento recusado entre o
restart e o reapontamento das instâncias. Com os dois segredos válidos ao mesmo
tempo, as duas URLs respondem enquanto se reaponta, e nada se perde.

    1. `--abrir`     gera o novo, move o atual para _ANTERIOR, grava o .env
       (reiniciar)   -> as DUAS URLs passam a valer
    2. reapontar     scripts/configurar_webhook_evolution.py
    3. `--conferir`  prova pelo ESTADO que evento novo está chegando
    4. `--fechar`    tira o _ANTERIOR do .env
       (reiniciar)   -> só a nova vale

🚨 O SEGREDO NUNCA É IMPRESSO, em nenhum modo. Ele é gerado aqui dentro e vai
direto para o arquivo; o que aparece na tela é o tamanho. Foi assim que o
`configurar_webhook_evolution.py` já fazia -- o vazamento de 12/08 não veio de
script, veio do log de acesso do uvicorn (corrigido por filtro no mesmo dia).

⚠️ VALIDA ANTES DE GRAVAR: monta o texto novo em memória, confere que as
chaves existem e são únicas, e só então escreve. Backup vai para FORA do
repositório -- `.env.bak` dentro dele já causou incidente.
"""
import secrets
import shutil
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, "/home/claude/movizap_painel")

from movizap import banco  # noqa: E402

ENV = Path("/home/claude/movizap_painel/.env")
BACKUP_DIR = Path("/home/claude/backups")
ATUAL = "MOVIZAP_WEBHOOK_SEGREDO"
ANTERIOR = "MOVIZAP_WEBHOOK_SEGREDO_ANTERIOR"


def _linhas() -> list[str]:
    return ENV.read_text(encoding="utf-8").splitlines(keepends=True)


def _valor(linhas: list[str], chave: str) -> str | None:
    for linha in linhas:
        if linha.strip().startswith(f"{chave}="):
            return linha.split("=", 1)[1].strip()
    return None


def _gravar(novas: list[str]) -> None:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    carimbo = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    destino = BACKUP_DIR / f"env_movizap_{carimbo}.bak"
    shutil.copy2(ENV, destino)
    destino.chmod(0o600)
    print(f"backup: {destino}")
    ENV.write_text("".join(novas), encoding="utf-8")
    ENV.chmod(0o600)


def abrir() -> None:
    linhas = _linhas()
    atual = _valor(linhas, ATUAL)
    if not atual:
        raise SystemExit(f"ABORTADO: {ATUAL} não existe no .env.")
    if _valor(linhas, ANTERIOR):
        raise SystemExit(
            f"ABORTADO: {ANTERIOR} já existe -- há uma rotação em curso. "
            f"Termine com --fechar antes de abrir outra.")

    novo = secrets.token_urlsafe(32)          # 43 caracteres, como o atual
    if novo == atual:                          # impossível na prática; barato conferir
        raise SystemExit("ABORTADO: o novo saiu igual ao atual.")

    novas, trocadas = [], 0
    for linha in linhas:
        if linha.strip().startswith(f"{ATUAL}="):
            fim = "\n" if linha.endswith("\n") else ""
            novas.append(f"{ATUAL}={novo}{fim}")
            novas.append(f"{ANTERIOR}={atual}\n")
            trocadas += 1
        else:
            novas.append(linha)
    if trocadas != 1:
        raise SystemExit(f"ABORTADO: esperava 1 linha {ATUAL}=, achei {trocadas}.")

    _gravar(novas)
    print(f"{ATUAL}: novo, {len(novo)} caracteres (nao impresso)")
    print(f"{ANTERIOR}: o de antes, ainda VÁLIDO")
    print()
    print("AGORA:  systemctl --user restart movizap")
    print("DEPOIS: ./venv/bin/python scripts/configurar_webhook_evolution.py")
    print("ENTÃO:  ./venv/bin/python scripts/rotacionar_webhook.py --conferir")


def conferir() -> None:
    """Duas provas, e as duas são necessárias.

    🚨 "CHEGARAM EVENTOS" NÃO PROVA NADA DURANTE A ROTAÇÃO. Os dois segredos
    estão válidos: se o Evolution ainda estivesse mandando para a URL ANTIGA,
    os eventos chegariam do mesmo jeito e o contador diria "OK". A primeira
    versão deste script fazia exatamente isso -- rótulo fixo ao lado de um
    número que não respondia a pergunta. Fechar em cima disso derrubaria o
    webhook no restart seguinte.

    O que se confere:
      1. o Evolution TEM a URL nova gravada (perguntado a ele, não suposto);
      2. e continua entregando (senão a URL pode estar certa e morta).
    """
    import httpx

    from movizap.config import settings

    linhas = _linhas()
    novo = _valor(linhas, ATUAL)
    print(f"{ATUAL} presente:   {bool(novo)}")
    print(f"{ANTERIOR} presente: {bool(_valor(linhas, ANTERIOR))}")

    esperada = f"https://{settings.dominio}/api/webhook/evolution/{novo}"
    cabecalhos = {"apikey": settings.evolution_api_key}
    instancias_ok, instancias_erradas = [], []
    with httpx.Client(base_url=settings.evolution_base_url, timeout=30) as c:
        for inst in ("atendimento", "informativos"):
            try:
                r = c.get(f"/webhook/find/{inst}", headers=cabecalhos)
                gravada = (r.json() or {}).get("url") or ""
            except Exception as e:
                instancias_erradas.append(f"{inst}: {type(e).__name__}")
                continue
            # Compara o valor inteiro, mas imprime só se BATE -- nunca a URL,
            # que carrega o segredo.
            (instancias_ok if gravada == esperada else instancias_erradas).append(inst)
    print(f"instâncias com a URL NOVA: {instancias_ok or 'nenhuma'}")
    if instancias_erradas:
        print(f"instâncias fora: {instancias_erradas}")

    banco.abrir()
    ultimo = banco.um(
        "SELECT id, recebido_em, now() - recebido_em AS ha "
        "  FROM webhook_evento ORDER BY id DESC LIMIT 1")
    recentes = banco.um(
        "SELECT count(*) AS n FROM webhook_evento "
        " WHERE recebido_em > now() - interval '10 minutes'")
    banco.fechar()

    print(f"último evento: {ultimo}")
    print(f"eventos nos últimos 10 min: {recentes['n']}")
    print()

    if instancias_erradas or not instancias_ok:
        print("NÃO FECHE: alguma instância não está com a URL nova.")
    elif not recentes["n"]:
        print("ESPERE: URL nova gravada, mas nenhum evento recente. Sem "
              "tráfego não dá para saber se ela entrega -- mande uma mensagem "
              "para o número do canal e rode de novo.")
    else:
        print("PODE FECHAR: as duas instâncias têm a URL nova E há tráfego.")


def fechar() -> None:
    linhas = _linhas()
    if not _valor(linhas, ANTERIOR):
        raise SystemExit(f"Nada a fazer: {ANTERIOR} não está no .env.")

    novas = [l for l in linhas if not l.strip().startswith(f"{ANTERIOR}=")]
    if len(novas) != len(linhas) - 1:
        raise SystemExit("ABORTADO: esperava remover exatamente 1 linha.")

    _gravar(novas)
    print(f"{ANTERIOR} removido. Só o segredo novo vale a partir do restart.")
    print()
    print("AGORA: systemctl --user restart movizap")


if __name__ == "__main__":
    if "--abrir" in sys.argv:
        abrir()
    elif "--fechar" in sys.argv:
        fechar()
    else:
        conferir()
