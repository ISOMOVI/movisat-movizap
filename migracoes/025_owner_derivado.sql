-- ============================================================================
-- MoviZap — migração 025: `atendente.owner` deixa de ser escrito e passa a ser
-- DERIVADO de `perfil`
--
-- Duas colunas diziam o mesmo fato -- `perfil = 'owner'` e `owner = true` -- e
-- nada impedia que discordassem. Discordar não daria erro: daria acesso
-- errado, porque as duas são lidas em lugares DIFERENTES.
--
--   `pode_acessar`            olha o BOOLEANO  (tela exclusiva do owner)
--   `permissoes_do_perfil`    olha o PERFIL    (conjunto de permissões)
--
-- Uma linha com `perfil='owner'` e `owner=false` receberia todas as
-- permissões e mesmo assim levaria 403 nas telas de owner -- um estado que
-- ninguém consegue explicar lendo a tela. Coluna gerada torna o estado
-- impossível, em vez de improvável.
--
-- ⚠️ CONFERIDO ANTES DE ESCREVER (12/08):
--   · nenhum código escreve `owner` -- varredura em `movizap/*.py` só achou
--     SELECT e leitura de dicionário;
--   · `INSERT INTO atendente` não lista a coluna e o `UPDATE` não a toca, o
--     que importa porque coluna gerada NÃO ACEITA escrita;
--   · não existe `SELECT *` em `atendente` -- todas as consultas nomeiam
--     colunas, então recriar a coluna no fim da tabela não quebra leitura.
--
-- 🚨 VAI NO MESMO DEPLOY QUE A RECUSA DE NOVOS OWNERS. Depois disto, marcar
-- `perfil='owner'` na CAD_2.1 passa a conceder owner pleno NA HORA -- antes
-- não concedia, porque o booleano continuava false. Sem a trava junto, esta
-- migração abre um caminho para nascer owner justo no dia em que se decidiu
-- que não nascem mais.
-- ============================================================================

ALTER TABLE atendente DROP COLUMN owner;
ALTER TABLE atendente ADD COLUMN owner boolean
    GENERATED ALWAYS AS (perfil = 'owner') STORED;

INSERT INTO schema_migracao (versao, aplicada_em, descricao)
VALUES ('025', now(), 'atendente.owner passa a ser derivado de perfil');
