"""OS 19 `botao--fraco` DA ABA 2 — a classe que NÃO EXISTE (bloco 3, 25/11).

🚨 **A CAUSA NÃO É GOSTO.** `botao--fraco` não está no `tokens.css`, nem no
`base.css`, nem no `componentes.css`, nem no `<style scoped>` da tela, nem no
CSS publicado — medido em 25/11. Os 19 renderizam como `.botao` base, com cara
de **primário**: uma tela de 19 botões todos primários não diz o que é a ação
principal de cada bloco. E passou por 3.898 testes verdes e pelas 9
conferências de CSS, porque **o jsdom não faz layout**.

As variantes que EXISTEM em `estilo/componentes.css`: `botao--contorno`,
`botao--fantasma`, `botao--primario`, `botao--perigo`, `botao--pequeno`,
`botao--largo`, `botao--icone`, `botao--faltando`.

🚨 **A REGRA APLICADA, e é uma só:** ação que FAZ algo = `botao--contorno`;
desistir, fechar ou limpar = `botao--fantasma`; `botao` puro fica para **a**
ação principal de cada bloco, que a tela já tinha (Preparar, Salvar, Remover
confirmado, Baixar o arquivo).

🔵 `botao--mini` sai (2 usos + a regra scoped): na aba 1 há **um** tamanho.

⚠️ Ícone `bi` antes do texto nos botões de ação dos cards, com o texto
mantido — ícone sozinho exigiria `title` + `aria-label`, e rótulo que some é
regressão (`M10`).

🚨 PATCH POR SCRIPT PORQUE VALIDA ANTES DE GRAVAR (`M8`): são 19 trocas com
âncoras parecidas entre si. Cada uma tem de aparecer **exatamente uma vez** —
senão nada é gravado e o script diz qual falhou.
"""
import pathlib
import shutil
import sys
from datetime import datetime

ALVO = pathlib.Path("/home/claude/movizap_painel/frontend/src/telas/"
                    "PainelServicoDosTecnicos.vue")

FRACO = 'class="botao botao--fraco" type="button"'
CONTORNO = 'class="botao botao--contorno" type="button"'
FANTASMA = 'class="botao botao--fantasma" type="button"'

