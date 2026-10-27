"""A pasta de coleta do agente: diagnóstico e canal de volta (bloco D, 26/10).

🔵 *"veja se da para atualizar do lado de ca para os computadores o local de
coleta das ligações gravadas"* e *"que permita inserir mais endereços por aqui
ou buscar pelo nome da pasta, pedindo permissão ao instalar"*.

🚨 ESCREVE EM TABELAS DE PRODUÇÃO (`agente_ligacao`, `atendente`) e apaga tudo
no fim. Marca deste teste: ramais `997xx`, login `zz_teste_pasta_`.

O que estes testes guardam:
  · 🚨 **o batimento deixou de ser só de ida** — a resposta carrega
    `config.pastas`, e é o que torna possível mandar o caminho daqui;
  · o diagnóstico é OPCIONAL: agente velho continua batendo sem ele, e nada
    falha (exigi-lo derrubaria a coleta dos 7 PCs para ganhar um rótulo);
  · `pasta_origem` fora da lista vira **nulo**, não erro — o CHECK da migração
    078 recusaria, e perder a gravação é pior que perder o rótulo;
  · **"agente antigo" ≠ "sem pasta"**: nulo significa que o PC não sabe
    contar, não que não há pasta;
  · o REC passa a **preferir o dado explícito**, e a dedução por ausência de
    aviso fica só para agente velho;
  · 🚨 **só o owner escreve o caminho** — a aba é `atendimento`, e "todo
    atendente vê a aba" não pode virar "todo atendente aponta o agente do
    colega para onde quiser";
  · a tela sabe se o PC vai **obedecer** (o `0.4` descarta a resposta).
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, "/home/claude/movizap_painel")
pytest.importorskip("psycopg")

from fastapi.testclient import TestClient  # noqa: E402

from movizap import (auth, banco, ligacoes, ligacoes_consulta, main,  # noqa: E402
                     operacao)
from movizap.config import settings  # noqa: E402

ENV = Path("/home/claude/movizap_painel/.env")
pytestmark = pytest.mark.skipif(
    not ENV.exists() or "MOVIZAP_DB_SENHA" not in ENV.read_text(encoding="utf-8"),
    reason="banco nao configurado no .env")

LOGIN = "zz_teste_pasta_"
RAMAL = "99701"


def limpar():
    banco.executar("DELETE FROM agente_ligacao WHERE ramal LIKE %s", ("997%",))
    banco.executar("DELETE FROM atendente WHERE login LIKE %s", (LOGIN + "%",))


@pytest.fixture(scope="module", autouse=True)
def base():
    banco.abrir()
    limpar()
    pessoa = operacao.criar_atendente("Zz Pasta Um", LOGIN + "1",
                                      LOGIN + "1@teste.invalid")
    chave = ligacoes.gerar_chave(pessoa["id"], RAMAL)
    agente = ligacoes.agente_da_chave(chave)
    yield {"pessoa": pessoa, "agente": agente, "chave": chave}
    banco.abrir()
    limpar()


def recarregar(agente_id):
    return banco.um("SELECT * FROM agente_ligacao WHERE id = %s", (agente_id,))


# ---------------------------------------------------------------------------
# [1] O BATIMENTO DEIXOU DE SER SÓ DE IDA
# ---------------------------------------------------------------------------
class TestCanalDeVolta:
    def test_a_resposta_carrega_config(self, base):
        """🚨 Até 26/10 o batimento devolvia `{ok, ramal, servidor_em}` e o
        agente DESCARTAVA a resposta. É esta chave que torna possível
        *"atualizar do lado de cá o local de coleta"*."""
        r = ligacoes.batimento(base["agente"], "PC-TESTE", "0.7", 0, None)
        assert "config" in r
        assert r["config"]["pastas"] == []

    def test_o_que_a_vps_manda_volta_no_batimento(self, base):
        ligacoes.definir_pastas_extra(base["agente"]["id"],
                                      [r"C:\Users\Zz\OneDrive\Recordings"])
        r = ligacoes.batimento(base["agente"], "PC-TESTE", "0.7", 0, None)
        assert r["config"]["pastas"] == [r"C:\Users\Zz\OneDrive\Recordings"]
        ligacoes.definir_pastas_extra(base["agente"]["id"], [])

    def test_lista_vazia_quer_dizer_NAO_INTERFIRO(self, base):
        """É o estado de todos os 7 PCs hoje, e tem de ser o padrão: a VPS não
        manda caminho até alguém mandar."""
        ligacoes.definir_pastas_extra(base["agente"]["id"], [])
        assert ligacoes.pastas_extra(base["agente"]["id"]) == []


# ---------------------------------------------------------------------------
# [2] O DIAGNÓSTICO É OPCIONAL — agente velho não pode quebrar
# ---------------------------------------------------------------------------
class TestDiagnostico:
    def test_agente_velho_bate_sem_os_campos_novos(self, base):
        """⚠️ Os 7 PCs rodam o `0.4`. Exigir os campos novos derrubaria a
        coleta inteira para ganhar um diagnóstico."""
        r = ligacoes.batimento(base["agente"], "PC-VELHO", "0.4", 0, None)
        assert r["ok"] is True

    def test_grava_o_caminho_e_como_decidiu(self, base):
        ligacoes.batimento(base["agente"], "PC-TESTE", "0.7", 0, None,
                           pasta=r"C:\Users\Zz\Desktop\Recordings",
                           pasta_origem="ini", auto_gravacao=True)
        linha = recarregar(base["agente"]["id"])
        assert linha["pasta"] == r"C:\Users\Zz\Desktop\Recordings"
        assert linha["pasta_origem"] == "ini"
        assert linha["auto_gravacao"] is True

    def test_origem_desconhecida_vira_NULO_e_nao_erro(self, base):
        """🚨 O CHECK da migração 078 recusaria, e um agente com versão nova
        demais não pode fazer o batimento falhar: perder a gravação é pior que
        perder o rótulo."""
        r = ligacoes.batimento(base["agente"], "PC-TESTE", "9.9", 0, None,
                               pasta=r"C:\x", pasta_origem="inventada")
        assert r["ok"] is True
        # ⚠️ `COALESCE` preserva o que já havia; o que se prova é que não
        # estourou e que o valor inválido não entrou.
        assert recarregar(base["agente"]["id"])["pasta_origem"] in (None, "ini")

    def test_o_que_nao_veio_NAO_apaga_o_que_havia(self, base):
        """⚠️ `COALESCE`: um batimento sem os campos (agente velho, ou uma
        passada que não mediu) não pode apagar o diagnóstico da passada boa."""
        ligacoes.batimento(base["agente"], "PC", "0.7", 0, None,
                           pasta=r"C:\guardado", pasta_origem="busca")
        ligacoes.batimento(base["agente"], "PC", "0.7", 0, None)
        assert recarregar(base["agente"]["id"])["pasta"] == r"C:\guardado"

    def test_teto_de_dez_caminhos_e_sem_repetido(self, base):
        gravadas = ligacoes.definir_pastas_extra(
            base["agente"]["id"],
            [f"C:\\p{i}" for i in range(15)] + [r"C:\p0"])
        assert len(gravadas) <= 10
        assert len(gravadas) == len(set(x.lower() for x in gravadas))
        ligacoes.definir_pastas_extra(base["agente"]["id"], [])

    def test_caminho_vazio_e_espaco_saem(self, base):
        gravadas = ligacoes.definir_pastas_extra(
            base["agente"]["id"], ["   ", "", r"  C:\limpo  "])
        assert gravadas == [r"C:\limpo"]
        ligacoes.definir_pastas_extra(base["agente"]["id"], [])


# ---------------------------------------------------------------------------
# [3] A FAIXA DE COBERTURA — e "agente antigo" ≠ "sem pasta"
# ---------------------------------------------------------------------------
class TestFaixa:
    def _meu(self):
        return next(a for a in ligacoes_consulta.agentes()
                    if a.get("ramal") == RAMAL)

    def test_a_faixa_traz_o_caminho_e_a_explicacao(self, base):
        ligacoes.batimento(base["agente"], "PC", "0.7", 0, None,
                           pasta=r"C:\Users\Zz\Desktop\Recordings",
                           pasta_origem="ini", auto_gravacao=True)
        info = self._meu()["pasta_info"]
        assert info["caminho"] == r"C:\Users\Zz\Desktop\Recordings"
        assert info["rotulo"] == "lida do MicroSIP"
        # A tela não escreve a própria versão do recado.
        assert "recordingPath" in info["explicacao"]
        assert info["atencao"] is False

    def test_PALPITE_pede_atencao_e_nomeia_o_OneDrive(self, base):
        """🚨 É o caso que motivou esta frente: o agente chutava a Área de
        Trabalho, e com OneDrive ela muda de lugar."""
        banco.executar("UPDATE agente_ligacao SET pasta_origem = 'palpite' "
                       " WHERE id = %s", (base["agente"]["id"],))
        info = self._meu()["pasta_info"]
        assert info["atencao"] is True
        assert "OneDrive" in info["explicacao"]

    def test_sem_informacao_e_AGENTE_ANTIGO_nao_sem_pasta(self, base):
        """⚠️ Nulo significa que o PC não sabe contar onde procura — não que
        não haja pasta. Ele pode estar coletando perfeitamente."""
        banco.executar("UPDATE agente_ligacao SET pasta = NULL, "
                       "    pasta_origem = NULL WHERE id = %s",
                       (base["agente"]["id"],))
        assert self._meu()["pasta_info"] is None

    def test_a_tela_escreve_agente_antigo_e_nao_sem_pasta(self):
        """`M13`: lê a TELA, não o seletor.

        ⚠️ MEDE O TEXTO QUE A PESSOA VÊ, sem os comentários: a frase "sem
        pasta" aparece no comentário que explica **por que** ela não é usada, e
        a primeira versão deste teste reprovou nesse próprio comentário --
        quarta vez no dia que um padrão largo meu acusa o código certo.
        """
        import re as _re
        tela = Path("/home/claude/movizap_painel/frontend/src/telas/Ligacoes.vue")
        fonte = tela.read_text(encoding="utf-8")
        # ⚠️ `rsplit`, não `split`: arquivo Vue tem `<template v-if>` dentro
        # do template, e cortar no PRIMEIRO `</template>` jogava metade da tela
        # fora -- inclusive a parte que este teste veio medir. Foi o que
        # aconteceu aqui, e o `-x` do pytest é que mostrou.
        template = fonte.split("<template>")[1].rsplit("</template>", 1)[0]
        visivel = _re.sub(r"<!--.*?-->", "", template, flags=_re.S)
        assert "agente antigo" in visivel
        assert "sem pasta" not in visivel


# ---------------------------------------------------------------------------
# [4] O REC passa a preferir o dado explícito
# ---------------------------------------------------------------------------
class TestRec:
    def test_explicito_ganha_da_deducao(self, base):
        """🚨 Até hoje "ligado" era deduzido da AUSÊNCIA de um aviso de texto.
        Isso quebra de dois jeitos: muda a frase do agente e a dedução
        inverte; chega aviso novo sobre outra coisa e o REC "desliga" sozinho.
        """
        linha = {"agente_id": 1, "ultimo_contato_em": "agora",
                 "ultimo_aviso": "gravacao automatica desligada no MicroSIP",
                 "auto_gravacao": True}
        assert ligacoes_consulta.rec_do_agente(linha) == "ligado"

    def test_explicito_desligado_tambem_ganha(self, base):
        linha = {"agente_id": 1, "ultimo_contato_em": "agora",
                 "ultimo_aviso": "", "auto_gravacao": False}
        assert ligacoes_consulta.rec_do_agente(linha) == "desligado"

    def test_sem_explicito_cai_na_deducao_de_antes(self, base):
        """⚠️ É o que vale para os 7 PCs de hoje, e é o melhor que existe para
        eles."""
        assert ligacoes_consulta.rec_do_agente(
            {"agente_id": 1, "ultimo_contato_em": "agora",
             "ultimo_aviso": "gravacao automatica desligada",
             "auto_gravacao": None}) == "desligado"
        assert ligacoes_consulta.rec_do_agente(
            {"agente_id": 1, "ultimo_contato_em": "agora",
             "ultimo_aviso": None, "auto_gravacao": None}) == "ligado"

    def test_quem_nunca_falou_continua_DESCONHECIDO(self, base):
        assert ligacoes_consulta.rec_do_agente(
            {"agente_id": 1, "ultimo_contato_em": None,
             "auto_gravacao": None}) == "desconhecido"


# ---------------------------------------------------------------------------
# [5] A ROTA — e a trava de owner
# ---------------------------------------------------------------------------
@pytest.fixture
def cliente():
    with TestClient(main.app) as c:
        yield c


@pytest.fixture
def cab():
    return {"Authorization": f"Bearer {auth.criar_token(settings.admin_login)}"}


class TestRota:
    def test_exige_token(self, cliente, base):
        r = cliente.put(f"/api/ligacoes/agentes/{base['agente']['id']}/pastas",
                        json={"pastas": [r"C:\x"]})
        assert r.status_code in (401, 403)

    def test_o_owner_grava(self, cliente, cab, base):
        r = cliente.put(f"/api/ligacoes/agentes/{base['agente']['id']}/pastas",
                        headers=cab, json={"pastas": [r"C:\Users\Zz\Recordings"]})
        assert r.status_code == 200
        assert r.json()["pastas"] == [r"C:\Users\Zz\Recordings"]

    def test_a_resposta_diz_se_o_PC_VAI_OBEDECER(self, cliente, cab, base):
        """🚨 O agente `0.4` descarta a resposta do batimento. Gravar e deixar
        a pessoa achar que resolveu seria a tela mentindo."""
        banco.executar("UPDATE agente_ligacao SET ultima_versao = '0.4' "
                       " WHERE id = %s", (base["agente"]["id"],))
        corpo = cliente.put(
            f"/api/ligacoes/agentes/{base['agente']['id']}/pastas",
            headers=cab, json={"pastas": [r"C:\x"]}).json()
        assert corpo["obedece"] is False
        assert corpo["versao_no_pc"] == "0.4"

        banco.executar("UPDATE agente_ligacao SET ultima_versao = '0.7' "
                       " WHERE id = %s", (base["agente"]["id"],))
        corpo = cliente.put(
            f"/api/ligacoes/agentes/{base['agente']['id']}/pastas",
            headers=cab, json={"pastas": [r"C:\x"]}).json()
        assert corpo["obedece"] is True

    def test_agente_inexistente_e_404(self, cliente, cab):
        r = cliente.put("/api/ligacoes/agentes/999999999/pastas",
                        headers=cab, json={"pastas": []})
        assert r.status_code == 404

    def test_a_rota_NAO_usa_a_permissao_da_aba(self, base):
        """🚨 A `LIG_1.1` é `atendimento`, aberta a todo atendente por decisão
        dele de 15/10. Este campo manda um programa no PC de outra pessoa ler
        uma pasta e subir o conteúdo -- "todo atendente vê a aba" não pode
        virar "todo atendente aponta o agente do colega para onde quiser".
        """
        from fastapi.routing import APIRoute
        for r in main.app.routes:
            if (isinstance(r, APIRoute)
                    and r.path == "/api/ligacoes/agentes/{agente_id}/pastas"):
                nomes = [d.call.__name__ for d in r.dependant.dependencies]
                # `get_usuario` + checagem de owner dentro, nunca `requer_tela`.
                assert "get_usuario" in nomes
                fonte = Path("/home/claude/movizap_painel/movizap/main.py") \
                    .read_text(encoding="utf-8")
                trecho = fonte.split("def definir_pastas_do_agente")[1][:1500]
                assert 'usuario.get("owner")' in trecho
                return
        raise AssertionError("a rota das pastas não existe")
