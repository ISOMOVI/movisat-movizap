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
    """A senha que ALISTA. 🚨 24/11: é a padrão, uma só para todos os ramais
    (*"Somente 'Movisat!@'"*). O argumento fica para as chamadas não mudarem
    todas, e para o dia em que a senha voltar a ser por ramal."""
    return ligacoes_alistar.senha_fixa()


def senha_derivada_de(ramal: str) -> str:
    """A senha de uso único de 15/10. ⚠️ Ela NÃO alista mais -- está aqui para
    os testes que medem justamente a recusa."""
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
    # 🚨 24/11: a senha padrão NÃO queima janela, então não nasce linha aqui.
    # Era `== 1` enquanto a derivada alistava.
    assert banco.um("SELECT count(*) n FROM alistamento_queimado WHERE ramal = %s",
                    ("99200",))["n"] == 0


def test_a_mesma_senha_SERVE_sempre():
    """🚨 INVERTIDO EM 24/11 (*"Somente 'Movisat!@'"*). Enquanto a senha era
    derivada, a mesma senha não servia duas vezes -- `UNIQUE (ramal, janela)`
    a travava. Agora a senha é a padrão e ela tem de servir em quantos PCs
    precisar: se queimasse, o primeiro PC trancaria todos os outros."""
    pessoa("99210")
    senha = senha_de("99210")
    assert ligacoes_alistar.alistar("99210", senha, pedido("99210"),
                                    pc="PC-UM", ip="10.0.0.2")["ok"]
    assert ligacoes_alistar.alistar("99210", senha, pedido("99210"),
                                    pc="PC-DOIS", ip="10.0.0.2")["ok"]


