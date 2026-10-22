"""Fase 1 do ajuste da aba Atendimento (22/10) -- so o registro de telas.

Tres mudancas, todas em `movizap/telas.py`:

  1. ATD_1.1 passa a se chamar "WhatsApp" (pedido dele, 22/10).
  2. ATD_6.1 (Chat interno) e EML_1.1 (E-mail) sobem para logo depois da
     conversa, nesta ordem -- a ordem do menu E a ordem do registro, e e o
     `test_do_usuario_preserva_a_ordem_do_registro` que garante isso.
     O EML_1.1 passa a ter `grupo: "Atendimento"`.
  3. ATD_1.3 (Fila) e ATD_5.1 (Historico) passam de `atendimento` para
     `equipe` -- a permissao que o PERFIS ja da a owner + admin, so.

M8: patch por script porque precisa validar antes de gravar. Grava .bak e
imprime a ordem final para conferencia.
"""
import re
import shutil
import sys

ALVO = "movizap/telas.py"

EML_NOVO = '''    {
        # 🚨 MÓDULO PRÓPRIO, NÃO ATD -- e continua sendo. Decisão do usuário em
        # 10/08: *"jamais misturemos whatsapp com gmail, nunca"*. Caixa
        # própria, marcadores próprios, fila própria, código `EML`, rota e
        # permissão próprias. Foi ela que aposentou a `ATD_4.1`.
        #
        # 🔵 22/10, decisão dele: no MENU o item passa a morar dentro de
        # "Atendimento", abaixo do Chat interno (*"pessoal deu feedback que é
        # melhor nessa ordem"*), e ele confirmou que é **só visual**. Por isso
        # muda o `grupo` e NADA mais: o módulo não se mistura, só o lugar em
        # que o menu o desenha. Grupo é apresentação, não permissão -- é o que
        # o cabeçalho deste arquivo diz desde 21/10.
        #
        # ⚠️ O grupo "E-mail" continua declarado em GRUPOS e fica VAZIO. O
        # MenuLateral não desenha grupo sem tela visível, então ele some da
        # tela sozinho -- igual a "Painéis › Operacional".
        "codigo": "EML_1.1",
        "titulo": "E-mail",
        "rota": "/email",
        "icone": "bi-envelope",
        "descricao": "Caixa de e-mail, separada do WhatsApp.",
        "grupo": "Atendimento",
        "permissao": "atendimento",
        "fase": 1,
    },
'''


def main() -> int:
    linhas = open(ALVO, encoding="utf-8").read().splitlines(keepends=True)

    def achar(codigo):
        """A faixa [inicio, fim) do dict desta tela -- o `{` e o `},` dele."""
        for i, l in enumerate(linhas):
            if f'"codigo": "{codigo}",' in l:
                ini = i
                while not linhas[ini].strip() == "{":
                    ini -= 1
                fim = i
                while linhas[fim].strip() != "},":
                    fim += 1
                return ini, fim + 1
        raise SystemExit(f"não achei o dict de {codigo}")

    eml = achar("EML_1.1")
    chat = achar("ATD_6.1")
    conversa = achar("ATD_1.2")

    print(f"EML_1.1  linhas {eml[0]+1}..{eml[1]}")
    print(f"ATD_6.1  linhas {chat[0]+1}..{chat[1]}")
    print(f"ATD_1.2  termina na linha {conversa[1]}")

    # 🚨 O COMENTÁRIO DO EML_1.1 MORA FORA DAS CHAVES -- as 4 linhas de
    # "# ---- EML: e-mail ----" e do 🚨 abaixo dele. Se o dict sair sozinho,
    # esse comentário fica órfão rotulando a tela seguinte, que é o WhatsApp:
    # comentário que mente é o `M12` na forma mais barata de produzir. Vai
    # junto, e o texto novo (já dentro do dict, no EML_NOVO) o substitui.
    #
    # ⚠️ O ATD_6.1 é o caso OPOSTO: o "# ---- reservados ----" acima dele
    # rotula a SEÇÃO, e quem fica embaixo é a CFG_2.2, que é fase 2 -- de
    # verdade reservada. Esse comentário FICA. Por isso os dois blocos não
    # podem ser tratados pela mesma regra.
    topo = eml[0] - 1
    while linhas[topo].strip().startswith("#"):
        topo -= 1
    if topo + 1 < eml[0]:
        print(f"  (o comentário do EML_1.1 sai junto: linhas {topo+2}..{eml[0]})")
        eml = (topo + 1, eml[1])

    bloco_chat = "".join(linhas[chat[0]:chat[1]])
    # Remove de baixo para cima, senão os índices andam.
    for ini, fim in sorted([eml, chat], reverse=True):
        del linhas[ini:fim]

    # Onde a conversa terminava, descontadas as remoções que vieram antes dela.
    destino = conversa[1]
    for ini, fim in [eml, chat]:
        if fim <= conversa[1]:
            destino -= (fim - ini)
    print(f"inserindo Chat interno + E-mail na linha {destino+1}")

    linhas[destino:destino] = [bloco_chat, EML_NOVO]

    texto = "".join(linhas)

    # --- 1. o título ---
    antes = texto
    texto = texto.replace('        "titulo": "Caixa de entrada",',
                          '        "titulo": "WhatsApp",')
    if texto == antes:
        raise SystemExit("não achei o título 'Caixa de entrada' para trocar")

    # --- 3. a permissão da Fila e do Histórico ---
    for codigo in ("ATD_1.3", "ATD_5.1"):
        padrao = re.compile(
            r'("codigo": "' + codigo + r'",.*?)"permissao": "atendimento",',
            re.S)
        novo, n = padrao.subn(r'\1"permissao": "equipe",', texto, count=1)
        if n != 1:
            raise SystemExit(f"não troquei a permissão de {codigo}")
        texto = novo

    shutil.copyfile(ALVO, ALVO + ".bak_2026-10-22_atendimento")
    open(ALVO, "w", encoding="utf-8").write(texto)
    print("gravado (com .bak_2026-10-22_atendimento)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
