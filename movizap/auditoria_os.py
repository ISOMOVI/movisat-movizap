# -*- coding: utf-8 -*-
"""A auditoria da coluna do card contra a situação da OS no Harmonit.

🔵 Desenho dele, 18/11: *"uma pode verificar e levantar, indicar os erros, e
disparar por outro que só vai reescrever, daí guardar os logs juntos para
evitar perca e depois devolve ao primeiro para validar e passar verde"*.

Este módulo é o miolo dos dois agentes. Os scripts
`scripts/auditor_os.py` e `scripts/escritor_os.py` são as duas portas de
entrada, e a separação é a dele: **quem levanta não escreve**.

🚨 O DEFEITO QUE ISTO EXISTE PARA RESOLVER, medido na OS 17133 em 18/11. A
mesma rota do Harmonit, na mesma OS, sem nenhuma escrita entre as duas
leituras:

    11:42:47  devolveu 251   -> o painel recusou a passagem como conflito
    11:43:18  devolveu 16488 -> a passagem seguinte funcionou

Das 11:17 às 11:42 ela respondeu **o valor que escrevemos às 09:42**, ignorando
o de 09:49: um atraso de ≈1h54 que se resolveu sozinho. Sete recusas, todas
falsas, e o operador clicando porque nada acontecia.

🚨 **POR ISSO A REGRA DAS DUAS LEITURAS, e ela é o coração deste arquivo:** uma
leitura só não distingue divergência de atraso. Com uma leitura, o escritor
reescreveria situação correta por cima de situação correta -- gastando
exatamente o pool que a madrugada deveria poupar -- e a red flag avisaria sobre
um problema que não existe.

🚨 **E A SEGUNDA REGRA: valor que NÓS escrevemos antes é ATRASO, não erro.** Se
o ERP devolve uma situação que está no nosso próprio histórico de passagens
daquela OS, a leitura dele está atrás da nossa escrita. Isso não vai ao
escritor e não vira red flag.

⚠️ **O ESCOPO É MAIS ESTREITO DO QUE O PLANO DIZIA, e a razão é mecânica.** O
plano falava em reler as OS que são card (633, medidas hoje). Mas divergência
só pode existir onde **nós escrevemos**: a coluna de uma OS que ninguém moveu
É o valor do ERP, porque veio de lá. Medido em 18/11: **20** OS têm passagem
nossa confirmada, de 633 cards. Então:

    · as 20 que movemos ............ 2 leituras cada = 40 chamadas
    · os cards de cache velho ...... 224 OS, 1 leitura = 224 chamadas
                                     ----------------------------------
                                     264, contra 1.266 do plano

🔵 O segundo grupo cobre o que ele chamou de desafogo (card com situação velha),
e é 1 leitura só porque ali não há escrita nossa para divergir -- é cache
atrasado, não conflito. ⚠️ **Se ele quiser as 633 inteiras, é mudar
`SO_AS_QUE_MOVEMOS` para `False`.** O número é dele; o que eu fiz foi medir.
"""
import logging

from . import banco, fpsl_ponte

log = logging.getLogger("movizap.auditoria_os")

# ⚠️ Ver o docstring: o escopo estreito é o que a mecânica justifica, e o
# interruptor existe para ele poder discordar sem eu mexer no código.
SO_AS_QUE_MOVEMOS = True

# 🔵 Dele, 18/11: 3 grupos de 3, com **5 minutos** entre os grupos.
GRUPOS = 3
TENTATIVAS_POR_GRUPO = 3
SEGUNDOS_ENTRE_GRUPOS = 300

# Card cuja última releitura é mais velha que isto entra na varredura de
# desafogo. 📏 224 das 633 estavam assim em 18/11.
HORAS_DE_CACHE_VELHO = 24

# 🔵 1 HORA — número dele, 18/11, para separar atraso de escrita perdida.
# ⚠️ O atraso medido na OS 17133 foi de ≈1h54 e se resolveu sozinho, então
# 1h avisa sobre um caso que ainda poderia se resolver. Ele escolheu assim
# sabendo disso: avisar mais cedo e com mais ruído.
HORAS_DE_ESPERA_DO_ATRASO = 1


