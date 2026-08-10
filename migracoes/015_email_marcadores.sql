-- ============================================================================
-- MoviZap — migração 015: marcadores, e a política de armazenamento
--
-- Perguntas do usuário em 10/08: *"o armazenamento seria duplicado? talvez
-- puxarmos até 01/26? já trazer os marcadores que as contas têm bem como
-- enviados?"*. As três respostas moram aqui.
--
-- ----------------------------------------------------------------------------
-- 🚨 POR QUE O `bruto` DEIXA DE SER REGRA E VIRA EXCEÇÃO
--
-- A migração 014 justificou guardar a mensagem RFC822 inteira com a regra
-- "gravar cru antes de interpretar" -- a mesma que, em 10/08, permitiu
-- recuperar 57 mídias e 31 nomes dos webhooks do Evolution.
--
-- ⚠️ MAS A REGRA NÃO SE APLICA IGUAL AQUI, e reconhecer isso é o ponto: o
-- webhook é EFÊMERO -- o Evolution dispara uma vez e não guarda; não gravar é
-- perder para sempre. **O Gmail não é efêmero.** A mensagem continua lá e é
-- buscável pelo id quando se quiser.
--
-- Guardar tudo duplicaria um arquivo que já tem dono, e o custo é medido:
-- ~1.800 e-mails/ano custam ~9 MB em metadados+texto, ~27 MB com html, e
-- ~360 MB com bruto e anexos. O banco inteiro tem 16 MB hoje.
--
-- A POLÍTICA, então:
--   metadados + texto + html  -> SEMPRE (é o que a tela desenha, e é barato)
--   anexo (bytes)             -> NUNCA  (guarda-se nome/tamanho/tipo; o
--                                        arquivo vem do Gmail no clique)
--   bruto                     -> só quando a mensagem for atendida
--
-- ----------------------------------------------------------------------------
-- CORTE DE HISTÓRICO
--
-- Decisão do usuário: puxar a partir de 01/2026. E-mail velho não é
-- atendimento, é arquivo -- e arquivo já tem lugar. O corte também torna a
-- primeira carga previsível, em vez de depender da idade da caixa.
--
-- ⚠️ Fica na CONTA, não em constante no código: caixas diferentes podem
-- querer cortes diferentes, e mudar um corte não pode exigir deploy.
--
-- ----------------------------------------------------------------------------
-- MARCADORES
--
-- São a navegação lateral da tela -- sem eles ela vira lista cronológica sem
-- estrutura. Enviados entra junto: sem ele se lê metade da conversa.
--
-- 🚨 O id do marcador é do PROVEDOR. Nomes mudam ("Financeiro" vira "Fin"),
-- ids não. Casar por nome faria a tela perder a caixa inteira numa renomeação.
-- ============================================================================

ALTER TABLE email_conta ADD COLUMN IF NOT EXISTS puxar_desde date;
COMMENT ON COLUMN email_conta.puxar_desde IS
    'Não lê mensagem anterior a esta data. NULL = sem corte. Decisão de 10/08: 2026-01-01.';

ALTER TABLE email_conta ADD COLUMN IF NOT EXISTS guardar_bruto boolean NOT NULL DEFAULT false;
COMMENT ON COLUMN email_conta.guardar_bruto IS
    'O Gmail não é efêmero: o bruto é refetchável. Só se guarda no que for atendido.';

-- Anexo: o QUE existe, nunca os bytes.
ALTER TABLE email_mensagem ADD COLUMN IF NOT EXISTS anexos jsonb NOT NULL DEFAULT '[]'::jsonb;
COMMENT ON COLUMN email_mensagem.anexos IS
    'Lista de {nome, tamanho, mime, id_externo}. Os bytes ficam no Gmail e '
    'vêm sob demanda -- guardar anexo aqui é o que multiplicaria o banco por 20.';

CREATE TABLE IF NOT EXISTS email_marcador (
    id           bigserial PRIMARY KEY,
    conta_id     bigint NOT NULL REFERENCES email_conta(id) ON DELETE CASCADE,
    -- 🚨 O id do provedor manda. Nome muda; id não.
    id_externo   text NOT NULL,
    nome         text NOT NULL,
    -- 'sistema' = INBOX, SENT, DRAFT, TRASH... 'usuario' = criados por gente.
    natureza     text NOT NULL DEFAULT 'usuario'
                 CHECK (natureza IN ('sistema', 'usuario')),
    cor          text,
    ordem        integer NOT NULL DEFAULT 0,
    UNIQUE (conta_id, id_externo)
);

CREATE TABLE IF NOT EXISTS email_mensagem_marcador (
    mensagem_id  bigint NOT NULL REFERENCES email_mensagem(id) ON DELETE CASCADE,
    marcador_id  bigint NOT NULL REFERENCES email_marcador(id) ON DELETE CASCADE,
    PRIMARY KEY (mensagem_id, marcador_id)
);

-- Postgres não indexa FK sozinho, e a tela lê SEMPRE por marcador.
CREATE INDEX IF NOT EXISTS ix_email_msg_marcador_marcador
    ON email_mensagem_marcador (marcador_id);

INSERT INTO schema_migracao (versao, aplicada_em, descricao)
VALUES ('015', now(), 'Marcadores do e-mail e política de armazenamento');
