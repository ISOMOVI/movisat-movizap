"""Ligações do MicroSIP — o backup na VPS (Plano 5, 25/09).

🔵 *"inicialmente o backup das ligações na VPS de uma forma bem inteligente"*
e *"um script que ... fique rodando 2x por dia no pc deles e que se ficar mais
1 dia sem comunicar com VPS, tenhamos um alerta pelo meu shell"*.

O agente do PC (`movizap-ligacoes.ps1`) fala com duas rotas:
  · `batimento`: toda passada, mesmo sem nada a enviar -- é o que prova que o
    PC está vivo. Sem batimento há mais de 24 h, `agentes_mudos()` acusa.
  · `enviar`: uma ligação (e, se houver, UMA gravação dela) por chamada.

🚨 IDEMPOTENTE. O agente reenvia sem medo: a ligação é única por
`(ramal, call_id)` e a gravação por SHA-256. A resposta devolve o hash do que
ESTÁ GUARDADO -- o agente só marca como salvo quando o hash bate (a regra da
casa: a prova é reler, não o código HTTP).

PORTA PRÓPRIA (Plano 5.1, 25/09): as rotas moram em `app_ligacoes.py`, na
8010, atrás de `ligacoesmicrosip.movisat.com.br` com certificado de cliente
(mTLS). As de `main.py` (`/api/ligacoes/agente/*`) ficam só até o PC dele
provar o caminho novo; depois saem.

🚨 A CHAVE NÃO SE GUARDA, SÓ O HASH. Ela aparece uma vez, na geração
(`scripts/chave_agente_ligacao.py`), e vai para o `config.json` do PC.
"""
import hashlib
import logging
import os
import secrets
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import unquote

import psycopg

from . import banco, telefone
from .operacao import DadoInvalido

log = logging.getLogger("movizap.ligacoes")

RAIZ = Path(os.environ.get("MOVIZAP_LIGACOES_DIR", "/home/claude/movizap_ligacoes"))
TETO_MB = 25
TETO = TETO_MB * 1024 * 1024
HORAS_MUDO = 24
SENTIDOS = ("feita", "recebida", "perdida")


class ChaveInvalida(Exception):
    """Chave ausente, desconhecida ou revogada. Vira 401."""


def _sha(texto: str) -> str:
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()


# ------------------------------------------------------------------ a chave

def gerar_chave(atendente_id: int, ramal: str) -> str:
    """Cria a chave do agente de um ramal. Devolve a chave EM CLARO, uma vez só."""
    ramal = (ramal or "").strip()
    if not ramal.isdigit():
        raise DadoInvalido("O ramal é só número (ex.: 3404).")
    if not banco.um("SELECT id FROM atendente WHERE id = %s AND ativo", (atendente_id,)):
        raise DadoInvalido("Atendente não encontrado ou inativo.")
    chave = "mzl_" + secrets.token_urlsafe(32)
    with banco.cursor() as cur:
        cur.execute("UPDATE atendente SET ramal = %s WHERE id = %s", (ramal, atendente_id))
        # Uma chave viva por ramal: a nova revoga a anterior.
        cur.execute("""UPDATE agente_ligacao SET revogado_em = now()
                        WHERE ramal = %s AND revogado_em IS NULL""", (ramal,))
        cur.execute("""INSERT INTO agente_ligacao (atendente_id, ramal, chave_sha256)
                       VALUES (%s, %s, %s)""", (atendente_id, ramal, _sha(chave)))
    log.info("chave de agente gerada para o ramal %s (atendente %s)", ramal, atendente_id)
    return chave


def agente_da_chave(chave: str | None, cert_pem: str | None = None,
                    exigir_cert: bool = False) -> dict:
    """A chave identifica o agente. Na porta própria (`app_ligacoes`, Plano 5.1)
    o certificado do PC também: os dois têm de ser do MESMO agente, e um sem o
    outro não entra."""
    if not chave:
        raise ChaveInvalida("Sem chave.")
    agente = banco.um("""SELECT id, atendente_id, ramal, cert_sha256, cert_validade
                           FROM agente_ligacao
                          WHERE chave_sha256 = %s AND revogado_em IS NULL""", (_sha(chave),))
    if not agente:
        raise ChaveInvalida("Chave desconhecida ou revogada.")
    if exigir_cert:
        from . import ligacoes_ca
        if not cert_pem:
            raise ChaveInvalida("Sem certificado do PC.")
        try:
            sha = ligacoes_ca.sha256_do_cert(unquote(cert_pem))
        except ValueError as e:
            raise ChaveInvalida("Certificado ilegível.") from e
        if not agente["cert_sha256"] or not secrets.compare_digest(sha, agente["cert_sha256"]):
            raise ChaveInvalida("O certificado não é o deste agente.")
        if agente["cert_validade"] and agente["cert_validade"] < datetime.now(timezone.utc):
            raise ChaveInvalida("Certificado vencido.")
    return agente