T = [
    # ---------------------------------------------------- limpar / cancelar
    ("limpar o filtro do card",
     f'''                            {FRACO}
                            @click="limparFiltro(cardAberto)">''',
     f'''                            {FANTASMA}
                            @click="limparFiltro(cardAberto)">'''),

    ("limpar os marcados",
     f'''                            {FRACO}
                            @click="limparMarcados(cardAberto)">''',
     f'''                            {FANTASMA}
                            @click="limparMarcados(cardAberto)">'''),

    # ------------------------------------------------- ações do card aberto
    ("marcar todos do card",
     f'''                    <button {FRACO}
                            @click="marcarTodosDoCard(cardAberto)">
                      Marcar todos''',
     f'''                    <button {CONTORNO}
                            @click="marcarTodosDoCard(cardAberto)">
                      <i class="bi bi-check2-all" aria-hidden="true"></i>
                      Marcar todos'''),

    ("comprovante do item",
     '''                                class="botao botao--fraco botao--mini"
                                type="button" @click="abrirComprovante(a)">
                          {{ a.comprovante_arquivo || a.comprovante_dispensa''',
     '''                                class="botao botao--contorno"
                                type="button" @click="abrirComprovante(a)">
                          <i class="bi bi-paperclip" aria-hidden="true"></i>
                          {{ a.comprovante_arquivo || a.comprovante_dispensa'''),

    ("remover o item",
     '''                                class="botao botao--fraco botao--mini"
                                type="button" @click="pedirDevolucao(a)">
                          Remover''',
     '''                                class="botao botao--contorno"
                                type="button" @click="pedirDevolucao(a)">
                          <i class="bi bi-x-circle" aria-hidden="true"></i>
                          Remover'''),

    ("atualizar o card",
     f'''                    <button {FRACO}
                            @click="revalidar(cardAberto)">Atualizar</button>''',
     f'''                    <button {CONTORNO}
                            @click="revalidar(cardAberto)">
                      <i class="bi bi-arrow-clockwise" aria-hidden="true"></i>
                      Atualizar
                    </button>'''),

    ("ler o DataScope",
     f'''                      <button {FRACO}
                              @click="lerDataScope(cardAberto)">
                        Ler DataScope''',
     f'''                      <button {CONTORNO}
                              @click="lerDataScope(cardAberto)">
                        <i class="bi bi-clipboard-data" aria-hidden="true"></i>
                        Ler DataScope'''),

    ("ver prévia na Validação",
     f'''                      <button {FRACO}
                              @click="verPrevia(cardAberto)">
                        Ver prévia''',
     f'''                      <button {CONTORNO}
                              @click="verPrevia(cardAberto)">
                        <i class="bi bi-eye" aria-hidden="true"></i>
                        Ver prévia'''),

    ("excluir o card",
     f'''                            {FRACO}
                            @click="pedirExclusaoDoCard(cardAberto)">
                      Excluir o card''',
     f'''                            {CONTORNO}
                            @click="pedirExclusaoDoCard(cardAberto)">
                      <i class="bi bi-trash" aria-hidden="true"></i>
                      Excluir o card'''),

    ("ver prévia no Procfy",
     f'''                      <button {FRACO}
                              @click="verPrevia(cardAberto)">Ver prévia</button>''',
     f'''                      <button {CONTORNO}
                              @click="verPrevia(cardAberto)">
                        <i class="bi bi-eye" aria-hidden="true"></i>
                        Ver prévia
                      </button>'''),

    ("marcar como enviado",
     f'''                      <button {FRACO}
                              @click="enviar(cardAberto)">Marcar como enviado</button>''',
     f'''                      <button {CONTORNO}
                              @click="enviar(cardAberto)">
                        <i class="bi bi-send-check" aria-hidden="true"></i>
                        Marcar como enviado
                      </button>'''),

    # ------------------------------------------- a conferência, uma a uma
    ("dar ciente da linha",
     f'''            <button v-if="!l.ciente_em" {FRACO}
                    @click="ciente(l)">Ciente</button>''',
     f'''            <button v-if="!l.ciente_em" {CONTORNO}
                    @click="ciente(l)">
              <i class="bi bi-check2" aria-hidden="true"></i>
              Ciente
            </button>'''),

    ("remover a linha da conferência",
     f'''            <button {FRACO}
                    @click="pedirDevolucao(l)">Remover</button>''',
     f'''            <button {CONTORNO}
                    @click="pedirDevolucao(l)">
              <i class="bi bi-x-circle" aria-hidden="true"></i>
              Remover
            </button>'''),

    # --------------------------------- fechar / cancelar dos seis diálogos
    ("fechar a conferência",
     f'''          <button {FRACO}
                  @click="conferindo = null">Fechar</button>''',
     f'''          <button {FANTASMA}
                  @click="conferindo = null">Fechar</button>'''),

    ("cancelar a devolução do item",
     f'''          <button {FRACO}
                  @click="devolvendo = null">Cancelar</button>''',
     f'''          <button {FANTASMA}
                  @click="devolvendo = null">Cancelar</button>'''),

    ("cancelar a exclusão do card",
     f'''          <button {FRACO}
                  @click="devolvendoLote = null">Cancelar</button>''',
     f'''          <button {FANTASMA}
                  @click="devolvendoLote = null">Cancelar</button>'''),

    ("cancelar o comprovante",
     f'''          <button {FRACO}
                  @click="comprovando = null">Cancelar</button>''',
     f'''          <button {FANTASMA}
                  @click="comprovando = null">Cancelar</button>'''),

    ("fechar a prévia",
     f'''          <button {FRACO}
                  @click="previa = null">Fechar</button>''',
     f'''          <button {FANTASMA}
                  @click="previa = null">Fechar</button>'''),

    ("fechar a ficha da OS",
     f'''          <button {FRACO}
                  @click="osAberta = null">Fechar</button>''',
     f'''          <button {FANTASMA}
                  @click="osAberta = null">Fechar</button>'''),

    # ------------------------------------------------- a regra da `--mini`
    ("a regra scoped da botao--mini",
     '''.botao--mini { font-size: var(--txt-xs); padding: 1px var(--e-2); }
''',
     ''),
]


def main() -> int:
    texto = ALVO.read_text(encoding="utf-8")
    falhou = False
    for rotulo, de, _para in T:
        vezes = texto.count(de)
        if vezes != 1:
            print(f"ABORTADO em '{rotulo}': a ancora aparece {vezes} vezes "
                  f"(tem de ser 1).", file=sys.stderr)
            falhou = True
    if falhou:
        print("NADA FOI GRAVADO.", file=sys.stderr)
        return 1

    novo = texto
    for _rotulo, de, para in T:
        novo = novo.replace(de, para, 1)

    sobraram = novo.count("botao--fraco") + novo.count("botao--mini")
    if sobraram:
        print(f"ABORTADO: sobraram {sobraram} usos de botao--fraco/--mini.",
              file=sys.stderr)
        return 1

    marca = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    shutil.copy2(ALVO, ALVO.with_suffix(ALVO.suffix + f".bak_{marca}_19_botoes"))
    ALVO.write_text(novo, encoding="utf-8")
    print(f"{len(T)} trocas gravadas; 0 uso de botao--fraco e de botao--mini")
    print(f"contorno: {novo.count('botao--contorno')}  "
          f"fantasma: {novo.count('botao--fantasma')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
