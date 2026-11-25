"""Alistamento do agente de ligações por SENHA (15/10/2026).

🚨 LEIA ISTO PRIMEIRO -- 24/11/2026, PEDIDO DELE: *"Somente 'Movisat!@'"*.
A senha de alistamento é UMA, padrão, igual para todos, guardada em
`config.ligacoes_senha_fixa` e comparada LITERALMENTE (maiúscula e símbolo
contam). A senha DERIVADA de uso único, descrita no resto deste cabeçalho,
**não alista mais**: `senha_da_janela` continua sendo calculada porque outras
ferramentas a importam, mas nenhuma janela abre a porta. O histórico abaixo
fica porque explica POR QUE a derivada existiu e o que se perdeu ao trocá-la.

⚠️ O QUE SE PERDEU, POR ESCRITO: a senha não vence mais, não serve uma vez só
e é a mesma para todos os ramais. Quem souber `Movisat!@` e um ramal ativo
alista um PC naquele ramal -- e alistar REVOGA o PC que estava usando. De pé
continuam: ramal tem de existir e estar ativo, limite de tentativas por IP, e
o certificado emitido vale só para aquele PC.


🔵 Pedido dele: *"considere que podem trocar de PC, então por isso o .exe deve
rodar livre assim, porém validar o atendente do MicroSip com uma senha que
será gerada sempre via algoritmo e é mutável para rodar"* e *"se trocarem de
PC é só executar novamente e me pedir a senha de uso"*.

O que isto substitui: os 9 passos do kit (gerar chave na VPS → pendrive com o
`config.json` → PC gera o `.req` → o `.req` volta → ele assina → o `.cer` volta
→ concluir). Agora são 2: ele dita a senha, a pessoa roda o instalador.

🚨 A SENHA NÃO É GUARDADA EM LUGAR NENHUM. Ela é DERIVADA aqui, na VPS, por
HMAC-SHA256 de um segredo próprio (`MOVIZAP_LIGACOES_SENHA_SEGREDO`, nunca o
`jwt_secret`) sobre `(ramal, janela de 10 minutos)`. O instalador não sabe
derivar nada: ele manda o que a pessoa digitou e esta função responde sim ou
não. Decompilar o `.exe` entrega a URL pública, e nada mais -- se o algoritmo
rodasse no PC, quem o abrisse passaria a FABRICAR senhas.

🚨 USO ÚNICO. A janela gasta vira linha em `alistamento_queimado`, e
`UNIQUE (ramal, janela)` é a trava: a mesma senha não alista duas vezes.

⏱️ **A senha vale 48 HORAS** (pedido dele em 15/10). Ela TROCA a cada 10 minutos,
e as senhas das últimas 24 h continuam sendo aceitas -- as duas coisas são
diferentes, e é essa separação que mantém a retentativa custando 10 minutos.
Ver o comentário de `JANELAS_ACEITAS`, que explica por que mexer na janela de
geração seria defeito.

🚨 A SENHA SÓ ALISTA. Ela não vale para o batimento nem para o envio: depois
do alistamento quem trabalha é a chave do agente mais o certificado do PC,
como já era. Se cada execução pedisse senha, a tarefa das 12:00 e 17:30
pararia de funcionar -- não haveria ninguém na frente do PC para digitar.

Limite de tentativas: o `ratelimit` que já trava o login (contador em SQLite,
sobrevive a restart, e `ip_do_cliente` que lê o X-Real-IP só quando a conexão
vem do proxy local). Chave `ip|alistar:<ramal>`, para o erro de um PC não
trancar o ramal de outro. Toda recusa vai para o log com ramal, PC e IP.
"""
import hashlib
import hmac
import logging
import re
import secrets
import time

import psycopg

from . import banco, ligacoes, ligacoes_ca, ratelimit
from .config import settings
from .operacao import DadoInvalido

log = logging.getLogger("movizap.ligacoes.alistar")

JANELA_S = 600               # 10 minutos: é de quanto em quanto tempo a senha TROCA

