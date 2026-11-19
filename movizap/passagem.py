"""Mover o card de etapa — Bloco D do pipeline da operação (29/10).

🔵 **As quatro decisões dele, nas palavras dele:**
  · *"O card pode ser por arrastar"* — o gesto;
  · *"deve ter o log de quem faz o que SEMPRE"* — e é a condição deste módulo;
  · *"que tal de caminho proibido é esse??"* — **não existe caminho proibido.**
    ⚠️ A pergunta era minha e foi descartada: **nada aqui valida transição**;
  · *"pode mover que tiver acesso a tela, por enquanto somente owner"* — quem
    cobra isso é a rota, e hoje a `PNL_1.1` é de permissão `owner`.

🚨 **O LOG É A CONDIÇÃO, NÃO UM EXTRA.** O Harmonit **não registra a situação na
linha do tempo** — só o `status`, conferido em 3 OS em 29/10. Então, movido o
card, não há como saber quem moveu, de onde e quando: nem aqui, nem lá. Sem a
`os_passagem` (migração 083), mover é escrita anônima e irreversível no ERP.

🚨 **A TENTATIVA RECUSADA TAMBÉM É GRAVADA**, e é metade do valor: escrita que o
ERP negou e não deixou rastro é a mesma família do `criada: null` da criação de
OS — ninguém descobre depois.

⚠️ **ESTE MÓDULO NÃO É O BLOCO C.** O C quer *"quanto tempo em cada etapa"*, com
os dois tempos no card. Aqui é o **registro da passagem** — e é ele que faz o C
sair barato depois, porque o dado passa a ser colhido desde já.
"""
import logging
import pathlib
import uuid

from . import (banco, checklist, disparo_etapa, fpsl_ponte, paineis)
from .operacao import DadoInvalido

log = logging.getLogger("movizap.passagem")


def _registrar(numero_os: int, de, para: int, atendente_id: int | None,
               ok: bool, erro: str | None, fora: dict | None,
               os_id: int | None = None) -> int:
    """Grava a passagem. 🔵 *"o log de quem faz o que SEMPRE"* — inclusive a
    recusada, e é por isso que esta função é chamada nos dois caminhos."""
    import json
    linha = banco.um(
        """INSERT INTO os_passagem
               (numero_os, os_id, de_situacao, para_situacao, atendente_id,
                ok, erro, fora_da_situacao)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id""",
        (numero_os, os_id, de, para, atendente_id, ok, erro,
         json.dumps(fora, ensure_ascii=False, default=str) if fora else None))
    return linha["id"]


# 🔵 60 SEGUNDOS, POR OS — número dele, 18/11. ⚠️ Não é um palpite meu e não se
# muda sem a palavra dele: limite é decisão dele.
SEGUNDOS_ENTRE_PASSAGENS = 60


def _passagem_recente(numero_os: int) -> int | None:
    """Quantos segundos ainda faltam para esta OS poder ser movida de novo.

    `None` quando pode mover. 🚨 A conta é feita **no banco**, com `now()`, e
    não em Python: comparar um `timestamptz` do Postgres com a hora do processo
    é o caminho mais curto para o vermelho intermitente de fuso que já custou
    uma sessão em 11/11 -- `::date` resolvido no fuso da sessão fazia um teste
    reprovar das 21h à meia-noite.

    ⚠️ Olha a última passagem **confirmada**: recusa não assenta nada no ERP, e
    travar o operador por causa de uma tentativa que não escreveu seria
    castigá-lo pelo defeito do Harmonit.
    """
    linha = banco.um(
        "SELECT CEIL(%s - EXTRACT(EPOCH FROM (now() - em)))::int AS falta "
        "  FROM os_passagem "
        " WHERE numero_os = %s AND ok AND de_situacao IS NOT NULL "
        "   AND em > now() - make_interval(secs => %s) "
        " ORDER BY em DESC, id DESC LIMIT 1",
        (SEGUNDOS_ENTRE_PASSAGENS, numero_os, SEGUNDOS_ENTRE_PASSAGENS))
    if not linha:
        return None
    # ⚠️ Nunca 0 nem negativo: 0 diria "pode mover" numa resposta que recusa.
    return max(1, int(linha["falta"] or 1))


