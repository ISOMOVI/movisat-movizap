# -*- coding: utf-8 -*-
"""A UX aprovada da aba 2 — 25/11: topo, nome do técnico, quadros, rodapé.

🔵 Ele, 25/11, sobre o mockup v2: *"Todo proposto está ótimo - pode seguir"*.

O que entra:
1. **ajuda no topo** (`AjudaDaTela`), com a identidade à esquerda e os
   controles à direita — o arranjo que ele aprovou na Operação em 05/11;
2. o **nome do técnico com destaque de identificador** (acento + peso forte),
   *"o mesmo destaque que os cards do OP com o Termo"*;
3. as cinco ações soltas do card aberto viram **quadros com o que cada uma
   faz**, agrupados por *conferir* / *fechar o pagamento* / *desfazer*;
4. o **rodapé numa faixa só**: a regra à esquerda, o `Fechar` em `fantasma` à
   direita — e o `Fechar` passa a existir **dentro dos dois braços** do
   diálogo, com trava medindo isso (sem ela, um terceiro braço nasceria sem
   porta de saída).

🚨 UMA DECISÃO MINHA, DECLARADA: os **dois ordenadores e a busca** da aba 2 vão
para o bloco de controles do topo, como no mockup — e com as duas pílulas e os
dois botões isso dá **sete** itens, que quebram em duas linhas na tela estreita.
Se incomodar, volto os ordenadores para a linha de baixo: é uma âncora só.
"""
import pathlib
import shutil
import sys
from datetime import datetime

ALVO = pathlib.Path("/home/claude/movizap_painel/frontend/src/telas/"
                    "PainelServicoDosTecnicos.vue")

# ----------------------------------------------------------------- 1. import
IMPORT_DE = "import BarraDeRolagem from '../componentes/BarraDeRolagem.vue'\n"
IMPORT_PARA = ("import AjudaDaTela from '../componentes/AjudaDaTela.vue'\n"
               "import BarraDeRolagem from '../componentes/BarraDeRolagem.vue'\n")

# ------------------------------------------------------------------- 2. topo
TOPO_DE = """    <header class="painel__topo">
      <h1 class="painel__titulo">{{ tituloDoPainel }}</h1>
      <div class="painel__medidas">"""

TOPO_PARA = """    <!-- 🔵 25/11: O TOPO NO PADRÃO DA OPERAÇÃO, e é o pedido dele de 05/11
         (*"o cabeçalho esta porco, organize de forma profissional"*): a
         IDENTIDADE à esquerda (o que é a tela) e os CONTROLES à direita (o que
         se faz com ela), em dois blocos que quebram juntos no celular.
         🔵 *"faltam recursos no topo da aba1 também"* — a mesma mudança chega
         ao `PainelAba.vue`, que serve os quatro painéis de aba. -->
    <header class="painel__topo">
      <div class="painel__identidade">
        <h1 class="painel__titulo">{{ tituloDoPainel }}</h1>
        <!-- 🚨 O TEXTO NÃO SE PERDE, ELE SE RECOLHE: o balão abre no hover
             **e** no foco, então quem usa teclado também o lê. -->
        <AjudaDaTela>
          Fecha o pagamento dos técnicos: a varredura das <strong>05:10</strong>
          traz a OS com valor de serviço ou km, o card anda pelas cinco colunas
          e o arquivo do Procfy sai da Validação.
          <strong>Só aparece serviço de {{ dataCurta(desdeDoQuadro) }} em
          diante</strong>, e o que é anterior segue no banco.
        </AjudaDaTela>
      </div>
      <div class="painel__medidas">
        <label class="controles__busca">
          <span class="so-leitor">
            Procurar por cliente, número da OS, termo, orçamento ou técnico
          </span>
          <input v-model="busca" type="search"
                 placeholder="cliente, OS, termo, orçamento ou técnico" />
        </label>

        <label class="controles__ordem">
          <span class="so-leitor">Ordenar os artefatos dentro do card</span>
          <select v-model="ordem">
            <option v-for="(rot, chave) in ROTULO_ORDEM" :key="chave"
                    :value="chave">{{ rot }}</option>
          </select>
        </label>

        <label class="controles__ordem">
          <span class="so-leitor">Ordenar os cards</span>
          <select v-model="ordemDosCards">
            <option v-for="(rot, chave) in ROTULO_ORDEM_CARDS" :key="chave"
                    :value="chave">{{ rot }}</option>
          </select>
        </label>
"""