# 🔵 15/10, pedido dele: *"podemos prolongar as senhas para 1 dia por
# enquanto?"*. São as últimas 24 h de senhas daquele ramal.
#
# 🚨 QUEM MUDA É A ACEITAÇÃO, NUNCA A JANELA DE GERAÇÃO. `JANELA_S = 86400`
# pareceria o caminho óbvio e seria defeito grave: `UNIQUE (ramal, janela)` é o
# que faz a senha servir UMA VEZ, então uma janela de um dia viraria **um
# alistamento por ramal por dia** -- e um alistamento que falhasse depois de a
# janela queimar (erro de certificado, rede caindo no meio) deixaria o ramal
# travado até o dia seguinte, porque "peça outra senha" devolveria a mesma
# senha já queimada. Com a geração de 10 min, uma falha custa 10 minutos.
#
# ⚠️ O QUE ISSO CUSTA, por escrito: uma senha ditada e NÃO usada continua
# servindo por até um dia, em vez de 20 minutos. Ela continua de uso único (a
# primeira utilização queima a janela), continua só alistando, e 5 erros
# seguidos continuam trancando o IP. O risco que cresce é o de alguém que
# ouviu a senha alistar o PC errado antes da pessoa certa -- e isso aparece na
# hora, porque alistar revoga o PC anterior e o vigia acusa o PC que parou de
# falar.
#
# ⚠️ Para voltar a 20 minutos é esta linha, e só ela: `JANELAS_ACEITAS = 2`.
JANELAS_ACEITAS = 288        # 288 × 10 min = 48 h (pedido dele, 15/10)

# 🔵 23/11, DELE: *"coloque a senha nova padrao de Movisat!@"* -- o valor de
# hoje está em `config.ligacoes_senha_fixa`.
# ⚠️ E O EFETIVO É `MOVISAT`: `senha_fixa()` passa a `_limpar()`, que
# maiusculiza e descarta o que não é `A-Z2-9` -- o `!@` sai. Digitar
# `Movisat!@`, `movisat` ou `MOVISAT` casa com a mesma linha.
#
# 🔵 13/11, DELE: *"deixar senha padrão de 'movicall' (essa senha não há muita
# exigência de segredo)"*. A senha derivada por HMAC continua existindo e
# continua valendo -- esta é um ATALHO, não uma substituição.
#
# 🚨 O QUE ELA CUSTA, POR ESCRITO: quem souber a senha padrão e um ramal alista um
# PC naquele ramal. Ele decidiu que o segredo aqui não é exigência, e as outras
# travas ficam de pé: limite de tentativas por IP, ramal que tem de existir e
# estar ativo, e certificado de cliente emitido para aquele PC.
#
# ⚠️ ELA NÃO QUEIMA JANELA, e isso é o ponto: a senha derivada serve UMA vez
# porque `UNIQUE (ramal, janela)` a trava. Se a fixa queimasse, o primeiro PC a
# usá-la trancaria todos os outros -- o oposto do pedido, que é justamente
# poder sair instalando nas máquinas.
CHAVE_SENHA_FIXA = "ligacoes_senha_fixa"


def senha_fixa() -> str:
    """A senha padrão de alistamento, LITERAL. Vazia TRANCA o alistamento.

    🚨 24/11: NÃO passa mais pelo `_limpar`. Enquanto passava, o valor
    guardado era reduzido a `A-Z2-9` -- `Movisat!@` virava `MOVISAT` no banco
    e na comparação, e por isso `MOVISAT`, `movisat` e `mo-vi-sat` alistavam
    igual. 🔵 Ele pediu *"Somente 'Movisat!@'"*: o valor vale como está
    escrito, com maiúscula e com símbolo.

    ⚠️ VAZIA NÃO É MAIS "DESLIGA O ATALHO": desde que a senha derivada deixou
    de alistar, esta é a única porta, e vazia significa que ninguém alista.
    """
    linha = banco.um("SELECT valor FROM config WHERE chave = %s",
                     (CHAVE_SENHA_FIXA,))
    return ((linha or {}).get("valor") or "").strip()
TAMANHO = 8
# Sem I, O, 0 e 1: a senha é DITADA por telefone, e "I" virando "1" custa uma
# tentativa queimada de verdade.
ALFABETO = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


class SenhaInvalida(Exception):
    """Senha errada, vencida ou já usada. Vira 401 na rota."""


# ------------------------------------------------------------------ a senha

def _segredo() -> bytes:
    bruto = settings.ligacoes_senha_segredo
    if len(bruto) < 32:
        raise DadoInvalido(
            "Falta MOVIZAP_LIGACOES_SENHA_SEGREDO no .env (32 caracteres ou mais).")
    return bruto.encode("utf-8")


