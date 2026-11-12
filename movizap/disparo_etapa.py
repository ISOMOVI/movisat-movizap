"""O DISPARO DA ETAPA — a mensagem que a etapa manda ao cliente (migração 102).

🔵 Pedido dele (11/11): *"Em configurações tela nova de 'Disparos Operação' ->
Deixar o campo de menagens que são enviadas em cada etapa do fluxo com
interruptor de 'ligado e desligado'"*, e, sobre como sai: *"inicialmente todo o
painel pronto com interuptor desligado, depois será validado em tela as
mensagens e ao ligar o interruptor, sairá automaticamente como na regra"*.

🚨 ESTA É A PRIMEIRA COISA DO PAINEL QUE FALA COM O CLIENTE SOZINHA, e isso
afrouxa — por decisão dele — a régua da ÁREA F de 04/11, que exigia confirmação
antes de cada envio. O que protege agora:

  1. **nasce desligada e sem texto**, e o banco não deixa ligar vazia;
  2. **nunca envia ao técnico** (*"por enquanto somente cliente"*), e não há
     caminho no código para isso -- o destinatário é derivado da OS, não
     escolhido;
  3. **falhar no envio não desfaz o mover** nem derruba a tela; fica registrado
     como observação do sistema no card;
  4. **só canal de atendimento**: o canal informativo é de campanha, e mandar
     mensagem de operação por ele a misturaria com disparo em massa.

⚠️ `canal` É SÓ WHATSAPP POR ORA (*"por hora só whatsapp"*), e o CHECK da 102
guarda isso: e-mail exige migração, de propósito -- canal novo muda para quem a
mensagem vai.
"""
import logging
import re

from . import banco
from .operacao import DadoInvalido

log = logging.getLogger("movizap.disparo_etapa")

TETO_TEXTO = 2000

# As variáveis que o texto dele usa, com as palavras dele (04/11).
#
# 🚨 A GRAFIA É A DELE, LITERAL, e não se "melhora": ele escreve o texto na
# tela copiando estes nomes, e qualquer divergência deixaria a variável sem
# resolver -- aparecendo crua para o cliente.
# ⚠️ O texto que ele passou em 04/11 NÃO sobreviveu em documento nenhum: do
# bloco daquele dia restaram só estes três nomes. Nada foi semeado.
VARIAVEIS = {
    "{{Contato: Primeiro nome}}": "primeiro nome do contato do cliente",
    "{{Nome}}": "o número da OS",
    "{{Código de envio/acompanhamento transporte}}":
        "o código de rastreio gravado na etapa 677",
}


def todos() -> list[dict]:
    """Uma linha por etapa, na ordem das colunas do painel."""
    from . import paineis
    ordem = {sid: i for i, (sid, _) in enumerate(paineis.SITUACOES)}
    linhas = banco.varios(
        """SELECT m.id, m.situacao_id, m.canal, m.texto, m.ativo,
                  m.atualizado_em, a.nome AS atualizado_por_nome
             FROM etapa_mensagem m
             LEFT JOIN atendente a ON a.id = m.atualizado_por""")
    nomes = dict(paineis.SITUACOES)
    # 🚨 AS TRES QUE SAIRAM DA OPERACAO EM 11/11 (15746, 15695, 16492) ainda
    # TEM LINHA nesta tabela, e as linhas ficam: apagar seria destruir
    # cadastro por causa de uma mudanca de layout. O que elas nao tem mais e
    # COLUNA -- e um disparo "ao mover para uma etapa que nao existe neste
    # painel" nao dispara nunca.
    #
    # ⚠️ Entao a tela nao as lista. As tres estao congeladas: `definir()` ja
    # recusa qualquer situacao fora das colunas, e todas as 17 nasceram
    # VAZIAS e DESLIGADAS -- nenhuma mensagem se perde.
    linhas = [l for l in linhas if l["situacao_id"] in nomes]
    for linha in linhas:
        linha["nome"] = nomes.get(linha["situacao_id"])
    return sorted(linhas, key=lambda x: ordem.get(x["situacao_id"], 999))


def da_etapa(situacao_id: int) -> dict | None:
    return banco.um(
        "SELECT id, situacao_id, canal, texto, ativo FROM etapa_mensagem "
        "WHERE situacao_id = %s", (int(situacao_id),))


def definir(situacao_id: int, texto: str | None, ativo: bool,
            atendente_id: int | None = None) -> dict:
    """Guarda o texto e o interruptor de uma etapa.

    🚨 LIGAR SEM TEXTO É RECUSADO AQUI **E** NO BANCO. Aqui para a pessoa ler
    uma frase; no banco porque é a única garantia que não depende de alguém ter
    lembrado.
    """
    from . import paineis
    situacao_id = int(situacao_id)
    if situacao_id not in dict(paineis.SITUACOES):
        raise DadoInvalido(
            f"A situação {situacao_id} não é uma das colunas do painel da "
            f"Operação.")

    limpo = (texto or "").strip() or None
    if limpo and len(limpo) > TETO_TEXTO:
        raise DadoInvalido(
            f"A mensagem passa de {TETO_TEXTO} caracteres.")
    if ativo and not limpo:
        raise DadoInvalido(
            "Escreva a mensagem antes de ligar o disparo desta etapa.")

    banco.executar(
        """UPDATE etapa_mensagem
              SET texto = %s, ativo = %s, atualizado_em = now(),
                  atualizado_por = %s
            WHERE situacao_id = %s""",
        (limpo, bool(ativo), atendente_id, situacao_id))
    log.info("disparo da etapa %s: ativo=%s, %s caracteres, por %s",
             situacao_id, bool(ativo), len(limpo or ""), atendente_id)
    return da_etapa(situacao_id)