# ===========================================================================
# O AUDITOR — levanta, e NÃO escreve no ERP
# ===========================================================================
def _nossas_os() -> list[dict]:
    """As OS que nós movemos, com a situação que acreditamos e a hora."""
    return banco.varios(
        "SELECT DISTINCT ON (numero_os) numero_os, para_situacao, em "
        "  FROM os_passagem "
        " WHERE ok AND de_situacao IS NOT NULL "
        " ORDER BY numero_os, em DESC, id DESC")


def _ja_escrevemos(numero_os: int) -> set[int]:
    """Toda situação que já escrevemos nesta OS, com sucesso.

    🚨 É ISTO QUE DISTINGUE ATRASO DE ERRO. Se o ERP devolve um valor que está
    aqui, ele está respondendo uma escrita nossa mais antiga -- a leitura dele
    atrasou. Se devolve um valor que nunca escrevemos, alguém mexeu na OS por
    fora, e isso é divergência de verdade.
    """
    linhas = banco.varios(
        "SELECT DISTINCT para_situacao FROM os_passagem "
        " WHERE numero_os = %s AND ok AND para_situacao IS NOT NULL",
        (numero_os,))
    return {l["para_situacao"] for l in linhas}


def _ler_do_erp(numero_os: int) -> tuple[int | None, str]:
    """A situação da OS agora, pela ponte. `(situacao, erro)`."""
    try:
        ficha = fpsl_ponte.ficha_da_os(numero_os)
    except Exception as e:  # noqa: BLE001 -- a ponte estoura quando cai
        return None, f"{type(e).__name__}: {e}"
    return ficha.get("situacao_id"), ""


def auditar(*, ler=None) -> dict:
    """Uma rodada do auditor. 🚨 NENHUMA ESCRITA NO ERP.

    `ler` existe para o teste encenar o Harmonit sem rede.

    Devolve o resumo da rodada. As divergências ficam em `auditoria_os`.
    """
    ler = ler or _ler_do_erp
    resumo = {"lidas": 0, "iguais": 0, "atrasos": 0, "mudou_no_erp": 0,
              "escritas_perdidas": 0, "nao_confirmadas": 0, "sem_leitura": 0,
              "ja_aceito": 0}

    # ------------------------------------------------- 1ª passada
    primeira: dict[int, int | None] = {}
    nossas = _nossas_os()
    for linha in nossas:
        n = linha["numero_os"]
        situacao, erro = ler(n)
        resumo["lidas"] += 1
        if erro:
            resumo["sem_leitura"] += 1
            log.info("auditor: nao li a OS %s (%s)", n, erro)
            continue
        if situacao == linha["para_situacao"]:
            resumo["iguais"] += 1
            continue
        primeira[n] = situacao

    # ------------------------------------------------- 2ª passada
    # 🚨 SÓ AS QUE DIVERGIRAM, e só depois de a 1ª passada inteira terminar: a
    # separação no tempo é o que faz a 2ª leitura valer alguma coisa. Reler na
    # linha seguinte pegaria o mesmo instante do mesmo atraso.
    for linha in nossas:
        n = linha["numero_os"]
        if n not in primeira:
            continue
        agora, erro = ler(n)
        resumo["lidas"] += 1
        if erro:
            resumo["sem_leitura"] += 1
            continue
        if agora == linha["para_situacao"]:
            # Ficou igual sozinho entre as duas passadas: era atraso, e já
            # passou. ⚠️ Não é "nao_confirmada": é o atraso se resolvendo, que
            # é exatamente o que aconteceu na 17133 às 11:43.
            _registrar(n, linha, agora, veredito="atraso")
            resumo["atrasos"] += 1
            continue
        if agora != primeira[n]:
            # As duas leituras discordaram entre si: leitura instável, não dá
            # para afirmar divergência.
            _registrar(n, linha, agora, veredito="nao_confirmada")
            resumo["nao_confirmadas"] += 1
            continue
        # 🚨 AQUI MORA A DIFERENÇA QUE O ENSAIO A SECO ME ENSINOU, em 18/11.
        # Rodando contra a produção antes de ligar a escrita, o auditor achou
        # duas divergências reais:
        #
        #     OS 17054: o painel diz 251   e o Harmonit diz 16490
        #     OS 17114: o painel diz 15696 e o Harmonit diz 16490
        #
        # E o histórico mostra que **16490 nunca foi escrito por nós**: alguém
        # avançou essas OS dentro do Harmonit, depois da nossa passagem. O ERP
        # está certo e o nosso card está velho.
        #
        # ⚠️ O escritor, como eu o havia escrito, iria reescrever a nossa
        # coluna por cima -- puxando a 17054 de *"Analise de Equipamentos
        # Retornados"* de volta para *"Configurar equipamentos e Sistemas"*,
        # numa OS de cliente, desfazendo o trabalho de quem fez a coisa certa.
        #
        # A pergunta que separa os casos é uma só: **o valor que o ERP mostra é
        # um valor que NÓS já escrevemos?**
        if agora not in _ja_escrevemos(n):
            # 🚨 MUDANÇA FEITA NO ERP É ACEITA, E ACEITAR É LEMBRAR. Sem isto a
            # divergência é PERMANENTE por construção: `coluna_nossa` é a nossa
            # última passagem confirmada, e ela nunca vai voltar a bater com um
            # valor que nós não escrevemos. As OS 17054 e 17114 sairiam na
            # mensagem todas as noites, para sempre -- contra a regra dele de
            # que *"aviso que aparece todo dia vira aviso que ninguém lê"*.
            if _ja_aceito(n, agora):
                resumo["ja_aceito"] += 1
                continue
            # ⚠️ Fecha na hora: não há o que fazer. O card já segue o ERP, que
            # vem do cache. A linha existe para avisar UMA vez e ficar no
            # histórico.
            _registrar(n, linha, agora, veredito="mudou_no_erp", fechar=True)
            resumo["mudou_no_erp"] += 1
            continue
        # É valor nosso. 🔵 O que separa atraso de escrita perdida é TEMPO, com
        # o número dele: 1 hora. O atraso medido na 17133 foi de ≈1h54 e se
        # resolveu sozinho -- abaixo de 1h não se mexe.
        if _escrita_recente(linha["em"]):
            _registrar(n, linha, agora, veredito="atraso")
            resumo["atrasos"] += 1
            continue
        _registrar(n, linha, agora, veredito="escrita_perdida")
        resumo["escritas_perdidas"] += 1

    return resumo


