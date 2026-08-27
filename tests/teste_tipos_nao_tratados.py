"""O que NÃO é mensagem para de virar mensagem — 27/08.

🚨 O QUE ISTO DEFENDE. Até 27/08 qualquer chave fora das 11 conhecidas virava
uma linha `[<chave> — tipo ainda não tratado]` gravada em `mensagem.conteudo`,
que aparece no balão da conversa e no resumo da lista com a MESMA CARA de uma
fala do cliente. Medido no dia: **84 linhas falsas em 28 conversas**, de 8
tipos — e crescendo, com duas entrando durante a própria medição (09:13 e
09:59). É o mesmo defeito que a reação teve até 26/08, quando eram 161.

🚨 A TRAVA MEDE O PARSER RODANDO, NÃO O NOME DAS COISAS. Cada payload aqui
reproduz a ESTRUTURA MEDIDA na `webhook_evento` em 27/08 — inclusive o
`jpegThumbnail` como objeto-por-byte e o voto criptografado. Um teste que
procurasse a palavra "albumMessage" no fonte passaria com o parser quebrado;
travas assim já reprovaram código correto oito vezes neste projeto.

⚠️ NÃO TOCA NO BANCO. Só o parser, que é função pura.
"""
import sys

import pytest

sys.path.insert(0, "/home/claude/movizap_painel")

from movizap import conversas  # noqa: E402


# ── payloads com a estrutura medida em 27/08 ─────────────────────────────────

VOTO = {"pollUpdateMessage": {
    "vote": {"encIv": {"0": 96, "1": 131, "2": 243},
             "encPayload": {"0": 11, "1": 121, "2": 68}}}}

ALBUM = {"albumMessage": {"expectedImageCount": 4, "expectedVideoCount": 0}}

PLACEHOLDER = {"placeholderMessage": {"type": 0}}

HISTORICO = {"messageHistoryNotice": {"messageHistoryMetadata": {
    "messageCount": {"low": 93, "high": 0, "unsigned": False},
    "historyReceivers": ["211635117531275@lid"]}}}

SECRETA = {"secretEncryptedMessage": {
    "encIv": {"0": 109, "1": 3, "2": 88},
    "encPayload": {"0": 175, "1": 26, "2": 62}}}

# O texto é o do evento 5306, medido: title + content separados.
TEMPLATE = {"templateMessage": {
    "templateId": "28766515122938013",
    "hydratedTemplate": {
        "templateId": "28766515122938013",
        "hydratedButtons": [],
        "hydratedTitleText": "PABX Telecom",
        "hydratedContentText":
            "Olá, Iago - Movisat, Boa tarde! Sobre o seu suporte técnico, "
            "podemos falar agora?"}}}

# Evento 149: template com imagem e SEM título.
TEMPLATE_SEM_TITULO = {"templateMessage": {
    "hydratedTemplate": {
        "imageMessage": {"jpegThumbnail": {"0": 255, "1": 216, "2": 255}},
        "hydratedContentText": "Un Cliente. Una Plataforma.",
        "hydratedFooterText": "Reply with 'STOP' to unsubscribe."}}}

ENQUETE = {"pollCreationMessageV3": {
    "name": "De acordo com uso de vocês . Qual melhor modelo.",
    "options": [{"optionName": "J16 simcom"}, {"optionName": "J16 quectel"},
                {"optionName": "EC33 4g e 2g"}, {"optionName": "EC33 4g puro"}],
    "selectableOptionsCount": 1}}

TEXTO = {"conversation": "bom dia"}

IMAGEM = {"imageMessage": {"caption": "segue a foto", "mimetype": "image/jpeg"}}

# 🚨 OS DOIS QUE A FIXTURE NÃO TINHA. Achados exercitando o parser contra os
# 14.206 eventos reais: não estavam na lista de oito porque nunca chegaram a
# virar mensagem -- se perdem antes, num defeito separado (0800 sem telefone).
# Estrutura do evento 42018 e do 42020.
MENU = {"listMessage": {
    "listType": 1,
    "sections": [{"rows": [
        {"rowId": "1", "title": "Plataforma e Produto"},
        {"rowId": "2", "title": "Financeiro"},
        {"rowId": "3", "title": "Outros Assuntos"}]}]}}

ESCOLHA = {"listResponseMessage": {
    "title": "Outros Assuntos", "listType": 1,
    "contextInfo": {"stanzaId": "9E37BE3F332A92583E"}}}

# O evento 42014 traz a chave com valor `null`: não pode estourar.
MENU_VAZIO = {"listMessage": None}


