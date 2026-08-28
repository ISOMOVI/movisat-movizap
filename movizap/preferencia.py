"""Preferência de cada pessoa — hoje, os atalhos de teclado.

Pedido dele em 28/08: *"crie nas configurações tela de atalhos e interruptor
desligado para eles e permita edição por lá também"*.

🚨 O PEDIDO NASCEU DE UMA PERGUNTA DELE QUE DERRUBOU UM RECURSO MEU: *"quem
pediu esses atalhos? ou eles já são nativos do WhatsApp?"*. Ninguém pediu, e
não são: `j`/`k` vêm do Gmail (e antes, do `vi`). Eu os levei para a Caixa de
entrada -- a tela que ELE escolheu entre cinco mockups para parecer o WhatsApp.
Convenção de Gmail numa tela que existe para parecer WhatsApp.

⚠️ E um deles agia sem perguntar: `a` assumia a conversa direto, com 380
conversas sem dono e nove pessoas testando.

🚨 NASCEM DESLIGADOS, e ausência de linha significa desligado. Quem nunca abriu
a tela não tem atalho -- que é o risco que este módulo veio fechar.
"""
import json
import logging

from . import banco

log = logging.getLogger(__name__)

CHAVE_LIGADOS = "atalhos_ligados"
CHAVE_TECLAS = "atalhos_teclas"

# 🚨 O CATÁLOGO VIVE NO BACKEND, e a tela o consome. Duplicá-lo no navegador
# criaria duas verdades, e a que o operador vê seria a errada -- é a mesma
# família do defeito de 17/08, em que a sidebar lia um contrato de JSON que o
# servidor tinha deixado de cumprir.
#
# ⚠️ `perigo` marca o que MUDA ESTADO sem perguntar. A tela usa isso para
# avisar antes de a pessoa ligar, em vez de ela descobrir apertando.
ATALHOS = [
    {"acao": "proxima", "tela": "Caixa de entrada", "padrao": "j",
     "descricao": "Próxima conversa", "perigo": False},
    {"acao": "anterior", "tela": "Caixa de entrada", "padrao": "k",
     "descricao": "Conversa anterior", "perigo": False},
    {"acao": "buscar", "tela": "Caixa de entrada", "padrao": "/",
     "descricao": "Ir para o campo de busca", "perigo": False},
    {"acao": "assumir", "tela": "Caixa de entrada", "padrao": "a",
     "descricao": "Assumir a conversa aberta",
     "perigo": True,
     "aviso": "Assume na hora, sem perguntar. A conversa passa a ser sua."},
    {"acao": "concluir", "tela": "Caixa de entrada", "padrao": "c",
     "descricao": "Abrir o concluir atendimento",
     "perigo": False,
     "aviso": "Abre a janela de concluir; quem conclui é o botão dela."},
    {"acao": "email_proxima", "tela": "E-mail", "padrao": "j",
     "descricao": "Próxima mensagem", "perigo": False},
    {"acao": "email_anterior", "tela": "E-mail", "padrao": "k",
     "descricao": "Mensagem anterior", "perigo": False},
    {"acao": "email_responder", "tela": "E-mail", "padrao": "r",
     "descricao": "Responder", "perigo": False},
    {"acao": "email_arquivar", "tela": "E-mail", "padrao": "e",
     "descricao": "Arquivar a mensagem aberta",
     "perigo": True,
     "aviso": "Arquiva na hora, sem perguntar."},
    {"acao": "email_nao_lida", "tela": "E-mail", "padrao": "u",
     "descricao": "Marcar como não lida", "perigo": False},
    {"acao": "email_estrela", "tela": "E-mail", "padrao": "s",
     "descricao": "Ligar/desligar a estrela", "perigo": False},
]

_ACOES = {a["acao"] for a in ATALHOS}
_PADRAO = {a["acao"]: a["padrao"] for a in ATALHOS}