def mover(numero_os: int, para_situacao: int, atendente_id: int | None,
          situacao_esperada: int | None = None) -> dict:
    """Move o card: escreve a situação no Harmonit e registra a passagem.

    🚨 **NÃO VALIDA TRANSIÇÃO**, por decisão dele — ver o cabeçalho. O que ela
    valida é que a situação de **destino** é uma das 17 do painel: um id
    inventado criaria um card sem coluna, e aí o card desapareceria da tela.

    🚨 **ESTOURA `DadoInvalido` SÓ ANTES DE TENTAR.** Depois de a escrita ser
    tentada, nada estoura: a resposta diz o que aconteceu e a passagem está
    gravada. Estourar depois perderia o registro de uma escrita que já pode ter
    chegado ao ERP.
    """
    # 🔵 A TRAVA DE 1 MINUTO — decisão dele, 18/11: *"vamos pensar em travas de
    # 1 minuto para poder mexer o card, com mensagem na tela, assim evitamos
    # gravação e movimentação rápida"*. 🔵 **No servidor**, não só na tela, e
    # **por OS** (o que assenta é a OS, não a pessoa): vale por qualquer
    # caminho — F5, outra aba, outro operador, duplo clique.
    #
    # 🚨 ANTES DE QUALQUER COISA, inclusive da validação da situação de
    # destino: a segunda passagem rápida não deve nem ser avaliada.
    #
    # ⚠️ E O QUE ELA NÃO RESOLVE, DITO AQUI PARA NÃO SE PERDER: as duas
    # passagens da OS 17133, em 18/11, foram 6m35s uma da outra, e o atraso de
    # leitura do Harmonit foi de ≈1h54. **Esta trava não teria evitado aquilo.**
    # Quem conserta a 17133 é a causa `leitura_atrasada` e a fila. Esta trava
    # evita o duplo clique e a corrida no instante da escrita, que são reais e
    # são outro problema.
    recente = _passagem_recente(numero_os)
    if recente is not None:
        return {
            "ok": False, "gravou": False, "numero_os": numero_os,
            "de": None, "para": para_situacao,
            "causa": "passagem_muito_recente",
            "espere_segundos": recente,
            # 🚨 A frase diz O QUE ESTÁ ACONTECENDO e quanto falta. Botão cinza
            # e calado é tela que mente (`M12`): quem move e não vê nada
            # conclui que o sistema travou e clica mais.
            "motivo": (f"esta OS acabou de ser movida (há "
                       f"{SEGUNDOS_ENTRE_PASSAGENS - recente}s). Espere "
                       f"{recente}s: o Harmonit ainda está assentando a "
                       f"mudança anterior, e mover agora pode gravar sobre uma "
                       f"leitura que ainda não a enxerga."),
        }

    conhecidas = {sid for sid, _ in paineis.SITUACOES}
    if para_situacao not in conhecidas:
        # ⚠️ A frase diz o que É: id fora das 17 não é "proibido", é
        # desconhecido para esta tela.
        raise DadoInvalido(
            f"A situação {para_situacao} não é uma das 17 do painel da "
            f"Operação — o card ficaria sem coluna.")

    resposta = fpsl_ponte.gravar_situacao_da_os(
        numero_os, para_situacao, situacao_esperada=situacao_esperada)

    # 🚨 O LOG SAI NOS DOIS CAMINHOS. ⚠️ Conflito de concorrência NÃO é gravado
    # como passagem: nada foi tentado no ERP, e registrar uma passagem que não
    # aconteceu encheria a linha do tempo da OS de ruído. A resposta diz o
    # conflito, e a tela recarrega.
    if resposta.get("conflito"):
        # 🚨 CONFLITO DEIXOU DE SER UMA COISA SÓ, em 18/11, e a OS 17133 é o
        # porquê. A mesma rota do Harmonit devolveu 251 às 11:42:47 e 16488 às
        # 11:43:18, sem nenhuma escrita entre as duas: das 11:17 às 11:42 ela
        # respondia **o valor que escrevemos às 09:42**, ignorando o de 09:49.
        # Sete recusas, todas falsas, e o operador clicando porque nada
        # acontecia.
        #
        # A pergunta que separa os dois casos é uma só: **o valor que o ERP
        # devolveu é um valor que NÓS já escrevemos nesta OS?**
        de = resposta.get("de")
        if de is not None and de in _ja_escrevemos(numero_os):
            # É nosso, de antes: a leitura dele atrasou. 🔵 Ele escolheu a FILA
            # aqui, não uma frase melhor: *"assim op não para de trabalhar e
            # seguimos no background com a OS"*.
            linha = _enfileirar(numero_os, de, para_situacao, atendente_id,
                                frase=resposta.get("frase")
                                or resposta.get("motivo"))
            log.info("OS %s: leitura atrasada (ERP em %s, que foi nosso) -- "
                     "card andou e a escrita entrou na fila (passagem %s)",
                     numero_os, de, linha)
            return {
                # 🚨 `ok: True` PORQUE O CARD ANDA. ⚠️ E `gravou: False` junto,
                # porque a OS **não** mudou ainda -- card que anda sem dizer
                # isso é tela que mente (`M12`), e o selo é o que impede isso.
                "ok": True, "gravou": False, "pendente": True,
                "numero_os": numero_os, "de": de, "para": para_situacao,
                "passagem_id": linha,
                "causa": "leitura_atrasada",
                "motivo": ("o Harmonit ainda está respondendo a situação "
                           "anterior, que foi escrita por nós. O card andou e "
                           "a escrita ficou na fila — ela insiste sozinha até "
                           "o Harmonit se acertar."),
            }
        # Valor que nunca escrevemos: alguém mexeu na OS dentro do Harmonit, e
        # o ERP é quem está certo. ⚠️ RECUSA, como sempre foi -- é o mesmo
        # discernimento que a auditoria faz do outro lado (migração 114), e é o
        # caso que o ensaio a seco encontrou nas OS 17054 e 17114.
        log.info("OS %s: conflito ao mover (ERP em %s, tela em %s)",
                 numero_os, resposta.get("de"), situacao_esperada)
        return resposta

    passagem = _registrar(
        numero_os=numero_os,
        de=resposta.get("de"),
        para=para_situacao,
        atendente_id=atendente_id,
        ok=bool(resposta.get("ok")),
        erro=None if resposta.get("ok") else (resposta.get("motivo")
                                             or "sem motivo informado"),
        fora=resposta.get("fora_da_situacao"),
    )

    # 🔵 04/11, decisão dele (O4): ao SAIR de uma etapa que tinha checklist, o
    # que foi feito vira **observação do card**. *"Só no MoviZap, como
    # observação"* -- gravar na `solucaoTecnica` exigiria reescrever a OS
    # inteira no Harmonit, e ele preferiu não tocar na OS.
    #
    # 🚨 SÓ QUANDO A MUDANÇA ACONTECEU DE VERDADE. Escrita recusada pelo ERP
    # não é saída de etapa: o card não saiu do lugar, e registrar o checklist
    # como encerrado afirmaria um fato que não houve.
    #
    # ⚠️ E A FALHA AQUI NÃO DERRUBA O MOVER. O card já mudou de situação no
    # ERP; perder o recado é ruim, devolver erro a quem moveu com sucesso é
    # pior -- e a passagem já está gravada de qualquer jeito.
    de_onde = resposta.get("de")
    if resposta.get("ok") and de_onde and de_onde != para_situacao:
        try:
            texto = checklist.como_texto(numero_os, de_onde)
            if texto:
                observar(numero_os, texto, atendente_id)
        except Exception:
            log.exception("OS %s: nao consegui guardar o checklist da etapa %s",
                          numero_os, de_onde)

    # 🔵 17/11, DECISÃO DELE: O DISPARO DA ETAPA PASSA A SER PERGUNTADO.
    # *"quando o card for movido e houver disparo de mensagens perguntar em
    # caixa de diálogo (se tiver ligado o interruptor) 'Deseja enviar aviso ao
    # cliente?'"*
    #
    # 🚨 MOVER NÃO AVISA MAIS NINGUÉM, e é a trava mais importante deste bloco:
    # o `preparar_da_etapa` **não fala com o cliente**. Ele monta o texto e o
    # destinatário, e quem envia é a rota do disparo, atrás de um clique. Isto
    # inverte, com autorização, o *"sairá automaticamente"* de 11/11 e restaura
    # a régua da Área F de 04/11.
    #
    # 🚨 DEPOIS DA ESCRITA NO ERP, E SÓ QUANDO ELA DEU CERTO -- a razão não
    # mudou: perguntar "avisar o cliente?" num mover que o ERP recusou
    # ofereceria avisar de um fato que não aconteceu.
    #
    # 🚨 E NUNCA DERRUBA O MOVER -- nem o `preparar_da_etapa`, que não levanta,
    # nem este `try`, que é a segunda rede. O card já mudou de situação; falhar
    # o clique por causa do Harmonit seria trocar um problema pequeno por um
    # grande.
    #
    # ⚠️ TUDO DESLIGADO HOJE: as 17 linhas da `etapa_mensagem` nascem sem texto
    # e com `ativo = false`, então isto devolve "desligado", a tela não pergunta
    # nada e ninguém é avisado. É o tempo 1 que ele pediu.
    disparo = {"pergunta": False, "motivo": None}
    if resposta.get("ok"):
        try:
            disparo = disparo_etapa.preparar_da_etapa(numero_os, para_situacao)
            # ⚠️ "NÃO DEU PARA PREPARAR" FICA NO CARD. Aqui ninguém foi
            # perguntado e ninguém foi avisado, e é a primeira coisa que alguém
            # pergunta depois. O caso comum é a ficha da OS não responder: 3 de
            # 6 leituras falharam na medição de 17/11.
            # ⚠️ "desligado" não vira observação: não é falha, é o estado
            # normal de 17 das 17 etapas hoje -- e encheria o card de ruído.
            if (not disparo.get("pergunta")
                    and disparo.get("motivo") not in (None, "desligado")):
                observar(numero_os,
                         f"[sistema] não deu para preparar o aviso desta "
                         f"etapa, e ninguém foi avisado: {disparo['motivo']}",
                         atendente_id)
        except Exception:
            log.exception("OS %s: falhou ao preparar o disparo da etapa %s",
                          numero_os, para_situacao)
            disparo = {"pergunta": False,
                       "motivo": "não deu para preparar o aviso"}

    log.info("OS %s: %s -> %s por %s (ok=%s, passagem %s)", numero_os,
             resposta.get("de"), para_situacao, atendente_id,
             resposta.get("ok"), passagem)
    # 🚨 `passagem_id` VIAJA PORQUE A DECISÃO DO DISPARO MORA NELA (migração
    # 111): é por ele que a rota do disparo sabe de qual movimento está falando,
    # e é ele que impede o mesmo aviso de sair duas vezes.
    return {**resposta, "passagem_id": passagem, "disparo": disparo}


