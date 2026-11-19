-- ===========================================================================
-- MoviZap — migração 117: a aba 2 do Financeiro, "Serviço dos técnicos"
-- ===========================================================================
--
-- 🔵 Pedido dele, 18/11: *"Nova aba2 no painel do Financeiro Movizap: 'Serviço
-- dos técnicos'"*, com cinco colunas — Movimentação, Preparação, Validação,
-- Procfy e Pagamento enviado.
--
-- 🔵 *"É possível fazer tudo no FPSL com as rotas e etc, mas o painel é aqui."*
-- Os dados e os gestos moram no FPSL (3 tabelas + 12 rotas de ponte); esta
-- migração só abre a porta da tela.
--
-- 🚨 ELA É DIFERENTE DAS OUTRAS ABAS, e por isso NÃO ganha `pipeline_etapa`:
-- as cinco colunas não são etapas nossas nem situações do ERP -- são estados do
-- **artefato de pagamento**, que vive no FPSL. Criar etapas aqui faria o
-- `quadro_da_aba` tentar desenhá-la como as outras e mostrar cinco colunas
-- vazias para sempre.
--
-- ⚠️ **NASCE FECHADA, só owner**, como toda aba nova. A permissão é campo da
-- entrada em `telas.py`, e ele decide quando conceder -- 🔵 *"a Erika, apenas a
-- aba 3"* é a régua que ele já deu para as abas do Pós-venda.
--
-- 📏 E o que ela vai mostrar no primeiro dia, medido em 18/11 contra o cache de
-- 633 OS: **79 artefatos** em **9 cards** -- Franck com 40 (R$ 3.430,00 +
-- R$ 933,10) e um card *"sem técnico identificado"* com **21** artefatos
-- somando **R$ 2.581,90** sem destinatário. 🚨 Esses 21 são o funil que ele
-- mandou consertar em 11/11 (70 → 16 → 8 OS): aqui eles aparecem em vez de
-- serem descartados.

BEGIN;

INSERT INTO painel_aba (painel, codigo_tela, titulo, ordem, ativo, criada_em)
VALUES ('financeiro', 'PNL_1.6', 'Serviço dos técnicos', 2, true, now())
ON CONFLICT DO NOTHING;

INSERT INTO schema_migracao (versao, aplicada_em, descricao)
VALUES ('117', now(), 'aba 2 do Financeiro: Servico dos tecnicos, as cinco colunas do pagamento de tecnico; os dados e os gestos moram no FPSL e esta aba so abre a tela');

COMMIT;
