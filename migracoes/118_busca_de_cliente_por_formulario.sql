-- ===========================================================================
-- MoviZap — migração 118: o botão Buscar passa a ser DADO, por formulário
-- ===========================================================================
--
-- 🔵 Decisão dele, 23/11: *"formulario de pagamento de parceiros esta errado,
-- ele nao precisa de cpf e cnpj, obviamente pois nao puxa de base alguma"* —
-- e, perguntado sobre o botão, **tirar onde não há base**.
--
-- 🚨 O DEFEITO, MEDIDO EM 23/11. O botão *Buscar* do CNPJ não era decisão de
-- ninguém: ele nascia de uma regra fixa na tela —
--
--     function temBusca(campo) {
--       return ehNovo.value && campo.validacao === 'cnpj'
--     }
--
-- — e `ehNovo` é verdade nos 15 desde 11/11. Resultado: todo formulário com
-- campo CNPJ ganhou o botão, inclusive os que **não procuram cliente nenhum**.
-- O `cliente_por_documento` varre a tabela `cliente` (960 linhas, os clientes
-- nossos): um parceiro técnico, um fornecedor ou um interessado em teste
-- gratuito **nunca** está lá. O botão aparecia, a pessoa clicava e a resposta
-- correta era *"não achou"* — comportamento certo numa tela que não devia
-- oferecer a busca.
--
-- ⚠️ POR QUE COLUNA, E NÃO UMA LISTA NA TELA: a mesma razão do `painel` e do
-- `formato`. Quem procura cliente é decisão dele, formulário por formulário;
-- em coluna, mudar de ideia é uma linha na carga — sem migração e sem build.
-- Lista dentro do `.vue` seria a terceira verdade do mesmo assunto.
--
-- 🚨 NASCE `false`, E É DE PROPÓSITO (régua da casa: atalho nasce desligado).
-- Formulário novo não oferece busca na base até alguém dizer que oferece.
BEGIN;

ALTER TABLE formulario
  ADD COLUMN IF NOT EXISTS busca_cliente boolean NOT NULL DEFAULT false;

-- Os SEIS que de fato resolvem um cliente nosso: são exatamente os que têm a
-- etapa "Contrato" com CPF/CNPJ **escondidos** atrás da pergunta PF/PJ, e cujo
-- CNPJ identifica quem já tem contrato. Medido um por um em 23/11.
--
-- ⚠️ A `FICHA_CADASTRAL` fica FORA: ela é a ficha de **novos** clientes — quem
-- preenche, por definição, ainda não está na base.
UPDATE formulario
   SET busca_cliente = true,
       atualizado_em = now()
 WHERE codigo IN ('SUPORTE', 'ADITIVO', 'ADMINISTRATIVO', 'FINANCEIRO',
                  'RESCISAO', 'SUBSTITUICAO');

INSERT INTO schema_migracao (versao, aplicada_em, descricao)
VALUES ('118', now(), 'busca_cliente por formulario: o botao Buscar do CNPJ deixa de ser regra fixa da tela e passa a ser dado; fica nos 6 que resolvem cliente nosso e sai dos demais');

COMMIT;
