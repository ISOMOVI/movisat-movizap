"""O vínculo do contato técnico com o cadastro do Harmonit — 21/10.

🔵 Pedido dele: *"podemos pensar em um vínculo de dados técnicos dentro do
cadastro do tipo 'técnico', assim já traz sugerido pelo número dele"*.
🔵 Decisões dele: a varredura **nasce ligada**, e a chave tenta **9 dígitos e
depois 8**, vinculando **só com candidato único**.

🚨 ESCREVE EM `contato` DE PRODUÇÃO, com marca própria, e apaga no fim. E
**não lê nem escreve a `config` real**: o interruptor chega por parâmetro,
como `distribuicao.distribuir(cfg=...)` -- foi um teste meu escrevendo lá que
desligou a distribuição por nove minutos em 19/10.

🚨 NÃO FALA COM O FPSL: a lista de técnicos é injetada. O que se mede é a
regra, não a rede.

O que estes testes guardam:
  · 9 dígitos e, falhando, 8 -- o número antigo sem o nono (ganha 7 vínculos);
  · candidato ambíguo **não vincula nada** (o estrago seria pôr o orçamento no
    nome de outra pessoa);
  · vínculo `manual` **nunca** é tocado pela varredura -- é o que sustenta a
    exceção dele (6168 → Iago, que por telefone jamais casaria);
  · a varredura **não muda o `relacao`** do contato;
  · conta interna (e-mail não numérico) não casa por acidente.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, "/home/claude/movizap_painel")
pytest.importorskip("psycopg")

from movizap import banco, tecnico_vinculo  # noqa: E402

ENV = Path("/home/claude/movizap_painel/.env")
pytestmark = pytest.mark.skipif(
    not ENV.exists() or "MOVIZAP_DB_SENHA" not in ENV.read_text(encoding="utf-8"),
    reason="banco nao configurado no .env")

MARCA = "Zz Teste Vinculo"
LIGADA = {tecnico_vinculo.CHAVE_LIGADO: "true"}

# O cadastro fingido, no formato que a ponte devolve.
FRANCK = {"tecnico_id": 14262, "nome": "Franck",
          "email": "997394026@movisat.com.br", "excluido": False,
          "chave": "997394026"}
ANTIGO = {"tecnico_id": 999001, "nome": "Zz Tecnico Antigo",
          "email": "33445566@movisat.com.br", "excluido": False,
          "chave": "33445566"}
IAGO = {"tecnico_id": 7493, "nome": "Iago Santos do Ó Souza",
        "email": "iago@movisat.com.br", "excluido": True, "chave": ""}
CADASTRO = [FRANCK, ANTIGO, IAGO]


def limpar():
    banco.executar(
        """DELETE FROM contato_telefone WHERE contato_id IN
            (SELECT id FROM contato WHERE nome LIKE %s)""", (MARCA + "%",))
    banco.executar("DELETE FROM contato WHERE nome LIKE %s", (MARCA + "%",))


def criar_contato(nome: str, e164: str, relacao: str = "tecnico") -> int:
    with banco.cursor() as cur:
        cur.execute("""INSERT INTO contato (nome, relacao, origem, ativo)
                       VALUES (%s, %s, 'movizap', true) RETURNING id""",
                    (f"{MARCA} {nome}", relacao))
        contato_id = cur.fetchone()["id"]
        cur.execute("""INSERT INTO contato_telefone (contato_id, e164, bruto,
                                                     principal)
                       VALUES (%s, %s, %s, true)""", (contato_id, e164, e164))
    return contato_id


@pytest.fixture(scope="module", autouse=True)
def base():
    banco.abrir()
    limpar()
    yield
    limpar()


class TestAChave:
    def test_nove_digitos_primeiro_depois_oito(self):
        assert tecnico_vinculo.chaves_do_telefone("+5519997394026") == [
            "997394026", "97394026"]

    def test_numero_antigo_so_tem_a_de_oito(self):
        """O número sem o nono dígito — é o que ganha os 7 vínculos."""
        assert tecnico_vinculo.chaves_do_telefone("+551933445566") == [
            "933445566", "33445566"]

    def test_telefone_curto_nao_vira_chave(self):
        assert tecnico_vinculo.chaves_do_telefone("4026") == []
        assert tecnico_vinculo.chaves_do_telefone(None) == []


class TestOCasamento:
    def setup_method(self):
        self.indice = tecnico_vinculo._indice(CADASTRO)

    def test_casa_pelos_nove(self):
        achado, _ = tecnico_vinculo.casar("+5519997394026", self.indice)
        assert achado["tecnico_id"] == 14262

    def test_casa_pelos_oito_quando_os_nove_falham(self):
        achado, _ = tecnico_vinculo.casar("+551933445566", self.indice)
        assert achado["tecnico_id"] == 999001

    def test_conta_interna_NAO_casa(self):
        """🚨 Se casasse, todo usuário do sistema viraria técnico."""
        achado, motivo = tecnico_vinculo.casar("+5518998116168", self.indice)
        assert achado is None
        assert "nenhum tecnico" in motivo

    def test_dois_candidatos_NAO_vinculam_nada(self):
        """🔵 Decisão dele: só com candidato único.

        Escolher um no escuro poria o orçamento no nome de outra pessoa.
        """
        gemeo = dict(FRANCK, tecnico_id=999002, nome="Zz Outro Franck")
        indice = tecnico_vinculo._indice([FRANCK, gemeo])
        achado, motivo = tecnico_vinculo.casar("+5519997394026", indice)
        assert achado is None
        assert "mais de um" in motivo

    def test_o_mesmo_tecnico_pelas_duas_chaves_nao_e_ambiguidade(self):
        indice = tecnico_vinculo._indice([FRANCK])
        achado, _ = tecnico_vinculo.casar("+5519997394026", indice)
        assert achado["tecnico_id"] == 14262


class TestAVarredura:
    def test_desligada_nao_faz_nada(self, base):
        r = tecnico_vinculo.uma_passada(
            cfg={tecnico_vinculo.CHAVE_LIGADO: "false"}, tecnicos=CADASTRO)
        assert r == {"ligado": False}

    def test_vincula_e_grava_o_nome_do_cadastro(self, base):
        contato_id = criar_contato("Franck", "+5519997394026")
        tecnico_vinculo.uma_passada(cfg=LIGADA, tecnicos=CADASTRO)
        guardado = tecnico_vinculo.do_contato(contato_id)
        assert guardado["harmonit_tecnico_id"] == 14262
        # 🔵 O nome do CADASTRO, que é o que o orçamento imprime.
        assert guardado["harmonit_tecnico_nome"] == "Franck"
        assert guardado["harmonit_vinculo_origem"] == "automatico"
        assert guardado["harmonit_vinculo_em"] is not None

    def test_a_segunda_passada_MANTEM_em_vez_de_reescrever(self, base):
        criar_contato("Franck Dois", "+5519997394026")
        tecnico_vinculo.uma_passada(cfg=LIGADA, tecnicos=CADASTRO)
        r = tecnico_vinculo.uma_passada(cfg=LIGADA, tecnicos=CADASTRO)
        assert r["mantidos"] >= 1

    def test_NAO_muda_o_tipo_do_contato(self, base):
        """🚨 Trocar `relacao` esconde empresas na ficha e muda regra de
        negócio -- continua sendo clique de gente."""
        contato_id = criar_contato("Sem Tipo", "+5519997394026", relacao="lead")
        tecnico_vinculo.uma_passada(cfg=LIGADA, tecnicos=CADASTRO)
        linha = banco.um("SELECT relacao, harmonit_tecnico_id FROM contato "
                         " WHERE id = %s", (contato_id,))
        # Vinculou (é o pedido dele: servir a quem ainda não tem o tipo)...
        assert linha["harmonit_tecnico_id"] == 14262
        # ...e não mexeu no tipo.
        assert linha["relacao"] == "lead"

    def test_vinculo_MANUAL_nunca_e_tocado(self, base):
        """🚨 É o que sustenta a exceção dele: 6168 → Iago.

        Pelo telefone aquele número nunca acharia o Iago (`iago@` não é
        numérico e está marcado como usuário do sistema).
        """
        contato_id = criar_contato("Excecao", "+5518998116168")
        tecnico_vinculo.vincular(contato_id, IAGO, "manual")
        tecnico_vinculo.uma_passada(cfg=LIGADA, tecnicos=CADASTRO)
        guardado = tecnico_vinculo.do_contato(contato_id)
        assert guardado["harmonit_tecnico_id"] == 7493
        assert guardado["harmonit_vinculo_origem"] == "manual"

    def test_manual_resiste_ate_quando_o_telefone_casaria_com_OUTRO(self, base):
        contato_id = criar_contato("Manual Forte", "+5519997394026")
        tecnico_vinculo.vincular(contato_id, IAGO, "manual")
        tecnico_vinculo.uma_passada(cfg=LIGADA, tecnicos=CADASTRO)
        assert tecnico_vinculo.do_contato(contato_id)["harmonit_tecnico_id"] == 7493

    def test_desvincular_devolve_o_contato_para_a_varredura(self, base):
        contato_id = criar_contato("Solto", "+5519997394026")
        tecnico_vinculo.vincular(contato_id, IAGO, "manual")
        tecnico_vinculo.desvincular(contato_id)
        assert tecnico_vinculo.do_contato(contato_id)["harmonit_tecnico_id"] is None
        tecnico_vinculo.uma_passada(cfg=LIGADA, tecnicos=CADASTRO)
        guardado = tecnico_vinculo.do_contato(contato_id)
        assert guardado["harmonit_tecnico_id"] == 14262
        assert guardado["harmonit_vinculo_origem"] == "automatico"

    def test_origem_invalida_e_recusada(self, base):
        contato_id = criar_contato("Origem", "+5519997394026")
        with pytest.raises(ValueError):
            tecnico_vinculo.vincular(contato_id, FRANCK, "chutado")

    def test_ponte_fora_do_ar_RELATA_em_vez_de_dizer_zero(self, monkeypatch):
        """🚨 Lista vazia aqui viraria "nenhum casou" como se fosse fato."""
        from movizap import fpsl_ponte

        def cai(*a, **k):
            raise fpsl_ponte.FpslIndisponivel("o FPSL não respondeu no tempo")

        monkeypatch.setattr(fpsl_ponte, "tecnicos_do_harmonit", cai)
        r = tecnico_vinculo.uma_passada(cfg=LIGADA)
        assert r["ligado"] is True
        assert "FPSL" in r["erro"]
        assert "novos" not in r
