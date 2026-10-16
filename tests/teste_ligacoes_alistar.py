"""Alistamento do agente por senha de uso único (15/10/2026).

🚨 Escreve em `atendente`, `agente_ligacao` e `alistamento_queimado`, tabelas
de PRODUÇÃO. Ramais `99xxx` e login `zz_teste_alist_`; tudo apagado no fim.

O que estes testes guardam, e que nenhum deles existia antes:
  · a senha NÃO fica guardada em lugar nenhum -- é derivada, e muda por ramal
    e por janela;
  · a mesma senha não serve duas vezes (é a trava `UNIQUE (ramal, janela)`);
  · senha errada e ramal sem dono dão a MESMA resposta, para não entregar a
    lista de ramais válidos a quem está adivinhando;
  · alistar num PC novo REVOGA o anterior do mesmo ramal (decisão dele, 15/10);
  · a senha só alista: o que trabalha depois é a chave mais o certificado.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, "/home/claude/movizap_painel")
pytest.importorskip("psycopg")
pytest.importorskip("cryptography")

from cryptography import x509  # noqa: E402
from cryptography.hazmat.primitives import hashes, serialization  # noqa: E402
from cryptography.hazmat.primitives.asymmetric import rsa  # noqa: E402
from cryptography.x509.oid import NameOID  # noqa: E402

from movizap import banco, ligacoes, ligacoes_alistar, operacao, ratelimit  # noqa: E402
from movizap.operacao import DadoInvalido  # noqa: E402

ENV = Path("/home/claude/movizap_painel/.env")
pytestmark = pytest.mark.skipif(
    not ENV.exists() or "MOVIZAP_LIGACOES_SENHA_SEGREDO" not in ENV.read_text(encoding="utf-8"),
    reason="segredo da senha de alistamento nao configurado no .env")

LOGIN = "zz_teste_alist_"
_seq = [0]
# Uma chave RSA só para todos os pedidos: gerar 2048 bits por teste custa
# segundos, e o que se testa aqui não é a criptografia do PC.
_chave = [None]


def limpar():
    banco.executar("DELETE FROM alistamento_queimado WHERE ramal LIKE '99%%'")
    banco.executar("DELETE FROM agente_ligacao WHERE ramal LIKE '99%%'")
    banco.executar("DELETE FROM atendente WHERE login LIKE %s", (LOGIN + "%",))
    ratelimit.zerar()


@pytest.fixture(scope="module", autouse=True)
def pool():
    banco.abrir()
    limpar()
    yield
    limpar()
    banco.fechar()


def pedido(ramal: str) -> str:
    """Um CSR como o que o `certreq` gera no PC da pessoa."""
    if _chave[0] is None:
        _chave[0] = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    csr = (x509.CertificateSigningRequestBuilder()
           .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, f"mzl-{ramal}-pc")]))
           .sign(_chave[0], hashes.SHA256()))
    return csr.public_bytes(serialization.Encoding.PEM).decode("ascii")


def pessoa(ramal: str) -> dict:
    _seq[0] += 1
    a = operacao.criar_atendente(f"Zz Alist {_seq[0]}", f"{LOGIN}{_seq[0]}",
                                 f"{LOGIN}{_seq[0]}@teste.invalid")
    banco.executar("UPDATE atendente SET ramal = %s WHERE id = %s", (ramal, a["id"]))
    return a


def senha_de(ramal: str) -> str:
    return ligacoes_alistar.formatar(
        ligacoes_alistar.senha_da_janela(ramal, ligacoes_alistar.janela_de()))


# ----------------------------------------------------------------- a derivação

def test_a_senha_e_derivada_e_nao_guardada():
    janela = ligacoes_alistar.janela_de()
    a = ligacoes_alistar.senha_da_janela("99100", janela)
    assert a == ligacoes_alistar.senha_da_janela("99100", janela), "mesma entrada, mesma senha"
    assert a != ligacoes_alistar.senha_da_janela("99101", janela), "muda por ramal"
    assert a != ligacoes_alistar.senha_da_janela("99100", janela - 1), "muda por janela"
    assert len(a) == ligacoes_alistar.TAMANHO
    # Ditada por telefone: I/O/0/1 não entram, e o hífen é só apresentação.
    assert not set(a) & set("IO01")
    assert ligacoes_alistar._limpar(ligacoes_alistar.formatar(a).lower()) == a


def test_preparar_recusa_ramal_de_outra_pessoa():
    pessoa("99110")
    outra = operacao.criar_atendente("Zz Alist outra", LOGIN + "outra",
                                     LOGIN + "outra@teste.invalid")
    with pytest.raises(DadoInvalido) as e:
        ligacoes_alistar.preparar("99110", "Zz Alist outra")
    assert "já é de" in str(e.value)
    assert banco.um("SELECT ramal FROM atendente WHERE id = %s", (outra["id"],))["ramal"] is None


def test_preparar_amarra_o_ramal_na_primeira_vez():
    a = operacao.criar_atendente("Zz Alist nova", LOGIN + "nova",
                                 LOGIN + "nova@teste.invalid")
    r = ligacoes_alistar.preparar("99120", "Zz Alist nova")
    assert r["atendente"] == "Zz Alist nova" and r["ramal"] == "99120"
    assert banco.um("SELECT ramal FROM atendente WHERE id = %s", (a["id"],))["ramal"] == "99120"
    # 🔵 15/10: a senha vale 1 DIA, e o prazo informado é o REAL -- enquanto
    # media só a janela de geração, a ferramenta dizia "7 min" de uma senha
    # que valia um dia.
    assert r["segundos"] > 44 * 3600
    assert r["segundos"] <= ligacoes_alistar.JANELAS_ACEITAS * ligacoes_alistar.JANELA_S


# ---------------------------------------------------------------- o alistamento

def test_alistar_devolve_chave_e_certificado_que_funcionam_juntos():
    pessoa("99200")
    r = ligacoes_alistar.alistar("99200", senha_de("99200"), pedido("99200"),
                                 pc="PC-TESTE", ip="10.0.0.1")
    assert r["chave"].startswith("mzl_") and "BEGIN CERTIFICATE" in r["cert_pem"]
    # A prova é reler: a chave e o certificado têm de ser do MESMO agente.
    agente = ligacoes.agente_da_chave(r["chave"], r["cert_pem"], exigir_cert=True)
    assert agente["ramal"] == "99200"
    assert banco.um("SELECT count(*) n FROM alistamento_queimado WHERE ramal = %s",
                    ("99200",))["n"] == 1


def test_a_mesma_senha_nao_serve_duas_vezes():
    pessoa("99210")
    senha = senha_de("99210")
    ligacoes_alistar.alistar("99210", senha, pedido("99210"), ip="10.0.0.2")
    with pytest.raises(ligacoes_alistar.SenhaInvalida) as e:
        ligacoes_alistar.alistar("99210", senha, pedido("99210"), ip="10.0.0.2")
    assert "já foi usada" in str(e.value)


def test_alistar_em_pc_novo_revoga_o_anterior(monkeypatch):
    """🔵 Decisão dele (15/10): quem alista de novo está trocando de PC, e dois
    PCs no mesmo ramal mandariam em dobro."""
    pessoa("99220")
    velho = ligacoes_alistar.alistar("99220", senha_de("99220"), pedido("99220"),
                                     pc="PC-VELHO", ip="10.0.0.3")
    # Janela seguinte: senha nova, porque a anterior já foi queimada.
    proxima = ligacoes_alistar.janela_de() + 1
    senha = ligacoes_alistar.formatar(ligacoes_alistar.senha_da_janela("99220", proxima))
    monkeypatch.setattr(ligacoes_alistar, "janela_de", lambda *_: proxima)
    novo = ligacoes_alistar.alistar("99220", senha, pedido("99220"),
                                    pc="PC-NOVO", ip="10.0.0.3")
    assert novo["pc_anterior"] == "PC-VELHO"
    with pytest.raises(ligacoes.ChaveInvalida):
        ligacoes.agente_da_chave(velho["chave"])          # o PC velho não entra mais
    assert ligacoes.agente_da_chave(novo["chave"])["ramal"] == "99220"
    vivos = banco.um("""SELECT count(*) n FROM agente_ligacao
                         WHERE ramal = %s AND revogado_em IS NULL""", ("99220",))
    assert vivos["n"] == 1, "um agente vivo por ramal"


def test_senha_errada_e_ramal_sem_dono_dizem_a_mesma_coisa():
    """Dizer qual é o caso entregaria a lista de ramais válidos."""
    pessoa("99230")
    with pytest.raises(ligacoes_alistar.SenhaInvalida) as errada:
        ligacoes_alistar.alistar("99230", "ZZZZ-ZZZZ", pedido("99230"), ip="10.0.0.4")
    with pytest.raises(ligacoes_alistar.SenhaInvalida) as sem_dono:
        ligacoes_alistar.alistar("99999", senha_de("99999"), pedido("99999"), ip="10.0.0.5")
    assert str(errada.value) == str(sem_dono.value)
    assert banco.um("SELECT count(*) n FROM alistamento_queimado WHERE ramal = %s",
                    ("99999",))["n"] == 0, "recusa não queima janela"


def test_tentativa_errada_demais_trava_o_ramal_naquele_ip():
    pessoa("99240")
    for _ in range(ratelimit.MAX_FALHAS):
        with pytest.raises(ligacoes_alistar.SenhaInvalida):
            ligacoes_alistar.alistar("99240", "ZZZZ-ZZZZ", pedido("99240"), ip="10.0.0.6")
    with pytest.raises(ligacoes_alistar.SenhaInvalida) as e:
        ligacoes_alistar.alistar("99240", senha_de("99240"), pedido("99240"), ip="10.0.0.6")
    assert "Tentativas demais" in str(e.value)
    # Outro IP não é punido pelo erro do primeiro.
    r = ligacoes_alistar.alistar("99240", senha_de("99240"), pedido("99240"), ip="10.0.0.7")
    assert r["chave"].startswith("mzl_")


def test_ramal_tem_de_ser_numero():
    with pytest.raises(DadoInvalido):
        ligacoes_alistar.alistar("abc", "ZZZZ-ZZZZ", pedido("abc"), ip="10.0.0.8")


class TestSenhaDeUmDia:
    """🔵 15/10: *"podemos prolongar as senhas para 1 dia por enquanto?"*.

    🚨 O que estes testes guardam é a SEPARAÇÃO entre as duas coisas: a senha
    TROCA a cada 10 minutos e é ACEITA por 24 h. Se alguém "simplificar" isso
    pondo `JANELA_S = 86400`, o `UNIQUE (ramal, janela)` passa a significar um
    alistamento por ramal por dia -- e um alistamento que falhe no meio tranca
    o ramal até o dia seguinte.
    """

    def test_a_senha_troca_a_cada_dez_minutos(self):
        assert ligacoes_alistar.JANELA_S == 600, (
            "mexer na janela de GERAÇÃO troca o prazo de retentativa: "
            "uma falha passaria a custar o tamanho da janela")

    def test_e_e_aceita_por_48_horas(self):
        assert (ligacoes_alistar.JANELAS_ACEITAS
                * ligacoes_alistar.JANELA_S) == 48 * 3600

    def test_senha_de_ontem_a_noite_ainda_serve(self):
        """23 h atrás: é o caso dele, de ditar a senha hoje e a pessoa rodar o
        instalador amanhã de manhã."""
        pessoa("99130")
        import time as _t
        janela_velha = ligacoes_alistar.janela_de(_t.time() - 23 * 3600)
        senha = ligacoes_alistar.senha_da_janela("99130", janela_velha)
        r = ligacoes_alistar.alistar("99130", senha, pedido("99130"), pc="PC-VELHA")
        assert r["ok"] and r["ramal"] == "99130"

    def test_senha_de_47_horas_ainda_serve(self):
        """É o caso dele: deixar as senhas prontas hoje e os operadores
        rodarem o instalador depois de amanhã."""
        pessoa("99134")
        import time as _t
        janela = ligacoes_alistar.janela_de(_t.time() - 47 * 3600)
        senha = ligacoes_alistar.senha_da_janela("99134", janela)
        assert ligacoes_alistar.alistar("99134", senha, pedido("99134"),
                                        pc="PC-47H")["ok"]

    def test_senha_de_mais_de_48_horas_nao_serve(self):
        pessoa("99131")
        import time as _t  # noqa: F811
        janela_antiga = ligacoes_alistar.janela_de(_t.time() - 49 * 3600)
        senha = ligacoes_alistar.senha_da_janela("99131", janela_antiga)
        with pytest.raises(ligacoes_alistar.SenhaInvalida):
            ligacoes_alistar.alistar("99131", senha, pedido("99131"), pc="PC-ANTIGA")

    def test_continua_de_uso_unico_dentro_do_dia(self):
        """Valer um dia não é poder usar duas vezes: a primeira utilização
        queima a janela."""
        pessoa("99132")
        senha = senha_de("99132")
        assert ligacoes_alistar.alistar("99132", senha, pedido("99132"),
                                        pc="PC-UM")["ok"]
        with pytest.raises(ligacoes_alistar.SenhaInvalida):
            ligacoes_alistar.alistar("99132", senha, pedido("99132"), pc="PC-DOIS")

    def test_uma_janela_queimada_nao_tranca_a_seguinte(self):
        """🚨 É O MOTIVO DE A GERAÇÃO FICAR EM 10 MIN. Queimada a senha de
        agora, a de 10 minutos atrás (ou a da próxima janela) continua
        servindo -- é isso que faz "peça outra senha" funcionar."""
        pessoa("99133")
        import time as _t
        agora = ligacoes_alistar.janela_de()
        assert ligacoes_alistar.alistar(
            "99133", ligacoes_alistar.senha_da_janela("99133", agora),
            pedido("99133"), pc="PC-A")["ok"]
        anterior = ligacoes_alistar.janela_de(_t.time() - 600)
        assert anterior != agora
        assert ligacoes_alistar.alistar(
            "99133", ligacoes_alistar.senha_da_janela("99133", anterior),
            pedido("99133"), pc="PC-B")["ok"]
