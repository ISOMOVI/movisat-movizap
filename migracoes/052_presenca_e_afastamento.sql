-- ============================================================================
-- MoviZap — migração 052: status por tempo, "sempre online", afastamento e a
-- mensagem de fim de expediente
--
-- 🔵 Pedidos dele em 24/09:
--   · *"painel de regra de tempo por status, igual ao MSN = 15min sem interação
--     -Ausente; 1h sem interação Offline"*, contando SÓ ação de atendimento;
--   · *"Não é possivel receber conversa se estiver offline"*;
--   · *"Para o owner, pode ter o status para marcar 'sempre online' - dentro da
--     jornada que o owner tbm terá, mas será exclusivo dele"*;
--   · o modal obrigatório de transferência *"somente em caso de férias ou algo
--     do tipo"*;
--   · *"fim do expediente não transfere, só informará mensagem pronta"*, com
--     texto em branco e flag *"ativar" ou "não"*.
--
-- 🚨 ISTO DERRUBA UMA REGRA DE 17/09: *"offline é escolhido, não deduzido"*
-- (044). Quem manda agora é a decisão dele. O que sobrevive da regra antiga é
-- `estado_automatico`: o sistema só DESFAZ o que ele mesmo fez. Status escolhido
-- à mão nunca volta sozinho para "disponível".
-- ============================================================================

BEGIN;

-- A última AÇÃO DE ATENDIMENTO (enviar, abrir, assumir, transferir, concluir).
-- NULL = nunca agiu desde que a regra existe; ao ligar a regra, vira "agora".
ALTER TABLE atendente ADD COLUMN ultima_acao_em timestamptz;

-- true = o estado atual foi posto pela regra de tempo, e a próxima ação o
-- desfaz (volta a "disponível"). false = foi a pessoa (ou o owner) quem pôs.
ALTER TABLE atendente ADD COLUMN estado_automatico boolean NOT NULL DEFAULT false;

-- Exclusivo do owner: dentro da jornada dele, a regra de tempo não o toca.
ALTER TABLE atendente ADD COLUMN sempre_online boolean NOT NULL DEFAULT false;
ALTER TABLE atendente ADD CONSTRAINT ck_sempre_online_so_owner
    CHECK (NOT sempre_online OR perfil = 'owner');

-- Férias, licença... Quem está afastado fica offline e não recebe.
-- `afastado_ate` é informativo (a volta é um clique); pode ficar em branco.
ALTER TABLE atendente ADD COLUMN afastamento_motivo text;
ALTER TABLE atendente ADD COLUMN afastado_ate date;
ALTER TABLE atendente ADD CONSTRAINT ck_afastamento_motivo
    CHECK (afastamento_motivo IS NULL OR length(btrim(afastamento_motivo)) > 0);

-- A trava de "uma vez por período" da mensagem de fim de expediente, no mesmo
-- desenho de `boas_vindas_em`: quem ganha o UPDATE manda.
ALTER TABLE conversa ADD COLUMN fora_expediente_em timestamptz;

INSERT INTO schema_migracao (versao, aplicada_em, descricao)
VALUES ('052', now(), 'status por tempo, sempre online, afastamento, msg de fim de expediente');

COMMIT;