def resolver(texto: str, contexto: dict) -> str:
    """Troca as variáveis dele pelos valores. O que não tem valor vira vazio.

    ⚠️ VARIÁVEL SEM VALOR SAI COMO NADA, e não como `{{...}}` cru: o cliente não
    tem o que fazer com a chave, e ver a chave é pior que ver a frase um pouco
    mais curta.
    ⚠️ O primeiro nome cai em *"tudo bem"* quando não há nome -- é o que o plano
    de 04/11 já previa, para a frase não começar com um vazio.
    """
    nome = (contexto.get("contato_nome") or "").strip()
    primeiro = nome.split()[0] if nome else "tudo bem"
    valores = {
        "{{Contato: Primeiro nome}}": primeiro,
        "{{Nome}}": str(contexto.get("numero_os") or ""),
        "{{Código de envio/acompanhamento transporte}}":
            str(contexto.get("rastreio") or ""),
    }
    saida = texto or ""
    for chave, valor in valores.items():
        saida = saida.replace(chave, valor)
    # 🚨 Qualquer `{{...}}` que sobrou sai FORA. Variável que eu não conheço
    # chegando ao cliente é o pior resultado possível desta função.
    sobrou = re.findall(r"\{\{[^}]*\}\}", saida)
    if sobrou:
        log.warning("variaveis desconhecidas no disparo: %s", sobrou)
        saida = re.sub(r"\{\{[^}]*\}\}", "", saida)
    return re.sub(r"[ \t]{2,}", " ", saida).strip()


def _canal_de_atendimento() -> dict | None:
    """O canal por onde a mensagem sai.

    🚨 **NUNCA O CANAL INFORMATIVO.** Ele é de campanha (`informativos.py`), e
    mandar mensagem de operação por ele a misturaria com disparo em massa -- com
    o número errado na tela do cliente.
    ⚠️ Escolher canal é frente própria: hoje existe **um** de atendimento.
    """
    # ⚠️ `estado` NAO E COLUNA do canal -- e derivado do Evolution a cada
    # leitura (`canais.listar`). Conferir conexao aqui custaria uma ida ao
    # gateway dentro do clique de mover; se o canal estiver fora do ar, o
    # proprio envio falha e o motivo chega na observacao do card.
    return banco.um(
        """SELECT id, nome FROM canal
            WHERE ativo AND tipo = 'atendimento'
            ORDER BY id LIMIT 1""")


def enviar_da_etapa(numero_os: int, situacao_id: int,
                    atendente_id: int | None = None) -> dict:
    """Manda a mensagem da etapa, se houver uma LIGADA. Devolve o que aconteceu.

    🚨 NÃO LEVANTA. Quem chama é o `passagem.mover`, e **mover tem de continuar
    funcionando** quando o WhatsApp, o ERP ou o canal falham: o card já mudou de
    situação no ERP quando esta função roda. Todo retorno é um dicionário com
    `enviou` e `motivo`.

    ⚠️ E NÃO FALA COM O `evolution` CRU: o envio passa pelo
    `conversas.iniciar_conversa`, que valida se o número tem WhatsApp, reusa a
    conversa aberta e **grava a mensagem na conversa**. Enviar por fora deixaria
    o cliente com uma mensagem que a operação não vê.
    """
    conf = da_etapa(situacao_id)
    if not conf or not conf["ativo"] or not (conf["texto"] or "").strip():
        return {"enviou": False, "motivo": "desligado"}

    canal = _canal_de_atendimento()
    if not canal:
        log.warning("disparo da etapa %s: nenhum canal de atendimento conectado",
                    situacao_id)
        return {"enviou": False, "motivo": "sem canal de atendimento conectado"}

    # O destinatário é DERIVADO da OS, nunca escolhido -- é o que garante o
    # *"por enquanto somente cliente"* sem depender de ninguém lembrar.
    from . import campo_etapa, fpsl_ponte
    try:
        ficha = fpsl_ponte.ficha_da_os(numero_os)
    except Exception as e:  # noqa: BLE001
        log.warning("disparo da etapa %s: nao li a OS %s: %s",
                    situacao_id, numero_os, e)
        return {"enviou": False, "motivo": f"não consegui ler a OS: {e}"}

    telefone = (ficha.get("cliente_telefone") or "").strip()
    if not telefone:
        return {"enviou": False,
                "motivo": "a OS não tem telefone do cliente"}

    rastreio = (campo_etapa.atuais(numero_os).get("rastreio") or {}).get("valor")
    texto = resolver(conf["texto"], {
        "contato_nome": ficha.get("cliente") or ficha.get("cliente_nome"),
        "numero_os": numero_os,
        "rastreio": rastreio,
    })
    if not texto:
        return {"enviou": False, "motivo": "a mensagem ficou vazia"}

    from . import conversas
    try:
        r = conversas.iniciar_conversa(canal["id"], telefone, texto,
                                       atendente_id)
    except Exception as e:  # noqa: BLE001
        log.warning("disparo da etapa %s: nao enviei para a OS %s: %s",
                    situacao_id, numero_os, e)
        return {"enviou": False, "motivo": str(e)}

    log.info("disparo da etapa %s enviado para a OS %s (conversa %s)",
             situacao_id, numero_os, (r or {}).get("conversa_id"))
    return {"enviou": True, "motivo": None, "telefone": telefone,
            "conversa_id": (r or {}).get("conversa_id"), "texto": texto}