# ------------------------------- 3. a linha de controles perde o que subiu
CONTROLES_DE = """    <div class="controles">
      <label class="controles__busca">
        <span class="so-leitor">
          Procurar por cliente, número da OS, termo, orçamento ou técnico
        </span>
        <input v-model="busca" type="search"
               placeholder="cliente, OS, termo, orçamento ou técnico" />
      </label>

      <label class="controles__ordem">
        <span class="so-leitor">Ordenar os artefatos dentro do card</span>
        <select v-model="ordem">
          <option v-for="(rot, chave) in ROTULO_ORDEM" :key="chave"
                  :value="chave">{{ rot }}</option>
        </select>
      </label>

      <label class="controles__ordem">
        <span class="so-leitor">Ordenar os cards</span>
        <select v-model="ordemDosCards">
          <option v-for="(rot, chave) in ROTULO_ORDEM_CARDS" :key="chave"
                  :value="chave">{{ rot }}</option>
        </select>
      </label>

      <!-- 🔵 D6/D7, 23/11:"""
CONTROLES_PARA = """    <!-- ⚠️ A busca e os dois ordenadores subiram para o topo (25/11). Esta
         linha ficou com o que é ESTADO do quadro, não controle: o corte de
         data e a hora da varredura. -->
    <div class="controles">
      <!-- 🔵 D6/D7, 23/11:"""

# ------------------------------------------------- 4. o nome do técnico
NOME_1_DE = """                    <span class="card__cliente"
                          :title="card.tecnico_nome || ''">"""
NOME_1_PARA = """                    <span class="card__tecnico"
                          :title="card.tecnico_nome || ''">"""

NOME_2_DE = """                    <span class="card__cliente" :title="card.tecnico_nome || ''">"""
NOME_2_PARA = """                    <span class="card__tecnico" :title="card.tecnico_nome || ''">"""

# ---------------------------------------- 5. o ramo 1: escolher e preparar
RAMO1_DE = """                  <div v-if="cardAberto.pode_preparar" class="card__acoes">
                    <button class="botao botao--contorno" type="button"
                            @click="marcarTodosDoCard(cardAberto)">
                      <i class="bi bi-check2-all" aria-hidden="true"></i>
                      Marcar todos
                    </button>
                    <button v-if="marcadosDo(cardAberto).length"
                            class="botao botao--fantasma" type="button"
                            @click="limparMarcados(cardAberto)">
                      Limpar
                    </button>
                    <button class="botao" type="button"
                            :disabled="!marcadosDo(cardAberto).length"
                            @click="preparar(cardAberto)">
                      Preparar os marcados ({{ marcadosDo(cardAberto).length }})
                    </button>
                  </div>
        </template>"""

