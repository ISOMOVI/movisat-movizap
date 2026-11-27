/* ============================================================================
   O dinheiro e os números das telas — um lugar só para ir e vir.
   ----------------------------------------------------------------------------
   🚨 POR QUE ESTE ARQUIVO NASCEU, em 26/11. A conversão já existia, certa e
   comentada, dentro da `FichaDoTecnico.vue` — e o modal do orçamento não a
   tinha. A Aline digitou `60,00` no preço, a tela validou, o POST mandou a
   linha CRUA e o servidor respondeu *"Erro interno"*: `Decimal("60,00")` não
   existe. Duas telas lidando com o mesmo dinheiro, uma sabendo converter e a
   outra não, é o mesmo defeito que a `util/mensagem_agendamento.js` veio
   corrigir em 21/10 para as duas mensagens do WhatsApp.

   🚨 A REGRA: A VÍRGULA É DA PESSOA, O PONTO É DO PROTOCOLO. O campo continua
   mostrando `77,7` — é o que se lê em português, e é o que a calculadora de km
   escreve. Quem atravessa a ponte é o formato canônico, e por isso a conversão
   mora na SAÍDA e não na digitação: converter enquanto se digita tiraria a
   vírgula da mão da pessoa no meio do número.

   ⚠️ E NENHUMA DESTAS FUNÇÕES ADIVINHA. `"1.000"` é mil para quem digita e
   **1** para o `Decimal` do servidor; aqui isso devolve `undefined`, que quer
   dizer RECUSAR, e a tela diz a frase. Palpite viraria valor errado em
   silêncio, que é pior que recusa — a mesma régua do `_em_decimal` do
   `movizap/orcamento.py`, do outro lado da ponte.
   ============================================================================ */

/* 🚨 OS TRÊS RETORNOS SÃO COISAS DIFERENTES, e misturá-los apaga uma decisão
   dele: `null` é VAZIO (não foi dito), `undefined` é RECUSAR (não é número), e
   `0` é ZERO de verdade. Na ficha do técnico, branco é *"não oferece"* e zero é
   *"cobra zero"* (cortesia, decisão dele de 04/11) — então quem testar com
   `if (!valor)` perde a cortesia pelo caminho. */
function limpar(texto) {
  return String(texto ?? '').replace(/\s/g, '').replace(',', '.');
}

/* Reais escritos em pt-BR -> centavos inteiros.
   ⚠️ `Number('199,90')` é NaN e `parseFloat('199,90')` devolve 199 — daí a
   vírgula trocada antes. E o arredondamento no inteiro, para 199,90 não virar
   19989 por ponto flutuante. */
export function paraCentavos(texto) {
  const limpo = limpar(texto);
  if (!limpo) return null;
  const n = Number(limpo);
  if (!Number.isFinite(n) || n < 0) return undefined;
  return Math.round(n * 100);
}

/* Centavos -> o que vai DENTRO do campo, com vírgula. */
export function paraReais(centavos) {
  if (centavos === null || centavos === undefined) return '';
  return (centavos / 100).toFixed(2).replace('.', ',');
}

/* O número para CONTA na tela (comparar com zero, somar o total mostrado).
   ⚠️ Devolve `NaN` no que não é número, de propósito: quem compara `> 0`
   recebe `false` sem precisar de um segundo teste. */
export function comoNumero(texto) {
  const limpo = limpar(texto);
  if (!limpo) return NaN;
  return Number(limpo);
}

/* O que ATRAVESSA A PONTE: `"77,7"` -> `"77.7"`, e `undefined` para recusar.
   🚨 Texto e não número: o servidor lê com `Decimal`, e passar por `float`
   no caminho é justamente o que faz 0,1 + 0,2 dar 0,30000000000000004. O
   `String(Number(x))` aqui só normaliza a forma, sem casa decimal nova. */
export function paraCanonico(texto) {
  const n = comoNumero(texto);
  if (!Number.isFinite(n)) return undefined;
  return String(n);
}