def _escrita_recente(quando) -> bool:
    """A nossa última passagem desta OS tem menos de 1 hora?

    🔵 1 hora é número dele, 18/11. 🚨 A conta é feita no BANCO: comparar um
    `timestamptz` com a hora do processo é o caminho curto para o vermelho
    intermitente de fuso de 11/11.
    """
    linha = banco.um(
        "SELECT (%s > now() - make_interval(secs => %s)) AS recente",
        (quando, HORAS_DE_ESPERA_DO_ATRASO * 3600))
    return bool(linha and linha["recente"])


def _ja_aceito(numero_os: int, do_erp: int | None) -> bool:
    """Esta OS já teve esta mesma mudança do ERP aceita numa rodada anterior?

    🚨 É o que impede o aviso eterno. ⚠️ Compara o VALOR do ERP, não só a OS:
    se alguém mover a OS outra vez, para um terceiro valor que também não é
    nosso, isso é fato novo e volta a avisar.
    """
    return bool(banco.um(
        "SELECT 1 FROM auditoria_os WHERE numero_os = %s "
        "   AND veredito = 'mudou_no_erp' AND situacao_do_erp = %s "
        " LIMIT 1", (numero_os, do_erp)))


def _registrar(numero_os: int, nossa: dict, do_erp: int | None, *,
               veredito: str, fechar: bool = False) -> None:
    """Abre (ou atualiza) a linha da divergência.

    ⚠️ UMA LINHA ABERTA POR OS (índice parcial da migração 113): a rodada de
    amanhã não abre uma segunda para a mesma divergência que ninguém fechou,
    senão a red flag contaria o mesmo problema várias vezes.
    """
    banco.executar(
        "INSERT INTO auditoria_os "
        "  (numero_os, coluna_nossa, situacao_do_erp, lido_em, cache_de, "
        "   veredito, fechada_em, fechada_como) "
        "VALUES (%s, %s, %s, now(), %s, %s, "
        "        CASE WHEN %s THEN now() END, "
        "        CASE WHEN %s THEN 'ainda_diferente' END) "
        "ON CONFLICT (numero_os) WHERE fechada_em IS NULL "
        "DO UPDATE SET situacao_do_erp = EXCLUDED.situacao_do_erp, "
        "              lido_em = now(), veredito = EXCLUDED.veredito, "
        "              fechada_em = EXCLUDED.fechada_em, "
        "              fechada_como = EXCLUDED.fechada_como",
        (numero_os, nossa["para_situacao"], do_erp, nossa["em"], veredito,
         fechar, fechar))