RAMO1_PARA = """                  <!-- 🔵 25/11: OS QUADROS DE AÇÃO. Cinco botões de larguras
                       diferentes numa fileira que quebrava onde dava, e sem
                       dizer o que fazem, foi o que ele chamou de *"terrível"*.
                       Agora: grade de larguras IGUAIS, cada ação com uma linha
                       dizendo o que faz, e separadas por quadro. 🚨 O
                       agrupamento não é enfeite: "Excluir o card" e
                       "Atualizar" lado a lado, do mesmo tamanho, é como se
                       clica no errado. -->
                  <div v-if="cardAberto.pode_preparar" class="acoes">
                    <div class="acoes__grupo">
                      <p class="acoes__titulo">Escolher o que vai pagar</p>
                      <div class="acoes__grade">
                        <button class="acao" type="button"
                                @click="marcarTodosDoCard(cardAberto)">
                          <span class="acao__nome">
                            <i class="bi bi-check2-all" aria-hidden="true"></i>
                            Marcar todos
                          </span>
                          <span class="acao__nota">
                            Marca os {{ artefatosVisiveis(cardAberto).length }}
                            artefato(s) à vista — o filtro acima manda.
                          </span>
                        </button>
                        <button v-if="marcadosDo(cardAberto).length"
                                class="acao" type="button"
                                @click="limparMarcados(cardAberto)">
                          <span class="acao__nome">
                            <i class="bi bi-x-lg" aria-hidden="true"></i>
                            Limpar a marcação
                          </span>
                          <span class="acao__nota">
                            Desmarca os {{ marcadosDo(cardAberto).length }}
                            marcados. Não mexe em artefato nenhum.
                          </span>
                        </button>
                      </div>
                    </div>
                    <div class="acoes__grupo">
                      <p class="acoes__titulo">Fechar o pagamento</p>
                      <div class="acoes__grade">
                        <button class="acao acao--principal" type="button"
                                :disabled="!marcadosDo(cardAberto).length"
                                @click="preparar(cardAberto)">
                          <span class="acao__nome">
                            <i class="bi bi-box-arrow-right" aria-hidden="true"></i>
                            Preparar os marcados
                            ({{ marcadosDo(cardAberto).length }})
                          </span>
                          <span class="acao__nota">
                            Cria o card do técnico na Preparação com os
                            marcados. O que ficar sem marca permanece aqui.
                          </span>
                        </button>
                      </div>
                    </div>
                  </div>

                  <!-- 🚨 O RODAPÉ NUMA FAIXA SÓ, e o `Fechar` mora DENTRO deste
                       braço: era ele que caía numa segunda faixa abaixo das
                       ações, com peso de ação principal. ⚠️ Está nos DOIS
                       braços do diálogo de propósito, e há trava medindo isso
                       (`aba2_rodape_2511.teste.js`) — braço sem `Fechar` é
                       diálogo sem porta de saída. -->
                  <div class="card__rodape">
                    <span class="nota pequeno">
                      <i class="bi bi-info-circle" aria-hidden="true"></i>
                      Só os artefatos marcados vão para a Preparação.
                    </span>
                    <div class="modal__acoes">
                      <button class="botao botao--fantasma" type="button"
                              @click="fecharCardDoTecnico">Fechar</button>
                    </div>
                  </div>
        </template>"""

# ------------------------------------------- 6. o ramo 2: os lotes (2 a 5)
RAMO2_DE = """                  <div class="card__acoes">
                    <!-- 🔵 *"todos os cards tem botão de 'atualizar'"*. -->
                    <button class="botao botao--contorno" type="button"
                            @click="revalidar(cardAberto)">
                      <i class="bi bi-arrow-clockwise" aria-hidden="true"></i>
                      Atualizar
                    </button>

                    <button v-if="colunaAberta === 'preparacao'" class="botao"
                            type="button" @click="abrirConferencia(cardAberto)">
                      Conferir e auditar
                    </button>

                    <template v-if="colunaAberta === 'validacao'">
                      <button class="botao botao--contorno" type="button"
                              @click="lerDataScope(cardAberto)">
                        <i class="bi bi-clipboard-data" aria-hidden="true"></i>
                        Ler DataScope
                      </button>
                      <button class="botao botao--contorno" type="button"
                              @click="verPrevia(cardAberto)">
                        <i class="bi bi-eye" aria-hidden="true"></i>
                        Ver prévia
                      </button>
                      <button class="botao" type="button"
                              @click="montarArquivo(cardAberto)">
                        Montar arquivo
                      </button>
                    </template>"""

