-- ============================================================================
-- MoviZap — migração 079: o FORMATO NOVO do formulário público
--
-- 🔵 Pedido dele, 29/10: *"ele ainda não passou por aqueles ajustes de UX/UI e
-- customização [...] ajuste ele no novo formato 'etapas, logo, cor, placas,
-- etc'"* -- sobre o formulário de Suporte.
--
-- O desenho está em `C:\Users\Lenovo\Desktop\Formularios_Movisat_Design.md`
-- (23/10): Bloco 1 (o `+`), Bloco 3 (máscaras), Bloco 5 (etapas) e Bloco 6
-- (logo e cor). Esta migração é o que FALTAVA DE DADO para os quatro.
--
-- 🚨 TRÊS COLUNAS, E NENHUMA LISTA NO CÓDIGO -- a mesma régua da 075: o dia em
-- que ele quiser o formato novo no 2º, no 5º e no 15º formulário não pode
-- exigir deploy. Quem escreve as três é o `scripts/carregar_formularios.py`,
-- UM lugar, e a carga reescreve a cada rodada.
--
-- 🚨 `formato` NASCE 'classico' NOS 15, de propósito. Esta é a casa onde
-- interruptor nasce desligado: o formato novo muda a tela que a internet vê, e
-- ele valida formulário por formulário no navegador. Ligar os outros 14 é uma
-- linha na carga, quando ele disser.
--
-- ⚠️ `etapas` É NULO EM QUASE TODOS, e isso é legítimo: 14 dos 15 continuam
-- num rolo único. E das 15 `page` que existem nos outros formulários, NENHUMA
-- está aqui -- o Suporte não tem `page` nenhuma, então as 4 etapas dele são
-- agrupamento NOSSO, proposto por mim, e por isso moram em dado onde ele pode
-- rever. Onde houver `page`, ela é que manda (Bloco 5 do plano).
--
-- ⚠️ `validacao` NÃO É BARREIRA. Quem recusa é o servidor
-- (`movizap/formularios.py:validar`); este campo diz à TELA qual máscara pôr e
-- qual frase mostrar. Gravar 'cpf' aqui não faz o servidor exigir dígito
-- verificador -- e isso está dito aqui para ninguém supor o contrário.
-- ============================================================================

BEGIN;

ALTER TABLE formulario
    ADD COLUMN IF NOT EXISTS formato varchar(10) NOT NULL DEFAULT 'classico',
    ADD COLUMN IF NOT EXISTS etapas  jsonb;

ALTER TABLE formulario DROP CONSTRAINT IF EXISTS formulario_formato_check;
ALTER TABLE formulario
    ADD CONSTRAINT formulario_formato_check
        CHECK (formato IN ('classico', 'novo'));

COMMENT ON COLUMN formulario.formato IS
    'classico = a pagina publica de 22/10, um rolo so, tokens do painel. '
    'novo = etapas, logo oficial, base #021529, repetidor e mascaras (desenho '
    'de 23/10). 🚨 Nasce classico nos 15: o formato novo muda o que a internet '
    've, e ele valida formulario por formulario. Reescrito pela carga.';

COMMENT ON COLUMN formulario.etapas IS
    'As etapas da pagina, como [{"titulo": ..., "campos": [nosso_nome, ...]}]. '
    'NULO = rolo unico (os 14 de hoje). ⚠️ Os campos sao citados pelo '
    '`nosso_nome`, nao pelo nome do Bitrix: e o unico dos dois que uma pessoa '
    'consegue ler e revisar. Quem traduz para o nome de origem e a rota '
    'publica. Onde o formulario tiver `page`, ela e que manda.';

ALTER TABLE formulario_campo
    ADD COLUMN IF NOT EXISTS validacao varchar(16);

ALTER TABLE formulario_campo DROP CONSTRAINT IF EXISTS formulario_campo_validacao_check;
ALTER TABLE formulario_campo
    ADD CONSTRAINT formulario_campo_validacao_check CHECK (
        validacao IS NULL OR validacao IN
            ('cpf', 'cnpj', 'placa', 'telefone', 'email', 'cep'));

COMMENT ON COLUMN formulario_campo.validacao IS
    'Qual mascara e qual conferencia a TELA aplica neste campo. 🚨 Nao e '
    'barreira: quem recusa e o servidor (formularios.validar). Existe porque '
    'o tipo do Bitrix nao diz o bastante -- 30 campos sao `double` e sao '
    'CNPJ, CPF, RG e quantidade. NULO = sem mascara.';

INSERT INTO schema_migracao (versao, aplicada_em, descricao)
VALUES ('079', now(), 'formato novo do formulario publico: etapas, mascaras e identidade (Suporte primeiro)');

COMMIT;

-- ----------------------------------------------------------------------------
-- CONFERÊNCIA (a prova é RELER o estado, nunca o retorno do comando):
--
--   SELECT codigo, formato, etapas IS NOT NULL AS tem_etapas FROM formulario
--    ORDER BY ordem;
--     -- antes da carga: os 15 em 'classico', etapas nulas
--     -- depois:         SUPORTE em 'novo' com 4 etapas; os outros 14 intactos
--
--   SELECT c.nosso_nome, c.validacao FROM formulario_campo c
--     JOIN formulario f ON f.id = c.formulario_id
--    WHERE f.codigo = 'SUPORTE' AND c.validacao IS NOT NULL ORDER BY c.ordem;
--     -- esperado: cnpj|cnpj · cpf|cpf · e-mail|email · telefone|telefone ·
--     --           veiculo-e-placa-somente-se-for-referente|placa
-- ----------------------------------------------------------------------------