# ===========================================================================
# A DECISÃO DO DISPARO — migração 111 (17/11)
#
# 🔵 Dele: *"Se clicar não, não envia nada"*, e, perguntado, clicar "Não"
# **registra no card**.
#
# 🚨 A DECISÃO MORA NA PASSAGEM, uma por movimento. Mover duas vezes para a
# mesma etapa são duas passagens e podem ser dois avisos (movimento novo, fato
# novo); a MESMA passagem decide uma vez só. Sem isto, recarregar a tela ou
# clicar duas vezes mandaria a mesma mensagem ao cliente outra vez -- e
# mensagem é irreversível.
# ===========================================================================

def disparo_da_passagem(passagem_id: int) -> dict | None:
    """A passagem e o que já se decidiu sobre o aviso dela."""
    return banco.um(
        """SELECT id, numero_os, para_situacao, ok, disparo_em,
                  disparo_recusado_em, disparo_texto, disparo_por
             FROM os_passagem WHERE id = %s""", (int(passagem_id),))


def decidir_disparo(passagem_id: int, *, enviado: bool, texto: str | None,
                    atendente_id: int | None) -> bool:
    """Marca a decisão. Devolve False se esta passagem já tinha decidido.

    🚨 É ATÔMICO E É A TRAVA: o `WHERE` exige que as duas colunas estejam
    nulas, então de dois cliques no mesmo instante **um só** passa. Quem chama
    usa isto para RESERVAR antes de enviar -- marcar depois do envio deixaria
    os dois cliques enviarem antes de qualquer um marcar.
    """
    return banco.executar(
        """UPDATE os_passagem
              SET disparo_em          = CASE WHEN %s THEN now() END,
                  disparo_recusado_em = CASE WHEN %s THEN NULL ELSE now() END,
                  disparo_texto = %s, disparo_por = %s
            WHERE id = %s
              AND disparo_em IS NULL AND disparo_recusado_em IS NULL""",
        (bool(enviado), bool(enviado), texto, atendente_id,
         int(passagem_id))) > 0


