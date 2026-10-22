"""Os textos que a MINHA PRIMEIRA VARREDURA PERDEU -- e por que perdeu.

🚨 O `grep` da Fase 0 foi "Caixa de entrada", com C maiusculo. Tres textos que
o operador LE escrevem "caixa de entrada" em minusculo, no meio da frase, e
passaram batido. O `M13` diz que a varredura le a TELA e nao o seletor; o que
faltou e o irmao disso: ler a tela nao e so olhar o lugar certo, e tambem nao
chutar a forma da palavra. Varredura de rotulo se faz sem sensibilidade a
caixa, sempre.

Os tres (os demais achados sao COMENTARIO e ficam):

  1. frontend/src/telas/Fila.vue -- o <AjudaDaTela>, que o operador abre no
     icone de ajuda da propria tela da Fila.
  2. frontend/src/telas/CaixaDeEntrada.vue -- o texto do modal "Reabrir esta
     conversa?", que explica para onde a conversa VAI.
  3. frontend/src/telas/Fila.vue -- o cabecalho do arquivo, que descreve o
     contraste entre as duas telas. E comentario, mas descreve comportamento
     de HOJE, nao historia: fica coerente.

⚠️ `Clientes.vue:372`, `Email.vue:449`, `ChatInterno.vue:1072/1827`,
`avatar.js`, `Inicio.vue:127`, `sessao.js:7` e `CaixaDeEntrada.vue:2275` sao
comentarios que NARRAM (de onde veio, por que e assim). Diario nao se
reescreve -- e a regra do proprio registro.
"""
import shutil
import sys

TROCAS = [
    ("frontend/src/telas/Fila.vue",
     "<AjudaDaTela>Conversas sem dono. A caixa de entrada mostra o que é seu; "
     "aqui é o que não é de ninguém.</AjudaDaTela>",
     "<AjudaDaTela>Conversas sem dono. O WhatsApp mostra o que é seu; "
     "aqui é o que não é de ninguém.</AjudaDaTela>", 1),
    ("frontend/src/telas/CaixaDeEntrada.vue",
     "'Ela sai do Histórico, volta para a caixa de entrada e você passa a '",
     "'Ela sai do Histórico, volta para o WhatsApp e você passa a '", 1),
    ("frontend/src/telas/Fila.vue",
     "   Não é a caixa de entrada filtrada: a caixa mostra o que é SEU, "
     "a fila mostra\n",
     "   Não é o WhatsApp filtrado: o WhatsApp mostra o que é SEU, "
     "a fila mostra\n", 1),
]


def main() -> int:
    erros = []
    for caminho, antes, depois, n in TROCAS:
        texto = open(caminho, encoding="utf-8").read()
        achadas = texto.count(antes)
        if achadas != n:
            erros.append(f"FALHOU {caminho}: {achadas} de {n} -- {antes[:60]!r}")
            print(erros[-1])
            continue
        bak = caminho + ".bak_2026-10-22_atendimento"
        try:
            open(bak, "x", encoding="utf-8").write(texto)
        except FileExistsError:
            pass
        open(caminho, "w", encoding="utf-8").write(texto.replace(antes, depois, n))
        print(f"ok  {caminho}: {antes[:58]!r}")
    return 1 if erros else 0


if __name__ == "__main__":
    sys.exit(main())
