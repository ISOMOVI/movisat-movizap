# -*- coding: utf-8 -*-
"""Tarefa 2.3 — remover o item com justificativa nas colunas 3, 4 e 5.

🔵 DELE: *"é possível clicar em remover, onde o item de pagamento será removido
e devolvido ao card na coluna de Movimentação abrindo um campo de
justificativa"*, e *"veja que aqui não retorna para a anterior e sim para o 1"*.

📏 MEDIDO EM 23/11, e o registro estava velho (*"a rota já existe, falta o
gesto"* -- o gesto existe, mas não onde ele pediu):
  · a rota `/devolver` existe nos dois lados e o serviço aceita devolver de
    QUALQUER coluna que não seja a 1 (`preparacao`, `validacao`, `procfy`,
    `enviado`);
  · a tela só tem o botão **dentro do diálogo de conferência**, que se abre da
    coluna 2 (`preparacao`). Nas colunas 3, 4 e 5 não há como remover um item.

🚨 NADA DE GESTO NOVO: reusa o `pedirDevolucao` e o diálogo de justificativa que
já existem. Um segundo caminho de devolução seria a mesma regra em dois
lugares -- e aqui a regra é dele ("sempre para a coluna 1").

🚨 E O DIÁLOGO PASSA A DIZER O QUE MUDA DEPOIS DO ARQUIVO. Remover da `procfy`
ou da `enviado` é remover um item cujo arquivo **já foi gerado** (e, na 5, já
foi enviado). Deixar a mesma frase das outras colunas faria a tela esconder a
consequência -- `M12`. O texto é condicional, não um aviso novo.
"""
import pathlib

p = pathlib.Path("frontend/src/telas/PainelServicoDosTecnicos.vue")
bruto = p.read_bytes()
CRLF = b"\r\n" in bruto
t = bruto.decode("utf-8").replace("\r\n", "\n")


def troca(velho, novo, rotulo):
    global t
    assert velho in t, "NAO ACHOU (%s)" % rotulo
    assert t.count(velho) == 1, "AMBIGUO %dx (%s)" % (t.count(velho), rotulo)
    t = t.replace(velho, novo, 1)
    print("  ok:", rotulo)


# --------------------------------------------- 1. o botão por item, nas 3,4,5
troca('''                        <button v-if="colunaAberta === 'validacao'"
                                class="botao botao--fraco botao--mini"
                                type="button" @click="abrirComprovante(a)">
                          {{ a.comprovante_arquivo || a.comprovante_dispensa
                             ? 'Trocar comprovante' : 'Comprovante' }}
                        </button>''',
      '''                        <button v-if="colunaAberta === 'validacao'"
                                class="botao botao--fraco botao--mini"
                                type="button" @click="abrirComprovante(a)">
                          {{ a.comprovante_arquivo || a.comprovante_dispensa
                             ? 'Trocar comprovante' : 'Comprovante' }}
                        </button>

                        <!-- 🔵 Tarefa 2.3: remover o item com justificativa
                             nas colunas 3, 4 e 5. 📏 Medido em 23/11: o
                             serviço já aceitava de qualquer coluna que não
                             seja a 1, e o botão existia só no diálogo de
                             conferência, que abre da coluna 2.
                             🚨 MESMO GESTO, não um segundo caminho: chama o
                             `pedirDevolucao` que a conferência usa, e a regra
                             dele ("sempre para a coluna 1") fica num lugar
                             só. -->
                        <button v-if="colunaAberta !== 'movimentacao'"
                                class="botao botao--fraco botao--mini"
                                type="button" @click="pedirDevolucao(a)">
                          Remover
                        </button>''',
      "1. o botao Remover por item, em toda coluna que nao seja a 1")

# --------------------------------------------- 2. o diálogo diz a consequência
troca('''        <p class="nota pequeno">
          A OS {{ devolvendo.numero_os }} volta para a Movimentação em laranja,
          com esta justificativa à vista.
        </p>''',
      '''        <p class="nota pequeno">
          A OS {{ devolvendo.numero_os }} volta para a Movimentação em laranja,
          com esta justificativa à vista.
        </p>
        <!-- 🚨 A CONSEQUÊNCIA, QUANDO HÁ UMA: na coluna 4 o arquivo do Procfy
             já foi montado com este item dentro, e na 5 ele já foi enviado.
             Remover sem dizer isso faria a tela esconder o que muda -- e é
             justamente aqui que a pessoa decide. -->
        <!-- ⚠️ `nota pequeno` e `selo--laranja`, que EXISTEM neste arquivo:
             em 23/11 eu ia escrever `nota--aviso`, que não existe em nenhum
             CSS -- a armadilha da `.pilula`, classe sem estilo que nenhum
             teste pega porque o jsdom não faz layout. -->
        <p v-if="colunaAberta === 'procfy' || colunaAberta === 'enviado'"
           class="nota pequeno">
          <span class="selo selo--laranja">atenção</span>
          {{ colunaAberta === 'enviado'
             ? 'Atenção: o arquivo deste lote já foi marcado como enviado. '
               + 'Remover aqui não desfaz o envio — o acerto é no Procfy.'
             : 'Atenção: o arquivo deste lote já foi montado com este item '
               + 'dentro. Depois de remover, monte o arquivo de novo.' }}
        </p>''',
      "2. o dialogo diz o que muda na 4 e na 5")

saida = t.replace("\n", "\r\n") if CRLF else t
p.write_bytes(saida.encode("utf-8"))
print("gravado:", p, len(saida), "bytes")
