-- ============================================================================
-- MoviZap — migração 014: e-mail, guardado cru antes de interpretado
--
-- Decisão do usuário em 10/08: uma tela de e-mail parecida com a do Gmail,
-- **jamais misturada com o WhatsApp**. Ela mora no MoviZap por dois motivos
-- dele: facilidade de atender, e somar cadastro -- o remetente identifica a
-- empresa, e com o tempo a pessoa por número e data do último e-mail.
--
-- ----------------------------------------------------------------------------
-- O NÚMERO QUE JUSTIFICA A TELA
--
-- Medido em 10/08: dos 944 clientes ativos, **788 têm e-mail** (83,5%) e
-- **442 têm e-mail e NENHUM WhatsApp alcançável**. O WhatsApp chega a 417
-- números; o e-mail chega a quase o dobro de clientes. Não é um canal
-- secundário -- é o que alcança quem o WhatsApp não alcança.
--
-- ----------------------------------------------------------------------------
-- 🚨 GRAVAR CRU ANTES DE INTERPRETAR
--
-- É a regra que mais pagou neste projeto. Os 722 eventos do Evolution
-- guardados inteiros desde 07/08 permitiram, em 10/08, recuperar 57 mídias,
-- 31 nomes de WhatsApp e 32 citações que os parsers da época descartavam --
-- sem pedir nada de volta a ninguém.
--
-- E-mail é pior que webhook nesse aspecto: MIME aninha, tem multipart, tem
-- charset por parte, tem anexo dentro de anexo. Qualquer parser nasce errado
-- em algum caso. `bruto` guarda a mensagem RFC822 inteira; as colunas ao lado
-- são a interpretação de hoje, e podem ser refeitas amanhã.
--
-- ⚠️ `bruto` NÃO é o corpo exibido. A tela lê `texto`/`html`; `bruto` existe
-- para reprocessar, nunca para desenhar.
--
-- ----------------------------------------------------------------------------
-- POR QUE `conta` É TABELA, E NÃO CONFIG
--
-- Uma linha por caixa lida. Hoje é uma; contato@ e financeiro@ são o caso
-- óbvio seguinte, e config com chave `email_conta_2` seria o começo de uma
-- faxina. O token do Google fica NA CONTA, não no .env: ele é por caixa e
-- expira -- é dado de operação, não configuração do sistema.
--
-- 🚨 IDENTIFICAÇÃO NÃO É ESCOLHA AUTOMÁTICA. `cliente_id` fica NULL quando o
-- remetente não casa com exatamente um cadastro -- a mesma regra da conversa
-- de WhatsApp, pela mesma razão: chutar de quem é custa mais que não saber.
-- ============================================================================

CREATE TABLE IF NOT EXISTS email_conta (
    id              bigserial PRIMARY KEY,
    endereco        text NOT NULL UNIQUE,
    nome_exibicao   text,
    -- 'gmail' hoje. O CHECK é contrato: provedor novo passa por migração,
    -- e não por alguém gravando uma string diferente sem ninguém ver.
    provedor        text NOT NULL DEFAULT 'gmail'
                    CHECK (provedor IN ('gmail')),
    -- Credencial do OAuth desta caixa. Nunca vai para o .env: é por conta,
    -- expira, e é revogável do lado do Google.
    refresh_token   text,
    token_expira_em timestamptz,
    -- Ponto de retomada da leitura. Sem isto, cada execução releria a caixa
    -- inteira -- e a segunda leitura custa o mesmo que a primeira.
    ultimo_historico text,
    ultima_leitura_em timestamptz,
    ativa           boolean NOT NULL DEFAULT true,
    criada_em       timestamptz NOT NULL DEFAULT now(),
    atualizada_em   timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS email_mensagem (
    id            bigserial PRIMARY KEY,
    conta_id      bigint NOT NULL REFERENCES email_conta(id) ON DELETE CASCADE,

    -- 🚨 IDEMPOTÊNCIA É DO BANCO, NÃO DA DISCIPLINA. Mesma lição do webhook:
    -- releitura da caixa é NORMAL, e sem esta trava a mesma mensagem viraria
    -- duas na tela. Nunca deduplicar por assunto ou data -- gente reenvia o
    -- mesmo assunto de propósito.
    id_externo    text NOT NULL,
    thread_externa text,

    remetente     text,
    remetente_nome text,
    destinatarios text,
    assunto       text,
    enviado_em    timestamptz,
    recebido_em   timestamptz NOT NULL DEFAULT now(),

    texto         text,
    html          text,
    tem_anexo     boolean NOT NULL DEFAULT false,

    -- A mensagem RFC822 inteira. É daqui que se reprocessa quando o parser
    -- de hoje estiver errado -- e ele vai estar, em algum caso.
    bruto         text,

    lida          boolean NOT NULL DEFAULT false,
    arquivada     boolean NOT NULL DEFAULT false,
    respondida_em timestamptz,

    -- Quem é, quando dá para saber com certeza. NULL é resposta honesta.
    cliente_id    bigint REFERENCES cliente(id) ON DELETE SET NULL,
    contato_id    bigint REFERENCES contato(id) ON DELETE SET NULL,

    UNIQUE (conta_id, id_externo)
);

-- 🚨 Postgres NÃO indexa chave estrangeira sozinho, e a tela lê sempre por
-- conta ordenando por data.
CREATE INDEX IF NOT EXISTS ix_email_caixa
    ON email_mensagem (conta_id, arquivada, enviado_em DESC);

-- O casamento com o cadastro é por endereço, em toda mensagem que chega.
CREATE INDEX IF NOT EXISTS ix_email_remetente
    ON email_mensagem (lower(remetente));

CREATE INDEX IF NOT EXISTS ix_email_cliente
    ON email_mensagem (cliente_id) WHERE cliente_id IS NOT NULL;

-- Casar remetente com o cadastro exige buscar `cliente.email` por igualdade
-- sem caixa. São 788 endereços e cresce; sem índice é varredura por mensagem.
CREATE INDEX IF NOT EXISTS ix_cliente_email
    ON cliente (lower(email)) WHERE email IS NOT NULL;

INSERT INTO schema_migracao (versao, aplicada_em, descricao)
VALUES ('014', now(), 'E-mail: conta e mensagem, guardadas cruas');