RAMO2_PARA = """                  <!-- 🔵 25/11: OS QUADROS DE AÇÃO (ver o braço da
                       Movimentação). Os grupos são três: o que só LÊ, o que
                       FECHA dinheiro e o que DESFAZ. -->
                  <div class="acoes">
                    <div class="acoes__grupo">
                      <p class="acoes__titulo">Conferir — nada se move</p>
                      <div class="acoes__grade">
                        <!-- 🔵 *"todos os cards tem botão de 'atualizar'"*. -->
                        <button class="acao" type="button"
                                @click="revalidar(cardAberto)">
                          <span class="acao__nome">
                            <i class="bi bi-arrow-clockwise" aria-hidden="true"></i>
                            Atualizar
                          </span>
                          <span class="acao__nota">
                            Roda as verificações deste card de novo, para
                            ajuste feito depois que ele nasceu. Não move nada.
                          </span>
                        </button>
                        <button v-if="colunaAberta === 'validacao'"
                                class="acao" type="button"
                                @click="lerDataScope(cardAberto)">
                          <span class="acao__nome">
                            <i class="bi bi-clipboard-data" aria-hidden="true"></i>
                            Ler DataScope
                          </span>
                          <span class="acao__nota">
                            Busca o formulário do técnico e marca o que ele
                            respondeu. Só leitura.
                          </span>
                        </button>
                        <button v-if="colunaAberta === 'validacao'
                                      || colunaAberta === 'procfy'"
                                class="acao" type="button"
                                @click="verPrevia(cardAberto)">
                          <span class="acao__nome">
                            <i class="bi bi-eye" aria-hidden="true"></i>
                            Ver prévia
                          </span>
                          <span class="acao__nota">
                            Mostra o que vai para o Procfy e quais colunas
                            saem em branco, antes de baixar o arquivo.
                          </span>
                        </button>
                      </div>
                    </div>

                    <div v-if="colunaAberta !== 'movimentacao'" class="acoes__grupo">
                      <p class="acoes__titulo">Fechar o pagamento</p>
                      <div class="acoes__grade">
                        <button v-if="colunaAberta === 'preparacao'"
                                class="acao acao--principal" type="button"
                                @click="abrirConferencia(cardAberto)">
                          <span class="acao__nome">
                            <i class="bi bi-list-check" aria-hidden="true"></i>
                            Conferir e auditar
                          </span>
                          <span class="acao__nota">
                            Abre a conferência um a um e leva para a Validação
                            só os cientes que não foram negados.
                          </span>
                        </button>
                        <button v-if="colunaAberta === 'validacao'"
                                class="acao acao--principal" type="button"
                                @click="montarArquivo(cardAberto)">
                          <span class="acao__nome">
                            <i class="bi bi-file-earmark-spreadsheet"
                               aria-hidden="true"></i>
                            Montar arquivo
                          </span>
                          <span class="acao__nota">
                            Fecha o lote e gera a planilha do Procfy. Artefato
                            sem comprovante nem dispensa fica para trás.
                          </span>
                        </button>
                        <button v-if="colunaAberta === 'procfy'"
                                class="acao acao--principal" type="button"
                                @click="baixar(cardAberto)">
                          <span class="acao__nome">
                            <i class="bi bi-download" aria-hidden="true"></i>
                            Baixar o arquivo
                          </span>
                          <span class="acao__nota">
                            Salva a planilha para importar no Procfy. Pode
                            baixar quantas vezes precisar.
                          </span>
                        </button>
                        <button v-if="colunaAberta === 'procfy'"
                                class="acao" type="button"
                                @click="enviar(cardAberto)">
                          <span class="acao__nome">
                            <i class="bi bi-send-check" aria-hidden="true"></i>
                            Marcar como enviado
                          </span>
                          <span class="acao__nota">
                            Move o card para a última coluna. Diz que o
                            pagamento saiu — não envia nada por si.
                          </span>
                        </button>
                        <button v-if="colunaAberta === 'enviado'"
                                class="acao" type="button"
                                @click="reabrirLote(cardAberto)">
                          <span class="acao__nome">
                            <i class="bi bi-arrow-counterclockwise"
                               aria-hidden="true"></i>
                            Reabrir para gerar de novo
                          </span>
                          <span class="acao__nota">
                            Devolve o lote à Validação, onde o "Montar
                            arquivo" serve outra vez.
                          </span>
                        </button>
                      </div>
                    </div>"""

