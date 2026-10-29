<script setup>
/* ============================================================================
   Os campos de um formulário, desenhados a partir da DEFINIÇÃO.
   ----------------------------------------------------------------------------
   🚨 UMA TELA PARA OS 15. A definição (campos, rótulos, opções, regras) é dado
   no banco, e este componente é quem a desenha -- é o mesmo desenho do
   `movizap/telas.py`, onde o menu é dado e não código. Formulário novo é linha
   em tabela; nenhum `.vue` nasce por causa dele.

   🚨 ELE NÃO VALIDA NADA PARA VALER. O `required` do HTML, a máscara e o aviso
   embaixo do campo são conforto de quem preenche; quem recusa é o servidor
   (`movizap/formularios.py:validar`). O Bitrix fazia o contrário -- toda a
   validação dos 239 campos no navegador -- e em 22/10 um POST com
   `values=[]` vazio criou registro lá dentro.

   🚨 SÃO DOIS FORMATOS, E O CLÁSSICO É O PADRÃO (29/10). `formato = 'novo'`
   acende o repetidor `+`, as máscaras e a frase de erro; `'classico'` desenha
   exatamente o que desenhava em 22/10. Quem manda é o banco
   (`formulario.formato`), e hoje só o Suporte está em `novo` -- ele valida
   formulário por formulário no navegador, e tela nova que nasce em 15 lugares
   de uma vez é 15 lugares para descobrir um defeito.

   ⚠️ `page` e `layout` NÃO SÃO PERGUNTA: `page` é quebra de página do Bitrix e
   `layout` é um traço decorativo. Viram separador, nunca campo. No formato
   novo as `page` são as ETAPAS, e aí quem as desenha é a página -- aqui elas
   são filtradas pelo `somente`.

   ⚠️ `product` (2 campos, no Aditivo e na Substituição) puxava catálogo do
   Bitrix. Sem equivalente nosso, nesta etapa é texto -- e está dito aqui para
   ninguém "descobrir" isso na tela.

   🚨 NENHUMA COR, TAMANHO OU ESPAÇAMENTO NA MÃO: tudo em token
   (`src/estilo/tokens.css`), inclusive o `--txt-campo` dos campos -- 16px ali
   não é estética, abaixo disso o iOS dá zoom sozinho ao focar.
   ============================================================================ */
import { computed, reactive } from 'vue'

import { visiveis } from '../util/regras_formulario.js'
import { conferir, limpar, mascarar } from '../util/validacao_campo.js'

const props = defineProps({
  campos: { type: Array, default: () => [] },
  regras: { type: Array, default: () => [] },
  valores: { type: Object, required: true },
  // Campos que chegaram preenchidos pelo vínculo (Etapa 2) e não se editam.
  travados: { type: Array, default: () => [] },
  erro: { type: String, default: '' },
  // 'classico' (22/10) ou 'novo' (29/10). O banco é quem diz.
  formato: { type: String, default: 'classico' },
  // Só estes campos, nesta ordem -- é como a página pede UMA etapa. Vazio
  // significa "todos", que é o rolo único de sempre.
  somente: { type: Array, default: () => [] },
  // Recado por campo, vindo de quem sabe: `{nome: "Cliente: Pastelaria..."}`.
  // ⚠️ É a PÁGINA que busca o cliente, não este componente -- ele desenha a
  // definição e não conhece rota nenhuma.
  recados: { type: Object, default: () => ({}) },
  // Sugestão por campo: `{nome: [{placa, apelido, veiculo}]}`. Hoje são as
  // placas ativas do cliente (`campo.fonte === 'weso_placas'`).
  sugestoes: { type: Object, default: () => ({}) },
  // O que a conferência da WESO respondeu, por texto escrito:
  // `{"abc1234": {conferiu, ativa, apelido}}`. 🔵 Regra dele: chamado só para
  // placa ativa na WESO.
  placas: { type: Object, default: () => ({}) },
})

