-- ============================================================================
-- MoviZap — migração 080: os ajustes NOSSOS em cima da definição do Bitrix
--
-- 🔵 Pedidos dele, 29/10, sobre o formulário de Suporte: *"na aba 2, somente 1
-- caixa para o nome já serve"* · *"no campo do telefone, deixar em fantasma o
-- modelo de preenchimento '(00) 123456789'"* · *"vamos mudar as opções do
-- 'Tipo de solicitação', pois são do bitrix e não nos satisfazem mais"* · *"o
-- assunto já é o próprio tipo de solicitação"* · *"o campo detalhe a
-- ocorrência pode ser um pouco mais alto"* · *"já podemos trazer no campo de
-- veículo placa os veículos que ele tem ativo na Weso"*.
--
-- 🚨 POR QUE ISTO É COLUNA E NÃO UMA EDIÇÃO NO BANCO: `gravar_definicao`
-- APAGA e reescreve campos e regras a cada carga, a partir do
-- `dados/formularios_bitrix/mapa_bruto.json`. Editar a opção à mão no banco
-- funcionaria hoje e desapareceria na próxima carga -- sem erro, sem aviso.
-- Por isso o ajuste vive na tabela `AJUSTES` do
-- `scripts/carregar_formularios.py`, UM lugar, e é reaplicado toda vez.
--
-- ⚠️ TIRAR CAMPO NÃO PRECISA DE COLUNA: o campo simplesmente não é inserido
-- (`fora` na tabela de ajustes). Trocar rótulo e opção também não -- `rotulo`
-- e `opcoes` já existem. O que FALTAVA é o que esta migração acrescenta.
-- ============================================================================

BEGIN;

ALTER TABLE formulario_campo
    ADD COLUMN IF NOT EXISTS fantasma varchar(60),
    ADD COLUMN IF NOT EXISTS linhas   smallint,
    ADD COLUMN IF NOT EXISTS fonte    varchar(20);

COMMENT ON COLUMN formulario_campo.fantasma IS
    'O modelo de preenchimento que aparece esmaecido DENTRO do campo '
    '(placeholder). Pedido dele no telefone: "(00) 123456789". 🚨 E apenas '
    'modelo: nao e valor, nao e enviado, e some ao digitar.';

COMMENT ON COLUMN formulario_campo.linhas IS
    'Altura do campo em linhas. Nulo = uma linha (input). Com valor, a tela '
    'desenha caixa de varias linhas -- e o campo "Detalhe a ocorrencia" e '
    '`string` no Bitrix, entao sem isto ele seria uma linha so, o que diz a '
    'quem preenche "escreva pouco".';

COMMENT ON COLUMN formulario_campo.fonte IS
    'De onde a tela puxa SUGESTAO para este campo. Hoje so `weso_placas`: as '
    'placas que o cliente tem ativas na WESO, quando o cliente foi '
    'identificado. 🚨 NAO e validacao: a pessoa sempre pode digitar uma placa '
    'que nao esta na lista -- e ha botao para isso, porque frota nossa '
    'desatualizada nao pode barrar chamado.';

ALTER TABLE formulario_campo DROP CONSTRAINT IF EXISTS formulario_campo_fonte_check;
ALTER TABLE formulario_campo
    ADD CONSTRAINT formulario_campo_fonte_check CHECK (
        fonte IS NULL OR fonte IN ('weso_placas'));

ALTER TABLE formulario_campo DROP CONSTRAINT IF EXISTS formulario_campo_linhas_check;
ALTER TABLE formulario_campo
    ADD CONSTRAINT formulario_campo_linhas_check CHECK (
        linhas IS NULL OR linhas BETWEEN 2 AND 20);

INSERT INTO schema_migracao (versao, aplicada_em, descricao)
VALUES ('080', now(), 'ajustes nossos no campo: modelo esmaecido, altura e fonte de sugestao');

COMMIT;

-- ----------------------------------------------------------------------------
-- CONFERÊNCIA:
--
--   SELECT nosso_nome, rotulo, fantasma, linhas, fonte
--     FROM formulario_campo c JOIN formulario f ON f.id = c.formulario_id
--    WHERE f.codigo = 'SUPORTE' ORDER BY c.ordem;
--     -- esperado depois da carga: 11 campos (sobrenome e assunto FORA),
--     --   "Nome completo" no lugar de "Primeiro Nome",
--     --   telefone com fantasma "(00) 123456789",
--     --   detalhe-a-ocorrencia com linhas = 6,
--     --   veiculo-e-placa com fonte = 'weso_placas'
-- ----------------------------------------------------------------------------