# ------------------- 7. o excluir vira o grupo "desfazer", e o procfy sai
EXCLUIR_DE = """                    <!-- 🔵 Tarefa 2.5: reabrir, só na coluna 5. Depois
                         disso o lote reaparece na Validação e o "Montar
                         arquivo" de lá serve de novo -- não há botão de
                         gerar aqui, para não existir um segundo caminho de
                         montar o arquivo. -->
                    <button v-if="colunaAberta === 'enviado'"
                            class="botao" type="button"
                            @click="reabrirLote(cardAberto)">
                      Reabrir para gerar de novo
                    </button>

                    <!-- 🔵 Tarefa 2.4: excluir o card inteiro. Vale de
                         qualquer coluna de lote (2 a 5) -- na coluna 1 o card
                         é o técnico, permanente, e não há lote para excluir.
                         🚨 Fica junto dos outros gestos do card, e não entre
                         os itens: o alvo aqui é o CARD. -->
                    <button v-if="colunaAberta !== 'movimentacao'"
                            class="botao botao--contorno" type="button"
                            @click="pedirExclusaoDoCard(cardAberto)">
                      <i class="bi bi-trash" aria-hidden="true"></i>
                      Excluir o card
                    </button>

                    <template v-if="colunaAberta === 'procfy'">
                      <button class="botao botao--contorno" type="button"
                              @click="verPrevia(cardAberto)">
                        <i class="bi bi-eye" aria-hidden="true"></i>
                        Ver prévia
                      </button>
                      <button class="botao" type="button" @click="baixar(cardAberto)">
                        Baixar o arquivo
                      </button>
                      <button class="botao botao--contorno" type="button"
                              @click="enviar(cardAberto)">
                        <i class="bi bi-send-check" aria-hidden="true"></i>
                        Marcar como enviado
                      </button>
                    </template>
                  </div>
        </template>

        <div class="modal__acoes">
          <button class="botao" type="button" @click="fecharCardDoTecnico">
            Fechar
          </button>
        </div>"""

EXCLUIR_PARA = """                    <!-- 🔵 Tarefa 2.4: excluir o card inteiro. Vale de
                         qualquer coluna de lote (2 a 5) -- na coluna 1 o card
                         é o técnico, permanente, e não há lote para excluir.
                         🚨 Fica em QUADRO PRÓPRIO, longe do "Atualizar": era
                         vizinho dele, do mesmo tamanho e da mesma cor. -->
                    <div v-if="colunaAberta !== 'movimentacao'" class="acoes__grupo">
                      <p class="acoes__titulo">Desfazer</p>
                      <div class="acoes__grade">
                        <button class="acao acao--perigo" type="button"
                                @click="pedirExclusaoDoCard(cardAberto)">
                          <span class="acao__nome">
                            <i class="bi bi-trash" aria-hidden="true"></i>
                            Excluir o card
                          </span>
                          <span class="acao__nota">
                            Devolve todos os artefatos à Movimentação, com uma
                            justificativa única. Pede confirmação.
                          </span>
                        </button>
                      </div>
                    </div>
                  </div>

                  <!-- 🚨 O MESMO RODAPÉ DO OUTRO BRAÇO. Ver o comentário de lá:
                       o `Fechar` mora dentro dos dois, e há trava medindo. -->
                  <div class="card__rodape">
                    <span class="nota pequeno">
                      <i class="bi bi-info-circle" aria-hidden="true"></i>
                      O arquivo do Procfy só sai com comprovante ou dispensa em
                      cada artefato.
                    </span>
                    <div class="modal__acoes">
                      <button class="botao botao--fantasma" type="button"
                              @click="fecharCardDoTecnico">Fechar</button>
                    </div>
                  </div>
        </template>"""