const emit = defineEmits(['arquivo', 'buscar', 'placa'])

const DECORATIVOS = ['page', 'layout']

const ehNovo = computed(() => props.formato === 'novo')

/* 🚨 O ERRO SÓ APARECE DEPOIS DE SAIR DO CAMPO. Campo que fica vermelho na
   terceira tecla é hostil -- e quem digita CPF ainda não errou nada no 3º
   dígito. `tocados` é por campo (e por linha, no repetidor). */
const tocados = reactive({})

const dePe = computed(() => visiveis(
  { campos: props.campos, regras: props.regras }, props.valores))

const lista = computed(() => {
  const todos = props.campos.filter(
    (c) => DECORATIVOS.includes(c.tipo) || dePe.value.has(c.nome))
  if (!props.somente.length) return todos
  /* A ordem é a do `somente`: etapa é agrupamento, e agrupar sem poder
     ordenar não serve. */
  const porNome = new Map(todos.map((c) => [c.nome, c]))
  return props.somente.map((n) => porNome.get(n)).filter(Boolean)
})

function ehTravado(campo) {
  return props.travados.includes(campo.nome)
}

/* O `type` do input por tipo do Bitrix. 🚨 `double` vira `text`, não `number`:
   o campo "CNPJ" do Bitrix é `double`, e `number` no celular esconde o teclado
   com pontuação e recusa máscara silenciosamente. */
function tipoDoInput(campo) {
  if (campo.tipo === 'email') return 'email'
  if (campo.tipo === 'phone') return 'tel'
  if (campo.tipo === 'date') return 'date'
  return 'text'
}

function longo(campo) {
  return campo.tipo === 'text' || campo.tipo === 'product'
}

/* ⚠️ Teclado numérico onde o conteúdo é número, sem usar `type=number`. */
function tecladoDe(campo) {
  if (['cpf', 'cnpj', 'cep', 'telefone'].includes(campo.validacao)) return 'numeric'
  return undefined
}

// ---------------------------------------------------------------------------
// O repetidor `+` (Bloco 1)
// ---------------------------------------------------------------------------
// 🚨 O ACHADO QUE ELE MANDOU OLHAR: 30 campos dos 239 são `multiplo` em 12 dos
// 15 formulários, o servidor sabe montar lista desde 22/10
// (`formularios.py:validar`) e NENHUMA tela desenhava o botão. Quem precisava
// informar 3 veículos informava 1 -- e o dado não era recusado, simplesmente
// nunca era coletado.
//
// 🚨 O FORMATO DO QUE É GRAVADO MUDA: um valor vira lista. Quem lê a
// solicitação tem de aceitar os dois, porque as antigas continuam com valor
// único -- e é por isso que isto entra agora, com 1 solicitação na base.
function repetido(campo) {
  return ehNovo.value && campo.multiplo && campo.tipo !== 'file'
}

function linhas(campo) {
  const atual = props.valores[campo.nome]
  if (Array.isArray(atual)) return atual.length ? atual : ['']
  return [atual ?? '']
}

function gravarLinha(campo, i, valor) {
  const atuais = [...linhas(campo)]
  atuais[i] = valor
  props.valores[campo.nome] = atuais
}

function adicionar(campo) {
  props.valores[campo.nome] = [...linhas(campo), '']
}

function remover(campo, i) {
  const atuais = linhas(campo).filter((_, j) => j !== i)
  props.valores[campo.nome] = atuais.length ? atuais : ['']
  delete tocados[`${campo.nome}#${i}`]
}

// ---------------------------------------------------------------------------
// Máscara e frase (Bloco 3)
// ---------------------------------------------------------------------------
function mascarado(campo) {
  return ehNovo.value && !!campo.validacao
}

function exibir(campo, valor) {
  return campo.validacao ? mascarar(campo.validacao, valor) : (valor ?? '')
}

