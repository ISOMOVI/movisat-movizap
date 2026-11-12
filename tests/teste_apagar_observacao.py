"""APAGAR OBSERVAÇÃO DO CARD — 11/11.

🔵 Dele: *"Permitir excluir OBS's, porém manter os logs e somente owner pode
visualizar o exlcuido, com botão, como no chat interno, sem que vejam essa
informação. Se excluírem, aparecerá como 'Observação excluida' e log's."*
E as três respostas do mesmo dia: apaga **todos que têm acesso à visualização do
painel**, **sem janela de tempo**, e **a autoria fica visível** (*"é um dos
objetivos, rastreabilidade"*).

🚨 ESCREVE EM TABELAS DE PRODUÇÃO (`os_observacao`, `os_observacao_arquivo`,
`atendente`) e apaga tudo no fim. Marcas: OS na faixa **99.904.x**, login
`zz_teste_apagar_`.

O que estas travas guardam:
  · o texto **não é destruído** -- quem esconde é a leitura;
  · quem **não é owner** perde o conteúdo E o anexo, mas **mantém a autoria**;
  · o **owner** continua vendo;
  · `eu` nulo recebe a versão **fechada** -- falha no lado seguro;
  · apagar **duas vezes** não rouba a autoria do primeiro;
  · **sem janela de tempo**, ao contrário das 48 h do chat interno;
  · o **anexo de recado apagado não se baixa** (senão o apagar é de mentira).
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, "/home/claude/movizap_painel")
pytest.importorskip("psycopg")

from movizap import banco, operacao, passagem  # noqa: E402
from movizap.operacao import DadoInvalido  # noqa: E402

ENV = Path("/home/claude/movizap_painel/.env")
pytestmark = pytest.mark.skipif(
    not ENV.exists() or "MOVIZAP_DB_SENHA" not in ENV.read_text(encoding="utf-8"),
    reason="banco nao configurado no .env")

LOGIN = "zz_teste_apagar_"
OS1 = 99_904_101
TEXTO = "zz recado que vai ser apagado"


def limpar():
    banco.executar(
        """DELETE FROM os_observacao_arquivo WHERE observacao_id IN
             (SELECT id FROM os_observacao WHERE numero_os = %s)""", (OS1,))
    banco.executar("DELETE FROM os_observacao WHERE numero_os = %s", (OS1,))
    banco.executar("DELETE FROM atendente WHERE login LIKE %s", (LOGIN + "%",))


@pytest.fixture(scope="module", autouse=True)
def base():
    banco.abrir()
    limpar()
    yield
    banco.abrir()
    limpar()


@pytest.fixture
def gente():
    limpar()
    autor = operacao.criar_atendente("Zz Autor", LOGIN + "a",
                                     LOGIN + "a@teste.invalid")
    outro = operacao.criar_atendente("Zz Outro", LOGIN + "b",
                                     LOGIN + "b@teste.invalid")
    dono = operacao.criar_atendente("Zz Dono", LOGIN + "o",
                                    LOGIN + "o@teste.invalid")
    # 🚨 O OWNER NAO SE ESCREVE: a coluna `atendente.owner` e GERADA
    # (`perfil = 'owner'`, migracao 025), e o banco recusa `SET owner = true`
    # com `GeneratedAlways`. Quem faz alguem owner e o PERFIL.
    # ⚠️ Minha primeira versao desta fixture tentava escrever a coluna, e as 15
    # travas cairam no setup -- fixture irreal, pega pela propria suite.
    banco.executar("UPDATE atendente SET perfil = 'owner' WHERE id = %s",
                   (dono["id"],))
    return {"autor": autor, "outro": outro, "dono": dono}


def um_recado(quem):
    passagem.observar(OS1, TEXTO, quem["id"])
    return passagem.observacoes(OS1, eu=quem["id"])[0]


class TestApagar:
    def test_marca_quem_apagou_e_quando(self, gente):
        r = um_recado(gente["autor"])
        passagem.apagar_observacao(r["id"], gente["outro"]["id"])
        linha = banco.um(
            "SELECT apagada_em, apagada_por FROM os_observacao WHERE id = %s",
            (r["id"],))
        assert linha["apagada_em"] is not None
        assert linha["apagada_por"] == gente["outro"]["id"]

    def test_o_TEXTO_NAO_e_destruido_no_banco(self, gente):
        """🚨 É isto que torna a decisão reversível e o owner capaz de ver."""
        r = um_recado(gente["autor"])
        passagem.apagar_observacao(r["id"], gente["outro"]["id"])
        linha = banco.um("SELECT texto FROM os_observacao WHERE id = %s",
                         (r["id"],))
        assert linha["texto"] == TEXTO

    def test_qualquer_pessoa_apaga_o_recado_de_outra(self, gente):
        """🔵 *"todos que tem acesso a visualização do painel"* -- diferente do
        chat interno, onde só o autor apaga."""
        r = um_recado(gente["autor"])
        passagem.apagar_observacao(r["id"], gente["outro"]["id"])
        assert passagem.observacoes(OS1, eu=gente["dono"]["id"])[0]["apagada_em"]

    def test_SEM_janela_de_tempo(self, gente):
        """🔵 *"não tem não, pode ser apagada conforme disponivel mesmo"* --
        o chat interno recusa depois de 48 h; aqui não há recusa por tempo."""
        r = um_recado(gente["autor"])
        banco.executar(
            "UPDATE os_observacao SET em = now() - interval '400 days' "
            "WHERE id = %s", (r["id"],))
        passagem.apagar_observacao(r["id"], gente["outro"]["id"])
        assert banco.um("SELECT apagada_em FROM os_observacao WHERE id = %s",
                        (r["id"],))["apagada_em"]

    def test_apagar_duas_vezes_recusa_e_NAO_rouba_a_autoria(self, gente):
        r = um_recado(gente["autor"])
        passagem.apagar_observacao(r["id"], gente["outro"]["id"])
        antes = banco.um(
            "SELECT apagada_em, apagada_por FROM os_observacao WHERE id = %s",
            (r["id"],))
        with pytest.raises(DadoInvalido) as e:
            passagem.apagar_observacao(r["id"], gente["dono"]["id"])
        assert "já estava excluída" in str(e.value)
        depois = banco.um(
            "SELECT apagada_em, apagada_por FROM os_observacao WHERE id = %s",
            (r["id"],))
        assert depois == antes

    def test_recado_que_nao_existe_recusa_com_frase(self, gente):
        with pytest.raises(DadoInvalido) as e:
            passagem.apagar_observacao(999_999_999, gente["dono"]["id"])
        assert "não existe" in str(e.value)


class TestAQuemALeituraEsconde:
    def test_quem_NAO_e_owner_perde_o_conteudo(self, gente):
        r = um_recado(gente["autor"])
        passagem.apagar_observacao(r["id"], gente["outro"]["id"])
        lido = passagem.observacoes(OS1, eu=gente["outro"]["id"])[0]
        assert lido["texto"] is None

    def test_mas_MANTEM_a_autoria_dos_dois_lados(self, gente):
        """🔵 *"deve ter disponivel exibição da autoria sim, é um dos objetivos,
        rastreabilidade"*. Some o QUE dizia, não QUEM escreveu nem QUEM apagou.
        """
        r = um_recado(gente["autor"])
        passagem.apagar_observacao(r["id"], gente["outro"]["id"])
        lido = passagem.observacoes(OS1, eu=gente["outro"]["id"])[0]
        assert lido["quem"] == "Zz Autor"
        assert lido["apagada_por_nome"] == "Zz Outro"
        assert lido["apagada_em"] is not None
        assert lido["em"] is not None

    def test_o_OWNER_continua_vendo_o_que_dizia(self, gente):
        r = um_recado(gente["autor"])
        passagem.apagar_observacao(r["id"], gente["outro"]["id"])
        lido = passagem.observacoes(OS1, eu=gente["dono"]["id"])[0]
        assert lido["texto"] == TEXTO

    def test_eu_NULO_recebe_a_versao_fechada(self, gente):
        """🚨 Falha no lado seguro: quem chamar sem dizer quem está lendo não
        recebe conteúdo escondido. Nulo não é owner."""
        r = um_recado(gente["autor"])
        passagem.apagar_observacao(r["id"], gente["outro"]["id"])
        assert passagem.observacoes(OS1)[0]["texto"] is None

    def test_o_recado_NAO_apagado_nao_muda_para_ninguem(self, gente):
        r = um_recado(gente["autor"])
        for quem in (gente["autor"], gente["outro"], gente["dono"]):
            lido = passagem.observacoes(OS1, eu=quem["id"])[0]
            assert lido["texto"] == TEXTO
            assert lido["apagada_em"] is None
        assert passagem.observacoes(OS1)[0]["texto"] == TEXTO
        assert r["id"]


class TestOAnexoDoApagado:
    def _com_anexo(self, quem):
        passagem.observar(OS1, TEXTO, quem["id"])
        r = passagem.observacoes(OS1, eu=quem["id"])[0]
        banco.executar(
            """INSERT INTO os_observacao_arquivo
                   (observacao_id, nome_original, caminho, bytes, mime)
               VALUES (%s, 'comprovante-pix.pdf', '/tmp/zz-nao-existe.pdf',
                       10, 'application/pdf')""", (r["id"],))
        return r

    def test_o_anexo_SOME_da_lista_para_quem_nao_e_owner(self, gente):
        """🚨 Deixar `comprovante-pix.pdf` ao lado de "Observação excluída"
        devolveria pela legenda o que o apagar tirou do texto -- é o vazamento
        que o chat interno fechou em 07/10, na mensagem citada."""
        r = self._com_anexo(gente["autor"])
        passagem.apagar_observacao(r["id"], gente["outro"]["id"])
        anexos = passagem.anexos_de([r["id"]])
        assert len(anexos[r["id"]]) == 1, "o anexo continua no banco"
        # e a leitura é que o tira:
        lido = passagem.observacoes(OS1, eu=gente["outro"]["id"])[0]
        lido["anexos"] = anexos.get(lido["id"], [])
        assert passagem._esconder_apagados([lido],
                                           gente["outro"]["id"])[0]["anexos"] == []

    def test_o_owner_continua_com_o_anexo(self, gente):
        r = self._com_anexo(gente["autor"])
        passagem.apagar_observacao(r["id"], gente["outro"]["id"])
        lido = passagem.observacoes(OS1, eu=gente["dono"]["id"])[0]
        lido["anexos"] = passagem.anexos_de([r["id"]]).get(r["id"], [])
        assert len(passagem._esconder_apagados(
            [lido], gente["dono"]["id"])[0]["anexos"]) == 1

    def test_anexo_e_de_apagada_responde_a_pergunta_do_download(self, gente):
        """🚨 A lista esconder não basta: a rota de download aceita um id, e
        esse id esteve na tela de quem viu o recado antes de apagarem."""
        r = self._com_anexo(gente["autor"])
        anexo_id = passagem.anexos_de([r["id"]])[r["id"]][0]["id"]
        assert passagem.anexo_e_de_apagada(anexo_id) is False
        passagem.apagar_observacao(r["id"], gente["outro"]["id"])
        assert passagem.anexo_e_de_apagada(anexo_id) is True


class TestOChamadoTambem:
    """⚠️ O recado de CHAMADO tem outro dono (`solicitacao_id`, migração 092),
    e a regra de esconder precisa valer nos DOIS caminhos -- regra que mora na
    rota é regra que o segundo caminho esquece."""

    def test_o_recado_do_chamado_esconde_igual(self, gente):
        f = banco.um("SELECT id FROM formulario WHERE slug = 'suporte'")
        s = banco.um(
            """INSERT INTO formulario_solicitacao (formulario_id, valores)
               VALUES (%s, '{}'::jsonb) RETURNING id""", (f["id"],))
        try:
            linha = banco.um(
                """INSERT INTO os_observacao (solicitacao_id, texto, atendente_id)
                   VALUES (%s, %s, %s) RETURNING id""",
                (s["id"], TEXTO, gente["autor"]["id"]))
            passagem.apagar_observacao(linha["id"], gente["outro"]["id"])

            fechado = passagem.observacoes_da_solicitacao(
                s["id"], eu=gente["outro"]["id"])[0]
            assert fechado["texto"] is None
            assert fechado["apagada_por_nome"] == "Zz Outro"

            aberto = passagem.observacoes_da_solicitacao(
                s["id"], eu=gente["dono"]["id"])[0]
            assert aberto["texto"] == TEXTO
        finally:
            banco.executar("DELETE FROM formulario_solicitacao WHERE id = %s",
                           (s["id"],))
