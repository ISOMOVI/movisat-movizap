"""O app da porta própria do agente de ligações (Plano 5.1, 25/09).

Prova as duas provas juntas -- chave e certificado do MESMO agente -- como o
app as recebe do nginx (`X-Cliente-Cert` = PEM codificado em URL).

🚨 Escreve em tabelas de PRODUÇÃO (ramais `98xxx`, login `zz_teste_app_lig_`,
tudo apagado no fim) e cria a CA e as gravações em pastas TEMPORÁRIAS.
"""
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

import pytest

sys.path.insert(0, "/home/claude/movizap_painel")
pytest.importorskip("psycopg")

from cryptography import x509  # noqa: E402
from cryptography.hazmat.primitives import hashes, serialization  # noqa: E402
from cryptography.hazmat.primitives.asymmetric import rsa  # noqa: E402
from cryptography.x509.oid import NameOID  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from movizap import app_ligacoes, banco, ligacoes, ligacoes_ca, operacao  # noqa: E402
from movizap.operacao import DadoInvalido  # noqa: E402

ENV = Path("/home/claude/movizap_painel/.env")
pytestmark = pytest.mark.skipif(
    not ENV.exists() or "MOVIZAP_DB_SENHA" not in ENV.read_text(encoding="utf-8"),
    reason="banco nao configurado no .env")

LOGIN = "zz_teste_app_lig_"


def limpar():
    banco.executar("""DELETE FROM ligacao_gravacao WHERE ligacao_id IN
        (SELECT id FROM ligacao WHERE ramal LIKE '98%%')""")
    banco.executar("DELETE FROM ligacao WHERE ramal LIKE '98%%'")
    banco.executar("DELETE FROM agente_ligacao WHERE ramal LIKE '98%%'")
    banco.executar("DELETE FROM atendente WHERE login LIKE %s", (LOGIN + "%",))


@pytest.fixture(scope="module", autouse=True)
def pool():
    banco.abrir()
    limpar()
    yield
    limpar()
    banco.fechar()


@pytest.fixture(scope="module", autouse=True)
def ca_temporaria():
    with tempfile.TemporaryDirectory() as d:
        antes = ligacoes_ca.CA_DIR
        ligacoes_ca.CA_DIR = Path(d) / "ca"
        ligacoes_ca.criar_ca()
        yield
        ligacoes_ca.CA_DIR = antes


@pytest.fixture(autouse=True)
def pasta_temporaria(monkeypatch):
    with tempfile.TemporaryDirectory() as d:
        monkeypatch.setattr(ligacoes, "RAIZ", Path(d))
        yield


# Sem `with`: o ciclo de vida do app abriria e FECHARIA o pool do módulo.
cliente = TestClient(app_ligacoes.app)
_seq = [0]


def pedido_do_pc() -> bytes:
    """O que o `certreq` do PC faria: chave nova e um CSR (com o NEW do Windows)."""
    chave = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    csr = (x509.CertificateSigningRequestBuilder()
           .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "PC-TESTE")]))
           .sign(chave, hashes.SHA256()))
    pem = csr.public_bytes(serialization.Encoding.PEM).decode()
    return pem.replace("CERTIFICATE REQUEST", "NEW CERTIFICATE REQUEST").encode()


def agente_com_cert():
    _seq[0] += 1
    a = operacao.criar_atendente(f"Zz App Lig {_seq[0]}", f"{LOGIN}{_seq[0]}",
                                 f"{LOGIN}{_seq[0]}@teste.invalid")
    ramal = f"98{_seq[0]:03d}"
    chave = ligacoes.gerar_chave(a["id"], ramal)
    r = ligacoes_ca.assinar(ramal, pedido_do_pc())
    return chave, quote(r["pem"]), ramal


def cabecalhos(chave, cert, ip="45.179.3.219"):
    h = {"X-Real-IP": ip}
    if chave:
        h["X-Agente-Chave"] = chave
    if cert:
        h["X-Cliente-Cert"] = cert
    return h