/* 🚨 O QUE VAI GRAVADO É O LIMPO. O servidor confere `cnpj`/`cpf` como
   `double`, e `"123.456.789-01"` não passa por `float()` -- gravar mascarado
   faria a rota responder *"informe um número"* num CPF correto. */
function digitou(campo, valor, i = null) {
  const guardar = campo.validacao ? limpar(campo.validacao, valor) : valor
  if (i === null) props.valores[campo.nome] = guardar
  else gravarLinha(campo, i, guardar)
}

function marcarTocado(campo, i = null) {
  tocados[i === null ? campo.nome : `${campo.nome}#${i}`] = true
}

function frase(campo, valor, i = null) {
  if (!mascarado(campo)) return ''
  if (!tocados[i === null ? campo.nome : `${campo.nome}#${i}`]) return ''
  return conferir(campo.validacao, valor)
}

/* 🔵 O botão *Buscar* do CNPJ -- pedido dele, 29/10. Só no CNPJ: o CPF não tem
   para onde preencher (o nome da pessoa é uma caixa livre, e dividir nome no
   palpite erra sobrenome composto). */
function temBusca(campo) {
  return ehNovo.value && campo.validacao === 'cnpj'
}

/* ⚠️ `linhas` manda mais que o tipo: "Detalhe a ocorrência" é `string` no
   Bitrix, e ele pediu o campo mais alto *"para exprimir que pode colocar mais
   texto"*. Campo de uma linha diz o contrário a quem preenche.

   🚨 ESTE E O `fantasma` NÃO OLHAM O FORMATO, de propósito: os dois são DADO
   do campo, e dado nulo não desenha nada. Nos outros 14 formulários as duas
   colunas estão nulas, então a tela deles não muda -- e no dia em que ele
   pedir um modelo esmaecido num formulário clássico, é uma linha na carga e
   não um `if` aqui. */
function alturaDe(campo) {
  return campo.linhas || 0
}

// ---------------------------------------------------------------------------
// A frota do cliente (29/10) — `fonte = 'weso_placas'`
// ---------------------------------------------------------------------------
// 🔵 *"se já tem o cliente validado, já podemos trazer no campo de veículo
// placa os veículos que ele tem ativo na Weso"* + *"ter um botão de 'meu
// veículo não está na lista' onde ele pode digitar a placa"*.
//
// 🚨 A LISTA É A REGRA, NÃO SUGESTÃO -- e esta frase já esteve escrita ao
// contrário aqui. 🔵 Regra dele: *"só é possível abrir chamados para placas
// ativas na weso. o match é basicamente de 100% mesmo. essa é a regra"*. Eu
// havia decidido sozinho que a lista "sugere, nunca restringe", e estava
// errado.
//
// ⚠️ O BOTÃO DE DIGITAR CONTINUA, e agora com outro papel: ele serve para a
// placa que está ativa na WESO e **não aparece na lista do cliente** -- são as
// 30 placas (medido em 29/10) que a WESO tem e o cadastro do Harmonit não, e
// que por isso não têm `clienteId` para cruzar. O que se digita ali é
// CONFERIDO contra a WESO, não aceito de olhos fechados.
const digitando = reactive({})

function comFrota(campo) {
  return ehNovo.value && campo.fonte === 'weso_placas'
     && (props.sugestoes[campo.nome] || []).length > 0
}

function escolhidas(campo) {
  const atual = props.valores[campo.nome]
  if (Array.isArray(atual)) return atual
  return String(atual ?? '').trim() ? [atual] : []
}

function marcada(campo, placa) {
  return escolhidas(campo).includes(placa)
}

function marcar(campo, placa) {
  const atuais = escolhidas(campo)
  props.valores[campo.nome] = marcada(campo, placa)
    ? atuais.filter((p) => p !== placa)
    : [...atuais, placa]
}

/* As linhas que a pessoa digitou -- o que está no valor e NÃO é da frota. */
function digitadas(campo) {
  const daFrota = new Set((props.sugestoes[campo.nome] || []).map((v) => v.placa))
  return escolhidas(campo).filter((p) => !daFrota.has(p))
}