# ------------------------------------------- 8. o modal do comprovante
COMPROVANTE_DE = """        <div class="comprovante__anexo">
          <input ref="inputDoAnexo" class="comprovante__arquivo" type="file"
                 @change="subirComprovante" />
          <button class="botao botao--contorno" type="button"
                  :disabled="subindoAnexo"
                  @click="inputDoAnexo?.click()">
            <i class="bi bi-paperclip" aria-hidden="true"></i>
            {{ subindoAnexo ? 'Enviando…'
               : comprovando.anexo ? 'Trocar o arquivo' : 'Anexar comprovante' }}
          </button>

          <!-- Anexo já enviado: link de download, com nome e tamanho. -->
          <p v-if="comprovando.anexo" class="nota pequeno">
            <a href="#" @click.prevent="baixarComprovante(comprovando.anexo.id)">
              <i class="bi bi-file-earmark-arrow-down" aria-hidden="true"></i>
              {{ comprovando.anexo.nome_original }}
            </a>
            &middot; {{ tamanhoCurto(comprovando.anexo.bytes) }}
          </p>
        </div>"""

COMPROVANTE_PARA = """        <!-- 🔵 25/11: o anexo vira QUADRO, no mesmo padrão das ações do
             card, e os passos ficam numerados — o campo do valor continua
             nascendo só depois do documento. -->
        <div class="acoes">
          <div class="acoes__grupo">
            <p class="acoes__titulo">1. O documento</p>
            <div class="acoes__grade">
              <input ref="inputDoAnexo" class="comprovante__arquivo" type="file"
                     @change="subirComprovante" />
              <button class="acao" type="button"
                      :class="{ 'acao--principal': !comprovando.anexo }"
                      :disabled="subindoAnexo"
                      @click="inputDoAnexo?.click()">
                <span class="acao__nome">
                  <i class="bi bi-paperclip" aria-hidden="true"></i>
                  {{ subindoAnexo ? 'Enviando…'
                     : comprovando.anexo ? 'Trocar o arquivo'
                     : 'Anexar comprovante' }}
                </span>
                <span class="acao__nota">
                  <template v-if="comprovando.anexo">
                    <strong>{{ comprovando.anexo.nome_original }}</strong>
                    &middot; {{ tamanhoCurto(comprovando.anexo.bytes) }}
                  </template>
                  <template v-else>
                    PDF, imagem, planilha ou documento, até 10 MB.
                  </template>
                </span>
              </button>
            </div>
            <!-- ⚠️ O link de baixar fica FORA do quadro: dentro dele, clicar
                 no link abriria também o seletor de arquivo do botão. -->
            <p v-if="comprovando.anexo" class="nota pequeno">
              <a href="#" @click.prevent="baixarComprovante(comprovando.anexo.id)">
                <i class="bi bi-file-earmark-arrow-down" aria-hidden="true"></i>
                baixar {{ comprovando.anexo.nome_original }}
              </a>
            </p>
          </div>
        </div>"""

ROTULOS_DE = """        <label class="campo__rotulo">
          Comprovante (link ou nome do arquivo)
          <input v-model="comprovando.arquivo" class="campo" maxlength="400"
                 placeholder="ex.: recibo_franck_1811.pdf" />
        </label>"""
ROTULOS_PARA = """        <label class="campo__rotulo">
          Comprovante (link ou nome do arquivo)
          <input v-model="comprovando.arquivo" class="campo" maxlength="400"
                 placeholder="ex.: recibo_franck_1811.pdf" />
        </label>"""

VALOR_DE = """        <label v-if="comprovando.arquivo.trim()" class="campo__rotulo">
          Valor que está no documento"""
VALOR_PARA = """        <label v-if="comprovando.arquivo.trim()" class="campo__rotulo">
          2. Valor que está no documento"""

