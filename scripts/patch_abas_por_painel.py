# -*- coding: utf-8 -*-
"""A tira de abas passa a sair do PAINEL, e nao de lista em codigo (06/11).

🚨 DEFEITO MEU, achado por ele: *"os itens do pos venda estao aparecendo dentro
do financeiro e contratual. qual a dificuldade em nate-los separados?"*.

A `PainelAba.vue` declarava `AS_ABAS = [PNL_1.2, PNL_1.3]` em codigo e filtrava
so por PERMISSAO. Reusei a tela nos dois paineis novos e a tira foi junto: quem
e owner tem as duas, entao a tira do Pos-venda aparecia no Financeiro e no
Contratual.

🔵 E ele fechou o desenho na mensagem seguinte: *"o financeiro tera suas
proprias abas, mas por agora so 1, o mesmo para o contratual, so o pos venda ja
temos as duas pipelines em abas"*. Entao a lista tem de sair do PAINEL -- quando
o Financeiro ganhar a segunda aba, ela aparece sozinha.

Idempotente, com guard pela linha NOVA.
"""
import pathlib
import sys

RAIZ = pathlib.Path("/home/claude/movizap_painel")

# ------------------------------------------------------- movizap/paineis.py
P = RAIZ / "movizap/paineis.py"
t = P.read_text(encoding="utf-8")
if "'abas': [" in t:
    print("  paineis.py: ja aplicado")
else:
    VELHO = """    return {
        'painel': aba['painel'],
        'aba': aba['codigo_tela'],
        'titulo': aba['titulo'],"""
    NOVO = """    return {
        'painel': aba['painel'],
        'aba': aba['codigo_tela'],
        'titulo': aba['titulo'],
        # 🚨 06/11: AS ABAS IRMAS, as deste painel e so dele. Achado por ele:
        # *"os itens do pos venda estao aparecendo dentro do financeiro e
        # contratual"*. A tela declarava a lista em CODIGO e filtrava so por
        # permissao -- reusada nos paineis novos, levava a tira do Pos-venda
        # para dentro deles.
        #
        # 🔵 Decisao dele no mesmo minuto: *"o financeiro tera suas proprias
        # abas, mas por agora so 1, o mesmo para o contratual, so o pos venda
        # ja temos as duas pipelines em abas"*. Por isso sai do BANCO: no dia
        # em que o Financeiro ganhar a segunda aba, ela aparece sozinha.
        #
        # ⚠️ O `titulo` daqui e o da ABA (`painel_aba.titulo`), que e onde
        # moram "Treinamentos" e "Pos-venda" -- no registro as duas telas se
        # chamam as duas "Pos-venda". A ROTA nao vem aqui: o frontend a resolve
        # pelo `sessao.telas`, e assim aba que a pessoa nao alcanca cai fora
        # sozinha, sem segunda regua de permissao.
        'abas': [{'codigo_tela': a['codigo_tela'], 'titulo': a['titulo']}
                 for a in pipeline.abas(aba['painel'])],"""
    if t.count(VELHO) != 1:
        sys.exit(f"paineis.py: ancora apareceu {t.count(VELHO)}x")
    P.write_text(t.replace(VELHO, NOVO), encoding="utf-8")
    print("  paineis.py: `abas` no quadro")

# ------------------------------------------- frontend/src/telas/PainelAba.vue
P = RAIZ / "frontend/src/telas/PainelAba.vue"
t = P.read_text(encoding="utf-8")
if "quadro.value?.abas" in t:
    print("  PainelAba.vue: ja aplicado")