def gravar_texto_do_disparo(passagem_id: int, texto: str) -> None:
    """Guarda o texto que SAIU, depois de o envio ter dado certo.

    🚨 SÓ DEPOIS DO ENVIO, e é o que dá sentido ao `disparo_texto`: a coluna
    guarda o que o cliente leu (migração 111), não o que se pretendia mandar.
    É também por ela que o `soltar_disparo` sabe que nada saiu -- reserva sem
    texto é reserva, com texto é mensagem entregue.
    """
    banco.executar(
        "UPDATE os_passagem SET disparo_texto = %s WHERE id = %s",
        (texto, int(passagem_id)))


def soltar_disparo(passagem_id: int) -> None:
    """Devolve a passagem ao estado "ninguém decidiu" — só quando o envio FALHOU.

    🚨 EXISTE PARA O OPERADOR PODER TENTAR DE NOVO. A reserva é feita antes do
    envio; se o WhatsApp estava fora do ar, nada saiu, e deixar a passagem
    marcada afirmaria um aviso que não houve -- e trancaria a segunda tentativa.
    ⚠️ Só solta o que ainda não foi enviado de verdade: `disparo_texto` nulo.
    """
    banco.executar(
        """UPDATE os_passagem
              SET disparo_em = NULL, disparo_recusado_em = NULL,
                  disparo_por = NULL
            WHERE id = %s AND disparo_texto IS NULL""", (int(passagem_id),))


def historico(numero_os: int) -> list[dict]:
    """A linha do tempo das passagens desta OS — a nossa, porque o ERP não tem.

    🔵 É o que o card aberto (Bloco E) vai ler, e já existe desde agora.
    """
    return banco.varios(
        """SELECT p.id, p.de_situacao, p.para_situacao, p.em, p.ok, p.erro,
                  p.fora_da_situacao, a.nome AS quem
             FROM os_passagem p
             LEFT JOIN atendente a ON a.id = p.atendente_id
            WHERE p.numero_os = %s
            ORDER BY p.em DESC, p.id DESC""", (numero_os,))


def ultima_passagem(numero_os: int) -> dict | None:
    """A última passagem **confirmada** desta OS — o que faz o "Voltar" existir.

    🟡 Proposta minha que ele não precisou decidir, porque é consequência do
    log: sabendo de onde o card veio, voltar é **uma nova passagem**, nunca um
    "desfazer". ⚠️ A palavra importa: o ERP não desfaz nada, e dizer "desfazer"
    afirmaria que a primeira escrita não aconteceu — e ela aconteceu.
    """
    return banco.um(
        """SELECT de_situacao, para_situacao, em
             FROM os_passagem
            WHERE numero_os = %s AND ok AND de_situacao IS NOT NULL
            ORDER BY em DESC, id DESC
            LIMIT 1""", (numero_os,))


# ===========================================================================
# O ANEXO DA OBSERVAÇÃO (migração 091, 04/11)
#
# 🔵 *"Card OBS anexos, texto, format conve -- exibir em modal"*.
#
# 🚨 NÃO USA A TABELA `midia`, e não é escolha de estilo: o banco proíbe. O
# `CHECK midia_tem_um_dono` exige conversa **ou** sala, e observação de card não
# é nenhuma das duas. Afrouxar o CHECK abriria caminho para mídia órfã -- que é
# mídia que ninguém acha para apagar.
#
# ⚠️ O molde é o `formularios.py`: pasta própria fora do repositório, lista
# BRANCA de extensão, nome original preservado só para exibir, e o arquivo
# gravado com nome sorteado.
# ===========================================================================

PASTA_ANEXOS_OBS = pathlib.Path("/home/claude/movizap_observacao_anexos")
TETO_ANEXO_OBS = 10 * 1024 * 1024        # o mesmo do formulário

# 🚨 LISTA BRANCA, nunca lista negra: o que não está aqui não entra. Lista
# negra é aposta de que alguém lembrou de todas as extensões perigosas.
EXTENSOES_DA_OBS = {
    ".pdf", ".jpg", ".jpeg", ".png", ".webp", ".heic",
    ".doc", ".docx", ".xls", ".xlsx", ".csv", ".txt",
}