RODAPE_COMPROVANTE_DE = """        <p class="nota pequeno">
          🚨 Sem comprovante e sem justificativa não há o que registrar — e o
          artefato fica parado na Validação quando o arquivo for montado.
        </p>

        <div class="modal__acoes">
          <button class="botao botao--fantasma" type="button"
                  @click="comprovando = null">Cancelar</button>
          <button class="botao" type="button" :disabled="!comprovantePodeSalvar"
                  @click="salvarComprovante">Salvar</button>
        </div>"""

RODAPE_COMPROVANTE_PARA = """        <div class="card__rodape">
          <span class="nota pequeno">
            <i class="bi bi-info-circle" aria-hidden="true"></i>
            Sem comprovante e sem justificativa não há o que registrar — e o
            artefato fica parado na Validação quando o arquivo for montado.
          </span>
          <div class="modal__acoes">
            <button class="botao botao--fantasma" type="button"
                    @click="comprovando = null">Cancelar</button>
            <button class="botao" type="button" :disabled="!comprovantePodeSalvar"
                    @click="salvarComprovante">Salvar</button>
          </div>
        </div>"""

# --------------------------------------------------------------- 9. o CSS
CSS_DE = """.painel__titulo { margin: 0; font-size: var(--txt-lg); }"""
CSS_PARA = """.painel__titulo { margin: 0; font-size: var(--txt-lg); }
/* 🔵 25/11 — a IDENTIDADE da tela: título e ajuda juntos, como na Operação.
   ⚠️ Nome próprio nesta tela: `cabecalho__identidade` é `scoped` dentro do
   `PainelOperacao.vue`, e copiar o nome de lá daria marcação SEM ESTILO --
   a armadilha da `.pilula` de 12/11. */
.painel__identidade {
  display: flex; align-items: center; gap: var(--e-2); min-width: 0;
}

/* 🔵 25/11, dele: *"o nome do tecnico pode ter o mesmo destaque que os cards
   do OP com o Termo"*. No card do técnico o nome é o IDENTIFICADOR -- é por
   ele que se cruza com a planilha do Procfy -- então ganha o tratamento que a
   OS e o TERMO têm lá: acento e peso forte, no mesmo tamanho.
   ⚠️ Herda a quebra em 2 linhas do `card__cliente`, que é de onde ele saiu. */
.card__tecnico {
  font-weight: var(--peso-forte); font-size: var(--txt-sm);
  color: var(--acento);
  display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical;
  overflow: hidden;
}

/* 🔵 25/11 — OS QUADROS DE AÇÃO, e o rodapé numa faixa só.
   🚨 O que eles consertam: cinco botões de larguras diferentes, sem dizer o
   que fazem, com "Excluir o card" vizinho de "Atualizar". A grade dá largura
   IGUAL e quebra previsível; a nota diz o efeito antes do clique; o grupo
   separa o que lê, o que fecha dinheiro e o que desfaz. */
.acoes { display: flex; flex-direction: column; gap: var(--e-3);
         margin-top: var(--e-3); }
.acoes__grupo { margin: 0; }
.acoes__titulo {
  margin: 0 0 var(--e-2); font-size: var(--txt-xs); color: var(--texto-fraco);
  text-transform: uppercase; letter-spacing: .04em;
  font-weight: var(--peso-forte);
}
.acoes__grade {
  display: grid; gap: var(--e-2);
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
}
.acao {
  display: flex; flex-direction: column; gap: 2px; text-align: left;
  padding: var(--e-2) var(--e-3); cursor: pointer; font: inherit;
  background: var(--superficie); color: var(--texto);
  border: var(--borda-fina) solid var(--borda-forte);
  border-radius: var(--r-md);
  transition: border-color var(--tempo-rapido) var(--curva),
              box-shadow var(--tempo-rapido) var(--curva);
}
.acao:hover { border-color: var(--acento); box-shadow: var(--sombra-1); }
.acao:focus-visible { outline: none; box-shadow: var(--foco); }
/* ⚠️ Desabilitado DIZ que está desabilitado: sem isto o quadro cinza continua
   com cara de clicável e a pessoa clica três vezes achando que travou. */
.acao:disabled { opacity: .55; cursor: not-allowed; box-shadow: none;
                 border-color: var(--borda); }
.acao__nome {
  display: flex; align-items: center; gap: var(--e-2);
  font-weight: var(--peso-forte); font-size: var(--txt-sm);
}
.acao__nota {
  font-size: var(--txt-xs); color: var(--texto-fraco);
  line-height: var(--entrelinha);
}
.acao--principal { border-color: var(--acento); background: var(--acento-suave); }
.acao--perigo:hover { border-color: var(--erro); }

/* A faixa única do rodapé: a regra à esquerda, o `Fechar` à direita.
   ⚠️ `.modal__acoes` já existe nesta folha e põe os botões à direita. */
.card__rodape {
  display: flex; flex-wrap: wrap; gap: var(--e-2);
  align-items: center; justify-content: space-between;
  margin-top: var(--e-3); padding-top: var(--e-3);
  border-top: var(--borda-fina) solid var(--borda);
}"""

