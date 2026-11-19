-- ===========================================================================
-- MoviZap — migração 115: o card anda, e a escrita vai para fila
-- ===========================================================================
--
-- 🔵 Decisão dele, 18/11: *"assim op não para de trabalhar e seguimos no
-- background com a OS"*. E, sobre o atraso de leitura, ele escolheu a fila em
-- vez de só trocar o texto da recusa: quer o conserto, não o aviso.
--
-- 🚨 O DEFEITO, MEDIDO NA OS 17133 EM 18/11. A mesma rota do Harmonit, na
-- mesma OS, sem nenhuma escrita entre as duas leituras:
--
--     11:42:47  devolveu 251   -> o painel recusou como "alguem mudou no meio"
--     11:43:18  devolveu 16488 -> a passagem seguinte funcionou
--
-- Das 11:17 às 11:42 ela respondeu **o valor que escrevemos às 09:42**,
-- ignorando o de 09:49. Sete recusas, todas falsas, e o operador clicando
-- porque nada acontecia.
--
-- 🚨 A DISTINÇÃO QUE FAZ A FILA SER SEGURA: o valor que o ERP devolveu é um
-- valor que **nós** já escrevemos nesta OS?
--
--   · é NOSSO de antes      -> a leitura dele atrasou. O card anda, a escrita
--                              vai para fila, e a fila insiste até o ERP se
--                              acertar. É a causa `leitura_atrasada`.
--   · nunca escrevemos      -> alguém mexeu na OS dentro do Harmonit. **RECUSA**,
--                              como hoje, e o operador recarrega: o ERP é quem
--                              está certo. (É o mesmo discernimento da
--                              migração 114, do lado da auditoria.)
--
-- ⚠️ **POR QUE FILA E NÃO GRAVAR NA HORA.** `_corpo_de_escrita`, no FPSL,
-- remonta a OS inteira a partir da leitura. Gravar sobre uma leitura atrasada
-- escreveria valores velhos nos 30 campos escalares da OS -- perderia edição
-- feita no ERP nas últimas horas. 🔵 É a decisão dele de *"aborta e não
-- escreve"* aplicada ao atraso.
--
-- 🚨 **A FILA SÃO LINHAS, NÃO MEMÓRIA**: reinício não pode perder escrita. Por
-- isso ela mora na `os_passagem`, que já é o registro de *"quem faz o que
-- SEMPRE"* -- e não numa tabela nova, que seria um segundo lugar para a mesma
-- verdade.

BEGIN;

ALTER TABLE os_passagem
    -- 🚨 NULO = não está na fila. Esta coluna é o que faz o card andar: a
    -- coluna do painel passa a sair daqui, e não do cache do FPSL, até a
    -- escrita ser confirmada.
    ADD COLUMN IF NOT EXISTS pendente_desde timestamptz,
    ADD COLUMN IF NOT EXISTS tentativas integer NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS pendente_erro text,
    -- Quando saiu da fila, para qualquer lado. ⚠️ Serve para a red flag saber
    -- o que já foi resolvido e não avisar duas vezes.
    ADD COLUMN IF NOT EXISTS resolvida_em timestamptz,
    ADD COLUMN IF NOT EXISTS avisada_em timestamptz;

-- A fila, mais antiga primeiro. 🚨 Índice parcial: o que interessa é o punhado
-- de linhas pendentes, não as 100 passagens que já se resolveram.
CREATE INDEX IF NOT EXISTS os_passagem_pendente_idx
    ON os_passagem (pendente_desde)
 WHERE pendente_desde IS NOT NULL AND resolvida_em IS NULL;

-- 🚨 UMA PENDENTE POR OS. Duas na mesma OS seriam duas verdades sobre em que
-- coluna o card está -- e a tela teria de escolher uma sem critério.
CREATE UNIQUE INDEX IF NOT EXISTS os_passagem_uma_pendente_por_os
    ON os_passagem (numero_os)
 WHERE pendente_desde IS NOT NULL AND resolvida_em IS NULL;

COMMENT ON COLUMN os_passagem.pendente_desde IS
    'Quando esta passagem entrou na fila. NULO = nao esta na fila. Enquanto '
    'preenchido, a coluna do card sai DAQUI e nao do cache do FPSL -- e o card '
    'carrega o selo dizendo que a OS ainda nao confirmou.';
COMMENT ON COLUMN os_passagem.pendente_erro IS
    'O ultimo retorno do Harmonit para esta pendencia, em frase -- nao o '
    'diagnostico cru. E o que a tela mostra no selo.';

INSERT INTO schema_migracao (versao, aplicada_em, descricao)
VALUES ('115', now(), 'o card anda na hora e a escrita vai para fila quando a leitura do Harmonit esta atrasada (causa leitura_atrasada, OS 17133); a fila sao linhas na propria os_passagem');

COMMIT;
