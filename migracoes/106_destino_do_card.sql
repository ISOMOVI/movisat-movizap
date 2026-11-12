-- ============================================================================
-- MoviZap — migração 106: a OS nasce no PAINEL certo, e o formulário diz em
--                         qual ETAPA o card dele nasce
--
-- 🔵 DUAS FRASES DELE, 11/11, e as duas são a mesma ideia:
--
--   · *"não é nesse financeiro que deve nascer, como foi dito essas etapas
--     finais do OP devem ser excluídas e deveria ter nascido no painel
--     Financeiro, na etapa correta 'Nova solicitação'"*;
--   · *"fiz teste com form de aditivo e não abriu card no contratual como foi
--     pedido"*.
--
-- 📏 MEDIDO ANTES (11/11): a OS **17119** (ressarcimento, termo 8947) nasceu
-- na situação **15746** e apareceu na coluna *Financeiro* do painel da
-- OPERAÇÃO. **Não houve passagem nenhuma** -- `os_passagem` tem ZERO linhas
-- para 15746/15695/16492: ela nasceu ali. E o envio de aditivo dele gerou a
-- solicitação **3437** com **nenhum card**, porque o portão do card era
-- `chamado_os.PROBLEMA_POR_FORMULARIO`, que tem **um** slug: `suporte`.
--
-- ----------------------------------------------------------------------------
-- AS DUAS COLUNAS, e por que são duas e não uma
-- ----------------------------------------------------------------------------
--
--   pipeline_etapa.recebe_situacao  -> "OS nesta situação do ERP mora NESTA
--                                       etapa" (a OS vindo do Harmonit)
--   formulario.etapa_destino_id     -> "o card deste formulário nasce NESTA
--                                       etapa" (a solicitação vindo do site)
--
-- 🚨 SÃO DOIS CAMINHOS DIFERENTES e misturá-los seria errado: a primeira é um
-- card que o ERP cria e nós apenas colocamos no lugar; a segunda é um card
-- que NASCE aqui, sem OS, como os chamados do Suporte desde 29/10.
--
-- ----------------------------------------------------------------------------
-- 🚨 POR QUE O DESTINO É DADO, E NÃO CÓDIGO
-- ----------------------------------------------------------------------------
-- As 17 situações da Operação vivem em código porque **o ERP as manda** e
-- renumerá-las aqui criaria duas verdades (migração 105). O destino é o
-- contrário: é decisão dele, muda por painel e por formulário, e mudar não
-- pode exigir deploy -- a mesma razão de `formulario.painel` ser coluna.
--
-- ⚠️ UMA SITUAÇÃO SÓ PODE SER RECEBIDA POR UMA ETAPA. Sem o índice único, a
-- mesma OS nasceria em dois painéis e ninguém saberia qual é o certo.
-- ============================================================================

BEGIN;

ALTER TABLE pipeline_etapa
    ADD COLUMN IF NOT EXISTS recebe_situacao integer;

COMMENT ON COLUMN pipeline_etapa.recebe_situacao IS
    'A situacao do ERP cuja OS nasce NESTA etapa. 🔵 Dele (11/11): a OS '
    'financeira "deveria ter nascido no painel Financeiro, na etapa correta '
    'Nova solicitacao". 🚨 Nulo = esta etapa nao recebe OS do ERP; o card '
    'dela nasce de solicitacao ou de arrasto. ⚠️ Tirar a situacao das 17 da '
    'Operacao SEM apontar uma etapa aqui faria a OS desaparecer de todo '
    'quadro -- e por isso que as tres saem e entram no mesmo passo.';

-- 🚨 Uma situação, uma etapa. Parcial porque nulo é a regra, não a exceção.
CREATE UNIQUE INDEX IF NOT EXISTS idx_pipeline_etapa_recebe_unica
    ON pipeline_etapa (recebe_situacao)
 WHERE recebe_situacao IS NOT NULL;

ALTER TABLE formulario
    ADD COLUMN IF NOT EXISTS etapa_destino_id integer
        REFERENCES pipeline_etapa(id) ON DELETE SET NULL;

COMMENT ON COLUMN formulario.etapa_destino_id IS
    'A etapa em que o card deste formulario nasce ao receber uma '
    'solicitacao. 🔵 Dele (11/11): "fiz teste com form de aditivo e nao abriu '
    'card no contratual como foi pedido". 🚨 Nulo = o envio NAO cria card '
    '(so entra na Caixa de Solicitacoes) -- e isso e decisao dele por '
    'formulario, nao defeito: o Contato e as duas pesquisas nao tem fila. '
    '⚠️ ON DELETE SET NULL, nao CASCADE: apagar uma etapa nao pode levar o '
    'formulario com ela.';

