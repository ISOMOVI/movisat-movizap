-- ============================================================================
-- MoviZap — migração 004: painel de demandas
--
-- Quadro simples de acompanhamento, fora do painel autenticado: quem tem o
-- link entra e interage. Mora no mesmo serviço porque o domínio e o banco já
-- existem -- subir um segundo serviço custaria nginx, porta e root para uma
-- tabela de 13 linhas.
--
-- 🚨 O link É a credencial. Por isso o token nasce longo e aleatório, e as
-- rotas do quadro NUNCA tocam nada fora destas três tabelas.
-- ============================================================================

BEGIN;

CREATE TABLE demanda_quadro (
    id        bigserial PRIMARY KEY,
    titulo    text NOT NULL,
    token     text NOT NULL UNIQUE,   -- vive na URL; é o que dá acesso
    ativo     boolean NOT NULL DEFAULT true,
    criado_em timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE demanda_frente (
    id        bigserial PRIMARY KEY,
    quadro_id bigint NOT NULL REFERENCES demanda_quadro(id) ON DELETE CASCADE,
    nome      text NOT NULL,
    contato   text,                   -- e-mail/dono da frente, quando há
    ordem     int NOT NULL DEFAULT 0
);
CREATE INDEX ix_frente_quadro ON demanda_frente (quadro_id, ordem);

-- 🚨 O encadeamento é DENTRO da frente, não no quadro inteiro (decisão do
-- usuário em 05/08): as quatro frentes andam ao mesmo tempo. Um item só
-- libera quando o de `ordem` anterior, na MESMA frente, está concluído.
CREATE TABLE demanda_item (
    id             bigserial PRIMARY KEY,
    frente_id      bigint NOT NULL REFERENCES demanda_frente(id) ON DELETE CASCADE,
    titulo         text NOT NULL,
    ordem          int NOT NULL DEFAULT 0,
    prazo          date,
    -- true = "Sem prazo ainda", gravado de propósito. Diferente de prazo
    -- NULL sem ninguém ter olhado: um é decisão, o outro é esquecimento.
    sem_prazo      boolean NOT NULL DEFAULT false,
    obs            text,
    atualizado_em  timestamptz NOT NULL DEFAULT now(),
    atualizado_por text,
    CHECK (NOT (sem_prazo AND prazo IS NOT NULL))
);
CREATE INDEX ix_item_frente ON demanda_item (frente_id, ordem);

-- Uma ou duas etapas por item. As setas do enunciado ("E-sim; Karla ->
-- Ativar e vincular; Iago") são handoff: o item só conclui quando as duas
-- fecharem.
CREATE TABLE demanda_etapa (
    id            bigserial PRIMARY KEY,
    item_id       bigint NOT NULL REFERENCES demanda_item(id) ON DELETE CASCADE,
    descricao     text NOT NULL,
    responsavel   text NOT NULL,
    ordem         int NOT NULL DEFAULT 0,
    concluida     boolean NOT NULL DEFAULT false,
    concluida_em  timestamptz,
    CHECK (concluida = (concluida_em IS NOT NULL))
);
CREATE INDEX ix_etapa_item ON demanda_etapa (item_id, ordem);

-- ---------------------------------------------------------------- semente

-- Token do link. `gen_random_uuid()` é nativo desde o PG13 e dá 122 bits de
-- aleatoriedade — sem `gen_random_bytes`, que exigiria a extensão pgcrypto e,
-- com ela, superusuário. Dois UUIDs concatenados por folga.
INSERT INTO demanda_quadro (titulo, token)
VALUES ('Comercial Interno × Externo',
        replace(gen_random_uuid()::text, '-', '')
        || replace(gen_random_uuid()::text, '-', ''));

INSERT INTO demanda_frente (quadro_id, nome, contato, ordem)
SELECT id, f.nome, f.contato, f.ordem FROM demanda_quadro,
  (VALUES
    ('Governança',                  'comercial@movisat.com.br · Rodrigo', 1),
    ('Prospecta',                    NULL,                               2),
    ('SDR / Nina',                   NULL,                               3),
    ('Reunião inteligente / Live coach', NULL,                           4)
  ) AS f(nome, contato, ordem)
WHERE titulo = 'Comercial Interno × Externo';

-- itens, na ordem em que foram ditados
INSERT INTO demanda_item (frente_id, titulo, ordem)
SELECT fr.id, i.titulo, i.ordem
FROM demanda_frente fr,
  (VALUES
    ('Governança', 'Manutenções nas bases',            1),
    ('Governança', 'Logins e acessos',                 2),
    ('Governança', 'Planos integrados',                3),
    ('Prospecta',  'Chip disparo',                     1),
    ('Prospecta',  'Teste disparo mensagens',          2),
    ('Prospecta',  'Base atual fora do prospect',      3),
    ('SDR / Nina', 'E-sim para API oficial',           1),
    ('SDR / Nina', 'Testes atendimento',               2),
    ('SDR / Nina', 'Prompt atendimento',               3),
    ('SDR / Nina', 'Configurações e registro',         4),
    ('Reunião inteligente / Live coach', 'Base clonada',       1),
    ('Reunião inteligente / Live coach', 'Firefile',           2),
    ('Reunião inteligente / Live coach', 'Controle de acessos', 3)
  ) AS i(frente, titulo, ordem)
WHERE fr.nome = i.frente;

-- etapas: uma por item, duas onde havia seta
INSERT INTO demanda_etapa (item_id, descricao, responsavel, ordem)
SELECT it.id, e.descricao, e.responsavel, e.ordem
FROM demanda_item it
JOIN demanda_frente fr ON fr.id = it.frente_id,
  (VALUES
    ('Governança', 'Manutenções nas bases',       'Manutenções nas bases',       'Rodrigo', 1),
    ('Governança', 'Logins e acessos',            'Logins e acessos',            'Rodrigo', 1),
    ('Governança', 'Planos integrados',           'Planos integrados',           'Rodrigo', 1),
    ('Prospecta',  'Chip disparo',                'Chip disparo',                'Karla',   1),
    ('Prospecta',  'Teste disparo mensagens',     'Teste disparo mensagens',     'Iago',    1),
    ('Prospecta',  'Base atual fora do prospect', 'Base atual fora do prospect', 'Iago',    1),
    ('SDR / Nina', 'E-sim para API oficial',      'E-sim para API oficial',      'Karla',   1),
    ('SDR / Nina', 'E-sim para API oficial',      'Ativar e vincular',           'Iago',    2),
    ('SDR / Nina', 'Testes atendimento',          'Testes atendimento',          'Iago',    1),
    ('SDR / Nina', 'Testes atendimento',          'On fire',                     'Rodrigo', 2),
    ('SDR / Nina', 'Prompt atendimento',          'Prompt atendimento',          'Rodrigo', 1),
    ('SDR / Nina', 'Configurações e registro',    'Configurações e registro',    'Rodrigo', 1),
    ('Reunião inteligente / Live coach', 'Base clonada',        'Base clonada',        'Iago',    1),
    ('Reunião inteligente / Live coach', 'Firefile',            'Firefile',            'Rodrigo', 1),
    ('Reunião inteligente / Live coach', 'Firefile',            'Integração',          'Iago',    2),
    ('Reunião inteligente / Live coach', 'Controle de acessos', 'Controle de acessos', 'Iago',    1)
  ) AS e(frente, item, descricao, responsavel, ordem)
WHERE fr.nome = e.frente AND it.titulo = e.item;

-- "Base clonada - Iago - 05/08" veio com data no enunciado.
UPDATE demanda_item SET prazo = DATE '2026-08-05'
WHERE titulo = 'Base clonada';

INSERT INTO schema_migracao (versao, descricao)
  VALUES ('004', 'Painel de demandas (Comercial Interno x Externo)');

COMMIT;
