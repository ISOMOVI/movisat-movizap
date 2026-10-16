"""Import retroativo de um pacote de PC sem agente (Bloco 9, 15/10).

🚨 Escreve em `atendente`, `agente_ligacao`, `ligacao` e `ligacao_gravacao`,
tabelas de PRODUÇÃO, e grava arquivos em pasta TEMPORÁRIA. Ramais `996xx` e
login `zz_teste_imp_`; tudo apagado no fim.

O que estes testes guardam:
  · IMPORTAR DUAS VEZES O MESMO PACOTE GRAVA ZERO NA SEGUNDA -- é a razão de o
    import entrar pelo mesmo `ligacoes.registrar()` do agente;
  · `--conferir` não grava NADA, e o número que ele promete é o que o import
    cumpre (ele pergunta ao banco, não ao pacote);
  · linha sem `call_id` é RECUSADA: sem ela não há idempotência, e a mesma
    ligação voltaria a cada import;
  · áudio que nenhuma ligação do pacote reivindica é RECUSADO: ele viraria uma
    ligação inventada;
  · sha256 diferente do declarado é RECUSADO (arquivo trocado no caminho);
  · nomes com BARRA INVERTIDA dentro do zip são aceitos -- é o que o
    `Compress-Archive` do Windows PowerShell 5.1 produz, medido em 15/10;
  · o agente de importação nasce REVOGADO e **não derruba** o agente vivo de
    outro ramal.
"""
import hashlib
import importlib.util
import json
import sys
import tempfile
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

sys.path.insert(0, "/home/claude/movizap_painel")
pytest.importorskip("psycopg")

from movizap import banco, ligacoes, operacao  # noqa: E402

ENV = Path("/home/claude/movizap_painel/.env")
pytestmark = pytest.mark.skipif(
    not ENV.exists() or "MOVIZAP_DB_SENHA" not in ENV.read_text(encoding="utf-8"),
    reason="banco nao configurado no .env")

LOGIN = "zz_teste_imp_"
RAMAL = "99600"        # ramal COM agente
RAMAL_SEM = "99601"    # ramal que nunca teve agente
RAMAL_VIVO = "99602"   # ramal com agente vivo, que o import nao pode derrubar


def carregar_script():
    """O importador é um script, não um módulo do pacote: entra por caminho."""
    caminho = Path("/home/claude/movizap_painel/scripts/importar_ligacoes.py")
    spec = importlib.util.spec_from_file_location("importar_ligacoes", caminho)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


imp = carregar_script()


def mp3(semente: int) -> bytes:
    return b"\xff\xe2\x48\xc4" + semente.to_bytes(8, "big") + b"\x00" * 200


def limpar():
    banco.executar("""DELETE FROM ligacao_gravacao WHERE ligacao_id IN
                       (SELECT id FROM ligacao WHERE ramal LIKE '996' || '%%')""")
    banco.executar("DELETE FROM ligacao WHERE ramal LIKE '996' || '%%'")
    banco.executar("DELETE FROM agente_ligacao WHERE ramal LIKE '996' || '%%'")
    banco.executar("DELETE FROM atendente WHERE login LIKE %s", (LOGIN + "%",))


@pytest.fixture(scope="module", autouse=True)
def cena():
    banco.abrir()
    limpar()
    pasta = tempfile.TemporaryDirectory()
    raiz_antiga = ligacoes.RAIZ
    ligacoes.RAIZ = Path(pasta.name)

    pessoa = operacao.criar_atendente("Zz Import Um", LOGIN + "1",
                                      LOGIN + "1@teste.invalid")
    ligacoes.gerar_chave(pessoa["id"], RAMAL)
    outra = operacao.criar_atendente("Zz Import Dois", LOGIN + "2",
                                     LOGIN + "2@teste.invalid")
    chave_viva = ligacoes.gerar_chave(outra["id"], RAMAL_VIVO)

    yield {"pessoa": pessoa, "outra": outra, "chave_viva": chave_viva,
           "temp": Path(pasta.name)}

    ligacoes.RAIZ = raiz_antiga
    limpar()
    pasta.cleanup()
    banco.fechar()