def guardar_anexo(observacao_id: int, nome: str, dados: bytes,
                  mime: str | None = None) -> dict:
    """Guarda um arquivo na observação, e devolve a linha gravada.

    ⚠️ RECUSA ANTES DE ESCREVER NO DISCO: extensão e tamanho são conferidos
    primeiro, para não deixar arquivo solto quando a linha não vai existir.
    """
    if not banco.um("SELECT id FROM os_observacao WHERE id = %s", (observacao_id,)):
        raise DadoInvalido("Observação não encontrada.")

    limpo = pathlib.Path(nome or "").name.strip() or "arquivo"
    extensao = pathlib.Path(limpo).suffix.lower()
    if extensao not in EXTENSOES_DA_OBS:
        raise DadoInvalido(
            f"{extensao or 'arquivo sem extensão'} não é um tipo aceito aqui. "
            f"Aceito: {', '.join(sorted(EXTENSOES_DA_OBS))}.")
    if len(dados) > TETO_ANEXO_OBS:
        raise DadoInvalido(
            f"O arquivo tem {len(dados) // 1024} KB e o limite é "
            f"{TETO_ANEXO_OBS // 1024 // 1024} MB.")
    if not dados:
        raise DadoInvalido("O arquivo veio vazio.")

    pasta = PASTA_ANEXOS_OBS / uuid.uuid4().hex
    pasta.mkdir(parents=True, exist_ok=True)
    destino = pasta / limpo
    destino.write_bytes(dados)

    linha = banco.um(
        """INSERT INTO os_observacao_arquivo
               (observacao_id, nome_original, caminho, bytes, mime)
           VALUES (%s, %s, %s, %s, %s) RETURNING id""",
        (observacao_id, limpo, str(destino), len(dados), mime))
    log.info("observacao %s: anexo %s guardado (%s bytes)",
             observacao_id, linha["id"], len(dados))
    return anexo(linha["id"])


def anexo(anexo_id: int) -> dict | None:
    return banco.um(
        """SELECT id, observacao_id, nome_original, caminho, bytes, mime,
                  criado_em
             FROM os_observacao_arquivo WHERE id = %s""", (anexo_id,))


def anexos_de(observacao_ids: list[int]) -> dict:
    """`{observacao_id: [anexos]}` — UMA consulta para a lista toda.

    ⚠️ O `caminho` NÃO sai daqui para a tela: é caminho de disco, e a tela não
    tem o que fazer com ele. Quem baixa usa o id.
    """
    if not observacao_ids:
        return {}
    por_obs: dict = {}
    for r in banco.varios(
            """SELECT id, observacao_id, nome_original, bytes, mime
                 FROM os_observacao_arquivo
                WHERE observacao_id = ANY(%s)
                ORDER BY id""", (list(observacao_ids),)):
        por_obs.setdefault(r["observacao_id"], []).append(r)
    return por_obs


def quem_mexeu(desde_dias: int = 7, teto: int = 200) -> list[dict]:
    """O log por pessoa. 🔵 *"o log de quem faz o que SEMPRE"* — e um log que
    ninguém consegue ler não cumpre o pedido."""
    return banco.varios(
        """SELECT p.numero_os, p.de_situacao, p.para_situacao, p.em, p.ok,
                  p.erro, a.nome AS quem
             FROM os_passagem p
             LEFT JOIN atendente a ON a.id = p.atendente_id
            WHERE p.em > now() - (%s || ' days')::interval
            ORDER BY p.em DESC
            LIMIT %s""", (desde_dias, teto))


# ----------------------------------------------------------------------------
# BLOCO C — de quando é a etapa atual de cada OS
# ----------------------------------------------------------------------------
# 🔵 *"o card mostra dois tempos: nesta etapa e total da OS"*.
#
# 🚨 UMA CONSULTA PARA TODOS OS CARDS. O quadro tem 11 cards e uma consulta por
# card seriam 11 idas ao banco por abertura de tela.


def etapa_desde(numeros: list[int]) -> dict:
    """`numero_os` -> quando a etapa atual começou, da última passagem CONFIRMADA.

    ⚠️ OS QUE NÃO ESTÁ NO RESULTADO NÃO TEM PASSAGEM, e isso é informação: a
    `os_passagem` começou em 29/10, então OS movida antes disso (ou nunca
    movida) não tem de onde tirar o tempo da etapa. Quem monta o card **diz
    "não medido"** em vez de inventar um zero -- a OS pode estar na etapa desde
    setembro e ninguém sabe.

    🚨 SÓ PASSAGEM CONFIRMADA (`ok`): uma tentativa recusada não moveu a OS, e
    contar o tempo a partir dela seria medir desde um evento que não aconteceu.
    """
    if not numeros:
        return {}
    linhas = banco.varios(
        """SELECT DISTINCT ON (numero_os) numero_os, em, de_situacao,
                  para_situacao
             FROM os_passagem
            WHERE ok AND numero_os = ANY(%s)
            ORDER BY numero_os, em DESC, id DESC""",
        ([int(n) for n in numeros],))
    return {linha["numero_os"]: linha for linha in linhas}


# ----------------------------------------------------------------------------
# A OBSERVAÇÃO DO PAINEL — Bloco F, fase 1 (migração 084)
# ----------------------------------------------------------------------------
# 🔵 *"observação do painel, com autor e hora, **no MoviZap**. Não vai para a
# `solucaoTecnica`"*.
#
# 🚨 NÃO SE EDITA, e não há coluna para isso: reescrever recado é reescrever a
# história que a operação leu. É a mesma régua do *"log de quem faz o que
# SEMPRE"*.
#
# ⚠️ APAGAR passou a existir em 11/11, por decisão dele -- e **apagar não
# destrói o texto**: quem esconde é a leitura. Ver `apagar_observacao` e
# `_esconder_apagados` abaixo.

PRIORIDADES = {381: "Baixa", 382: "Normal", 383: "Alta", 384: "Urgente"}


def observar(numero_os: int, texto: str, atendente_id: int | None) -> dict:
    """Grava uma observação do painel sobre a OS."""
    texto = (texto or "").strip()
    if not texto:
        raise DadoInvalido("Escreva a observação antes de salvar.")
    if len(texto) > 4000:
        raise DadoInvalido("A observação passa de 4000 caracteres.")
    linha = banco.um(
        """INSERT INTO os_observacao (numero_os, texto, atendente_id)
           VALUES (%s, %s, %s) RETURNING id, em""",
        (int(numero_os), texto, atendente_id))
    log.info("OS %s: observacao %s por %s", numero_os, linha["id"], atendente_id)
    return {"id": linha["id"], "em": linha["em"]}