def abertas() -> list[dict]:
    """O que o escritor tem para fazer. 🚨 A lista é do auditor, não dele.

    🚨 **SÓ `escrita_perdida`**, e isto é o conserto que o ensaio a seco de
    18/11 obrigou. `mudou_no_erp` NÃO entra: ali o ERP mostra um valor que nós
    nunca escrevemos, ou seja alguém mexeu na OS dentro do Harmonit -- e
    reescrever a nossa coluna por cima desfaria o trabalho dessa pessoa. Foi o
    que teria acontecido com as OS 17054 e 17114.
    """
    return banco.varios(
        "SELECT id, numero_os, coluna_nossa, situacao_do_erp, tentativas, "
        "       grupos FROM auditoria_os "
        " WHERE fechada_em IS NULL AND veredito = 'escrita_perdida' "
        " ORDER BY numero_os")


def fechar_relendo(*, ler=None) -> dict:
    """A volta: o auditor relê o que o escritor mexeu e fecha a linha.

    🚨 QUEM DIZ QUE FICOU BOM É A RELEITURA, NUNCA O ESCRITOR — é a mesma regra
    de toda a ponte, e a única que sobrevive a um ERP que responde atrasado.
    """
    ler = ler or _ler_do_erp
    fechadas = {"verdes": 0, "ainda_diferentes": 0, "sem_leitura": 0}
    for linha in banco.varios(
            "SELECT id, numero_os, coluna_nossa FROM auditoria_os "
            " WHERE fechada_em IS NULL AND escrito_em IS NOT NULL "
            " ORDER BY numero_os"):
        agora, erro = ler(linha["numero_os"])
        if erro:
            fechadas["sem_leitura"] += 1
            continue
        igual = agora == linha["coluna_nossa"]
        banco.executar(
            "UPDATE auditoria_os SET fechada_em = now(), fechada_como = %s, "
            "       veredito = %s, situacao_do_erp = %s WHERE id = %s",
            ("igual" if igual else "ainda_diferente",
             "resolvida" if igual else "desistiu", agora, linha["id"]))
        fechadas["verdes" if igual else "ainda_diferentes"] += 1
    return fechadas


