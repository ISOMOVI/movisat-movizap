"""A CA própria dos agentes de ligação: o certificado de cliente de cada PC (Plano 5.1, 25/09).

🔵 *"uma saída segura que poderia ter o nginx específico para não misturar
outro"* e *"também fora"* (há PC fora do escritório, então o IP não serve de
filtro). O nginx de `ligacoesmicrosip.movisat.com.br` só deixa passar quem
apresenta um certificado assinado por ESTA CA; o app confere se o certificado
é o do mesmo agente da chave.

🚨 A CHAVE PRIVADA DO PC NASCE NO PC E NUNCA SAI DELE. O `instalar.ps1` gera o
pedido (CSR) com `certreq`, chave não exportável; aqui só se ASSINA o pedido.
O assunto do certificado é nosso (`mzl-<ramal>-<agente>`), não o do pedido.

🚨 A CHAVE DA CA FICA FORA DO BACKUP, pela mesma lógica do `.env` (decisão
dele, 28/08): cópia única, 0600. Perdê-la não perde dado nenhum -- obriga a
emitir certificado novo para cada PC (os mesmos dois passos da instalação).
"""
import hashlib
import os
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, rsa
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

from . import banco
from .operacao import DadoInvalido

CA_DIR = Path(os.environ.get("MOVIZAP_LIGACOES_CA", "/home/claude/movizap_ligacoes_ca"))
VALIDADE_DIAS = 730          # 2 anos por certificado de PC
VALIDADE_CA_DIAS = 3650      # 10 anos a CA
NOME_CA = "MoviZap Ligacoes CA"


def _arquivos() -> tuple[Path, Path]:
    return CA_DIR / "ca.key", CA_DIR / "ca.crt"


def criar_ca() -> Path:
    """Cria a CA uma vez. Recusa se já existir: CA nova invalida todo PC."""
    chave_arq, cert_arq = _arquivos()
    if chave_arq.exists() or cert_arq.exists():
        raise DadoInvalido(f"A CA já existe em {CA_DIR}. Criar outra invalida todos os PCs.")
    CA_DIR.mkdir(parents=True, exist_ok=True)
    os.chmod(CA_DIR, 0o700)
    chave = rsa.generate_private_key(public_exponent=65537, key_size=3072)
    nome = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, NOME_CA),
                      x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Movisat")])
    agora = datetime.now(timezone.utc)
    cert = (x509.CertificateBuilder()
            .subject_name(nome).issuer_name(nome)
            .public_key(chave.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(agora - timedelta(minutes=5))
            .not_valid_after(agora + timedelta(days=VALIDADE_CA_DIAS))
            .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
            .add_extension(x509.KeyUsage(digital_signature=False, content_commitment=False,
                                         key_encipherment=False, data_encipherment=False,
                                         key_agreement=False, key_cert_sign=True, crl_sign=True,
                                         encipher_only=False, decipher_only=False), critical=True)
            .add_extension(x509.SubjectKeyIdentifier.from_public_key(chave.public_key()),
                           critical=False)
            .sign(chave, hashes.SHA256()))
    # A chave nasce 0600 antes de ter conteúdo: nunca existe legível por outro.
    fd = os.open(chave_arq, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as f:
        f.write(chave.private_bytes(serialization.Encoding.PEM,
                                    serialization.PrivateFormat.PKCS8,
                                    serialization.NoEncryption()))
    cert_arq.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    os.chmod(cert_arq, 0o644)
    return cert_arq


def _ca():
    chave_arq, cert_arq = _arquivos()
    if not chave_arq.exists():
        raise DadoInvalido(f"A CA ainda não existe em {CA_DIR} (rode com --criar-ca).")
    chave = serialization.load_pem_private_key(chave_arq.read_bytes(), password=None)
    return chave, x509.load_pem_x509_certificate(cert_arq.read_bytes())


def sha256_do_cert(pem: str | bytes) -> str:
    """SHA-256 do certificado em DER. É a identidade do PC no banco."""
    if isinstance(pem, str):
        pem = pem.encode("ascii")
    cert = x509.load_pem_x509_certificate(pem)
    return hashlib.sha256(cert.public_bytes(serialization.Encoding.DER)).hexdigest()


def _ler_pedido(pedido: str | bytes) -> x509.CertificateSigningRequest:
    if isinstance(pedido, bytes):
        pedido = pedido.decode("ascii", errors="strict")
    # O `certreq` do Windows escreve "NEW CERTIFICATE REQUEST"; o padrão é sem o NEW.
    pedido = pedido.replace("NEW CERTIFICATE REQUEST", "CERTIFICATE REQUEST").strip()
    try:
        csr = x509.load_pem_x509_csr(pedido.encode("ascii"))
    except ValueError as e:
        raise DadoInvalido("O arquivo não é um pedido de certificado (CSR) válido.") from e
    if not csr.is_signature_valid:
        raise DadoInvalido("A assinatura do pedido não confere.")
    chave = csr.public_key()
    if isinstance(chave, rsa.RSAPublicKey) and chave.key_size < 2048:
        raise DadoInvalido("Chave RSA abaixo de 2048 bits.")
    if not isinstance(chave, (rsa.RSAPublicKey, ec.EllipticCurvePublicKey)):
        raise DadoInvalido("Tipo de chave não aceito (RSA ou EC).")
    return csr


def assinar(ramal: str, pedido: str | bytes) -> dict:
    """Assina o pedido do PC do ramal e amarra o certificado ao agente VIVO dele.
    Um certificado novo substitui o anterior: o velho deixa de entrar."""
    agente = banco.um("""SELECT id FROM agente_ligacao
                          WHERE ramal = %s AND revogado_em IS NULL""", (str(ramal).strip(),))
    if not agente:
        raise DadoInvalido(f"O ramal {ramal} não tem agente vivo: gere a chave primeiro.")
    csr = _ler_pedido(pedido)
    chave_ca, cert_ca = _ca()
    agora = datetime.now(timezone.utc)
    validade = agora + timedelta(days=VALIDADE_DIAS)
    rsa_pc = isinstance(csr.public_key(), rsa.RSAPublicKey)
    cert = (x509.CertificateBuilder()
            .subject_name(x509.Name([x509.NameAttribute(
                NameOID.COMMON_NAME, f"mzl-{ramal}-{agente['id']}")]))
            .issuer_name(cert_ca.subject)
            .public_key(csr.public_key())
            .serial_number(int.from_bytes(secrets.token_bytes(16), "big") >> 1)
            .not_valid_before(agora - timedelta(minutes=5))
            .not_valid_after(validade)
            .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
            .add_extension(x509.KeyUsage(digital_signature=True, content_commitment=False,
                                         key_encipherment=rsa_pc, data_encipherment=False,
                                         key_agreement=False, key_cert_sign=False, crl_sign=False,
                                         encipher_only=False, decipher_only=False), critical=True)
            .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.CLIENT_AUTH]), critical=False)
            .add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(
                chave_ca.public_key()), critical=False)
            .sign(chave_ca, hashes.SHA256()))
    pem = cert.public_bytes(serialization.Encoding.PEM).decode("ascii")
    sha = sha256_do_cert(pem)
    banco.executar("""UPDATE agente_ligacao SET cert_sha256 = %s, cert_validade = %s
                       WHERE id = %s""", (sha, validade, agente["id"]))
    return {"agente_id": agente["id"], "pem": pem, "cert_sha256": sha, "validade": validade}
