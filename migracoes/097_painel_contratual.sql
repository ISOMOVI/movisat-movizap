-- ============================================================================
-- 097 — O PAINEL DO CONTRATUAL, com as colunas que ele mandou
-- ============================================================================
-- 🔵 06/11, pedido dele: *"Depois gere a mesmta tela do 'Financeiro' para o
-- 'Contratual' - seguindo o seguindo modelo para colunas"*, e a lista colada:
--
--     Regras de automação e gatilhos
--
--     pesquisar
--     Elaborar contrato
--     Aguardando pendencias
--     Aguardando assinatura
--     Assinado
--     Não assinado
--     Desistiu de cancelar
--
-- 🚨 **AS DUAS PRIMEIRAS LINHAS NÃO SÃO COLUNAS, E ESTA É UMA LEITURA MINHA.**
-- *"Regras de automação e gatilhos"* e *"pesquisar"* são a moldura da tela de
-- onde ele copiou (o link de automação e a caixa de busca do CRM), não etapas de
-- contrato. Três razões:
--   1. Na lista do Financeiro, meia hora antes, a primeira linha era o cabeçalho
--      literal **"Colunas"** -- mesma moldura, mesmo lugar.
--   2. *"pesquisar"* em minúscula, no meio de sete títulos capitalizados.
--   3. As seis restantes formam um fluxo fechado de contrato, de "Elaborar" a
--      três fins.
-- ⚠️ **SE EU ERREI, o conserto é uma linha nesta lista** -- e está escrito nos
-- Próximos Passos como pergunta aberta, não como fato. Deixar *"pesquisar"*
-- virar coluna de um painel que ele vai abrir seria pior que perguntar.
--
-- 🚨 NENHUMA DESTAS COLUNAS EXISTE NO HARMONIT: mover card aqui escreve **só
-- aqui**, como no Financeiro (096) e nas abas do Pós-venda (094).
--
-- 🚨 TRÊS COLUNAS FINAIS. "Assinado", "Não assinado" e "Desistiu de cancelar"
-- são os três fins deste fluxo -- marcar só a última diria que chegar em
-- "Assinado" não é terminar, e isso é falso. ⚠️ `final` continua sendo só o fato
-- escrito no banco: nada na tela depende dele ainda.
--
-- ⚠️ "Aguardando pendencias" e "Desistiu de cancelar" ENTRAM COMO ELE ESCREVEU,
-- sem acento em "pendencias" e com a frase inteira. Corrigir ortografia de
-- rótulo que ele ditou é mudar o nome da coluna dele sem pedir.
--
-- 🔴 O PAINEL NASCE VAZIO, e ele já disse que é assim: *"as regras de criação de
-- cards em 'financeiro', 'pós-venda' e 'Contratual' ainda ficam em branco mesmo.
-- Mas eleas ja devem aparecer no menu para owner"*. A tela escreve "Nenhum card
-- nesta aba ainda." em vez de parecer quebrada (`M12`).
-- ============================================================================

BEGIN;

-- ---------------------------------------------------------------------------
-- 1. A ABA
-- ---------------------------------------------------------------------------
INSERT INTO painel_aba (painel, codigo_tela, titulo, ordem, ativo)
     SELECT 'contratual', 'PNL_1.5', 'Contratual', 1, true
      WHERE NOT EXISTS (SELECT 1 FROM painel_aba WHERE codigo_tela = 'PNL_1.5');

-- ---------------------------------------------------------------------------
-- 2. AS SEIS COLUNAS, NA ORDEM DELE
-- ---------------------------------------------------------------------------
-- 🚨 A ORDEM É O FLUXO. O `teste_painel_contratual.py` compara a lista inteira,
-- posição por posição, e prende também que as duas linhas de moldura NÃO
-- entraram.
INSERT INTO pipeline_etapa (aba_id, titulo, ordem, ativo, final)
     SELECT a.id, t.titulo, t.ordem, true, t.final
       FROM painel_aba a
       CROSS JOIN (VALUES ('Elaborar contrato',      1, false),
                          ('Aguardando pendencias',  2, false),
                          ('Aguardando assinatura',  3, false),
                          ('Assinado',               4, true),
                          ('Não assinado',           5, true),
                          ('Desistiu de cancelar',   6, true))
                  AS t(titulo, ordem, final)
      WHERE a.codigo_tela = 'PNL_1.5'
        AND NOT EXISTS (SELECT 1 FROM pipeline_etapa e
                         WHERE e.aba_id = a.id AND e.titulo = t.titulo);

INSERT INTO schema_migracao (versao, aplicada_em, descricao)
VALUES ('097', now(),
        'o painel do Contratual (PNL_1.5) com as 6 colunas dele');

COMMIT;

-- ============================================================================
-- CONFERÊNCIA (rodar depois, e o esperado está escrito)
-- ============================================================================
--   SELECT painel, codigo_tela, titulo FROM painel_aba ORDER BY painel, ordem;
--     -- esperado: contratual/PNL_1.5 · financeiro/PNL_1.4 · operacao/PNL_1.1 ·
--     --           pos_venda/PNL_1.2 · pos_venda/PNL_1.3
--   SELECT e.ordem, e.titulo, e.final FROM pipeline_etapa e
--     JOIN painel_aba a ON a.id = e.aba_id
--    WHERE a.codigo_tela = 'PNL_1.5' ORDER BY e.ordem;
--     -- esperado: as 6 na ordem dele, `final` nas três últimas, e NENHUMA
--     -- chamada "pesquisar" ou "Regras de automação e gatilhos"
-- ============================================================================