def eh_owner(atendente_id: int | None) -> bool:
    """🚨 Quem vê o conteúdo de um recado apagado. **Só o owner.**

    🔵 Decisão dele (11/11): *"somente owner pode visualizar o exlcuido, com
    botão, como no chat interno, sem que vejam essa informação"*.

    ⚠️ É a mesma consulta do `chat._eh_owner`, e **não** importo o `chat` para
    isto: aquele módulo é sobre salas e mensagens entre atendentes, e acoplar o
    painel a ele por causa de um `SELECT` de uma coluna faria o painel carregar
    o chat inteiro. Duas linhas iguais custam menos que essa dependência.
    """
    if not atendente_id:
        return False
    r = banco.um("SELECT owner FROM atendente WHERE id = %s",
                 (int(atendente_id),))
    return bool(r and r["owner"])


def _esconder_apagados(recados: list[dict], eu: int | None) -> list[dict]:
    """Tira o conteúdo do que foi apagado — para quem não é owner.

    🚨 **QUEM ESCONDE É A LEITURA, NÃO O BANCO.** O texto continua gravado
    (senão o owner não teria o que ver), e é isto que torna a decisão
    reversível. Molde exato do `chat.py:421-444`.

    🔵 E A AUTORIA FICA VISÍVEL PARA TODOS, por pedido dele: *"deve ter
    disponivel exibição da autoria sim, é um dos objetivos, rastreabilidade"*.
    Então quem não é owner continua lendo **quem escreveu**, **quando**, **quem
    apagou** e **quando apagou** — o que some é só o que o recado dizia.

    ⚠️ **O ANEXO SOME DA LISTA JUNTO.** Deixar o nome do arquivo
    (`comprovante-pix-joao.pdf`) ao lado de "Observação excluída" devolveria
    pela legenda o que o apagar tirou do texto. É o vazamento que o chat já
    tinha corrigido em 07/10, na mensagem citada.
    """
    sou_owner = eh_owner(eu)
    for o in recados:
        if o.get("apagada_em") and not sou_owner:
            o["texto"] = None
            o["anexos"] = []
    return recados


def observacoes(numero_os: int, eu: int | None = None) -> list[dict]:
    """As observações desta OS, da mais nova para a mais velha.

    ⚠️ `eu` NASCE NULO e nulo não é owner: quem chamar sem passar quem está
    lendo recebe a versão **mais fechada**, não a mais aberta. Falha no lado
    seguro, que é o único lado aceitável aqui.
    """
    recados = banco.varios(
        """SELECT o.id, o.texto, o.em, a.nome AS quem,
                  o.apagada_em, q.nome AS apagada_por_nome
             FROM os_observacao o
             LEFT JOIN atendente a ON a.id = o.atendente_id
             LEFT JOIN atendente q ON q.id = o.apagada_por
            WHERE o.numero_os = %s
            ORDER BY o.em DESC, o.id DESC""", (int(numero_os),))
    return _esconder_apagados(recados, eu)


def observacoes_da_solicitacao(solicitacao_id: int,
                               eu: int | None = None) -> list[dict]:
    """O mesmo, para o recado de CHAMADO (dono duplo, migração 092).

    ⚠️ Esta função nasceu movendo a consulta que estava dentro da rota: com o
    apagar, a regra de esconder passou a ser obrigatória nos DOIS caminhos, e
    regra que mora na rota é regra que o segundo caminho esquece.
    """
    if not solicitacao_id:
        return []
    recados = banco.varios(
        """SELECT o.id, o.texto, o.em, a.nome AS quem,
                  o.apagada_em, q.nome AS apagada_por_nome
             FROM os_observacao o
             LEFT JOIN atendente a ON a.id = o.atendente_id
             LEFT JOIN atendente q ON q.id = o.apagada_por
            WHERE o.solicitacao_id = %s
            ORDER BY o.em DESC, o.id DESC""", (int(solicitacao_id),))
    return _esconder_apagados(recados, eu)


def anexo_e_de_apagada(anexo_id: int) -> bool:
    """O anexo pertence a um recado que foi apagado?

    🚨 Molde do `chat._eh_de_apagada`. A lista de recados já esconde o anexo de
    quem não é owner, mas **a rota de download aceita um id** -- e esse id
    esteve na tela de quem viu o recado antes de alguém apagar. Esconder na
    lista e deixar baixar seria apagar de mentira.
    """
    r = banco.um(
        """SELECT 1 FROM os_observacao_arquivo a
             JOIN os_observacao o ON o.id = a.observacao_id
            WHERE a.id = %s AND o.apagada_em IS NOT NULL""", (int(anexo_id),))
    return bool(r)


