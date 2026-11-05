"""O anexo da observação do card — área D (04/11).

🚨 ESCREVE EM PRODUÇÃO (`os_observacao`, `os_observacao_arquivo`) **e no
disco**, em `/home/claude/movizap_observacao_anexos`. Apaga tudo no fim,
inclusive as pastas que criou. Marca: OS na faixa **99.90x**.

O que estes testes guardam:
  · a lista de extensão é **branca**: o que não está nela não entra;
  · arquivo grande demais e arquivo vazio são recusados **antes** de tocar o
    disco — recusar depois deixaria lixo sem linha no banco;
  · os anexos vêm junto das observações, numa consulta;
  · 🚨 o `caminho` de disco **não sai** para quem lista;
  · arquivo sumido do disco é **410**, não 500 — esta pasta não tem backup.
"""
import shutil
import sys
from pathlib import Path

import pytest

sys.path.insert(0, "/home/claude/movizap_painel")
pytest.importorskip("psycopg")

from movizap import banco, passagem  # noqa: E402
from movizap.operacao import DadoInvalido  # noqa: E402

ENV = Path("/home/claude/movizap_painel/.env")
pytestmark = pytest.mark.skipif(
    not ENV.exists() or "MOVIZAP_DB_SENHA" not in ENV.read_text(encoding="utf-8"),
    reason="banco nao configurado no .env")

OS = 99_901_555


def limpar():
    for r in banco.varios(
            """SELECT a.caminho FROM os_observacao_arquivo a
                 JOIN os_observacao o ON o.id = a.observacao_id
                WHERE o.numero_os = %s""", (OS,)):
        pasta = Path(r["caminho"]).parent
        if pasta.is_dir() and pasta.parent == passagem.PASTA_ANEXOS_OBS:
            shutil.rmtree(pasta, ignore_errors=True)
    banco.executar(
        """DELETE FROM os_observacao_arquivo WHERE observacao_id IN
            (SELECT id FROM os_observacao WHERE numero_os = %s)""", (OS,))
    banco.executar("DELETE FROM os_observacao WHERE numero_os = %s", (OS,))


@pytest.fixture(scope="module", autouse=True)
def base():
    banco.abrir()
    limpar()
    yield
    banco.abrir()
    limpar()


@pytest.fixture
def recado():
    """Um recado novo por teste — cada um monta o próprio estado."""
    passagem.observar(OS, "Zz recado de teste", None)
    return passagem.observacoes(OS)[0]["id"]


class TestGuardar:
    def test_guarda_e_devolve_a_linha(self, recado):
        a = passagem.guardar_anexo(recado, "nota.pdf", b"%PDF-1.4 teste",
                                   "application/pdf")
        assert a["nome_original"] == "nota.pdf"
        assert a["bytes"] == len(b"%PDF-1.4 teste")
        assert Path(a["caminho"]).is_file()

    def test_extensao_fora_da_lista_BRANCA_recusa(self, recado):
        """🚨 Lista branca, nunca negra: o que não está nela não entra."""
        with pytest.raises(DadoInvalido) as e:
            passagem.guardar_anexo(recado, "script.exe", b"MZ")
        assert ".exe" in str(e.value)

    def test_arquivo_sem_extensao_recusa(self, recado):
        with pytest.raises(DadoInvalido):
            passagem.guardar_anexo(recado, "arquivo", b"dados")

    def test_vazio_recusa(self, recado):
        with pytest.raises(DadoInvalido) as e:
            passagem.guardar_anexo(recado, "vazio.txt", b"")
        assert "vazio" in str(e.value)

    def test_grande_demais_recusa_SEM_tocar_o_disco(self, recado):
        """⚠️ Recusar depois de escrever deixaria arquivo sem linha no banco —
        e ninguém acha para apagar."""
        antes = len(list(passagem.PASTA_ANEXOS_OBS.glob("*"))) \
            if passagem.PASTA_ANEXOS_OBS.is_dir() else 0
        with pytest.raises(DadoInvalido) as e:
            passagem.guardar_anexo(recado, "enorme.pdf",
                                   b"x" * (passagem.TETO_ANEXO_OBS + 1))
        assert "limite" in str(e.value)
        depois = len(list(passagem.PASTA_ANEXOS_OBS.glob("*"))) \
            if passagem.PASTA_ANEXOS_OBS.is_dir() else 0
        assert depois == antes

    def test_observacao_inexistente_recusa(self):
        with pytest.raises(DadoInvalido):
            passagem.guardar_anexo(0, "nota.pdf", b"dados")

    def test_o_nome_do_arquivo_nao_escapa_da_pasta(self, recado):
        """🚨 `../../.env` como nome não pode virar caminho — `Path.name` corta
        o diretório, e é por isso que ele está ali."""
        a = passagem.guardar_anexo(recado, "../../.env.txt", b"segredo=nao")
        assert Path(a["caminho"]).parent.parent == passagem.PASTA_ANEXOS_OBS
        assert a["nome_original"] == ".env.txt"


class TestListar:
    def test_os_anexos_vem_por_observacao(self, recado):
        passagem.guardar_anexo(recado, "um.txt", b"a")
        passagem.guardar_anexo(recado, "dois.txt", b"bb")
        mapa = passagem.anexos_de([recado])
        assert len(mapa[recado]) == 2
        assert {a["nome_original"] for a in mapa[recado]} == {"um.txt", "dois.txt"}

    def test_o_CAMINHO_de_disco_nao_sai_na_lista(self, recado):
        """🚨 A tela não tem o que fazer com caminho de disco, e mandar um é
        convidar alguém a tentar abri-lo."""
        passagem.guardar_anexo(recado, "um.txt", b"a")
        item = passagem.anexos_de([recado])[recado][0]
        assert "caminho" not in item
        assert set(item) == {"id", "observacao_id", "nome_original", "bytes",
                             "mime"}

    def test_lista_vazia_nao_consulta(self):
        assert passagem.anexos_de([]) == {}

    def test_recado_sem_anexo_nao_aparece_no_mapa(self, recado):
        assert passagem.anexos_de([recado]) == {}


class TestOArquivoSumido:
    def test_a_linha_sobrevive_ao_arquivo(self, recado):
        """⚠️ Esta pasta **não tem backup**: o backup leva o banco, então a
        linha fica e o arquivo não. A rota devolve 410 — e o teste prova que o
        estado é alcançável."""
        a = passagem.guardar_anexo(recado, "some.txt", b"dados")
        Path(a["caminho"]).unlink()
        guardado = passagem.anexo(a["id"])
        assert guardado is not None
        assert not Path(guardado["caminho"]).is_file()
