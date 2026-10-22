"""Fase 1, parte 2: o contador de e-mail nao lido em /api/eu/notificacoes.

Por que AQUI e nao numa rota nova: esta rota ja roda em TODA tela (o
`Notificador.vue` esta montado no App.vue, de 8 em 8 segundos) e ja nao exige
`requer_tela` -- e a pessoa olhando para si. Rota nova significaria um segundo
ritmo de polling para o mesmo selo.

🚨 O FILTRO E O MESMO DA ABA "ENTRADA" da EML_1.1, copiado de
`/api/email/mensagens` (`NOT arquivada AND na_lixeira_desde IS NULL`): a
bolinha nao pode discordar da tela -- a mesma regra que o `abas.minhas` segue
desde 24/09.
"""
import shutil
import sys

ALVO = "movizap/main.py"

FUNCAO = '''
def _email_nao_lidos(eu: int) -> int:
    """Quantos nao lidos na ENTRADA das caixas que esta pessoa conectou.

    🔵 22/10, pedido dele: o selo de nao lidas do E-mail no menu, junto do do
    WhatsApp e do Chat interno, e os tres somados no cabecalho fechado.

    🚨 MESMO FILTRO DA ABA "ENTRADA" (`/api/email/mensagens`): fora o
    arquivado e fora a lixeira. Selo que conta arquivada mandaria a pessoa
    abrir a tela para procurar uma mensagem que a tela nao mostra -- e o
    `abas.minhas` existe desde 24/09 justamente com a regra de que a bolinha
    conta pela MESMA regua da lista.

    ⚠️ Quem nunca conectou caixa recebe 0, nao erro: a rota serve todo mundo,
    inclusive quem nao tem a EML_1.1. `_caixas_do_usuario` ja trata isso do
    lado da tela; aqui a subconsulta vazia faz o mesmo sozinha.
    """
    linha = banco.um(
        """SELECT count(*) AS quantas
             FROM email_mensagem e
            WHERE e.conta_id IN (SELECT id FROM email_conta
                                  WHERE atendente_id = %s AND ativa)
              AND NOT e.lida
              AND NOT e.arquivada
              AND e.na_lixeira_desde IS NULL""", (eu,))
    return int(linha["quantas"] if linha else 0)


'''

ANCORA_FUNCAO = '@app.get("/api/eu/notificacoes")\n'

VAZIO_ANTES = '''        return {"ativa": False, "tom": "classico", "volume": 3,
                "abas": {"minhas": 0, "time": 0}, "assumidas": [], "donas": []}'''
VAZIO_DEPOIS = '''        return {"ativa": False, "tom": "classico", "volume": 3,
                "abas": {"minhas": 0, "time": 0}, "email_nao_lidos": 0,
                "assumidas": [], "donas": []}'''

RETORNO_ANTES = '        "abas": {"minhas": len(minhas), "time": len(do_time)},\n'
RETORNO_DEPOIS = (
    '        "abas": {"minhas": len(minhas), "time": len(do_time)},\n'
    '        # 🔵 22/10: o terceiro selo do menu. Sai daqui, e nao de rota\n'
    '        # propria, porque esta rota ja bate em toda tela -- um ritmo so.\n'
    '        "email_nao_lidos": _email_nao_lidos(eu),\n')


def main() -> int:
    texto = open(ALVO, encoding="utf-8").read()

    if "_email_nao_lidos" in texto:
        raise SystemExit("ja aplicado -- `_email_nao_lidos` existe no arquivo")

    for antes, depois, nome in (
        (ANCORA_FUNCAO, FUNCAO.lstrip("\n") + ANCORA_FUNCAO, "a funcao"),
        (VAZIO_ANTES, VAZIO_DEPOIS, "o retorno de quem nao e atendente"),
        (RETORNO_ANTES, RETORNO_DEPOIS, "o retorno normal"),
    ):
        if texto.count(antes) != 1:
            raise SystemExit(
                f"{nome}: achei {texto.count(antes)} ocorrencias do ancora, esperava 1")
        texto = texto.replace(antes, depois, 1)
        print(f"ok: {nome}")

    shutil.copyfile(ALVO, ALVO + ".bak_2026-10-22_atendimento")
    open(ALVO, "w", encoding="utf-8").write(texto)
    print("gravado (com .bak_2026-10-22_atendimento)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