# ------------------------------------------------------------------ batimento

def batimento(agente: dict, pc: str | None, versao: str | None,
              pendentes: int | None, erro: str | None,
              ip: str | None = None, aviso: str | None = None) -> dict:
    banco.executar(
        """UPDATE agente_ligacao
              SET ultimo_contato_em = now(), ultimo_pc = %s, ultima_versao = %s,
                  pendentes = %s, ultimo_erro = %s,
                  ultimo_ip = COALESCE(%s, ultimo_ip), ultimo_aviso = %s
            WHERE id = %s""",
        ((pc or "")[:100] or None, (versao or "")[:20] or None, pendentes,
         (erro or "")[:500] or None, (ip or "")[:45] or None,
         (aviso or "")[:500] or None, agente["id"]))
    return {"ok": True, "ramal": agente["ramal"],
            "servidor_em": datetime.now(timezone.utc).isoformat()}


def agentes_com_aviso() -> list[dict]:
    """Os que FALAM (não estão mudos) mas trouxeram erro ou aviso na última
    passada: gravação desligada, arquivo pulado, disco quase cheio. Mudo já
    sai em `agentes_mudos`; aqui é o PC vivo que pede olho."""
    return banco.varios(
        """SELECT g.ramal, a.nome AS operador, g.ultimo_pc, g.ultimo_contato_em,
                  g.ultimo_erro, g.ultimo_aviso
             FROM agente_ligacao g JOIN atendente a ON a.id = g.atendente_id
            WHERE g.revogado_em IS NULL
              AND g.ultimo_contato_em >= now() - make_interval(hours => %s)
              AND (g.ultimo_erro IS NOT NULL OR g.ultimo_aviso IS NOT NULL)
            ORDER BY g.ramal""", (HORAS_MUDO,))


def certs_vencendo(dias: int = 30) -> list[dict]:
    """Certificado de PC que vence em menos de `dias` (ou já venceu)."""
    return banco.varios(
        """SELECT g.ramal, a.nome AS operador, g.ultimo_pc, g.cert_validade
             FROM agente_ligacao g JOIN atendente a ON a.id = g.atendente_id
            WHERE g.revogado_em IS NULL AND g.cert_validade IS NOT NULL
              AND g.cert_validade < now() + make_interval(days => %s)
            ORDER BY g.cert_validade""", (dias,))


def agentes_mudos(horas: int = HORAS_MUDO) -> list[dict]:
    """Os agentes vivos (não revogados) sem contato há mais de `horas`.
    Nunca falou também conta: chave gerada e agente nunca instalado é mudo."""
    return banco.varios(
        """SELECT g.ramal, a.nome AS operador, g.ultimo_pc, g.ultimo_contato_em,
                  g.ultimo_erro, g.pendentes, g.criado_em
             FROM agente_ligacao g JOIN atendente a ON a.id = g.atendente_id
            WHERE g.revogado_em IS NULL
              AND COALESCE(g.ultimo_contato_em, g.criado_em) < now() - make_interval(hours => %s)
            ORDER BY g.ramal""", (horas,))


# ------------------------------------------------------------------ enviar

def _data(valor) -> datetime:
    try:
        d = datetime.fromisoformat(str(valor).replace("Z", "+00:00"))
    except ValueError as e:
        raise DadoInvalido("Data inválida: use ISO 8601.") from e
    if d.tzinfo is None:
        raise DadoInvalido("A data precisa do fuso (ex.: -03:00).")
    return d


