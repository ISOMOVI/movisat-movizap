"""`ligacoes.agentes_vivos_resumo()`: os numeros do resumo diario do vigia."""
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
ALVO = RAIZ / "movizap" / "ligacoes.py"

ANCORA = "def agentes_mudos("
NOVO = '''def agentes_vivos_resumo() -> dict:
    """Os números do resumo diário do vigia (15/10).

    🔵 Pedido dele: um resumo quando está tudo em dia -- antes o vigia ficava
    mudo, e silêncio não distingue "nada errado" de "o cron parou de rodar".

    🚨 DIZ O NÚMERO, não "tudo ok". A frase que não conta nada não distingue
    vigia funcionando de vigia olhando para uma base vazia -- e era disso que
    ele estava se protegendo ao pedir o resumo.
    """
    return dict(banco.um(
        """SELECT (SELECT count(*) FROM agente_ligacao
                    WHERE revogado_em IS NULL)                      AS com_agente,
                  (SELECT count(*) FROM atendente a
                    WHERE a.ativo AND NOT EXISTS (
                      SELECT 1 FROM agente_ligacao g
                       WHERE g.atendente_id = a.id
                         AND g.revogado_em IS NULL))                 AS sem_agente,
                  (SELECT count(*) FROM ligacao
                    WHERE inicio >= date_trunc('day', now()))        AS ligacoes_hoje"""))


'''

texto = ALVO.read_text(encoding="utf-8")
if "def agentes_vivos_resumo(" in texto:
    print("ja aplicado")
else:
    assert texto.count(ANCORA) == 1, f"ancora {texto.count(ANCORA)}x"
    novo = texto.replace(ANCORA, NOVO + ANCORA, 1)
    compile(novo, str(ALVO), "exec")
    ALVO.write_text(novo, encoding="utf-8")
    print("aplicado: ligacoes.agentes_vivos_resumo()")
