"""O resumo diário do vigia de ligações (15/10).

🚨 RODA O SCRIPT SEM `--avisar-whatsapp`, de propósito: com a bandeira ele
manda mensagem de verdade pelo Evolution, e teste não manda WhatsApp para
ninguém. Foi a lição do mesmo dia, quando um teste chamou `conversas.bloquear()`
e a suíte ficou pendurada tentando bloquear um número na API real.

O que estes testes guardam:
  · o SILÊNCIO continua sendo a regra sem `--resumo` -- nada errado, nada dito,
    que é o que faz um alerta ser alerta;
  · com `--resumo`, "tudo em dia" fala, e fala com NÚMERO: "tudo ok" não
    distingue vigia funcionando de vigia olhando para uma base vazia;
  · o cron de 18:10 é o único com `--resumo` (uma mensagem por dia, não duas).
"""
import subprocess
import sys
from pathlib import Path

import pytest

RAIZ = Path("/home/claude/movizap_painel")
sys.path.insert(0, str(RAIZ))
pytest.importorskip("psycopg")

from movizap import banco, ligacoes  # noqa: E402

ENV = RAIZ / ".env"
pytestmark = pytest.mark.skipif(
    not ENV.exists() or "MOVIZAP_DB_SENHA" not in ENV.read_text(encoding="utf-8"),
    reason="banco nao configurado no .env")


def rodar(*bandeiras):
    """O script, sem nunca passar `--avisar-whatsapp`."""
    assert "--avisar-whatsapp" not in bandeiras, "teste não manda WhatsApp"
    r = subprocess.run(
        [str(RAIZ / "venv/bin/python"), "scripts/agentes_mudos.py", *bandeiras],
        cwd=RAIZ, capture_output=True, text=True, timeout=60)
    return r.stdout.strip()


@pytest.fixture(scope="module", autouse=True)
def base():
    banco.abrir()
    yield
    banco.fechar()


def test_os_numeros_do_resumo_saem_do_banco():
    r = ligacoes.agentes_vivos_resumo()
    assert set(r) == {"com_agente", "sem_agente", "ligacoes_hoje"}
    assert all(isinstance(v, int) for v in r.values())
    # Hoje há pelo menos um agente vivo (o do ramal 3404). Se este teste
    # começar a falhar, é porque alguém ficou sem agente -- e isso é notícia,
    # não defeito do teste.
    assert r["com_agente"] >= 1


def test_sem_resumo_tudo_em_dia_e_silencio():
    """🚨 A regra não afrouxou: sem a bandeira, nada errado = nada dito."""
    saida = rodar()
    # Pode haver alerta real na base (um PC mudo de verdade); o que não pode é
    # aparecer a frase do resumo.
    assert "tudo em dia" not in saida


def test_com_resumo_tudo_em_dia_fala_e_diz_numero():
    saida = rodar("--resumo")
    if "ALERTA" in saida or "AVISO" in saida:
        pytest.skip("ha alerta real na base agora: o resumo cede a vez ao alerta")
    assert "tudo em dia" in saida
    assert "PC(s) enviando" in saida
    # O número, e não um "tudo ok" que não conta nada.
    assert any(c.isdigit() for c in saida)


def test_o_cron_manda_resumo_uma_vez_por_dia():
    """Duas linhas: 08:10 sem resumo, 18:10 com. Se o `--resumo` voltar para a
    linha de dois horários, ele vira duas mensagens diárias para sempre."""
    cron = subprocess.run(["crontab", "-l"], capture_output=True, text=True).stdout
    linhas = [l for l in cron.splitlines()
              if "agentes_mudos" in l and not l.strip().startswith("#")]
    assert len(linhas) == 2, linhas
    com = [l for l in linhas if "--resumo" in l]
    assert len(com) == 1
    assert com[0].startswith("10 18 "), com[0]
    sem = [l for l in linhas if "--resumo" not in l][0]
    assert sem.startswith("10 8 "), sem