function abrirDigitacao(campo) {
  digitando[campo.nome] = true
  if (digitadas(campo).length === 0) {
    props.valores[campo.nome] = [...escolhidas(campo), '']
  }
}

/* ⚠️ Mexe SÓ nas digitadas: a conta é por posição dentro delas, para marcar e
   desmarcar placa da frota não embaralhar o que foi escrito à mão. */
function gravarDigitada(campo, i, valor) {
  const daFrota = new Set((props.sugestoes[campo.nome] || []).map((v) => v.placa))
  const atuais = escolhidas(campo)
  let vistas = -1
  props.valores[campo.nome] = atuais.map((p) => {
    if (daFrota.has(p)) return p
    vistas += 1
    return vistas === i ? valor : p
  })
}

function tirarDigitada(campo, i) {
  const daFrota = new Set((props.sugestoes[campo.nome] || []).map((v) => v.placa))
  const atuais = escolhidas(campo)
  let vistas = -1
  props.valores[campo.nome] = atuais.filter((p) => {
    if (daFrota.has(p)) return true
    vistas += 1
    return vistas !== i
  })
}

function maisUmaDigitada(campo) {
  props.valores[campo.nome] = [...escolhidas(campo), '']
}

/* 🔵 REGRA DELE: *"só é possível abrir chamados para placas ativas na weso"*.
   A tela avisa na hora para a pessoa não preencher tudo e tomar a recusa no
   fim -- mas quem recusa de verdade continua sendo o servidor, no envio.

   ⚠️ Pergunta só ao SAIR do campo, e só com algo escrito. */
function conferirPlaca(valor) {
  if (String(valor ?? '').trim()) emit('placa', valor)
}

function recadoDaPlaca(valor) {
  const r = props.placas[valor]
  if (!r) return null
  if (!r.conferiu) {
    return { erro: false, texto: 'Não consegui conferir agora — pode seguir.' }
  }
  if (r.ativa) {
    return { erro: false, texto: r.apelido ? `✓ ${r.apelido}` : '✓ ativa' }
  }
  return {
    erro: true,
    texto: 'Sem rastreador ativo neste cadastro — confira a placa ou fale '
         + 'com a Movisat.',
  }
}

function pedeConferencia(campo) {
  return ehNovo.value && campo.fonte === 'weso_placas'
}
</script>