-- ----------------------------------------------------------------------------
-- SEED 1 — quem recebe cada uma das três situações que saem da Operação
-- ----------------------------------------------------------------------------
-- 🔵 A frase dele nomeia a etapa: **"Nova solicitação"**. Ela existe no
-- Financeiro (#875) e no Pós-venda (#469), com esse nome exato.
--
-- 🔴 NO CONTRATUAL ELA NÃO EXISTE: as seis colunas que ele escreveu começam em
-- *"Elaborar contrato"*. Então a 16492 vai para a **primeira etapa** daquele
-- painel, e isto fica marcado para ele confirmar -- inventar uma coluna
-- "Nova solicitação" no Contratual seria mexer numa lista que é dele.
-- Mudar é UMA linha: `UPDATE pipeline_etapa SET recebe_situacao = ...`.
UPDATE pipeline_etapa e SET recebe_situacao = 15746
 WHERE e.titulo = 'Nova solicitação'
   AND e.aba_id = (SELECT id FROM painel_aba WHERE codigo_tela = 'PNL_1.4')
   AND NOT EXISTS (SELECT 1 FROM pipeline_etapa x
                    WHERE x.recebe_situacao = 15746);

UPDATE pipeline_etapa e SET recebe_situacao = 15695
 WHERE e.titulo = 'Nova solicitação'
   AND e.aba_id = (SELECT id FROM painel_aba WHERE codigo_tela = 'PNL_1.3')
   AND NOT EXISTS (SELECT 1 FROM pipeline_etapa x
                    WHERE x.recebe_situacao = 15695);

UPDATE pipeline_etapa e SET recebe_situacao = 16492
 WHERE e.id = (SELECT id FROM pipeline_etapa
                WHERE aba_id = (SELECT id FROM painel_aba
                                 WHERE codigo_tela = 'PNL_1.5')
                ORDER BY ordem, id LIMIT 1)
   AND NOT EXISTS (SELECT 1 FROM pipeline_etapa x
                    WHERE x.recebe_situacao = 16492);

-- ----------------------------------------------------------------------------
-- SEED 2 — a etapa de destino de cada formulário
-- ----------------------------------------------------------------------------
-- 🚨 A REGRA É DERIVADA, NÃO ESCRITA À MÃO: cada formulário já diz o PAINEL
-- dele (`formulario.painel`, migração 075, o mapa dele de 23/10). O destino é
-- a **primeira etapa daquele painel** -- que é "Nova solicitação" em três dos
-- quatro, por ser como ele nomeou a primeira coluna.
--
-- ⚠️ O SUPORTE É A EXCEÇÃO NOMEADA: ele vai para `Chamados`, que é a etapa
-- nossa da Operação e já recebe os chamados dele desde 29/10. A primeira
-- etapa da Operação é justamente a `Chamados`, então a regra derivada acerta
-- sozinha -- e esta frase existe para quem leia e estranhe.
--
-- 🚨 FORMULÁRIO SEM PAINEL FICA SEM DESTINO, de propósito: o Contato e o
-- `IDEIAS` não têm fila (decisão dele), e inventar uma os colocaria numa
-- coluna que ninguém olha.
-- 🚨 O EMPATE DO POS-VENDA, NOMEADO: aquele painel tem DUAS abas
-- (Treinamentos e Pos-venda) e "a primeira por ordem" entregaria as duas
-- PESQUISAS na fila de Treinamentos. Pesquisa nao e treinamento. ⚠️ Derivacao
-- com empate precisa de desempate nomeado, nao do acaso da `ordem`.
UPDATE formulario f SET etapa_destino_id = (
        SELECT e.id FROM pipeline_etapa e JOIN painel_aba a ON a.id = e.aba_id
         WHERE a.codigo_tela = 'PNL_1.3' AND e.titulo = 'Nova solicitação'
         LIMIT 1)
 WHERE f.codigo IN ('CES', 'NPS')
   AND f.etapa_destino_id IS NULL;

WITH primeira AS (
    SELECT a.painel,
           (SELECT e.id FROM pipeline_etapa e
             WHERE e.aba_id = a.id AND e.ativo
             ORDER BY e.ordem, e.id LIMIT 1) AS etapa_id
      FROM painel_aba a
     WHERE a.ativo
       -- ⚠️ Painel com DUAS abas (o Pós-venda tem Treinamentos e Pós-venda):
       -- vale a aba de MENOR ordem, que é a que a tela abre primeiro.
       AND a.ordem = (SELECT min(x.ordem) FROM painel_aba x
                       WHERE x.painel = a.painel AND x.ativo)
)
UPDATE formulario f SET etapa_destino_id = p.etapa_id
  FROM primeira p
 WHERE f.painel = p.painel
   AND p.etapa_id IS NOT NULL
   AND f.etapa_destino_id IS NULL;

INSERT INTO schema_migracao (versao, aplicada_em, descricao)
VALUES ('106', now(), 'destino do card: a OS nasce no painel certo e o formulario diz a etapa do card dele');

COMMIT;
