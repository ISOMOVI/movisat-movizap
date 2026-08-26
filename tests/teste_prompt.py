"""Testes do versionamento do prompt da IA — CFG_2.1.

🚨 Estes testes escrevem em `prompt_versao`, que é tabela de produção, e um
deles PUBLICA. Publicar mexe no que estaria valendo: por isso a fixture guarda
qual versão estava ativa antes e a devolve no fim. Sem isso, rodar a suíte
deixaria a IA apontando para um texto de teste — e nada falharia para avisar.

⚠️ Nada aqui chama modelo nenhum. O módulo `prompt` continua sendo só texto
versionado, mesmo depois de o motor entrar em 26/08: quem fala com o modelo é
`movizap/ia.py`, e quem sabe da chave é `movizap/llm/`.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, "/home/claude/movizap_painel")
pytest.importorskip("psycopg")

from movizap import banco, prompt  # noqa: E402

ENV = Path("/home/claude/movizap_painel/.env")
pytestmark = pytest.mark.skipif(
    not ENV.exists() or "MOVIZAP_DB_SENHA" not in ENV.read_text(encoding="utf-8"),
    reason="banco nao configurado no .env")

MARCA = "PROMPT DE TESTE zz_teste_ -- nao e conteudo real, pode apagar. "
TEXTO = MARCA + "x" * 80


@pytest.fixture(scope="module", autouse=True)
def pool():
    banco.abrir()
    antes = banco.um("SELECT id FROM prompt_versao WHERE ativo")
    yield
    banco.executar("DELETE FROM prompt_versao WHERE conteudo LIKE %s", (MARCA + "%",))
    # devolve o estado: se havia uma ativa, ela volta a ser a ativa
    if antes:
        banco.executar("UPDATE prompt_versao SET ativo = false WHERE ativo")
        banco.executar("UPDATE prompt_versao SET ativo = true WHERE id = %s",
                       (antes["id"],))
    banco.fechar()


def test_texto_curto_demais_nao_vira_versao():
    with pytest.raises(ValueError):
        prompt.criar("curto")


def test_versao_nova_nao_sobrescreve_a_anterior():
    """Gravar sempre cria a próxima. É o que torna respondível "o que ela
    estava lendo naquele dia?"."""
    primeira = prompt.criar(TEXTO + " um")
    segunda = prompt.criar(TEXTO + " dois")
    assert segunda["versao"] == primeira["versao"] + 1
    assert prompt.ver(primeira["id"])["conteudo"].endswith("um")


def test_rascunho_nao_publica_sozinho():
    rascunho = prompt.criar(TEXTO + " rascunho", publicar_agora=False)
    assert rascunho["ativo"] is False


def test_publicar_deixa_exatamente_uma_ativa():
    a = prompt.criar(TEXTO + " a", publicar_agora=True)
    b = prompt.criar(TEXTO + " b", publicar_agora=True)
    assert prompt.ver(a["id"])["ativo"] is False
    assert prompt.ver(b["id"])["ativo"] is True
    assert banco.um("SELECT COUNT(*) AS n FROM prompt_versao WHERE ativo")["n"] == 1


def test_voltar_para_a_anterior_e_republicar():
    a = prompt.criar(TEXTO + " velha", publicar_agora=True)
    prompt.criar(TEXTO + " nova", publicar_agora=True)
    prompt.publicar(a["id"])
    assert prompt.ativa()["id"] == a["id"]


def test_montado_troca_a_marca_pelos_times_de_verdade():
    """🚨 A camada 5 é montada na hora, não copiada para dentro da versão:
    time criado depois passaria a faltar num prompt congelado."""
    marca = "(As descrições dos times entram aqui automaticamente, do CAD_2.2.)"
    versao = prompt.criar(TEXTO + "\n" + marca, publicar_agora=True)
    montado = prompt.montado(versao["id"])
    assert marca not in montado["texto"]
    nomes = [t["nome"] for t in banco.varios("SELECT nome FROM time WHERE ativo")]
    assert nomes, "sem time ativo não dá para provar a montagem"
    assert nomes[0] in montado["texto"]


def test_sem_a_marca_os_times_entram_no_fim():
    versao = prompt.criar(TEXTO + " sem marca nenhuma")
    montado = prompt.montado(versao["id"])
    assert "TIMES DISPONÍVEIS" in montado["texto"]


def test_estado_mostra_que_a_ia_esta_desligada():
    """🚨 Ter prompt publicado NÃO é a IA estar no ar. Quem decide é
    `canal.ia_ligada`, por canal.

    ⚠️ ATÉ 25/08 ESTE TESTE EXIGIA `motor_existe is False`, e estava certo: não
    havia motor. Em 26/08 o motor entrou e a exigência virou mentira sobre o
    mundo — o teste reprovaria código correto. O que ele defende continua
    idêntico e é a linha de baixo: **motor existir não liga a IA para
    ninguém.**
    """
    from movizap import ia

    estado = prompt.estado()
    assert estado["motor_existe"] == ia.estado()["disponivel"], \
        "motor_existe é medido, não escrito -- literal aqui apodrece em silêncio"
    assert estado["canais"], "nenhum canal ativo para responder pela IA"
    assert all(c["ia_ligada"] is False for c in estado["canais"]), \
        "algum canal está com a IA ligada -- isso é decisão do usuário, não do código"


def test_sugestao_inicial_traz_as_sete_camadas():
    for camada in ("QUEM SOMOS", "O QUE VOCÊ PODE FAZER", "O QUE VOCÊ NÃO PODE FAZER",
                   "COMO TRIAR", "PARA ONDE MANDAR", "QUANDO CALAR",
                   "LIMITES DO CANAL"):
        assert camada in prompt.SUGESTAO_INICIAL