<template>
  <div class="campos">
    <template v-for="campo in lista" :key="campo.nome">
      <!-- quebra de página e traço: separadores, não perguntas -->
      <hr v-if="campo.tipo === 'layout'" class="campos__traco" />
      <p v-else-if="campo.tipo === 'page'" class="campos__etapa">
        {{ campo.rotulo }}
      </p>

      <!-- ============ a frota do cliente, com o escape de digitar ============ -->
      <div v-else-if="comFrota(campo)" class="campo campo--multiplo">
        <span class="campo__rotulo">
          {{ campo.rotulo || campo.nome }}
          <span v-if="campo.obrigatorio" class="campo__obrigatorio" aria-hidden="true">*</span>
        </span>
        <span class="campo__ajuda">
          Marque os veículos deste chamado.
        </span>

        <label v-for="v in sugestoes[campo.nome]" :key="v.placa" class="frota">
          <input
            type="checkbox"
            :checked="marcada(campo, v.placa)"
            @change="marcar(campo, v.placa)"
          />
          <span class="frota__placa">{{ v.placa }}</span>
          <!-- ⚠️ O apelido é o que a pessoa reconhece ("SAVEIRO / BRUNO"); o
               modelo do Harmonit é o reforço. Os dois podem faltar, e aí
               sobra a placa -- que é o que importa. -->
          <span v-if="v.apelido" class="frota__apelido">{{ v.apelido }}</span>
          <span v-else-if="v.veiculo" class="frota__apelido">{{ v.veiculo }}</span>
        </label>

        <!-- 🔵 O botão que ele pediu, com as palavras dele. -->
        <button
          v-if="!digitando[campo.nome] && digitadas(campo).length === 0"
          type="button"
          class="campo__adicionar"
          @click="abrirDigitacao(campo)"
        >Meu veículo não está na lista</button>

        <template v-else>
          <div v-for="(valor, i) in digitadas(campo)" :key="`d${i}`" class="linha">
            <input
              class="campo__entrada"
              :value="valor"
              placeholder="Placa e veículo"
              :aria-label="`Outro veículo — ${i + 1}`"
              @input="gravarDigitada(campo, i, $event.target.value)"
              @blur="conferirPlaca(valor)"
            />
            <button
              type="button"
              class="linha__tirar"
              :aria-label="`Remover ${i + 1}`"
              @click="tirarDigitada(campo, i)"
            >×</button>
          </div>
          <template v-for="(valor, i) in digitadas(campo)" :key="`m${i}`">
            <span
              v-if="recadoDaPlaca(valor)"
              class="campo__recado"
              :class="{ 'campo__frase': recadoDaPlaca(valor).erro }"
            >{{ recadoDaPlaca(valor).texto }}</span>
          </template>
          <button type="button" class="campo__adicionar" @click="maisUmaDigitada(campo)">
            + Adicionar outro
          </button>
        </template>
      </div>

      <!-- ===================== o repetidor `+` ===================== -->
      <div v-else-if="repetido(campo)" class="campo campo--multiplo">
        <span class="campo__rotulo">
          {{ campo.rotulo || campo.nome }}
          <span v-if="campo.obrigatorio" class="campo__obrigatorio" aria-hidden="true">*</span>
        </span>

        <div v-for="(valor, i) in linhas(campo)" :key="i" class="linha">
          <input
            class="campo__entrada"
            :type="tipoDoInput(campo)"
            :inputmode="tecladoDe(campo)"
            :value="exibir(campo, valor)"
            :placeholder="campo.fantasma || undefined"
            :aria-label="`${campo.rotulo || campo.nome} — ${i + 1}`"
            :disabled="ehTravado(campo)"
            @input="digitou(campo, $event.target.value, i)"
            @blur="marcarTocado(campo, i); pedeConferencia(campo) && conferirPlaca(valor)"
          />
          <!-- ⚠️ Remover DESABILITADO quando só resta uma linha: tirar a
               última deixaria o campo sem onde escrever. -->
          <button
            type="button"
            class="linha__tirar"
            :disabled="linhas(campo).length < 2"
            :aria-label="`Remover ${i + 1}`"
            @click="remover(campo, i)"
          >×</button>
        </div>

        <!-- 🔵 O botão COM DESTAQUE -- decisão dele, 23/10. -->
        <button type="button" class="campo__adicionar" @click="adicionar(campo)">
          + Adicionar outro
        </button>

        <span v-if="campo.ajuda" class="campo__ajuda">{{ campo.ajuda }}</span>
        <template v-for="(valor, i) in linhas(campo)" :key="`e${i}`">
          <span v-if="frase(campo, valor, i)" class="campo__frase" role="alert">
            {{ i + 1 }}: {{ frase(campo, valor, i) }}
          </span>
          <span
            v-else-if="pedeConferencia(campo) && recadoDaPlaca(valor)"
            class="campo__recado"
            :class="{ 'campo__frase': recadoDaPlaca(valor).erro }"
          >{{ i + 1 }}: {{ recadoDaPlaca(valor).texto }}</span>
        </template>
      </div>

      <!-- ===================== o campo de sempre ===================== -->
      <label v-else class="campo">
        <span class="campo__rotulo">
          {{ campo.rotulo || campo.nome }}
          <span v-if="campo.obrigatorio" class="campo__obrigatorio" aria-hidden="true">*</span>
        </span>

        <!-- 🔵 "Escolha…" NÃO É OPÇÃO DA LISTA (pedido dele, 29/10): é o campo
             esmaecido enquanto nada foi escolhido. `disabled` impede escolher
             e `hidden` tira do menu -- quem abre a lista vê só as respostas
             de verdade. ⚠️ O `value=""` tem de continuar existindo, senão o
             navegador mostra a primeira opção real como se já estivesse
             escolhida, e a pessoa envia o que não leu. -->
        <select
          v-if="campo.tipo === 'list'"
          v-model="valores[campo.nome]"
          class="campo__entrada"
          :class="{ 'campo__entrada--esmaecido': !valores[campo.nome] }"
          :disabled="ehTravado(campo)"
          :required="campo.obrigatorio"
        >
          <option value="" disabled hidden>Escolha…</option>
          <option v-for="o in campo.opcoes" :key="o.value" :value="o.value">
            {{ o.label }}
          </option>
        </select>

        <textarea
          v-else-if="longo(campo) || alturaDe(campo)"
          v-model="valores[campo.nome]"
          class="campo__entrada campo__entrada--longa"
          :rows="alturaDe(campo) || 4"
          :disabled="ehTravado(campo)"
          :required="campo.obrigatorio"
        ></textarea>

        <!-- ⚠️ `multiple` SÓ no formato novo e SÓ onde o campo é múltiplo: a
             rota já aceita vários arquivos por campo desde 22/10 (as duas
             listas paralelas), então aqui não há nada de servidor a mudar. -->
        <input
          v-else-if="campo.tipo === 'file'"
          type="file"
          class="campo__entrada"
          :multiple="ehNovo && campo.multiplo"
          :required="campo.obrigatorio"
          @change="emit('arquivo', campo.nome, $event.target.files)"
        />

        <span v-else-if="mascarado(campo)" class="linha">
          <input
            class="campo__entrada"
            :type="tipoDoInput(campo)"
            :inputmode="tecladoDe(campo)"
            :value="exibir(campo, valores[campo.nome])"
            :placeholder="campo.fantasma || undefined"
            :disabled="ehTravado(campo)"
            :required="campo.obrigatorio"
            @input="digitou(campo, $event.target.value)"
            @blur="marcarTocado(campo)"
          />
          <!-- 🔵 Buscar na nossa base e preencher a empresa. ⚠️ Desabilitado
               enquanto o CNPJ não tem 14 dígitos: buscar meio documento só
               gastaria a cota da pessoa. -->
          <button
            v-if="temBusca(campo)"
            type="button"
            class="campo__buscar"
            :disabled="conferir('cnpj', valores[campo.nome]) !== '' || !valores[campo.nome]"
            @click.prevent="emit('buscar', campo.nome, valores[campo.nome])"
          >Buscar</button>
        </span>

        <input
          v-else
          v-model="valores[campo.nome]"
          class="campo__entrada"
          :type="tipoDoInput(campo)"
          :placeholder="campo.fantasma || undefined"
          :disabled="ehTravado(campo)"
          :required="campo.obrigatorio"
        />

        <span v-if="campo.ajuda" class="campo__ajuda">{{ campo.ajuda }}</span>
        <span v-if="recados[campo.nome]" class="campo__recado">
          {{ recados[campo.nome] }}
        </span>
        <!-- ⚠️ O campo travado DIZ POR QUÊ. Campo cinza sem explicação parece
             defeito; é o precedente do ModalAgendar, que explica em vez de
             sumir. -->
        <span v-if="ehTravado(campo)" class="campo__ajuda">
          Veio do cadastro desta conversa.
        </span>
        <span
          v-if="frase(campo, valores[campo.nome])"
          class="campo__frase"
          role="alert"
        >{{ frase(campo, valores[campo.nome]) }}</span>
      </label>
    </template>

    <p v-if="erro" class="campos__erro" role="alert">{{ erro }}</p>
  </div>