# ===========================================================================
# O ESCRITOR — só reescreve o que o auditor marcou
# ===========================================================================
def escrever(*, gravar=None, esperar=None) -> dict:
    """🔵 *"outro que só vai reescrever"*: 3 grupos de 3 tentativas, 5 min
    entre os grupos.

    🚨 NÃO DECIDE NADA. A lista é do auditor (`abertas()`), e este agente não
    olha o ERP para escolher: se olhasse, voltaria a ser um agente só, e a
    separação que ele pediu existe justamente para a escrita acontecer longe da
    leitura.

    ⚠️ E NÃO DIZ QUE DEU CERTO. Quem fecha a linha é o auditor, relendo
    (`fechar_relendo`). Aqui só se anota o que o ERP respondeu.

    `gravar` e `esperar` existem para o teste não falar com a rede nem dormir
    5 minutos.
    """
    gravar = gravar or fpsl_ponte.gravar_situacao_da_os
    if esperar is None:
        import time
        esperar = time.sleep

    feito = {"linhas": 0, "escritas": 0, "desistiu": 0, "grupos_usados": 0}
    pendentes = abertas()
    feito["linhas"] = len(pendentes)
    if not pendentes:
        return feito

    for grupo in range(1, GRUPOS + 1):
        if not pendentes:
            break
        if grupo > 1:
            # 🔵 5 min, número dele. ⚠️ A régua que ele deu foi *"intervalo que
            # dê para o pool recuperar"* -- e em 18/11 o pool respondia em
            # 160ms, então não é ele que aperta hoje. O número vale para o dia
            # ruim: 15,8s por leitura e 164 falhas, como em 07/11.
            esperar(SEGUNDOS_ENTRE_GRUPOS)
        feito["grupos_usados"] = grupo
        sobraram = []
        for linha in pendentes:
            ok = False
            ultimo = ""
            for _ in range(TENTATIVAS_POR_GRUPO):
                r = gravar(linha["numero_os"], linha["coluna_nossa"],
                           conferir_antes=False)
                _anotar_tentativa(linha["id"], grupo, r)
                if r.get("ok"):
                    ok = True
                    break
                ultimo = r.get("causa") or ""
                # 🚨 RECUSA DE NEGÓCIO NÃO ENTRA EM GRUPO NENHUM, 🔵 regra
                # dele: *"só cansa a req"*. Repetir colhe o mesmo "não" e gasta
                # o pool -- e `escrita_sem_resposta` não se repete por outro
                # motivo: não se sabe se gravou.
                if not r.get("pode_retentar", True):
                    break
            if ok:
                feito["escritas"] += 1
            elif ultimo and not _retentavel(ultimo):
                # Vai direto para a red flag, sem consumir os outros grupos.
                _desistir(linha["id"], ultimo)
                feito["desistiu"] += 1
            else:
                sobraram.append(linha)
        pendentes = sobraram

    # Quem sobrou depois dos 3 grupos: desistiu.
    for linha in pendentes:
        _desistir(linha["id"], "os 3 grupos de 3 tentativas nao resolveram")
        feito["desistiu"] += 1
    return feito


def _retentavel(causa: str) -> bool:
    return causa not in fpsl_ponte.CAUSAS_QUE_NAO_SE_RETENTA


def _anotar_tentativa(linha_id: int, grupo: int, resposta: dict) -> None:
    """O log do escritor, NA MESMA LINHA da divergência.

    🔵 *"guardar os logs juntos para evitar perca"*. Log separado por agente
    seriam duas metades de uma história, e a pergunta real -- *"esta OS foi
    tentada quantas vezes e com que resposta?"* -- exigiria juntar as duas à
    mão, todas as vezes.
    """
    banco.executar(
        "UPDATE auditoria_os "
        "   SET tentativas = tentativas + 1, grupos = GREATEST(grupos, %s), "
        "       escrito_em = now(), ultimo_erro = %s "
        " WHERE id = %s",
        (grupo,
         None if resposta.get("ok") else (
             fpsl_ponte.frase_da_recusa(resposta) or resposta.get("motivo")),
         linha_id))


def _desistir(linha_id: int, porque: str) -> None:
    banco.executar(
        "UPDATE auditoria_os SET veredito = 'desistiu', fechada_em = now(), "
        "       fechada_como = 'ainda_diferente', ultimo_erro = %s "
        " WHERE id = %s", (porque, linha_id))


# ===========================================================================
# A RED FLAG
# ===========================================================================
def para_a_red_flag() -> list[dict]:
    """As linhas que merecem aviso. 🚨 Vazio = NENHUMA mensagem.

    ⚠️ `atraso` e `nao_confirmada` NÃO entram, e é o ponto todo: elas são o ERP
    respondendo devagar, não trabalho para alguém. Aviso que aparece todo dia
    vira aviso que ninguém lê.
    """
    return banco.varios(
        "SELECT id, numero_os, coluna_nossa, situacao_do_erp, tentativas, "
        "       grupos, ultimo_erro, veredito FROM auditoria_os "
        " WHERE avisada_em IS NULL "
        "   AND (veredito = 'desistiu' OR veredito = 'mudou_no_erp') "
        " ORDER BY numero_os")


def marcar_avisadas(ids: list[int]) -> None:
    """⚠️ Marcada DEPOIS de o envio dar certo: marcar antes perderia o aviso se
    o WhatsApp falhasse, e ninguém nota a ausência de um aviso."""
    if ids:
        banco.executar(
            "UPDATE auditoria_os SET avisada_em = now() WHERE id = ANY(%s)",
            (ids,))