T = [("o import do AjudaDaTela", IMPORT_DE, IMPORT_PARA),
     ("a identidade e os controles no topo", TOPO_DE, TOPO_PARA),
     ("a linha de controles sem o que subiu", CONTROLES_DE, CONTROLES_PARA),
     ("o nome do técnico na Movimentação", NOME_1_DE, NOME_1_PARA),
     ("o nome do técnico nos lotes", NOME_2_DE, NOME_2_PARA),
     ("os quadros do braço da Movimentação", RAMO1_DE, RAMO1_PARA),
     ("os quadros do braço dos lotes", RAMO2_DE, RAMO2_PARA),
     ("o grupo Desfazer e o rodapé dos lotes", EXCLUIR_DE, EXCLUIR_PARA),
     ("o quadro do anexo do comprovante", COMPROVANTE_DE, COMPROVANTE_PARA),
     ("o passo 2 do comprovante", VALOR_DE, VALOR_PARA),
     ("o rodapé do comprovante", RODAPE_COMPROVANTE_DE, RODAPE_COMPROVANTE_PARA),
     ("o CSS novo", CSS_DE, CSS_PARA)]


def main() -> int:
    texto = ALVO.read_text(encoding="utf-8")
    ruim = False
    for rotulo, de, _para in T:
        if texto.count(de) != 1:
            print(f"ABORTADO em '{rotulo}': ancora aparece "
                  f"{texto.count(de)} vezes (tem de ser 1).", file=sys.stderr)
            ruim = True
    if ruim:
        print("NADA FOI GRAVADO.", file=sys.stderr)
        return 1

    novo = texto
    for _r, de, para in T:
        novo = novo.replace(de, para, 1)

    # 🚨 As duas asserções que o patch promete, medidas no resultado.
    # ⚠️ A conta é de USO (`class="..."`), não do nome cru: a regra de CSS fica,
    # e o comentário novo CITA a classe de onde o `card__tecnico` saiu -- contar
    # o nome solto reprovava por causa da minha própria prosa, que é a 4ª forma
    # do `feedback_validar_estrutura_nao_sintaxe`.
    if 'class="card__cliente' in novo:
        print("ABORTADO: sobrou card__cliente em uso.", file=sys.stderr)
        return 1
    if novo.count('@click="fecharCardDoTecnico"') != 2:
        print("ABORTADO: o Fechar tem de existir nos DOIS braços "
              f"(achei {novo.count('@click=\"fecharCardDoTecnico\"')}).",
              file=sys.stderr)
        return 1

    marca = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    shutil.copy2(ALVO, ALVO.with_suffix(ALVO.suffix + f".bak_{marca}_ux_aprovada"))
    ALVO.write_text(novo, encoding="utf-8")
    print(f"{len(T)} trocas gravadas; linhas "
          f"{len(texto.splitlines())} -> {len(novo.splitlines())}")
    print(f"quadros de acao: {novo.count('class=\"acao')} · "
          f"Fechar nos bracos: 2 · card__tecnico: {novo.count('card__tecnico')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