else:
    VELHO = """/* 🔵 AS ABAS DENTRO DA TELA -- correcao dele em 05/11: *"so aba principal
   no menu. As demais sao dentro dela ja"*.

   ⚠️ A LISTA SAI DA PERMISSAO, e nao de uma constante solta: quem nao tem
   a `PNL_1.3` nao ve a segunda aba. A fonte e o `codigosPermitidos` da
   sessao -- a mesma que a guarda de rota usa, porque duas fontes
   divergiriam no dia em que ele conceder uma aba a alguem.

   🚨 E ELAS SAO DECLARADAS AQUI, e nao lidas do servidor, de proposito: o
   nome e a ORDEM das abas sao dele (*"Aba 1: Treinamentos (...) Aba 2:
   Pos-venda"*), e o `telas.py` ja e a fonte de quem pode abrir cada uma. */
const AS_ABAS = [
  { codigo: 'PNL_1.2', titulo: 'Treinamentos', rota: '/paineis/pos-venda' },
  { codigo: 'PNL_1.3', titulo: 'Pós-venda',
    rota: '/paineis/pos-venda/realizado' },
]
const abasVisiveis = computed(
  () => AS_ABAS.filter((a) => codigosPermitidos.value.has(a.codigo)),
)"""
    NOVO = """/* 🔵 AS ABAS DENTRO DA TELA -- correcao dele em 05/11: *"so aba principal
   no menu. As demais sao dentro dela ja"*.

   🚨 06/11, A LISTA PASSOU A SAIR DO PAINEL, e e conserto de um defeito meu
   que ELE achou: *"os itens do pos venda estao aparecendo dentro do financeiro
   e contratual. qual a dificuldade em mante-los separados?"*. Antes era uma
   constante `AS_ABAS = [PNL_1.2, PNL_1.3]` escrita aqui, filtrada so por
   PERMISSAO -- e eu reusei esta tela nos dois paineis novos. Quem e owner tem
   as duas abas do Pos-venda, entao a tira delas aparecia dentro do Financeiro
   e do Contratual. ⚠️ Nao era permissao errada: era a lista nao ter dono.

   🔵 E ele fechou o desenho no mesmo minuto: *"o financeiro tera suas
   proprias abas, mas por agora so 1, o mesmo para o contratual, so o pos
   venda ja temos as duas pipelines em abas"*. Com a lista vindo do painel, a
   segunda aba do Financeiro vai aparecer SOZINHA no dia em que ele a criar --
   nenhuma linha daqui muda.

   ⚠️ DUAS FONTES, cada uma com o que e dela: o SERVIDOR diz quais abas sao
   deste painel e como se chamam (`painel_aba`, que e onde moram
   "Treinamentos" e "Pos-venda" -- no registro as duas telas se chamam as duas
   "Pos-venda"); o `sessao.telas` da a ROTA e, de graca, a permissao: aba que
   a pessoa nao alcanca nao esta nessa lista e cai fora sem segunda regua. */
const abasVisiveis = computed(() => {
  const doPainel = quadro.value?.abas || []
  const porCodigo = new Map(sessao.telas.map((t) => [t.codigo, t]))
  return doPainel
    .filter((a) => porCodigo.has(a.codigo_tela))
    .map((a) => ({ codigo: a.codigo_tela, titulo: a.titulo,
                   rota: porCodigo.get(a.codigo_tela).rota }))
})"""
    if t.count(VELHO) != 1:
        sys.exit(f"PainelAba.vue: ancora da lista apareceu {t.count(VELHO)}x")
    t = t.replace(VELHO, NOVO)

    # O import: `codigosPermitidos` ficou sem uso; entra `sessao`.
    VELHO_IMP = "import { codigosPermitidos } from '../estado/sessao.js'"
    NOVO_IMP = "import { sessao } from '../estado/sessao.js'"
    if t.count(VELHO_IMP) != 1:
        sys.exit("PainelAba.vue: import nao bateu")
    t = t.replace(VELHO_IMP, NOVO_IMP)

    # O rotulo do `nav` era fixo no Pos-venda.
    VELHO_NAV = '''    <nav v-if="abasVisiveis.length > 1" class="abas"
         aria-label="Abas do Pós-venda">'''
    NOVO_NAV = '''    <!-- ⚠️ O rotulo do `nav` sai do TITULO DO PAINEL, e nao fixo no
         Pos-venda: com a tela servindo cinco abas de tres paineis, "Abas do
         Pos-venda" seria a tela mentindo para quem usa leitor de tela. -->
    <nav v-if="abasVisiveis.length > 1" class="abas"
         :aria-label="`Abas de ${quadro?.titulo || 'painel'}`">'''
    if t.count(VELHO_NAV) != 1:
        sys.exit("PainelAba.vue: nav nao bateu")
    t = t.replace(VELHO_NAV, NOVO_NAV)

    P.write_text(t, encoding="utf-8")
    print("  PainelAba.vue: abas vindas do painel, import e rotulo")

print("\nconferindo com grep -i:")
t = (RAIZ / "frontend/src/telas/PainelAba.vue").read_text(encoding="utf-8")
print("  AS_ABAS restante      :", t.count("AS_ABAS"))
print("  codigosPermitidos     :", t.count("codigosPermitidos"))
print("  quadro.value?.abas    :", t.count("quadro.value?.abas"))
t = (RAIZ / "movizap/paineis.py").read_text(encoding="utf-8")
print("  'abas': [ em paineis  :", t.count("'abas': ["))
