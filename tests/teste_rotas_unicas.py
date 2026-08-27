"""Duas rotas com o mesmo caminho — a trava de 27/08.

🚨 ESCRITO PORQUE ACONTECEU. Eu registrei um segundo
`GET /api/conversas/{conversa_id}/participantes` sem ver que ele já existia e
significava OUTRA COISA: o primeiro devolve os atendentes convidados para a
conversa; o meu devolvia os participantes do grupo de WhatsApp.

**No FastAPI a primeira registrada vence.** Então a segunda vira código morto —
ela existe, é importada, aparece no fonte, e nunca responde. Nenhum
`py_compile` acusa, nenhum import falha, e o teste que pegou foi um de
permissão que reclamou de um 409 estranho, longe da causa.

⚠️ É PRIMA DAS ARMADILHAS QUE O PROJETO JÁ CATALOGA: "rota literal antes de
rota com parâmetro" e "parâmetro aceito e ignorado". Todas da mesma família —
o roteador aceita, não reclama, e escolhe sozinho.

⚠️ MEDE O APP MONTADO, não o texto do `main.py`. Um `grep` por `@app.get`
contaria decorador comentado e perderia rota registrada em runtime.
"""
import sys
from collections import Counter

sys.path.insert(0, "/home/claude/movizap_painel")

from movizap import main  # noqa: E402


def _caminhos():
    """(método, caminho) de cada rota do app, sem as internas do FastAPI."""
    fora = {"/openapi.json", "/docs", "/docs/oauth2-redirect", "/redoc"}
    pares = []
    for rota in main.app.routes:
        caminho = getattr(rota, "path", None)
        metodos = getattr(rota, "methods", None)
        if not caminho or not metodos or caminho in fora:
            continue
        for metodo in metodos:
            if metodo in ("HEAD", "OPTIONS"):
                continue
            pares.append((metodo, caminho))
    return pares


def test_nenhuma_rota_esta_registrada_duas_vezes():
    """🚨 A trava. Duas iguais = a segunda nunca responde."""
    repetidas = [par for par, n in Counter(_caminhos()).items() if n > 1]
    assert not repetidas, (
        f"caminho registrado mais de uma vez: {repetidas}. No FastAPI a "
        f"PRIMEIRA vence e a segunda vira código morto — que existe, é "
        f"importada e nunca responde.")


def test_o_app_tem_rota_de_verdade():
    """⚠️ Sem isto, o teste acima passaria num app vazio — que é a pior forma
    de passar, e o projeto já foi mordido por ela no `include` do vitest."""
    assert len(_caminhos()) > 50


def test_as_duas_rotas_que_colidiram_continuam_separadas():
    """O caso concreto de 27/08, fixado pelo nome para não voltar."""
    caminhos = {c for _, c in _caminhos()}
    assert "/api/conversas/{conversa_id}/participantes" in caminhos, \
        "os atendentes convidados"
    assert "/api/conversas/{conversa_id}/quem-chamar" in caminhos, \
        "os participantes do grupo de WhatsApp"
