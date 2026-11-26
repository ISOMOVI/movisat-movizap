-- ============================================================================
-- MoviZap — migração 120: o TERMO posto à mão no card (Contratual, PNL_1.5)
-- ============================================================================
--
-- 🔵 Pedido dele, 25/11: *"os cards fechados na aba contratual devem ter o
-- numero do termo antes do nome do cliente: TERMO: '12345 - PASTELARIA
-- VELASCO'"*; e, sobre de onde vem o número: *"o operador coloca a mão no
-- card, pois só depois de assinado que ele será gerado oficialmente"*.
--
-- 📏 **A MEDIÇÃO QUE OBRIGOU ESTA MIGRAÇÃO.** O quadro do Contratual tem
-- **6 cards e nenhum com termo**, porque os seis são **solicitações sem OS**
-- ("Aditivo contratual", "Substituição de veículos") — e o termo não é campo
-- da OS no Harmonit: ele é extraído de dentro do corpo dela
-- (`fpsl_weso/termo_da_os.py`). Sem OS, não existe termo em lugar nenhum.
-- As respostas dos formulários foram abertas uma por uma: há CNPJ, placas,
-- endereço e responsável, e **nenhum campo de termo ou contrato**.
--
-- 🚨 **O TERMO DA OS CONTINUA GANHANDO.** Quando a OS existir, o número dela é
-- o oficial e é ele que a tela mostra; esta coluna preenche só o vazio, que é
-- exatamente a janela entre assinar e gerar a OS. O card diz qual é a origem
-- (`termo_a_mao`), porque tela que não distingue "oficial" de "digitado" é
-- tela mentindo (`M12`).
--
-- ⚠️ **SEM MÁSCARA NO NÚMERO**, e é decisão declarada: medi apenas **dois**
-- termos reais no Financeiro (8953 e 8958), e inventar formato a partir de dois
-- exemplos barra dado verdadeiro. A coluna é `text` e a rota só apara e limita
-- o tamanho.
--
-- 🚨 **NÃO SE REGISTRA PASSAGEM AO GRAVAR O TERMO.** Medido: o `etapa_desde` do
-- card sai de `max(pipeline_passagem.em)`, então uma passagem a cada digitação
-- zeraria o contador de "está nesta etapa desde", que é o que mostra card
-- parado. Quem conta a história deste campo são as próprias colunas
-- `termo_por` e `termo_em`.
--
-- O par `termo`/`termo_em` segue a régua que o `desfecho` já usa nesta tabela:
-- os dois juntos ou os dois nulos, garantido por CHECK -- data sem valor (ou
-- valor sem data) seria estado que a tela não sabe desenhar.
-- ============================================================================

BEGIN;

ALTER TABLE pipeline_card
  ADD COLUMN IF NOT EXISTS termo     text,
  ADD COLUMN IF NOT EXISTS termo_por integer,
  ADD COLUMN IF NOT EXISTS termo_em  timestamptz;

-- Mesma forma do `desfecho_por`: o card sobrevive à saída do atendente, e o
-- nome de quem pôs apenas deixa de ser conhecido.
ALTER TABLE pipeline_card
  DROP CONSTRAINT IF EXISTS pipeline_card_termo_por_fkey;
ALTER TABLE pipeline_card
  ADD CONSTRAINT pipeline_card_termo_por_fkey
  FOREIGN KEY (termo_por) REFERENCES atendente(id) ON DELETE SET NULL;

ALTER TABLE pipeline_card
  DROP CONSTRAINT IF EXISTS pipeline_card_termo_tem_data;
ALTER TABLE pipeline_card
  ADD CONSTRAINT pipeline_card_termo_tem_data
  CHECK ((termo IS NULL) = (termo_em IS NULL));

COMMENT ON COLUMN pipeline_card.termo IS
  'Numero do termo POSTO A MAO pelo operador, para a janela entre assinar e '
  'gerar a OS (o termo oficial so nasce depois). O termo da OS, quando '
  'existe, GANHA deste. Sem mascara de proposito: so dois termos reais '
  'medidos, e formato inventado barra dado verdadeiro.';
COMMENT ON COLUMN pipeline_card.termo_por IS
  'Atendente que pos o numero. Nao se grava pipeline_passagem para isto: o '
  'etapa_desde do card sai de max(passagem.em) e seria zerado a cada '
  'digitacao.';
COMMENT ON COLUMN pipeline_card.termo_em IS
  'Quando o numero foi posto. Nulo exatamente quando termo e nulo (CHECK).';

INSERT INTO schema_migracao (versao, aplicada_em, descricao)
VALUES ('120', now(), 'termo posto a mao no pipeline_card (Contratual PNL_1.5): o quadro tem 6 cards sem OS e o termo so existe dentro da OS, entao o operador poe o numero enquanto a OS nao nasce; o termo da OS continua ganhando');

COMMIT;