def test_alistar_em_pc_novo_revoga_o_anterior():
    """🔵 Decisão dele (15/10), e ela NÃO mudou com a senha padrão: quem alista
    de novo está trocando de PC, e dois PCs no mesmo ramal mandariam em dobro."""
    pessoa("99220")
    velho = ligacoes_alistar.alistar("99220", senha_de("99220"), pedido("99220"),
                                     pc="PC-VELHO", ip="10.0.0.3")
    novo = ligacoes_alistar.alistar("99220", senha_de("99220"), pedido("99220"),
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

    def test_a_derivada_NAO_ALISTA_MAIS(self):
        """🚨 24/11, DELE: *"Somente 'Movisat!@'"*. A senha de uso único
        continua sendo CALCULADA (o `senhas_dos_ramais.py` e o
        `segundos_restantes` a importam), e deixou de abrir a porta. Esta
        trava é a que impede alguém de "reativar" o caminho sem decidir."""
        pessoa("99130")
        senha = senha_derivada_de("99130")
        with pytest.raises(ligacoes_alistar.SenhaInvalida):
            ligacoes_alistar.alistar("99130", senha, pedido("99130"), pc="PC-DERIVADA")

    def test_a_derivada_de_qualquer_janela_e_recusada(self):
        """Nenhuma janela abre: nem a de agora, nem a de ontem, nem a de 47 h.
        Enquanto a derivada valia, as três entravam."""
        pessoa("99134")
        import time as _t
        for horas in (0, 23, 47):
            janela = ligacoes_alistar.janela_de(_t.time() - horas * 3600)
            senha = ligacoes_alistar.senha_da_janela("99134", janela)
            with pytest.raises(ligacoes_alistar.SenhaInvalida):
                ligacoes_alistar.alistar("99134", senha, pedido("99134"),
                                         pc=f"PC-{horas}H")

    def test_recusar_a_derivada_nao_queima_janela(self):
        """⚠️ Recusa não pode gastar nada: se queimasse, uma tentativa à toa
        trancaria a janela daquele ramal."""
        pessoa("99131")
        with pytest.raises(ligacoes_alistar.SenhaInvalida):
            ligacoes_alistar.alistar("99131", senha_derivada_de("99131"),
                                     pedido("99131"), pc="PC-ANTIGA")
        assert banco.um("SELECT count(*) n FROM alistamento_queimado WHERE ramal = %s",
                        ("99131",))["n"] == 0


# ── 13/11: A SENHA FIXA ──────────────────────────────────────────────────────
#
# 🔵 23/11: o valor virou `Movisat!@` (efetivo `MOVISAT`). O que estas travas
# medem é o MECANISMO, por `senha_fixa()`, e não o valor -- trocar a senha no
# `/config` não pode deixar a suíte vermelha.
# 🔵 Dele, 13/11: *"deixar senha padrão de 'movicall' (essa senha não há muita
# exigência de segredo)"*. Nasceu como ATALHO ao lado da derivada.
#
# 🚨 24/11, DELE: *"Somente 'Movisat!@'"*. Deixou de ser atalho e passou a ser
# A ÚNICA porta, comparada literalmente. Os testes abaixo medem as duas metades
# novas: a padrão entra em quantos PCs precisar, e nada mais entra.


def test_a_senha_fixa_alista():
    """O caminho novo: a pessoa aperta Enter no instalador e o PC entra."""
    pessoa("99300")
    r = ligacoes_alistar.alistar("99300", ligacoes_alistar.senha_fixa(),
                                 pedido("99300"), ip="10.0.0.30")
    assert r["ok"] is True
    assert r["ramal"] == "99300"


def test_a_senha_fixa_NAO_QUEIMA_e_serve_em_varios_PCs():
    """🚨 ESTE É O PONTO DO RECURSO. A senha derivada serve UMA vez porque
    `UNIQUE (ramal, janela)` a trava. Se a fixa queimasse junto, o primeiro PC
    a usá-la trancaria todos os outros -- o oposto do que ele pediu, que é
    poder sair instalando nas máquinas."""
    pessoa("99310")
    fixa = ligacoes_alistar.senha_fixa()
    primeiro = ligacoes_alistar.alistar("99310", fixa, pedido("99310"),
                                        pc="PC-UM", ip="10.0.0.31")
    segundo = ligacoes_alistar.alistar("99310", fixa, pedido("99310"),
                                       pc="PC-DOIS", ip="10.0.0.31")
    assert primeiro["ok"] and segundo["ok"]
    assert segundo["pc_anterior"] == "PC-UM"


def test_a_senha_padrao_e_a_UNICA_que_alista():
    """🚨 INVERTIDO EM 24/11. Até 23/11 esta trava media o contrário -- que a
    senha padrão não havia desligado o caminho de 15/10. 🔵 Ele fechou:
    *"Somente 'Movisat!@'"*. Então o par tem de valer junto: a padrão entra,
    a derivada do MESMO ramal não."""
    pessoa("99320")
    assert ligacoes_alistar.alistar("99320", senha_de("99320"), pedido("99320"),
                                    ip="10.0.0.32")["ok"] is True
    with pytest.raises(ligacoes_alistar.SenhaInvalida):
        ligacoes_alistar.alistar("99320", senha_derivada_de("99320"),
                                 pedido("99320"), ip="10.0.0.32")


def test_a_senha_padrao_e_comparada_LITERALMENTE():
    """🚨 24/11. Enquanto os dois lados passavam pelo `_limpar` (que reduz a
    `A-Z2-9`), o `!@` era descartado ANTES de comparar -- e `MOVISAT`,
    `movisat` e `mo-vi-sat` alistavam igual. *"Somente 'Movisat!@'"* quer
    dizer o valor como está escrito.

    ⚠️ Mede pelo valor REAL de `senha_fixa()`, não pela string crua: trocar a
    senha no `/config` não pode deixar a suíte vermelha."""
    padrao = ligacoes_alistar.senha_fixa()
    assert padrao, "a senha padrão tem de estar definida no config"
    pessoa("99330")
    # Variantes que o `_limpar` tornava equivalentes e que agora são recusadas.
    for variante in {padrao.upper(), padrao.lower(),
                     ligacoes_alistar._limpar(padrao)} - {padrao}:
        with pytest.raises(ligacoes_alistar.SenhaInvalida):
            ligacoes_alistar.alistar("99330", variante, pedido("99330"),
                                     ip="10.0.0.35")
    # E o valor exato entra.
    assert ligacoes_alistar.alistar("99330", padrao, pedido("99330"),
                                    ip="10.0.0.36")["ok"]


def test_a_senha_fixa_nao_alista_ramal_que_nao_existe():
    """🚨 A senha ser conhecida não abre ramal nenhum: o ramal tem de existir e
    estar ativo. Sem esta trava, a senha padrão viraria uma porta para inventar
    agente de ramal que não é da casa."""
    with pytest.raises(ligacoes_alistar.SenhaInvalida):
        ligacoes_alistar.alistar("99999", ligacoes_alistar.senha_fixa(),
                                 pedido("99999"), ip="10.0.0.33")


def test_senha_fixa_vazia_TRANCA_o_alistamento(monkeypatch):
    """🚨 MUDOU DE SIGNIFICADO EM 24/11. Enquanto a derivada alistava, esvaziar
    `config.ligacoes_senha_fixa` só desligava um atalho. Agora que a padrão é
    a única porta, vazia significa que NINGUÉM alista -- e isso é o jeito de
    parar o alistamento de propósito, não um acidente.

    ⚠️ Mede com a derivada TAMBÉM, porque é ela que entraria se o caminho
    antigo tivesse sobrado."""
    pessoa("99340")
    monkeypatch.setattr(ligacoes_alistar, "senha_fixa", lambda: "")
    for senha in ("zz-senha-que-nao-existe", senha_derivada_de("99340")):
        with pytest.raises(ligacoes_alistar.SenhaInvalida):
            ligacoes_alistar.alistar("99340", senha, pedido("99340"),
                                     ip="10.0.0.34")