class TestDescarte:
    """Os cinco que somem. Cada um devolve MOTIVO, e motivo é o que o webhook
    grava em `webhook_evento.motivo_ignorado` — o dado não some, a exibição
    é que some."""

    @pytest.mark.parametrize("payload,marca", [
        (VOTO, "pollUpdateMessage"),
        (ALBUM, "albumMessage"),
        (PLACEHOLDER, "placeholderMessage"),
        (HISTORICO, "messageHistoryNotice"),
    ])
    def test_nao_vira_mensagem_e_diz_por_que(self, payload, marca):
        motivo = conversas.motivo_de_descarte(payload)
        assert motivo, f"{marca} voltou a virar mensagem"
        assert marca in motivo, (
            f"o motivo não nomeia a chave: sem isso a contagem por "
            f"`motivo_ignorado` não distingue um tipo do outro. Veio: {motivo}")

    def test_tipo_que_o_whatsapp_ainda_vai_inventar_tambem_e_descartado(self):
        """🚨 O CORAÇÃO DESTA RODADA. O ramo antigo transformava a chave nova
        em texto para o atendente ler, e o WhatsApp inventa tipo o tempo todo:
        o defeito se repunha sozinho."""
        motivo = conversas.motivo_de_descarte({"algoQueAindaNaoExisteMessage": {"x": 1}})
        assert motivo and "algoQueAindaNaoExisteMessage" in motivo

    def test_messageContextInfo_sozinho_nao_e_tipo(self):
        """Ele acompanha várias mensagens e não é tipo nenhum. Classificar por
        ele seria classificar pela companhia."""
        assert conversas.motivo_de_descarte({"messageContextInfo": {"x": 1}}) is None


class TestSegueOFluxo:
    """O que continua sendo mensagem tem de continuar passando."""

    @pytest.mark.parametrize("payload", [TEXTO, IMAGEM, TEMPLATE, ENQUETE, SECRETA,
                                         MENU, ESCOLHA, MENU_VAZIO])
    def test_nao_e_descartado(self, payload):
        assert conversas.motivo_de_descarte(payload) is None, (
            f"descartou o que era mensagem: {list(payload)[0]}")


class TestTextoLegivel:
    """Os dois que carregavam texto real e chegavam ilegíveis."""

    def test_template_junta_titulo_e_corpo(self):
        tipo, texto = conversas._tipo_e_texto(TEMPLATE)
        assert tipo == "texto"
        assert texto == ("PABX Telecom — Olá, Iago - Movisat, Boa tarde! "
                         "Sobre o seu suporte técnico, podemos falar agora?")

    def test_template_sem_titulo_traz_so_o_corpo(self):
        _, texto = conversas._tipo_e_texto(TEMPLATE_SEM_TITULO)
        assert texto == "Un Cliente. Una Plataforma."

    def test_enquete_traz_a_pergunta_e_as_opcoes(self):
        _, texto = conversas._tipo_e_texto(ENQUETE)
        assert "Qual melhor modelo" in texto
        for opcao in ("J16 simcom", "J16 quectel", "EC33 4g e 2g", "EC33 4g puro"):
            assert opcao in texto, f"a opção {opcao} sumiu"

    def test_enquete_de_versao_futura_tambem_e_lida(self):
        """⚠️ O WhatsApp versiona: `pollCreationMessage`, `V2`, `V3`… Casar
        pelo prefixo é o que impede a próxima versão de cair no descarte."""
        futura = {"pollCreationMessageV9": ENQUETE["pollCreationMessageV3"]}
        assert conversas.motivo_de_descarte(futura) is None
        _, texto = conversas._tipo_e_texto(futura)
        assert "Qual melhor modelo" in texto

    def test_menu_traz_o_texto_e_as_opcoes(self):
        _, texto = conversas._tipo_e_texto(MENU)
        for opcao in ("Plataforma e Produto", "Financeiro", "Outros Assuntos"):
            assert opcao in texto, f"a opção {opcao} sumiu do menu"

    def test_escolha_no_menu_e_fala_e_nao_pode_sumir(self):
        """⚠️ `listResponseMessage` é a pessoa RESPONDENDO. Descartá-la apagaria
        o que ela escolheu -- foi o defeito que este teste impediu de nascer."""
        _, texto = conversas._tipo_e_texto(ESCOLHA)
        assert "Outros Assuntos" in texto

    def test_menu_com_valor_nulo_nao_estoura(self):
        assert conversas._tipo_e_texto(MENU_VAZIO) == ("texto", None)

    def test_visualizacao_unica_vira_aviso_legivel(self):
        """Ela não pode sumir: o atendente precisa saber que o cliente mandou
        algo. E não pode ser lida: chega criptografada e não temos a chave."""
        _, texto = conversas._tipo_e_texto(SECRETA)
        assert texto == "[mensagem de visualização única]"


class TestNuncaMaisONomeCru:
    """🚨 A TRAVA DE FUNDO: nenhum caminho pode devolver o nome da chave como
    se fosse texto do cliente. Era isso que o atendente vinha lendo."""

    @pytest.mark.parametrize("payload", [
        VOTO, ALBUM, PLACEHOLDER, HISTORICO, SECRETA, TEMPLATE, ENQUETE,
        MENU, ESCOLHA, MENU_VAZIO,
        {"algoNovoMessage": {"x": 1}}, {"outroMessage": None},
    ])
    def test_nenhum_tipo_produz_o_nome_da_chave_como_texto(self, payload):
        if conversas.motivo_de_descarte(payload):
            return  # descartado: não chega a virar texto
        _, texto = conversas._tipo_e_texto(payload)
        if texto is None:
            return
        assert "tipo ainda não tratado" not in texto
        assert "tipo não tratado" not in texto
        for chave in payload:
            assert chave not in texto, (
                f"o nome cru da chave `{chave}` foi para o balão do atendente")

    def test_o_texto_conhecido_nao_foi_afetado(self):
        assert conversas._tipo_e_texto(TEXTO) == ("texto", "bom dia")
        assert conversas._tipo_e_texto(IMAGEM) == ("imagem", "segue a foto")
