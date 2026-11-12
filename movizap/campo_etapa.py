"""O CAMPO DE TEXTO QUE A ETAPA PEDE — Rastreamento e Devolução (migração 099).

🔵 Pedido dele (11/11), duas vezes com a mesma forma: *"Abaixo de
'Observações', criar um campo de texto chamado 'Rastreamento'"* (etapa 677,
**vai ao cliente**) e *"um campo de texto chamado 'Devolução' (...) Apenas para
consulta interna da operadora"* (etapa 15696).

🚨 AS DUAS NÃO SÃO A MESMA COISA, e é por isso que são duas chaves e não um
campo genérico: o rastreio **sai para o cliente** (é o que a mensagem da etapa
seguinte vai levar) e a devolução é **consulta interna**. Tratá-las como o
mesmo campo faria a primeira automação de disparo mandar o código errado.

🚨 NÃO EXISTIA NENHUM CAMPO LIVRE POR ETAPA ANTES DISTO. O que havia era o item
de checklist *"Inserir código de rastreio"* (etapa 677, migração 090) -- que
só MARCA que alguém inseriu, e **não guarda o código**. Marcar o item continua
valendo; agora há onde escrever.

⚠️ GRAVAR NÃO ESCREVE NO HARMONIT. Nenhuma destas funções fala com a ponte.
Escrever na OS exigiria `SalvarOrdemServico` -- a OS inteira --, que é a
armadilha do endereço e da situação, e ninguém pediu isso aqui.
"""
import logging

from . import banco
from .operacao import DadoInvalido

log = logging.getLogger("movizap.campo_etapa")

TETO = 120

# chave -> (situação do painel onde o campo aparece, rótulo, vai ao cliente?)
#
# 🚨 A SITUAÇÃO MORA AQUI, e não no banco: é regra de tela, muda com o fluxo
# dele, e botá-la em tabela exigiria uma migração para cada mudança de etapa.
# ⚠️ Mexer nesta lista é mexer no CHECK `os_campo_chave_check` da 099 -- chave
# nova sem migração é recusada pelo banco, de propósito.
CAMPOS = {
    "rastreio": {
        "situacao_id": 677,
        "rotulo": "Rastreamento",
        "ajuda": ("O código que será enviado ao cliente junto com o item."),
        "ao_cliente": True,
    },
    "devolucao": {
        "situacao_id": 15696,
        "rotulo": "Devolução",
        "ajuda": ("O código de devolução do item. Consulta interna da "
                  "operadora — não é enviado ao cliente."),
        "ao_cliente": False,
    },
}


def da_situacao(situacao_id: int | None) -> dict | None:
    """O campo que ESTA etapa pede, ou nada. É o que decide se a tela desenha."""
    if situacao_id is None:
        return None
    for chave, c in CAMPOS.items():
        if c["situacao_id"] == int(situacao_id):
            return dict(c, chave=chave)
    return None


def atuais(numero_os: int) -> dict:
    """`chave` -> o valor de agora, com quem escreveu e quando.

    🚨 O MAIS RECENTE POR CHAVE, e o histórico fica. `DISTINCT ON` é o mesmo
    molde do `passagem.etapa_desde`.
    """
    linhas = banco.varios(
        """SELECT DISTINCT ON (c.chave) c.chave, c.valor, c.em,
                  a.nome AS quem
             FROM os_campo_da_etapa c
             LEFT JOIN atendente a ON a.id = c.atendente_id
            WHERE c.numero_os = %s
            ORDER BY c.chave, c.em DESC, c.id DESC""", (int(numero_os),))
    return {linha["chave"]: {"valor": linha["valor"], "em": linha["em"],
                             "quem": linha["quem"]} for linha in linhas}


def historico(numero_os: int, chave: str) -> list[dict]:
    """Tudo o que já foi escrito naquela chave, do mais novo para o mais velho.

    ⚠️ Existe porque o código trocado pode já ter ido para o cliente: saber o
    anterior é o que permite dizer "mandei o errado".
    """
    return banco.varios(
        """SELECT c.id, c.valor, c.em, a.nome AS quem
             FROM os_campo_da_etapa c
             LEFT JOIN atendente a ON a.id = c.atendente_id
            WHERE c.numero_os = %s AND c.chave = %s
            ORDER BY c.em DESC, c.id DESC""", (int(numero_os), str(chave)))


def gravar(numero_os: int, chave: str, valor: str,
           atendente_id: int | None = None) -> dict:
    """Grava o valor e devolve o estado novo daquela chave.

    🔵 *"Ao mudar de etapa, os checklist e a situação deles, gerar OBS (...) O
    mesmo para os dados de 'Rastreamento' (...) o mesmo para o campo de
    'Devolução'"*.

    🚨 QUEM ESCREVE A OBSERVAÇÃO É AQUI, E NÃO O MOVER. Para o checklist a OBS
    sai ao SAIR da etapa, porque o que vale registrar é o placar final; para
    estes campos sai na GRAVAÇÃO, porque o que vale registrar é *qual código
    foi posto e por quem* -- e esperar a saída da etapa perderia a troca de
    código feita no meio.

    ⚠️ A OBS falhar NÃO desfaz a gravação: o código é o dado, a OBS é o rastro.
    """
    chave = str(chave or "").strip()
    if chave not in CAMPOS:
        raise DadoInvalido(f"O campo '{chave}' não existe nesta etapa.")
    valor = str(valor or "").strip()
    if not valor:
        raise DadoInvalido(
            f"Escreva o código de {CAMPOS[chave]['rotulo'].lower()}.")
    if len(valor) > TETO:
        raise DadoInvalido(
            f"{CAMPOS[chave]['rotulo']}: passa de {TETO} caracteres.")

    banco.executar(
        """INSERT INTO os_campo_da_etapa (numero_os, chave, valor, atendente_id)
           VALUES (%s, %s, %s, %s)""",
        (int(numero_os), chave, valor, atendente_id))
    log.info("campo da etapa: OS %s %s = %r por %s",
             numero_os, chave, valor, atendente_id)

    try:
        from . import passagem
        passagem.observar(
            int(numero_os),
            f"[sistema] {CAMPOS[chave]['rotulo']}: {valor}",
            atendente_id)
    except Exception:  # noqa: BLE001 -- o código é o dado; a OBS é o rastro
        log.exception("OS %s: gravei %s e não consegui guardar a observação",
                      numero_os, chave)

    return atuais(int(numero_os)).get(chave) or {}