def _guardar_arquivo(dados: bytes, inicio: datetime | None) -> tuple[str, str]:
    sha = hashlib.sha256(dados).hexdigest()
    quando = inicio or datetime.now(timezone.utc)
    pasta = RAIZ / f"{quando:%Y}" / f"{quando:%m}"
    pasta.mkdir(parents=True, exist_ok=True)
    destino = pasta / f"{sha}.mp3"
    if not destino.exists():
        temporario = destino.with_suffix(".parcial")
        temporario.write_bytes(dados)
        os.chmod(temporario, 0o640)
        temporario.replace(destino)  # atômico: nunca fica meio arquivo com o nome final
    # Relê o que está no disco: é esse hash que volta ao agente.
    sha_disco = hashlib.sha256(destino.read_bytes()).hexdigest()
    return str(destino), sha_disco


def registrar(agente: dict, dados: dict, arquivo: bytes | None = None,
              nome_arquivo: str | None = None, pc: str | None = None) -> dict:
    """Uma ligação (e, se vier, uma gravação dela). Idempotente."""
    call_id = str(dados.get("call_id") or "").strip()
    if not call_id:
        raise DadoInvalido("Falta o call_id da ligação.")
    sentido = dados.get("sentido")
    if sentido not in SENTIDOS:
        raise DadoInvalido(f"Sentido inválido. Vale: {', '.join(SENTIDOS)}.")
    numero = str(dados.get("numero") or "").strip()
    if not numero:
        raise DadoInvalido("Falta o número.")
    inicio = _data(dados.get("inicio"))
    duracao = max(0, int(dados.get("duracao_s") or 0))

    with banco.cursor() as cur:
        cur.execute(
            """INSERT INTO ligacao (agente_id, atendente_id, ramal, call_id, numero_bruto,
                                    telefone_e164, sentido, situacao, inicio, duracao_s, pc)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
               ON CONFLICT (ramal, call_id) DO NOTHING
               RETURNING id""",
            (agente["id"], agente["atendente_id"], agente["ramal"], call_id, numero[:40],
             telefone.normalizar(numero), sentido, (dados.get("situacao") or "")[:100] or None,
             inicio, duracao, (pc or "")[:100] or None))
        nova = cur.fetchone()
        if nova:
            ligacao_id, ligacao_nova = nova["id"], True
        else:
            cur.execute("SELECT id FROM ligacao WHERE ramal = %s AND call_id = %s",
                        (agente["ramal"], call_id))
            ligacao_id, ligacao_nova = cur.fetchone()["id"], False

    resposta = {"ok": True, "ligacao_id": ligacao_id, "ligacao_nova": ligacao_nova}
    if arquivo is None:
        return resposta

    if not arquivo:
        raise DadoInvalido("Arquivo vazio.")
    if len(arquivo) > TETO:
        raise DadoInvalido(f"Gravação acima de {TETO_MB} MB.")
    # MP3: começa com "ID3" ou com a sincronia de quadro (0xFFE, 11 bits em 1).
    if not (arquivo[:3] == b"ID3" or (arquivo[0] == 0xFF and (arquivo[1] & 0xE0) == 0xE0)):
        raise DadoInvalido("A gravação não é MP3.")
    ja = banco.um("SELECT ligacao_id, arquivo_sha256 FROM ligacao_gravacao WHERE arquivo_sha256 = %s",
                  (hashlib.sha256(arquivo).hexdigest(),))
    if ja:
        resposta.update(gravacao_nova=False, arquivo_sha256=ja["arquivo_sha256"])
        return resposta
    grav_inicio = _data(dados["gravacao_inicio"]) if dados.get("gravacao_inicio") else None
    caminho, sha = _guardar_arquivo(arquivo, grav_inicio or inicio)
    try:
        banco.executar(
            """INSERT INTO ligacao_gravacao (ligacao_id, nome_original, arquivo_sha256,
                                             arquivo_bytes, caminho, inicio)
               VALUES (%s, %s, %s, %s, %s, %s)""",
            (ligacao_id, (nome_arquivo or "gravacao.mp3")[:200], sha, len(arquivo),
             caminho, grav_inicio))
    except psycopg.errors.UniqueViolation:
        pass  # outra passada gravou o mesmo arquivo no mesmo instante
    log.info("ligação %s: gravação %s (%d bytes) guardada", ligacao_id, sha[:12], len(arquivo))
    resposta.update(gravacao_nova=True, arquivo_sha256=sha)
    return resposta