# ⚠️ Uma tecla, sem modificador. `Ctrl`/`Alt`/`Cmd` são do navegador e o
# manipulador já os recusa; aceitar aqui prometeria o que a tela não cumpre.
_PROIBIDAS = {" ", "Enter", "Escape", "Tab", "Backspace"}


def _ler(atendente_id: int, chave: str) -> str | None:
    linha = banco.um(
        "SELECT valor FROM preferencia_atendente WHERE atendente_id = %s "
        "AND chave = %s", (atendente_id, chave))
    return linha["valor"] if linha else None


def _gravar(atendente_id: int, chave: str, valor: str) -> None:
    banco.executar(
        """INSERT INTO preferencia_atendente (atendente_id, chave, valor)
           VALUES (%s, %s, %s)
           ON CONFLICT (atendente_id, chave)
           DO UPDATE SET valor = EXCLUDED.valor, atualizado_em = now()""",
        (atendente_id, chave, valor))


def dos_atalhos(atendente_id: int | None) -> dict:
    """O que a tela precisa: se estão ligados, e a tecla de cada ação.

    ⚠️ Sem atendente (conta sem vínculo de atendimento) devolve o catálogo
    desligado, em vez de estourar: a tela existe para todo mundo.
    """
    ligados = False
    teclas = dict(_PADRAO)
    if atendente_id:
        bruto = _ler(atendente_id, CHAVE_LIGADOS)
        ligados = bruto == "true"
        guardadas = _ler(atendente_id, CHAVE_TECLAS)
        if guardadas:
            try:
                # ⚠️ Só sobrescreve ação CONHECIDA. Chave estranha guardada por
                # versão antiga não vira atalho fantasma.
                for acao, tecla in (json.loads(guardadas) or {}).items():
                    if acao in _ACOES and tecla:
                        teclas[acao] = tecla
            except (ValueError, TypeError):
                log.warning("atalhos_teclas ilegível para atendente %s -- "
                            "usando o padrão", atendente_id)
    return {
        "ligados": ligados,
        "teclas": teclas,
        "catalogo": ATALHOS,
    }


def ligar_atalhos(atendente_id: int, ligados: bool) -> dict:
    _gravar(atendente_id, CHAVE_LIGADOS, "true" if ligados else "false")
    log.info("atalhos %s para o atendente %s",
             "LIGADOS" if ligados else "desligados", atendente_id)
    return dos_atalhos(atendente_id)


def definir_teclas(atendente_id: int, teclas: dict) -> dict:
    """Troca as teclas. Valida antes de gravar, nunca depois.

    🚨 DUAS AÇÕES COM A MESMA TECLA NA MESMA TELA É RECUSA. Sem isto, `j` para
    "próxima" e para "assumir" faria a pessoa assumir conversa tentando andar
    na lista -- e ela não teria como saber por quê.
    """
    limpas = {}
    for acao, tecla in (teclas or {}).items():
        if acao not in _ACOES:
            return {"ok": False, "motivo": f"Ação desconhecida: {acao!r}."}
        tecla = str(tecla or "").strip()
        if len(tecla) != 1 or tecla in _PROIBIDAS:
            return {"ok": False,
                    "motivo": f"{tecla!r} não serve: use UMA tecla, e não "
                              f"espaço, Enter, Esc, Tab nem Backspace."}
        limpas[acao] = tecla

    final = dict(_PADRAO)
    final.update(limpas)
    por_tela: dict[str, dict] = {}
    for item in ATALHOS:
        tela = item["tela"]
        tecla = final[item["acao"]]
        if tecla in por_tela.setdefault(tela, {}):
            outra = por_tela[tela][tecla]
            return {"ok": False,
                    "motivo": f"A tecla {tecla!r} está em duas ações da tela "
                              f"{tela}: {outra} e {item['descricao']}."}
        por_tela[tela][tecla] = item["descricao"]

    _gravar(atendente_id, CHAVE_TECLAS, json.dumps(limpas, ensure_ascii=False))
    log.info("atalhos do atendente %s redefinidos: %s", atendente_id, limpas)
    return {"ok": True, **dos_atalhos(atendente_id)}
