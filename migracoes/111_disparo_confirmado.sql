-- ============================================================================
-- MoviZap — migração 111: o disparo da etapa passa a ser CONFIRMADO, e a
--                         decisão fica gravada na própria passagem
--
-- 🔵 DECISÃO DELE, 17/11: *"quando o card for movido e houver disparo de
--   mensagens perguntar em caixa de diálogo (se tiver ligado o interruptor)
--   'Deseja enviar aviso ao cliente?' Se Sim = abre a mensagem que será
--   enviada e permite edição rápida dela e o botão enviar envia (...) Se
--   clicar não, não envia nada."* E, perguntado: clicar "Não" **registra no
--   card**.
--
-- 🚨 ISTO INVERTE, COM AUTORIZAÇÃO, A DECISÃO DE 11/11. Lá ele disse *"ao
--   ligar o interruptor, sairá automaticamente como na regra"*, e a migração
--   102 nasceu assim. O interruptor passa a significar **"pergunta"**, não
--   **"manda"** -- o que restaura a régua da Área F de 04/11 (confirmar antes
--   de cada envio), que a 102 havia afrouxado de propósito. Está escrito aqui
--   para ninguém "consertar" de volta achando que é engano.
--
-- 🚨 A DECISÃO MORA NA PASSAGEM, e não numa tabela nova: a `os_passagem`
--   (migração 083) já é UMA LINHA POR MOVIMENTO, e o disparo é consequência de
--   um movimento -- um para um. Tabela separada criaria duas versões do mesmo
--   fato, e a pergunta "este movimento avisou o cliente?" passaria a ter dois
--   lugares para discordar.
--
-- 🚨 E É ESTA LINHA QUE VIRA A TRAVA DE REENVIO. Mover duas vezes para a mesma
--   etapa são DUAS passagens e podem ser dois avisos (é movimento novo, fato
--   novo); mas a MESMA passagem decide uma vez só. Sem isto, recarregar a tela
--   ou clicar duas vezes mandaria a mesma mensagem duas vezes ao cliente --
--   irreversível.
--
-- ⚠️ O texto gravado é o que SAIU, já editado pelo operador e com as chaves
--   resolvidas, e não o molde da `etapa_mensagem`: o molde muda depois, e aí a
--   linha deixaria de dizer o que o cliente leu.
-- ============================================================================

BEGIN;

ALTER TABLE os_passagem
    ADD COLUMN IF NOT EXISTS disparo_em          timestamptz,
    ADD COLUMN IF NOT EXISTS disparo_recusado_em timestamptz,
    ADD COLUMN IF NOT EXISTS disparo_texto       text,
    ADD COLUMN IF NOT EXISTS disparo_por         bigint REFERENCES atendente(id);

-- 🚨 UMA DECISÃO POR PASSAGEM: enviado **ou** recusado, nunca os dois. Sem o
-- CHECK, uma corrida entre dois cliques deixaria a linha afirmando as duas
-- coisas, e aí nenhuma das duas seria confiável.
-- ⚠️ `ADD CONSTRAINT` não tem `IF NOT EXISTS` no Postgres -- daí o bloco.
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint
                    WHERE conname = 'os_passagem_disparo_uma_decisao') THEN
        ALTER TABLE os_passagem
            ADD CONSTRAINT os_passagem_disparo_uma_decisao
            CHECK (disparo_em IS NULL OR disparo_recusado_em IS NULL);
    END IF;
END $$;

COMMENT ON COLUMN os_passagem.disparo_em IS
  'Quando o aviso da etapa foi enviado ao cliente, por decisão do operador na caixa de diálogo (migração 111). Nulo = não foi enviado.';
COMMENT ON COLUMN os_passagem.disparo_recusado_em IS
  'Quando o operador respondeu NÃO à caixa de diálogo. Nulo = não recusou (pode ser que nem tenha sido perguntado).';
COMMENT ON COLUMN os_passagem.disparo_texto IS
  'O texto que SAIU, já editado e com as chaves resolvidas -- não o molde da etapa_mensagem, que muda depois.';
COMMENT ON COLUMN os_passagem.disparo_por IS
  'Quem decidiu enviar ou não enviar. A autoria fica à vista, como no apagar de observação (11/11).';

INSERT INTO schema_migracao (versao, aplicada_em, descricao)
VALUES ('111', now(), 'o disparo da etapa passa a ser confirmado em caixa de dialogo e a decisao fica gravada na passagem');

COMMIT;
