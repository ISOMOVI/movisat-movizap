# -*- coding: utf-8 -*-
"""Patch 29/10 (parte 9): os tres textos que ele mandou tirar do painel.

🔵 *"bem como os comentarios [...] tbm devem sumir dali"*:
  1. *"Mover o card vai escrever a situacao na OS do Harmonit, e essa rota
     ainda nao existe. Para ela nascer falta voce confirmar qual problema cada
     formulario gera."*
  2. a lista dos formularios com a contagem de campos (Suporte 11 campos,
     Demonstracao 15, ...);
  3. *"Nenhuma solicitacao da Operacao chegou ainda -- as colunas estao
     desenhadas e vazias, e e o estado certo. Os quatro formularios estao no ar
     em forms.movisat.com.br."*

⚠️ O QUE SOME E O TEXTO, NAO O COMPORTAMENTO: mover o card continua nao
existindo, e `pode_mover` segue `false`. O backend para de MANDAR a frase; a
tela para de desenhar o aviso, a lista de formularios e o cartao de vazio.
Quando mover existir, quem muda e o `pode_mover`.
"""
import pathlib
import sys

MOVI = pathlib.Path("/home/claude/movizap_painel")


def trocar(caminho: pathlib.Path, velho: str, novo: str, rotulo: str) -> None:
    texto = caminho.read_text(encoding="utf-8")
    if novo and novo in texto:
        print(f"  = {rotulo}: ja aplicado")
        return
    if texto.count(velho) != 1:
        sys.exit(f"  ! {rotulo}: achei {texto.count(velho)} ocorrencias, "
                 f"esperava 1 -- PAREI sem gravar nada")
    caminho.write_text(texto.replace(velho, novo), encoding="utf-8")
    print(f"  + {rotulo}")


# ---------------------------------------------------------------------------
# 1. O backend para de mandar a frase e a lista de formularios
# ---------------------------------------------------------------------------
p = MOVI / "movizap" / "paineis.py"
print(p.name)

trocar(p, '''    formularios = banco.varios(
        """SELECT codigo, slug, titulo, ativo,
                  (SELECT count(*) FROM formulario_campo c
                    WHERE c.formulario_id = f.id) AS campos
             FROM formulario f
            WHERE f.painel = %s
            ORDER BY f.ordem""", (painel,))

''',
       '''''',
       "paineis.py: sai a consulta dos formularios")

trocar(p, '''        "formularios": formularios,
        "colunas": colunas,''',
       '''        "colunas": colunas,''',
       "paineis.py: sai `formularios` da resposta")

trocar(p, '''        "total": len(linhas),
        # 🚨 A TELA DIZ O QUE AINDA NÃO FAZ, em vez de oferecer o gesto que não
        # grava. É o precedente do `ModalAgendar`, que explica em vez de sumir.
        "pode_mover": False,
        "porque_nao_move": (
            "Mover o card vai escrever a situação na OS do Harmonit, e essa "
            "rota ainda não existe. Para ela nascer falta você confirmar qual "
            "problema cada formulário gera."),
    }''',
       '''        "total": len(linhas),
        # ⚠️ MOVER AINDA NÃO EXISTE, e `pode_mover` continua sendo a verdade
        # disso -- o que saiu em 29/10, a pedido dele, foi a FRASE que a tela
        # desenhava ao lado das colunas (*"os comentários tbm devem sumir
        # dali"*). O gesto não passou a existir por isso: quem o ligar muda
        # este campo, e aí a tela ganha o `draggable`.
        "pode_mover": False,
    }''',
       "paineis.py: sai a frase do porque_nao_move")

print()
print("ok -- falta a tela")


# ---------------------------------------------------------------------------
# 2. A tela para de desenhar os tres
# ---------------------------------------------------------------------------
t = MOVI / "frontend" / "src" / "telas" / "PainelOperacao.vue"
print(t.name)

trocar(t, '''      <p v-if="!quadro.pode_mover" class="aviso aviso--info">
        <i class="bi bi-info-circle aviso__icone" aria-hidden="true"></i>
        <span>{{ quadro.porque_nao_move }}</span>
      </p>

      <p class="apagado pequeno formularios">
        <span v-for="f in quadro.formularios" :key="f.codigo">
          {{ f.titulo }} <small>· {{ f.campos }} campos{{ f.ativo ? '' : ' · fora do ar' }}</small>
        </span>
      </p>

      <p v-if="vazio" class="aviso aviso--atencao">
        <i class="bi bi-inbox aviso__icone" aria-hidden="true"></i>
        <span>
          Nenhuma solicitação da Operação chegou ainda — as colunas estão
          desenhadas e vazias, e é o estado certo. Os quatro formulários estão
          no ar em <strong>forms.movisat.com.br</strong>.
        </span>
      </p>

''',
       '''      <!-- 🔵 29/10, ele: *"os comentários tbm devem sumir dali"*. Saíram os
           três textos que ficavam aqui -- o aviso de que mover não existe, a
           lista dos formulários com a contagem de campos, e o cartão de
           "nenhuma solicitação chegou ainda".
           ⚠️ O que saiu é o TEXTO: mover continua não existindo
           (`quadro.pode_mover` segue falso e não há `draggable`), e coluna
           vazia continua colapsada com o contador à vista. -->

''',
       "tela: saem os tres textos")

trocar(t, '''.formularios { display: flex; flex-wrap: wrap; gap: var(--e-3); margin: 0 0 var(--e-3); }
''', '''''', "tela: sai o estilo da lista de formularios")

print()
print("ok")
