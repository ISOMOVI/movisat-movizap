<script setup>
/* ============================================================================
   Os campos de um formulário, desenhados a partir da DEFINIÇÃO.
   ----------------------------------------------------------------------------
   🚨 UMA TELA PARA OS 15. A definição (campos, rótulos, opções, regras) é dado
   no banco, e este componente é quem a desenha -- é o mesmo desenho do
   `movizap/telas.py`, onde o menu é dado e não código. Formulário novo é linha
   em tabela; nenhum `.vue` nasce por causa dele.

   🚨 ELE NÃO VALIDA NADA PARA VALER. O `required` do HTML e o aviso embaixo do
   campo são conforto de quem preenche; quem recusa é o servidor
   (`movizap/formularios.py:validar`). O Bitrix fazia o contrário -- toda a
   validação dos 239 campos no navegador -- e em 22/10 um POST com
   `values=[]` vazio criou registro lá dentro.

   ⚠️ `page` e `layout` NÃO SÃO PERGUNTA: `page` é quebra de página do Bitrix e
   `layout` é um traço decorativo. Viram separador, nunca campo.

   ⚠️ `product` (2 campos, no Aditivo e na Substituição) puxava catálogo do
   Bitrix. Sem equivalente nosso, nesta etapa é texto -- e está dito aqui para
   ninguém "descobrir" isso na tela.

   🚨 NENHUMA COR, TAMANHO OU ESPAÇAMENTO NA MÃO: tudo em token
   (`src/estilo/tokens.css`), inclusive o `--txt-campo` dos campos -- 16px ali
   não é estética, abaixo disso o iOS dá zoom sozinho ao focar.
   ============================================================================ */
import { computed } from 'vue'

import { visiveis } from '../util/regras_formulario.js'

const props = defineProps({
  campos: { type: Array, default: () => [] },
  regras: { type: Array, default: () => [] },
  valores: { type: Object, required: true },
  // Campos que chegaram preenchidos pelo vínculo (Etapa 2) e não se editam.
  travados: { type: Array, default: () => [] },
  erro: { type: String, default: '' },
})

const DECORATIVOS = ['page', 'layout']

const dePe = computed(() => visiveis(
  { campos: props.campos, regras: props.regras }, props.valores))

const lista = computed(() => props.campos.filter(
  (c) => DECORATIVOS.includes(c.tipo) || dePe.value.has(c.nome)))

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
</script>

<template>
  <div class="campos">
    <template v-for="campo in lista" :key="campo.nome">
      <!-- quebra de página e traço: separadores, não perguntas -->
      <hr v-if="campo.tipo === 'layout'" class="campos__traco" />
      <p v-else-if="campo.tipo === 'page'" class="campos__etapa">
        {{ campo.rotulo }}
      </p>

      <label v-else class="campo">
        <span class="campo__rotulo">
          {{ campo.rotulo || campo.nome }}
          <span v-if="campo.obrigatorio" class="campo__obrigatorio" aria-hidden="true">*</span>
        </span>

        <select
          v-if="campo.tipo === 'list'"
          v-model="valores[campo.nome]"
          class="campo__entrada"
          :disabled="ehTravado(campo)"
          :required="campo.obrigatorio"
        >
          <option value="">Escolha…</option>
          <option v-for="o in campo.opcoes" :key="o.value" :value="o.value">
            {{ o.label }}
          </option>
        </select>

        <textarea
          v-else-if="longo(campo)"
          v-model="valores[campo.nome]"
          class="campo__entrada campo__entrada--longa"
          rows="4"
          :disabled="ehTravado(campo)"
          :required="campo.obrigatorio"
        ></textarea>

        <input
          v-else-if="campo.tipo === 'file'"
          type="file"
          class="campo__entrada"
          :required="campo.obrigatorio"
          @change="$emit('arquivo', campo.nome, $event.target.files)"
        />

        <input
          v-else
          v-model="valores[campo.nome]"
          class="campo__entrada"
          :type="tipoDoInput(campo)"
          :disabled="ehTravado(campo)"
          :required="campo.obrigatorio"
        />

        <span v-if="campo.ajuda" class="campo__ajuda">{{ campo.ajuda }}</span>
        <!-- ⚠️ O campo travado DIZ POR QUÊ. Campo cinza sem explicação parece
             defeito; é o precedente do ModalAgendar, que explica em vez de
             sumir. -->
        <span v-if="ehTravado(campo)" class="campo__ajuda">
          Veio do cadastro desta conversa.
        </span>
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

.campos__erro {
  margin: 0;
  padding: var(--e-3);
  border: var(--borda-fina) solid var(--erro);
  border-radius: var(--r-md);
  color: var(--erro);
}
</style>