</template>

<style scoped>
/* 🚨 `.campo`, `.campo__rotulo`, `.campo__entrada` e `.campo__ajuda` JA EXISTEM
   em `src/estilo/componentes.css`, com o 16px e os 44px que o iOS cobra. Este
   bloco só acrescenta o que é deste componente -- redeclarar as quatro aqui
   criaria uma segunda verdade de estilo, que divergiria na primeira mexida. */
.campos { display: flex; flex-direction: column; gap: var(--e-4); }
.campos__traco { width: 100%; border: 0; border-top: var(--borda-fina) solid var(--borda); margin: 0; }
.campos__etapa { margin: 0; font-weight: var(--peso-forte); color: var(--texto-fraco); }

/* O `.campo` global traz `margin-bottom`; aqui o espaço é do `gap` da coluna. */
.campo { margin-bottom: 0; }
.campo__obrigatorio { color: var(--erro); }
.campo__entrada--longa { min-height: calc(var(--altura-toque) * 2); resize: vertical; }
.campo__entrada:disabled { background: var(--superficie-2); color: var(--texto-fraco); }

/* ---- o repetidor ---- */
.campo--multiplo { display: flex; flex-direction: column; gap: var(--e-2); }
/* ⚠️ No celular a linha EMPILHA, e o `×` continua alcançável com o polegar. */
.linha { display: flex; gap: var(--e-2); align-items: center; }
.linha .campo__entrada { flex: 1; min-width: 0; }
.linha__tirar {
  flex: none;
  width: var(--altura-toque);
  min-height: var(--altura-toque);
  border: var(--borda-fina) solid var(--borda);
  border-radius: var(--r-md);
  background: var(--superficie);
  color: var(--texto-fraco);
  font-size: var(--txt-lg);
  cursor: pointer;
}
.linha__tirar:disabled { opacity: .4; cursor: not-allowed; }
/* 🔵 COM DESTAQUE (decisão dele, 23/10): borda cheia, fundo e sinal. */
.campo__adicionar {
  align-self: flex-start;
  min-height: var(--altura-toque);
  padding: var(--e-2) var(--e-4);
  border: var(--borda-fina) solid var(--acento);
  border-radius: var(--r-md);
  background: var(--acento-suave);
  color: var(--acento);
  font-size: var(--txt-md);
  font-weight: var(--peso-medio);
  cursor: pointer;
}
.campo__frase { color: var(--erro); font-size: var(--txt-sm); }

