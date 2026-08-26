"""Versões do prompt da IA — a `CFG_2.1`.

🚨 ESTE MÓDULO CONTINUA NÃO FALANDO COM MODELO NENHUM, mesmo depois que o
motor entrou em 26/08. Ele guarda texto versionado e monta a pré-visualização
do que a IA receberia; quem chama o modelo é `movizap/ia.py`, e quem sabe da
chave é `movizap/llm/`. A separação é o que permite escrever, revisar e
versionar o prompt inteiro sem risco de responder a um cliente de verdade.

⚠️ `motor_existe` DEIXOU DE SER CONSTANTE. Ele agora pergunta ao motor, e o
motor responde `False` quando falta chave -- então a tela continua honesta nos
dois mundos, sem ninguém lembrar de trocar um literal.

🚨 A CONVERSA GRAVA QUAL VERSÃO A ATENDEU (`conversa.prompt_versao_id`, que já
existe no banco). Sem isso, "a IA respondeu errado semana passada" é uma
frase irrespondível: o texto já mudou e ninguém sabe o que ela lia na hora.
"""
import logging

from . import banco

log = logging.getLogger("movizap.prompt")

# As 7 camadas do `docs/06_Conteudo_das_Telas.md`. Serve de ponto de partida
# quando ainda não existe nenhuma versão -- tela em branco convida a improviso,
# e prompt improvisado é o que responde errado para cliente real.
SUGESTAO_INICIAL = """\
# 1. QUEM SOMOS
Você atende no WhatsApp da Movisat, que trabalha com rastreamento de frotas.
Fale em português do Brasil, por você, com frases curtas. Sem menu numerado:
o cliente escreve do jeito dele e você entende.

# 2. O QUE VOCÊ PODE FAZER
Consultar, pelas ferramentas disponíveis: cliente, veículo, contrato e fatura.
Sempre que responder um dado, ele tem que ter vindo de uma consulta.

# 3. O QUE VOCÊ NÃO PODE FAZER
Prometer prazo. Dar desconto. Cancelar contrato. Falar de valor que você não
leu. Inventar número de protocolo. Se não sabe, diga que vai transferir.

# 4. COMO TRIAR
Identificar quem é -> entender o que quer -> resolver se der -> transferir com
um resumo do que já foi conversado.

# 5. PARA ONDE MANDAR
(As descrições dos times entram aqui automaticamente, do CAD_2.2.)

# 6. QUANDO CALAR
Assim que um atendente humano assumir a conversa, pare de responder e não
volte sozinha. Só volta se alguém devolver a conversa para você.

# 7. LIMITES DO CANAL
Ainda não dá para receber nem mandar arquivo. Avise o cliente em vez de
prometer e falhar.
"""


class SemVersao(Exception):
    """Não há versão publicada. Vira 404 -- e a tela oferece a sugestão."""


def _linha(sql: str, params: tuple = ()) -> dict | None:
    return banco.um(
        "SELECT p.id, p.versao, p.conteudo, p.ativo, p.criado_em, p.autor_id, "
        "       a.nome AS autor_nome "
        "  FROM prompt_versao p LEFT JOIN atendente a ON a.id = p.autor_id " + sql,
        params)


def ativa() -> dict | None:
    return _linha("WHERE p.ativo")


def ver(versao_id: int) -> dict | None:
    return _linha("WHERE p.id = %s", (versao_id,))


def listar() -> list[dict]:
    """O histórico, mais novo primeiro. Sem o conteúdo: a lista não precisa
    carregar sete versões de texto para mostrar data e autor."""
    return banco.varios(
        """SELECT p.id, p.versao, p.ativo, p.criado_em, p.autor_id,
                  a.nome AS autor_nome, length(p.conteudo) AS tamanho
             FROM prompt_versao p LEFT JOIN atendente a ON a.id = p.autor_id
            ORDER BY p.versao DESC""")


def criar(conteudo: str, autor_id: int | None = None,
          publicar_agora: bool = False) -> dict:
    """Grava uma versão nova. Publicar é decisão separada, e é isso que
    permite escrever e revisar sem trocar o que está valendo."""
    conteudo = (conteudo or "").strip()
    if len(conteudo) < 50:
        raise ValueError("O prompt está curto demais para valer como versão.")

    with banco.cursor() as cur:
        cur.execute("SELECT COALESCE(MAX(versao), 0) + 1 AS proxima FROM prompt_versao")
        proxima = cur.fetchone()["proxima"]
        if publicar_agora:
            cur.execute("UPDATE prompt_versao SET ativo = false WHERE ativo")
        cur.execute(
            """INSERT INTO prompt_versao (versao, conteudo, autor_id, ativo)
               VALUES (%s, %s, %s, %s) RETURNING id""",
            (proxima, conteudo, autor_id, publicar_agora))
        novo = cur.fetchone()["id"]
    log.info("prompt versão %s gravada (publicada=%s)", proxima, publicar_agora)
    return ver(novo)


