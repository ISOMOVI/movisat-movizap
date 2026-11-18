"""O DISPARO DA ETAPA — a mensagem que a etapa manda ao cliente (migração 102).

🔵 Pedido dele (11/11): *"Em configurações tela nova de 'Disparos Operação' ->
Deixar o campo de menagens que são enviadas em cada etapa do fluxo com
interruptor de 'ligado e desligado'"*, e, sobre como sai: *"inicialmente todo o
painel pronto com interuptor desligado, depois será validado em tela as
mensagens e ao ligar o interruptor, sairá automaticamente como na regra"*.

🚨 **17/11: O INTERRUPTOR PASSA A SIGNIFICAR "PERGUNTA", NÃO "MANDA".** Decisão
dele: *"quando o card for movido e houver disparo de mensagens perguntar em
caixa de diálogo (se tiver ligado o interruptor) 'Deseja enviar aviso ao
cliente?' Se Sim = abre a mensagem que será enviada e permite edição rápida
dela e o botão enviar envia (...) Se clicar não, não envia nada."*

  Isto **inverte, com autorização, o "sairá automaticamente" de 11/11** e
  restaura a régua da ÁREA F de 04/11, que exigia confirmação antes de cada
  envio -- a mesma que a 102 havia afrouxado de propósito. Está escrito aqui
  para ninguém "consertar" de volta achando que é engano.

  🚨 **NENHUMA FUNÇÃO DESTE MÓDULO É CHAMADA PELO `mover` PARA ENVIAR.** O
  `passagem.mover` só chama o `preparar_da_etapa`, que **não fala com ninguém**;
  quem envia é a rota do disparo, atrás de um clique. Quem procurar aqui a
  função que o mover usava (`enviar_da_etapa`) não vai achar: ela foi partida
  em duas de propósito, e isso é a trava mais importante do arquivo.

O que protege o cliente, hoje:

  1. **nasce desligada e sem texto**, e o banco não deixa ligar vazia;
  2. **nunca envia ao técnico** (*"por enquanto somente cliente"*), e não há
     caminho no código para isso -- o destinatário é derivado da OS, não
     escolhido;
  3. **o operador vê o texto e o destinatário antes**, e pode editar;
  4. **uma decisão por passagem** (migração 111): a mesma passagem não envia
     duas vezes, e recarregar a tela não reenvia;
  5. **falhar no envio não desfaz o mover** nem derruba a tela; fica registrado
     como observação do sistema no card;
  6. **só canal de atendimento**: o canal informativo é de campanha, e mandar
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

# As variáveis que o texto dele usa, com as palavras dele (04/11 e 17/11).
#
# 🚨 A GRAFIA É A DELE, LITERAL, e não se "melhora": ele escreve o texto na
# tela copiando estes nomes, e qualquer divergência deixaria a variável sem
# resolver -- aparecendo crua para o cliente.
# ⚠️ O texto que ele passou em 04/11 NÃO sobreviveu em documento nenhum: do
# bloco daquele dia restaram só os três primeiros nomes. Nada foi semeado.
# 🆕 17/11: as três últimas são dele, copiadas das mensagens que ele já
# escreveu na `CFG_16.1`. ⚠️ `{{Nome}}` continua sendo **o número da OS** --
# parece nome de pessoa e não é, e trocar o significado agora mudaria em
# silêncio as mensagens que ele já escreveu.
VARIAVEIS = {
    "{{Contato: Primeiro nome}}": "primeiro nome do contato do cliente",
    "{{Nome}}": "o número da OS",
    "{{Código de envio/acompanhamento transporte}}":
        "o código de rastreio gravado na etapa 677",
    "{{Termo}}": "o número do termo, lido da descrição da OS",
    "{{Serviço Técnico}}": "o serviço, lido da descrição da OS",
    "{{Veículo e Placa}}": "o veículo e a placa, lidos da descrição da OS",
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


# ── O que se lê da DESCRIÇÃO da OS (17/11) ───────────────────────────────────
#
# 🔵 DECISÃO DELE, 17/11: o `{{Termo}}`, o `{{Serviço Técnico}}` e o
# `{{Veículo e Placa}}` saem do **texto da descrição da OS**.
#
# 📏 MEDIDO ANTES, em 6 OS reais pela ponte, e é o que descartou as outras
# fontes: `ficha.placas` veio **VAZIA em 6 de 6** (a placa vem da oficina, e só
# 236 de 572 OS têm oficina), e `ficha.problema` veio como **número** (7502,
# 7384) e não como nome. A descrição, essa sim, trazia tudo em texto:
#
#   'Retirada: TJN 0B09 | FABIANO ALPHA ROTA NORTE | 007563342 (Suntech ST310)
#    | TERMO 8952 | O.S: 17126'
#
# 🚨 O FORMATO NÃO É ADIVINHAÇÃO: são os `descricao_template` do FPSL que o
# escrevem, e todos têm a forma `PREFIXO: {placa} | {veiculo} | ...`, com
# `| TERMO {termo}` quando vem de contrato. Os prefixos medidos: `Instalação`,
# `Retirada`, `SUBSTITUIÇÃO RETIRADA`, `SUBSTITUIÇÃO INSTALAÇÃO`,
# `TRANSFERENCIA TITULARIDADE (ANTIGO TITULAR)`, `Upgrade`,
# `MANUTENÇÃO NO LOCAL`, `MANUTENÇÃO COM TROCA`.
#
# ⚠️ MANUTENÇÃO NÃO TEM TERMO, e isso é da natureza dela: não vem de contrato,
# e o template dela não escreve TERMO nenhum. `{{Termo}}` sair vazio ali é
# certo, não defeito -- medido: 1 das 6 OS da amostra tinha TERMO.
_RX_TERMO = re.compile(r"TERMO\s+([A-Za-z0-9][A-Za-z0-9\-/\.]*)", re.I)


def _da_descricao(descricao: str | None) -> dict:
    """Serviço, placa, veículo e termo, lidos da descrição da OS.

    🚨 NUNCA LEVANTA E NUNCA ADIVINHA. Descrição fora do padrão devolve tudo
    vazio, e a régua do `resolver` faz o resto: variável sem valor sai como
    nada. Inventar valor aqui mandaria texto errado ao cliente, que é pior que
    uma frase mais curta.

    ⚠️ A GUARDA É ESTRUTURAL, NÃO DE VOCABULÁRIO: só aceita o prefixo como
    serviço se **depois dos dois pontos houver pelo menos um `|`**. Sem isso,
    uma OS aberta à mão com *"Cliente pediu X: fazer Y"* teria "Cliente pediu X"
    como serviço. Conferir o prefixo contra uma lista de nomes seria criar aqui
    uma sétima lista de serviços do ecossistema -- e ela divergiria na primeira
    operação nova do FPSL.
    """
    vazio = {"servico": "", "placa": "", "veiculo": "", "termo": ""}
    texto = (descricao or "").strip()
    if not texto:
        return vazio

    achado = dict(vazio)
    m = _RX_TERMO.search(texto)
    if m:
        achado["termo"] = m.group(1).strip(" .|")

    prefixo, dois_pontos, resto = texto.partition(":")
    if not dois_pontos or "|" not in resto or "|" in prefixo:
        return achado
    achado["servico"] = prefixo.strip()
    partes = [p.strip() for p in resto.split("|")]
    achado["placa"] = partes[0] if partes else ""
    # ⚠️ RISCO MEDIDO: o nome do veículo pode conter ` | ` ('M. BENZ | 314 CDIS
    # TREET C'), e aí este segundo segmento perde a cauda. Fica o começo, que é
    # o que identifica o veículo para o cliente -- juntar até o próximo segmento
    # "técnico" (série, SAIRÁ, TERMO, O.S) seria heurística com mais chance de
    # errar do que de acertar. A placa, que é o 1º segmento, foi consistente em
    # 3 de 3 descrições legíveis.
    achado["veiculo"] = partes[1] if len(partes) > 1 else ""
    return achado


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
    da_os = _da_descricao(contexto.get("descricao"))
    # 🆕 17/11: *"Veículo e Placa"* na ordem em que ele escreveu a chave, e o
    # separador é ` - ` porque é o que esta casa já usa para dizer "depois disto
    # vem a placa" (a régua do `reference_placa_identificador`).
    veiculo_e_placa = " - ".join(p for p in (da_os["veiculo"], da_os["placa"]) if p)
    valores = {
        "{{Contato: Primeiro nome}}": primeiro,
        "{{Nome}}": str(contexto.get("numero_os") or ""),
        "{{Código de envio/acompanhamento transporte}}":
            str(contexto.get("rastreio") or ""),
        "{{Termo}}": da_os["termo"],
        "{{Serviço Técnico}}": da_os["servico"],
        "{{Veículo e Placa}}": veiculo_e_placa,
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


def telefone_da_os(ficha: dict) -> dict:
    """Para quem a mensagem vai: o contato da OS e, faltando, o do cadastro.

    🔵 DECISÃO DELE, 17/11: *"envia para o numero que estiver como contato na
    OS e depois do cliente"*, e, perguntado se era um envio ou dois, ele
    escolheu **um envio, com reserva** -- o contato da OS manda, e o telefone
    do cliente cadastrado é o caminho de quem não tem contato na OS.

    🚨 CONTINUA DERIVADO, NUNCA ESCOLHIDO. É o que garante o *"por enquanto
    somente cliente"* sem depender de ninguém lembrar: não existe parâmetro
    nesta função para dizer "manda para outro número".

    📏 MEDIDO (17/11): 819 dos 960 clientes têm telefone pelo caminho do
    cadastro, então a reserva alcança a maioria -- mas não todos, e `telefone`
    nulo é resposta legítima.
    """
    da_os = (ficha.get("cliente_telefone") or "").strip()
    if da_os:
        return {"telefone": da_os, "de_onde": "o contato da OS"}

    harmonit_id = ficha.get("cliente_id")
    if not harmonit_id:
        return {"telefone": None, "de_onde": None}
    linha = banco.um(
        """SELECT t.e164
             FROM cliente c
             JOIN contato ct ON ct.cliente_id = c.id
             JOIN contato_telefone t ON t.contato_id = ct.id
            WHERE c.harmonit_id = %s
            ORDER BY t.principal DESC, t.id
            LIMIT 1""", (str(harmonit_id),))
    if linha and (linha.get("e164") or "").strip():
        return {"telefone": linha["e164"].strip(),
                "de_onde": "o cadastro do cliente"}
    return {"telefone": None, "de_onde": None}


def preparar_da_etapa(numero_os: int, situacao_id: int) -> dict:
    """Monta a mensagem da etapa e **não envia nada**. Devolve o que mostrar.

    🚨 ESTA FUNÇÃO NÃO FALA COM O CLIENTE, e é por isso que ela existe: quem a
    chama é o `passagem.mover`, e depois de 17/11 **mover não avisa ninguém**.
    O retorno alimenta a caixa de diálogo; o envio é outro clique, outra rota.

    🚨 AS CHAVES SÃO RESOLVIDAS AQUI, NO SERVIDOR, ANTES DE MOSTRAR. O operador
    lê exatamente o que vai sair, e nenhuma `{{...}}` crua pode chegar ao
    cliente por edição.

    ⚠️ `pergunta: False` NÃO É ERRO -- é "não há o que perguntar", e o `motivo`
    diz por quê. O caminho mais comum depois de "desligado" é a ficha da OS não
    responder: **3 de 6 leituras falharam** na amostra de 17/11 (pool do
    Harmonit). A tela mostra o motivo no lugar da caixa, e nada é enviado.
    """
    conf = da_etapa(situacao_id)
    if not conf or not conf["ativo"] or not (conf["texto"] or "").strip():
        return {"pergunta": False, "motivo": "desligado"}

    canal = _canal_de_atendimento()
    if not canal:
        log.warning("disparo da etapa %s: nenhum canal de atendimento conectado",
                    situacao_id)
        return {"pergunta": False,
                "motivo": "sem canal de atendimento conectado"}

    from . import campo_etapa, fpsl_ponte
    try:
        ficha = fpsl_ponte.ficha_da_os(numero_os)
    except Exception as e:  # noqa: BLE001
        log.warning("disparo da etapa %s: nao li a OS %s: %s",
                    situacao_id, numero_os, e)
        return {"pergunta": False, "motivo": f"não consegui ler a OS: {e}"}

    destino = telefone_da_os(ficha)
    if not destino["telefone"]:
        return {"pergunta": False,
                "motivo": "a OS não tem telefone do cliente, nem o cadastro"}

    rastreio = (campo_etapa.atuais(numero_os).get("rastreio") or {}).get("valor")
    texto = resolver(conf["texto"], {
        "contato_nome": ficha.get("cliente") or ficha.get("cliente_nome"),
        "numero_os": numero_os,
        "rastreio": rastreio,
        "descricao": ficha.get("descricao"),
    })
    if not texto:
        return {"pergunta": False, "motivo": "a mensagem ficou vazia"}

    return {"pergunta": True, "situacao_id": int(situacao_id),
            "texto": texto, "telefone": destino["telefone"],
            "destinatario": destino["de_onde"], "motivo": None}


def enviar_preparado(numero_os: int, situacao_id: int, texto: str,
                     atendente_id: int | None = None) -> dict:
    """Manda o texto que o operador confirmou na caixa de diálogo.

    🚨 NÃO LEVANTA, como a função que ela substituiu: quem chama é a rota, e o
    card já mudou de situação no ERP. Todo retorno é um dicionário com `enviou`
    e `motivo`.

    🚨 O DESTINATÁRIO E O CANAL SÃO REDERIVADOS AQUI, e nunca vêm da tela: o
    texto é do operador, o número não. Aceitar número da tela abriria o caminho
    para mandar mensagem de operação para qualquer um -- inclusive o técnico,
    que o *"por enquanto somente cliente"* proíbe.

    🚨 O INTERRUPTOR É CONFERIDO DE NOVO. Entre a pergunta e o clique alguém
    pode ter desligado a etapa, e desligar é dizer *"pare de falar com os
    clientes"*: a decisão mais nova ganha.

    ⚠️ E NÃO FALA COM O `evolution` CRU: o envio passa pelo
    `conversas.iniciar_conversa`, que valida se o número tem WhatsApp, reusa a
    conversa aberta e **grava a mensagem na conversa**. Enviar por fora deixaria
    o cliente com uma mensagem que a operação não vê.
    """
    limpo = (texto or "").strip()
    if not limpo:
        return {"enviou": False, "motivo": "a mensagem está vazia"}
    if len(limpo) > TETO_TEXTO:
        return {"enviou": False,
                "motivo": f"a mensagem passa de {TETO_TEXTO} caracteres"}
    # 🚨 Nenhuma chave crua sai daqui, nem por edição do operador: ele pode ter
    # colado `{{...}}` na caixa, e o cliente não tem o que fazer com a chave.
    if re.search(r"\{\{[^}]*\}\}", limpo):
        limpo = resolver(limpo, {})

    conf = da_etapa(situacao_id)
    if not conf or not conf["ativo"]:
        return {"enviou": False, "motivo": "o disparo desta etapa está desligado"}

    canal = _canal_de_atendimento()
    if not canal:
        return {"enviou": False, "motivo": "sem canal de atendimento conectado"}

    from . import fpsl_ponte
    try:
        ficha = fpsl_ponte.ficha_da_os(numero_os)
    except Exception as e:  # noqa: BLE001
        return {"enviou": False, "motivo": f"não consegui ler a OS: {e}"}
    destino = telefone_da_os(ficha)
    if not destino["telefone"]:
        return {"enviou": False,
                "motivo": "a OS não tem telefone do cliente, nem o cadastro"}

    from . import conversas
    try:
        r = conversas.iniciar_conversa(canal["id"], destino["telefone"], limpo,
                                       atendente_id)
    except Exception as e:  # noqa: BLE001
        log.warning("disparo da etapa %s: nao enviei para a OS %s: %s",
                    situacao_id, numero_os, e)
        return {"enviou": False, "motivo": str(e)}

    log.info("disparo da etapa %s enviado para a OS %s por %s (conversa %s)",
             situacao_id, numero_os, atendente_id, (r or {}).get("conversa_id"))
    return {"enviou": True, "motivo": None, "telefone": destino["telefone"],
            "destinatario": destino["de_onde"],
            "conversa_id": (r or {}).get("conversa_id"), "texto": limpo}