def janela_de(quando: float | None = None) -> int:
    return int((quando if quando is not None else time.time()) // JANELA_S)


def senha_da_janela(ramal: str, janela: int) -> str:
    """A senha daquele ramal naquela janela. Mesma entrada, mesma senha —
    é isso que permite a ele ler a senha sem que ninguém a guarde."""
    mac = hmac.new(_segredo(), f"{ramal}:{janela}".encode("utf-8"), hashlib.sha256).digest()
    valor = int.from_bytes(mac, "big")
    letras = []
    for _ in range(TAMANHO):
        valor, resto = divmod(valor, len(ALFABETO))
        letras.append(ALFABETO[resto])
    return "".join(letras)


def formatar(senha: str) -> str:
    """`ABCD-EFGH`: a senha é ditada em voz alta, e o hífen evita que a pessoa
    se perca no meio."""
    return f"{senha[:4]}-{senha[4:]}"


def _limpar(digitado: str) -> str:
    """Aceita como a pessoa digitou: minúscula, com hífen, com espaço."""
    return re.sub(r"[^A-Z2-9]", "", (digitado or "").upper())


def segundos_restantes(janela: int | None = None) -> int:
    """Quanto tempo esta senha AINDA SERVE.

    🚨 É até o fim da última janela que ainda a aceita, e não até o fim da
    janela em que ela nasceu. Enquanto media só a janela de geração, a
    ferramenta dizia "vale por 7 min" de uma senha que valia um dia -- e
    ferramenta que mente sobre o próprio prazo faz ele pedir senha nova sem
    precisar, ou desistir de uma que ainda servia.
    """
    janela = janela if janela is not None else janela_de()
    return int((janela + JANELAS_ACEITAS) * JANELA_S - time.time())


# ------------------------------------------------- preparar (ferramenta dele)

def preparar(ramal: str, nome: str | None = None) -> dict:
    """Devolve a senha da janela atual do ramal, para ele ditar.

    Com `nome`, amarra o ramal àquele atendente antes (é o que o
    `Preparar operador` fazia, menos a chave: a chave passa a nascer no
    alistamento). Sem `nome`, o ramal já tem de estar amarrado a alguém —
    senão não há a quem atribuir as ligações.
    """
    ramal = (ramal or "").strip()
    if not ramal.isdigit():
        raise DadoInvalido("O ramal é só número (ex.: 3404).")

    if nome:
        achados = banco.varios(
            """SELECT id, nome, ramal FROM atendente
                WHERE ativo AND lower(nome) LIKE lower(%s) ORDER BY nome""",
            (f"%{nome.strip()}%",))
        if not achados:
            raise DadoInvalido(f"Nenhum atendente ativo com '{nome}' no nome.")
        if len(achados) > 1:
            quais = ", ".join(a["nome"] for a in achados[:6])
            raise DadoInvalido(f"Mais de um atendente com '{nome}' no nome: {quais}.")
        atendente = achados[0]
        dono = banco.um("SELECT id, nome FROM atendente WHERE ramal = %s", (ramal,))
        if dono and dono["id"] != atendente["id"]:
            raise DadoInvalido(f"O ramal {ramal} já é de {dono['nome']}. "
                               "Um ramal é de uma pessoa só.")
        if atendente["ramal"] != ramal:
            banco.executar("UPDATE atendente SET ramal = %s WHERE id = %s",
                           (ramal, atendente["id"]))
            log.info("ramal %s amarrado ao atendente %s", ramal, atendente["id"])
    else:
        atendente = banco.um(
            "SELECT id, nome FROM atendente WHERE ramal = %s AND ativo", (ramal,))
        if not atendente:
            raise DadoInvalido(
                f"O ramal {ramal} não está com ninguém. Use --nome para amarrá-lo.")

    janela = janela_de()
    agente = banco.um("""SELECT ultimo_pc, ultimo_contato_em FROM agente_ligacao
                          WHERE ramal = %s AND revogado_em IS NULL""", (ramal,))
    return {"ramal": ramal, "atendente": atendente["nome"],
            "senha": formatar(senha_da_janela(ramal, janela)),
            "janela": janela, "segundos": segundos_restantes(janela),
            "pc_atual": agente["ultimo_pc"] if agente else None,
            "pc_atual_em": agente["ultimo_contato_em"] if agente else None}


# ---------------------------------------------------------------- o alistamento

def alistar(ramal: str, senha: str, pedido_pem: str | bytes,
            pc: str | None = None, ip: str | None = None) -> dict:
    """Uma chamada e o PC está pronto: confere a senha padrão, revoga o PC
    anterior, cria a chave nova e assina o certificado deste PC.

    🚨 24/11: A SENHA É UMA SÓ, a de `senha_fixa()`, e ela NÃO queima janela —
    serve em quantos PCs precisar. O bloco de `alistamento_queimado` abaixo
    ficou de pé para as linhas que já existem e para o dia em que a senha
    derivada voltar; com `achada` sempre None, ele não roda.

    🚨 Revoga o PC anterior do mesmo ramal (decisão dele, 15/10): quem alista
    de novo está trocando de PC, e dois PCs no mesmo ramal mandariam em
    dobro. Quem faz a revogação é `ligacoes.gerar_chave`, que já era assim.
    """
    ramal = (ramal or "").strip()
    if not ramal.isdigit():
        raise DadoInvalido("O ramal é só número (ex.: 3404).")
    trava = ratelimit.chave_de(ip or "?", f"alistar:{ramal}")
    espera = ratelimit.bloqueado_por(trava)
    if espera > 0:
        log.warning("alistamento do ramal %s barrado por tentativas (pc=%s ip=%s)",
                    ramal, pc, ip)
        raise SenhaInvalida(
            f"Tentativas demais. Espere {espera // 60 + 1} min e peça outra senha.")

    atendente = banco.um(
        "SELECT id, nome FROM atendente WHERE ramal = %s AND ativo", (ramal,))
    # 🔵 24/11, DELE: *"Somente 'Movisat!@'"*. A SENHA DERIVADA DEIXOU DE
    # ALISTAR. `senha_da_janela` continua existindo e continua sem ser
    # guardada (outras ferramentas a importam), mas nenhuma janela abre a
    # porta: a única senha que alista é a de `senha_fixa()`.
    #
    # 🚨 E A COMPARAÇÃO É LITERAL. Até hoje os dois lados passavam pelo
    # `_limpar`, que reduz a `A-Z2-9` -- e por isso `MOVISAT`, `movisat` e
    # `mo-vi-sat` alistavam igual, porque o `!@` era descartado ANTES de
    # comparar. "Somente" quer dizer o valor como está escrito: maiúscula
    # conta, símbolo conta.
    #
    # 🚨 COMPARA EM BYTES, não em str: `compare_digest` com str exige ASCII, e
    # um acento digitado por engano levantaria TypeError -- 500 no lugar do
    # 401 que a pessoa precisa ler.
    #
    # ⚠️ `achada` fica SEMPRE None de propósito: é o que mantém a janela sem
    # ser queimada mais abaixo, e a senha padrão nunca queimou janela (se
    # queimasse, o primeiro PC a usá-la trancaria todos os outros).
    digitada = (senha or "").strip()
    achada = None
    usou_fixa = False
    padrao = senha_fixa()
    if atendente and padrao and secrets.compare_digest(
            digitada.encode("utf-8"), padrao.encode("utf-8")):
        usou_fixa = True
        log.info("alistamento do ramal %s pela senha padrao (pc=%s ip=%s)",
                 ramal, pc, ip)

    if not usou_fixa:
        ratelimit.registrar_falha(trava)
        # Ramal sem dono e senha errada dão a MESMA resposta: dizer qual é o
        # caso entrega a lista de ramais válidos a quem está tentando adivinhar.
        log.warning("alistamento recusado: ramal %s, pc=%s, ip=%s", ramal, pc, ip)
        raise SenhaInvalida("Senha inválida ou vencida. Peça a senha de novo.")

    queimado_id = None
    try:
        with banco.cursor() as cur:
            if achada is not None:
                cur.execute("""INSERT INTO alistamento_queimado (ramal, janela, pc, ip)
                               VALUES (%s, %s, %s, %s) RETURNING id""",
                            (ramal, achada,
                             (pc or "")[:100] or None, (ip or "")[:45] or None))
                queimado_id = cur.fetchone()["id"]
    except psycopg.errors.UniqueViolation as e:
        ratelimit.registrar_falha(trava)
        log.warning("alistamento recusado (senha já usada): ramal %s, pc=%s, ip=%s",
                    ramal, pc, ip)
        raise SenhaInvalida("Essa senha já foi usada. Peça outra.") from e

    anterior = banco.um("""SELECT ultimo_pc FROM agente_ligacao
                            WHERE ramal = %s AND revogado_em IS NULL""", (ramal,))
    chave = ligacoes.gerar_chave(atendente["id"], ramal)   # revoga o PC anterior
    cert = ligacoes_ca.assinar(ramal, pedido_pem)
    # 🚨 O PC fica gravado JÁ NO ALISTAMENTO, não só no primeiro batimento:
    # senão o `Conferir agentes` não sabe dizer em que máquina o ramal entrou
    # enquanto a primeira passada não acontece -- e "PC trocado" ficaria cego
    # justamente no dia da troca.
    banco.executar("""UPDATE agente_ligacao
                         SET ultimo_pc = %s, ultimo_ip = COALESCE(%s, ultimo_ip)
                       WHERE id = %s""",
                   ((pc or "")[:100] or None, (ip or "")[:45] or None, cert["agente_id"]))
    if queimado_id is not None:
        banco.executar("UPDATE alistamento_queimado SET agente_id = %s WHERE id = %s",
                       (cert["agente_id"], queimado_id))
    ratelimit.registrar_sucesso(trava)
    log.info("ramal %s alistado no PC %s (agente %s); PC anterior: %s",
             ramal, pc, cert["agente_id"], anterior["ultimo_pc"] if anterior else "nenhum")
    return {"ok": True, "ramal": ramal, "atendente": atendente["nome"],
            "chave": chave, "cert_pem": cert["pem"],
            "cert_validade": cert["validade"].isoformat(),
            "pc_anterior": anterior["ultimo_pc"] if anterior else None}