def apagar_observacao(observacao_id: int, atendente_id: int | None) -> dict:
    """Marca o recado como apagado. **Não destrói o texto.**

    🔵 Decisões dele (11/11): apagar é de *"todos que tem acesso a visualização
    do painel"* — não só do autor, como no chat interno —, e **sem janela de
    tempo**: *"pode ser apagada conforme disponivel mesmo"*.

    🚨 **POR ISSO EXISTE `apagada_por`**: com qualquer pessoa podendo apagar o
    recado de qualquer um, "quem apagou" deixa de ser dedutível do autor. No
    chat interno a coluna não existe porque lá só o autor apaga.

    ⚠️ **Apagar duas vezes não reescreve a primeira** (`AND apagada_em IS
    NULL`): a hora e o autor do apagar são do primeiro, e um segundo clique não
    pode roubar a autoria de quem apagou de fato.
    """
    observacao_id = int(observacao_id)
    atual = banco.um(
        "SELECT id, numero_os, solicitacao_id, apagada_em FROM os_observacao "
        "WHERE id = %s", (observacao_id,))
    if not atual:
        raise DadoInvalido("Esta observação não existe mais.")
    if atual["apagada_em"]:
        raise DadoInvalido("Esta observação já estava excluída.")

    banco.executar(
        "UPDATE os_observacao SET apagada_em = now(), apagada_por = %s "
        "WHERE id = %s AND apagada_em IS NULL",
        (atendente_id, observacao_id))
    log.info("observacao %s apagada por %s (OS %s, solicitacao %s)",
             observacao_id, atendente_id, atual["numero_os"],
             atual["solicitacao_id"])
    return {"id": observacao_id, "numero_os": atual["numero_os"],
            "solicitacao_id": atual["solicitacao_id"]}


def quantas_observacoes(numeros: list[int]) -> dict:
    """`numero_os` -> quantas observações. 🚨 UMA consulta para todos os cards.

    ⚠️ O card fechado mostra só o NÚMERO: recado é para ler no card aberto, e
    um trecho no card fechado faria a coluna crescer sem limite.
    """
    if not numeros:
        return {}
    linhas = banco.varios(
        """SELECT numero_os, count(*) AS quantas
             FROM os_observacao
            WHERE numero_os = ANY(%s)
            GROUP BY numero_os""", ([int(n) for n in numeros],))
    return {linha["numero_os"]: linha["quantas"] for linha in linhas}


def mudar_prioridade(numero_os: int, prioridade_id: int,
                     atendente_id: int | None,
                     prioridade_esperada: int | None = None) -> dict:
    """Muda a prioridade da OS no Harmonit, e REGISTRA quem mudou.

    🔵 *"deve ter o log de quem faz o que SEMPRE"* — vale para a prioridade
    como vale para a etapa. ⚠️ O registro vai na `os_observacao`, como uma
    linha escrita pelo sistema: criar uma segunda tabela de log para uma
    escrita de um campo seria tabela por campo.
    """
    if prioridade_id not in PRIORIDADES:
        raise DadoInvalido(
            f"A prioridade {prioridade_id} não existe. "
            f"As quatro são: {', '.join(PRIORIDADES.values())}.")

    resposta = fpsl_ponte.gravar_prioridade_da_os(
        numero_os, prioridade_id, prioridade_esperada=prioridade_esperada)

    if resposta.get("ok") and resposta.get("gravou"):
        de = PRIORIDADES.get(resposta.get("de"), resposta.get("de"))
        para = PRIORIDADES[prioridade_id]
        banco.executar(
            """INSERT INTO os_observacao (numero_os, texto, atendente_id)
               VALUES (%s, %s, %s)""",
            (int(numero_os), f"[sistema] prioridade: {de} → {para}",
             atendente_id))
    return resposta


# ===========================================================================
# A FILA DAS PASSAGENS — migração 115, 🔵 decisão dele de 18/11
# ===========================================================================
# 🔵 *"assim op não para de trabalhar e seguimos no background com a OS"*.
#
# 🚨 A FILA SÃO LINHAS, NÃO MEMÓRIA: reinício não pode perder escrita. E ela
# mora na própria `os_passagem`, que já é o registro de *"quem faz o que
# SEMPRE"* -- tabela nova seria um segundo lugar para a mesma verdade.

# 🔵 1 HORA — número dele, 18/11, para a pendência virar red flag.
# ⚠️ O atraso medido na OS 17133 foi de ≈1h54 e se resolveu sozinho, então 1h
# avisa sobre um caso que ainda poderia se resolver. Ele escolheu assim
# sabendo: avisar mais cedo, com mais ruído.
HORAS_PARA_A_RED_FLAG = 1


def _ja_escrevemos(numero_os: int) -> set[int]:
    """Toda situação que já escrevemos nesta OS, com sucesso.

    🚨 É ISTO QUE DISTINGUE ATRASO DE MUDANÇA DE TERCEIRO. Se o ERP devolve um
    valor que está aqui, ele está respondendo uma escrita nossa mais antiga --
    a leitura dele atrasou (OS 17133, 18/11). Se devolve um valor que nunca
    escrevemos, alguém mexeu na OS por fora, e o ERP é quem está certo.

    ⚠️ Mesma pergunta que `auditoria_os._ja_escrevemos` faz do lado da
    madrugada. Duas cópias de uma pergunta são duas chances de ela divergir --
    mas importar a auditoria aqui criaria ciclo (`auditoria_os` importa
    `fpsl_ponte`, que é vizinho deste módulo), e a consulta é de três linhas.
    🚨 Se uma mudar, a outra tem de mudar: há teste que compara as duas.
    """
    linhas = banco.varios(
        "SELECT DISTINCT para_situacao FROM os_passagem "
        " WHERE numero_os = %s AND ok AND para_situacao IS NOT NULL",
        (numero_os,))
    return {l["para_situacao"] for l in linhas}