def montar_pacote(destino: Path, ramal: str, ligs: list[dict],
                  arquivos: dict[str, bytes], separador: str = "/") -> Path:
    """Um zip no formato que o agente grava. `separador` existe para provar o
    caso do PowerShell 5.1, que escreve `gravacoes\\x.mp3`."""
    zip_path = destino / f"pacote-{ramal}-{separador == '/' and 'barra' or 'contrabarra'}.zip"
    pacote = {"pacote": "movizap-ligacoes", "versao": 1, "agente": "0.5",
              "pc": "PC-DE-TESTE", "ramal": ramal,
              "gerado_em": datetime.now(timezone.utc).isoformat(),
              "fora_do_padrao": [], "em_uso_agora": [], "ligacoes": ligs}
    with zipfile.ZipFile(zip_path, "w") as z:
        z.writestr("pacote.json", json.dumps(pacote))
        for nome, conteudo in arquivos.items():
            z.writestr(f"gravacoes{separador}{nome}", conteudo)
    return zip_path


def uma(call_id, numero, gravacoes=(), dias=1, sentido="feita"):
    inicio = datetime.now(timezone.utc) - timedelta(days=dias)
    return {"call_id": call_id, "sentido": sentido, "numero": numero,
            "inicio": inicio.isoformat(), "duracao_s": 42,
            "situacao": "Chamada encerrada",
            "gravacoes": [
                {"arquivo": n, "nome_original": n,
                 "sha256": hashlib.sha256(c).hexdigest(), "bytes": len(c),
                 "inicio": inicio.isoformat()}
                for n, c in gravacoes]}


def quantas(ramal=RAMAL):
    return banco.um(
        """SELECT (SELECT count(*) FROM ligacao WHERE ramal = %s) AS ligacoes,
                  (SELECT count(*) FROM ligacao_gravacao g JOIN ligacao l
                          ON l.id = g.ligacao_id WHERE l.ramal = %s) AS gravacoes""",
        (ramal, ramal))


# -------------------------------------------------------- o caminho normal

def test_conferir_nao_grava_nada_e_promete_o_que_cumpre(cena):
    a = mp3(1)
    pacote = montar_pacote(cena["temp"], RAMAL,
                           [uma("imp-1", "+5518999990001", [("a.mp3", a)]),
                            uma("imp-2", "+5518999990002")],
                           {"a.mp3": a})
    antes = quantas()
    imp.importar(pacote, None, conferir=True)
    assert quantas() == antes, "a conferencia gravou alguma coisa"

    imp.importar(pacote, None, conferir=False)
    depois = quantas()
    assert depois["ligacoes"] == antes["ligacoes"] + 2
    assert depois["gravacoes"] == antes["gravacoes"] + 1


def test_importar_duas_vezes_grava_zero_na_segunda(cena):
    a = mp3(2)
    pacote = montar_pacote(cena["temp"], RAMAL,
                           [uma("imp-3", "+5518999990003", [("b.mp3", a)])],
                           {"b.mp3": a})
    imp.importar(pacote, None, conferir=False)
    meio = quantas()
    imp.importar(pacote, None, conferir=False)
    assert quantas() == meio, "a segunda rodada duplicou"


def test_o_pc_fica_marcado_como_importado():
    linha = banco.um("SELECT pc FROM ligacao WHERE ramal = %s AND call_id = %s",
                     (RAMAL, "imp-1"))
    assert linha["pc"] == "importado:PC-DE-TESTE", \
        "sem a marca, o grid nao distingue retroativo de envio ao vivo"


def test_nome_com_barra_invertida_no_zip_e_aceito(cena):
    """O `Compress-Archive` do Windows PowerShell 5.1 grava `gravacoes\\x.mp3`.
    Medido em 15/10: procurar só por `gravacoes/` recusava 19 gravações boas."""
    a = mp3(3)
    pacote = montar_pacote(cena["temp"], RAMAL,
                           [uma("imp-4", "+5518999990004", [("c.mp3", a)])],
                           {"c.mp3": a}, separador="\\")
    antes = quantas()
    imp.importar(pacote, None, conferir=False)
    assert quantas()["gravacoes"] == antes["gravacoes"] + 1


# ------------------------------------------------------------- as recusas