def batida(chave, cert, **kw):
    return cliente.post("/agente/batimento", headers=cabecalhos(chave, cert, **kw),
                        json={"pc": "PC-TESTE", "versao": "0.3", "pendentes": 0})


def test_as_duas_provas_juntas_entram_e_o_ip_fica():
    chave, cert, ramal = agente_com_cert()
    r = batida(chave, cert, ip="200.1.2.3")
    assert r.status_code == 200, r.text
    linha = banco.um("SELECT ultimo_ip, ultima_versao FROM agente_ligacao "
                     "WHERE ramal = %s AND revogado_em IS NULL", (ramal,))
    assert linha["ultimo_ip"] == "200.1.2.3" and linha["ultima_versao"] == "0.3"


def test_sem_certificado_ou_sem_chave_nao_entra():
    chave, cert, _ = agente_com_cert()
    assert batida(chave, None).status_code == 401
    assert batida(None, cert).status_code == 401


def test_certificado_de_outro_agente_nao_entra():
    chave_a, _, _ = agente_com_cert()
    _, cert_b, _ = agente_com_cert()
    r = batida(chave_a, cert_b)
    assert r.status_code == 401 and "não é o deste agente" in r.json()["detail"]


def test_certificado_novo_substitui_o_velho():
    chave, cert_velho, ramal = agente_com_cert()
    novo = quote(ligacoes_ca.assinar(ramal, pedido_do_pc())["pem"])
    assert batida(chave, cert_velho).status_code == 401
    assert batida(chave, novo).status_code == 200


def test_revogado_e_vencido_nao_entram():
    chave, cert, ramal = agente_com_cert()
    banco.executar("UPDATE agente_ligacao SET cert_validade = now() - interval '1 minute' "
                   "WHERE ramal = %s AND revogado_em IS NULL", (ramal,))
    assert "vencido" in batida(chave, cert).json()["detail"]
    banco.executar("UPDATE agente_ligacao SET revogado_em = now() WHERE ramal = %s", (ramal,))
    assert batida(chave, cert).status_code == 401


def test_enviar_uma_ligacao_com_gravacao_pela_porta_nova():
    import json
    chave, cert, _ = agente_com_cert()
    mp3 = b"\xff\xe2\x48\xc4" + b"app-lig" + b"\x00" * 400
    dados = {"call_id": "app-c1", "sentido": "feita", "numero": "+5518998116168",
             "inicio": datetime.now(timezone.utc).isoformat(), "duracao_s": 5}
    r = cliente.post("/agente/enviar", headers=cabecalhos(chave, cert),
                     data={"dados": json.dumps(dados)},
                     files={"arquivo": ("teste.mp3", mp3, "audio/mpeg")})
    assert r.status_code == 200, r.text
    import hashlib
    assert r.json()["arquivo_sha256"] == hashlib.sha256(mp3).hexdigest()


def test_pedido_invalido_e_ramal_sem_agente_sao_recusados():
    with pytest.raises(DadoInvalido):
        ligacoes_ca.assinar("98999", pedido_do_pc())
    _, _, ramal = agente_com_cert()
    with pytest.raises(DadoInvalido):
        ligacoes_ca.assinar(ramal, b"isto nao e um pedido")


def test_a_ca_nao_se_recria_e_a_chave_dela_e_0600():
    with pytest.raises(DadoInvalido):
        ligacoes_ca.criar_ca()
    assert (ligacoes_ca.CA_DIR / "ca.key").stat().st_mode & 0o777 == 0o600


def test_aviso_de_pc_vivo_sai_no_alerta():
    chave, cert, ramal = agente_com_cert()
    r = cliente.post("/agente/batimento", headers=cabecalhos(chave, cert),
                     json={"pc": "PC-TESTE", "versao": "0.3", "pendentes": 0,
                           "aviso": "gravação automática desligada no MicroSIP"})
    assert r.status_code == 200
    assert ramal in [m["ramal"] for m in ligacoes.agentes_com_aviso()]


def test_so_agente_responde():
    assert cliente.get("/docs").status_code == 404
    assert cliente.get("/openapi.json").status_code == 404