def publicar(versao_id: int) -> dict:
    """Torna esta versão a ativa. É também o "voltar para a anterior".

    🚨 Os dois UPDATE vão na MESMA transação. `ux_prompt_ativo` é único em
    `(ativo) WHERE ativo`: se o desligar e o ligar ficassem em transações
    separadas, uma falha no meio deixaria o sistema sem versão ativa nenhuma.
    """
    if not banco.um("SELECT id FROM prompt_versao WHERE id = %s", (versao_id,)):
        raise SemVersao("Versão não encontrada.")
    with banco.cursor() as cur:
        cur.execute("UPDATE prompt_versao SET ativo = false WHERE ativo")
        cur.execute("UPDATE prompt_versao SET ativo = true WHERE id = %s", (versao_id,))
    log.info("prompt versão id=%s publicada", versao_id)
    return ver(versao_id)


def bloco_dos_times() -> str:
    """A camada 5, montada do CAD_2.2 na hora de usar.

    ⚠️ Não é copiada para dentro do texto da versão de propósito: time criado
    ou descrição corrigida depois passaria a mentir dentro de um prompt
    congelado, e ninguém desconfiaria.
    """
    times = banco.varios(
        "SELECT nome, descricao FROM time WHERE ativo ORDER BY nome")
    if not times:
        return "(Nenhum time ativo cadastrado.)"
    linhas = []
    for t in times:
        descricao = (t["descricao"] or "").strip()
        linhas.append(f"- {t['nome']}: {descricao or '(sem descrição -- a IA vai chutar)'}")
    return "\n".join(linhas)


def montado(versao_id: int | None = None) -> dict:
    """O texto como a IA receberia: a versão + a camada 5 preenchida.

    É o que a tela chama de pré-visualização. ⚠️ Não é o "rascunho testável"
    inteiro que o doc pede -- testar de verdade exige o modelo, que é o passo
    8. Aqui dá para ver o texto final e conferir se algum time entrou sem
    descrição; não dá para ver a IA respondendo.
    """
    versao = ver(versao_id) if versao_id else ativa()
    if not versao:
        raise SemVersao("Nenhuma versão de prompt existe ainda.")
    conteudo = versao["conteudo"]
    bloco = bloco_dos_times()
    marca = "(As descrições dos times entram aqui automaticamente, do CAD_2.2.)"
    if marca in conteudo:
        final = conteudo.replace(marca, bloco)
    else:
        final = f"{conteudo}\n\n# TIMES DISPONÍVEIS\n{bloco}"
    return {"versao": versao["versao"], "id": versao["id"], "ativo": versao["ativo"],
            "texto": final, "times_no_prompt": bloco}


def estado() -> dict:
    """O cabeçalho da tela: o que está valendo e se a IA está de fato ligada.

    🚨 As duas perguntas são diferentes. Ter prompt publicado NÃO significa que
    a IA responde: quem decide isso é `canal.ia_ligada`, por canal, e hoje os
    dois estão desligados. Mostrar só o prompt faria a tela sugerir que a IA
    está no ar.

    ⚠️ Importação tardia do `ia`: ele importa este módulo. No topo, os dois se
    importariam em círculo e o painel não subiria.
    """
    from . import ia

    canais = banco.varios(
        "SELECT nome, tipo, ia_ligada, ia_ligada_em FROM canal WHERE ativo ORDER BY nome")
    versao = ativa()
    motor = ia.estado()
    return {
        "versao_ativa": ({"id": versao["id"], "versao": versao["versao"],
                          "criado_em": versao["criado_em"],
                          "autor_nome": versao["autor_nome"]} if versao else None),
        "total_versoes": banco.um("SELECT COUNT(*) AS n FROM prompt_versao")["n"],
        "canais": canais,
        # 🚨 MEDIDO, NÃO ESCRITO. Era um literal `False` e teria continuado
        # `False` depois de o motor entrar -- exatamente o tipo de contador em
        # prosa que nasce errado e ninguém percebe.
        "motor_existe": bool(motor["disponivel"]),
        "motor": motor,
    }