def test_linha_sem_call_id_e_recusada(cena):
    sem = uma("", "+5518999990005")
    pacote = montar_pacote(cena["temp"], RAMAL, [sem], {})
    antes = quantas()
    imp.importar(pacote, None, conferir=False)
    assert quantas() == antes, "entrou ligacao sem call_id"


def test_audio_sem_ligacao_correspondente_e_recusado(cena):
    sobra = mp3(4)
    pacote = montar_pacote(cena["temp"], RAMAL,
                           [uma("imp-6", "+5518999990006")],
                           {"orfa.mp3": sobra})
    imp.importar(pacote, None, conferir=False)
    assert banco.um("SELECT 1 FROM ligacao_gravacao WHERE arquivo_sha256 = %s",
                    (hashlib.sha256(sobra).hexdigest(),)) is None, \
        "audio sem ligacao no pacote entrou e virou ligacao inventada"


def test_sha256_diferente_do_declarado_e_recusado(cena):
    certo, trocado = mp3(5), mp3(6)
    ligs = [uma("imp-7", "+5518999990007", [("d.mp3", certo)])]
    pacote = montar_pacote(cena["temp"], RAMAL, ligs, {"d.mp3": trocado})
    imp.importar(pacote, None, conferir=False)
    assert banco.um("SELECT 1 FROM ligacao_gravacao WHERE arquivo_sha256 = %s",
                    (hashlib.sha256(trocado).hexdigest(),)) is None


def test_pacote_de_outra_origem_e_recusado(cena):
    caminho = cena["temp"] / "alheio.zip"
    with zipfile.ZipFile(caminho, "w") as z:
        z.writestr("pacote.json", json.dumps({"pacote": "outro", "ramal": "99600"}))
    with pytest.raises(SystemExit):
        imp.importar(caminho, None, conferir=True)


def test_versao_futura_e_recusada(cena):
    caminho = cena["temp"] / "futuro.zip"
    with zipfile.ZipFile(caminho, "w") as z:
        z.writestr("pacote.json", json.dumps(
            {"pacote": "movizap-ligacoes", "versao": 99, "ramal": "99600"}))
    with pytest.raises(SystemExit):
        imp.importar(caminho, None, conferir=True)


# ------------------------------------------------------ de quem e o ramal

def test_ramal_sem_agente_e_sem_atendente_recusa_e_explica(cena):
    pacote = montar_pacote(cena["temp"], RAMAL_SEM,
                           [uma("imp-8", "+5518999990008")], {})
    with pytest.raises(SystemExit) as e:
        imp.importar(pacote, None, conferir=False)
    assert "nunca teve agente" in str(e.value)


def test_agente_de_importacao_nasce_revogado_e_nao_derruba_o_vivo(cena):
    pacote = montar_pacote(cena["temp"], RAMAL_SEM,
                           [uma("imp-9", "+5518999990009")], {})
    imp.importar(pacote, LOGIN + "2", conferir=False)

    novo = banco.um("""SELECT revogado_em, ultima_versao FROM agente_ligacao
                        WHERE ramal = %s ORDER BY id DESC LIMIT 1""", (RAMAL_SEM,))
    assert novo["revogado_em"] is not None, \
        "agente de importacao vivo seria uma chave de envio que ninguem pediu"
    assert novo["ultima_versao"] == "import"

    # E o agente VIVO de outro ramal da mesma pessoa continua vivo: o PC que
    # manda hoje nao pode cair porque alguem importou um arquivo velho.
    assert ligacoes.agente_da_chave(cena["chave_viva"])["ramal"] == RAMAL_VIVO
    assert quantas(RAMAL_SEM)["ligacoes"] == 1


def test_a_chave_do_agente_de_importacao_nao_serve_para_entrar():
    """Ela é aleatória e nunca é mostrada; o teste prova que o caminho de
    autenticação não aceita um agente revogado."""
    agente = banco.um("""SELECT chave_sha256 FROM agente_ligacao
                          WHERE ramal = %s ORDER BY id DESC LIMIT 1""", (RAMAL_SEM,))
    assert agente["chave_sha256"]
    with pytest.raises(ligacoes.ChaveInvalida):
        # Mesmo quem adivinhasse a chave em claro bateria na revogação.
        ligacoes.agente_da_chave("mzl_" + "z" * 43)