def _enfileirar(numero_os: int, de, para: int, atendente_id: int | None,
                *, frase: str | None) -> int:
    """Grava a passagem JÁ na fila. ⚠️ `ok=False` porque a OS não mudou.

    🚨 UMA PENDENTE POR OS (índice único parcial da migração 115): duas na
    mesma OS seriam duas verdades sobre em que coluna o card está, e a tela
    teria de escolher uma sem critério. Se já houver uma, ela é ATUALIZADA para
    o novo destino -- o operador acabou de dizer para onde quer o card.
    """
    import json
    existente = banco.um(
        "SELECT id FROM os_passagem WHERE numero_os = %s "
        "   AND pendente_desde IS NOT NULL AND resolvida_em IS NULL",
        (numero_os,))
    if existente:
        banco.executar(
            "UPDATE os_passagem SET para_situacao = %s, de_situacao = %s, "
            "       atendente_id = %s, pendente_desde = now(), "
            "       tentativas = 0, pendente_erro = %s, em = now() "
            " WHERE id = %s",
            (para, de, atendente_id, frase, existente["id"]))
        return existente["id"]
    linha = banco.um(
        """INSERT INTO os_passagem
               (numero_os, de_situacao, para_situacao, atendente_id, ok, erro,
                pendente_desde, pendente_erro)
           VALUES (%s, %s, %s, %s, false, %s, now(), %s)
        RETURNING id""",
        (numero_os, de, para, atendente_id,
         "a escrita ficou na fila: a leitura do Harmonit estava atrasada",
         frase))
    return linha["id"]


def pendentes_por_os() -> dict[int, dict]:
    """A coluna que o card deve mostrar, por OS, enquanto a fila não fecha.

    🚨 **É ISTO QUE FAZ O CARD ANDAR**, e é a parte que vence o cache do FPSL:
    o quadro lê o `situacao_id` do cache, varrido a cada 5 min, e aqui está o
    que o operador já decidiu. ⚠️ Sem isto o card voltaria para a coluna antiga
    na próxima abertura do painel -- e a pessoa concluiria que não gravou e
    moveria de novo, que é exatamente o laço de 7 cliques da OS 17133.
    """
    linhas = banco.varios(
        "SELECT numero_os, para_situacao, pendente_desde, tentativas, "
        "       pendente_erro FROM os_passagem "
        " WHERE pendente_desde IS NOT NULL AND resolvida_em IS NULL")
    return {l["numero_os"]: l for l in linhas}


def fila() -> list[dict]:
    """O que a fila tem para tentar, mais antigo primeiro."""
    return banco.varios(
        "SELECT id, numero_os, de_situacao, para_situacao, tentativas, "
        "       pendente_desde FROM os_passagem "
        " WHERE pendente_desde IS NOT NULL AND resolvida_em IS NULL "
        " ORDER BY pendente_desde")


def escoar_fila(*, gravar=None) -> dict:
    """Uma passada na fila. 🚨 Uma tentativa por linha, por passada.

    ⚠️ NÃO insiste em laço aqui: insistir dentro da mesma execução é o
    *"só cansa a req"* dele. Quem dá o ritmo é o cron; cada passada custa uma
    tentativa por OS pendente.
    """
    gravar = gravar or fpsl_ponte.gravar_situacao_da_os
    feito = {"tentadas": 0, "resolvidas": 0, "continuam": 0, "desistiu": 0}
    for linha in fila():
        feito["tentadas"] += 1
        # 🚨 `conferir_antes=False`: a trava compararia com uma
        # `situacao_esperada` que a fila não tem, e recusaria a própria
        # correção -- seria o conflito falso de novo, agora contra nós mesmos.
        r = gravar(linha["numero_os"], linha["para_situacao"],
                   conferir_antes=False)
        if r.get("ok"):
            banco.executar(
                "UPDATE os_passagem SET ok = true, resolvida_em = now(), "
                "       tentativas = tentativas + 1, erro = NULL, "
                "       pendente_erro = NULL WHERE id = %s", (linha["id"],))
            feito["resolvidas"] += 1
            continue
        frase = fpsl_ponte.frase_da_recusa(r)
        banco.executar(
            "UPDATE os_passagem SET tentativas = tentativas + 1, "
            "       pendente_erro = %s WHERE id = %s", (frase, linha["id"]))
        if not r.get("pode_retentar", True):
            # 🔵 Recusa que não se retenta sai da fila e vira aviso: insistir
            # colhe o mesmo não. ⚠️ `resolvida_em` aqui quer dizer "saiu da
            # fila", não "deu certo" -- e `ok` continua falso, que é a verdade.
            banco.executar(
                "UPDATE os_passagem SET resolvida_em = now() WHERE id = %s",
                (linha["id"],))
            feito["desistiu"] += 1
            continue
        feito["continuam"] += 1
    return feito


def pendentes_para_a_red_flag() -> list[dict]:
    """Pendência velha demais, ou que saiu da fila sem ter gravado.

    🔵 1 hora, número dele. 🚨 Vazio = NENHUMA mensagem: aviso que aparece todo
    dia vira aviso que ninguém lê.
    """
    return banco.varios(
        "SELECT id, numero_os, de_situacao, para_situacao, tentativas, "
        "       pendente_desde, pendente_erro FROM os_passagem "
        " WHERE pendente_desde IS NOT NULL AND avisada_em IS NULL "
        "   AND ((resolvida_em IS NULL "
        "         AND pendente_desde < now() - make_interval(hours => %s)) "
        "        OR (resolvida_em IS NOT NULL AND NOT ok)) "
        " ORDER BY pendente_desde",
        (HORAS_PARA_A_RED_FLAG,))


def marcar_avisadas(ids: list[int]) -> None:
    """⚠️ Para a mesma pendência não ser avisada em toda rodada do cron."""
    if ids:
        banco.executar(
            "UPDATE os_passagem SET avisada_em = now() WHERE id = ANY(%s)",
            (ids,))