/* ---- a frota do cliente ---- */
.frota {
  display: flex;
  align-items: center;
  gap: var(--e-2);
  min-height: var(--altura-toque);
  padding: var(--e-1) var(--e-2);
  border: var(--borda-fina) solid var(--borda);
  border-radius: var(--r-md);
  margin: 0;
  cursor: pointer;
}
.frota__placa { font-weight: var(--peso-forte); white-space: nowrap; }
/* ⚠️ O apelido pode ser longo; ele encurta, a placa nunca. */
.frota__apelido {
  color: var(--texto-fraco);
  font-size: var(--txt-sm);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.campo__recado { color: var(--texto); font-size: var(--txt-sm); font-weight: var(--peso-medio); }

/* 🔵 "Escolha…" esmaecido no campo, não opção na lista (pedido dele, 29/10). */
.campo__entrada--esmaecido { color: var(--texto-apagado); }

.campo__buscar {
  flex: none;
  min-height: var(--altura-toque);
  padding: var(--e-2) var(--e-4);
  border: var(--borda-fina) solid var(--acento);
  border-radius: var(--r-md);
  background: var(--acento-suave);
  color: var(--acento);
  font-size: var(--txt-md);
  font-weight: var(--peso-medio);
  cursor: pointer;
  white-space: nowrap;
}
.campo__buscar:disabled { opacity: .45; cursor: not-allowed; }

.campos__erro {
  margin: 0;
  padding: var(--e-3);
  border: var(--borda-fina) solid var(--erro);
  border-radius: var(--r-md);
  color: var(--erro);
}
</style>
