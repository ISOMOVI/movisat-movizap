-- 099 — o campo de texto por etapa: Rastreamento e Devolução
--
-- 🔵 Pedido dele (11/11), duas vezes com a mesma forma:
--   · *"Enviar por correio - Abaixo de 'Observações', criar um campo de texto
--     chamado 'Rastreamento' que é onde a operadora irá colocar o código de
--     rastreamento que será enviado ao cliente"*;
--   · *"Aguardando devolução - Abaixo de 'Observações', criar um campo de texto
--     chamado 'Devolução' (...) Apenas para consulta interna da operadora."*
--
-- 🚨 UMA TABELA PARA OS DOIS, e não duas colunas na OS. O terceiro campo por
-- etapa vai aparecer -- ele já pediu dois no mesmo bloco --, e coluna por
-- pedido é como nasce tabela larga que ninguém sabe ler. A chave é texto, e o
-- que cada chave significa mora no código (`movizap/campo_etapa.py`), onde dá
-- para ler a regra junto.
--
-- 🚨 NUNCA SE DÁ `UPDATE`: cada gravação é uma LINHA NOVA, e o valor de agora é
-- o mais recente. É a régua da casa (a `os_observacao` não se reescreve, o
-- `checklist_item` desmarcado não se apaga): a operadora que troca o código de
-- rastreio não apaga o anterior, que pode já ter ido para o cliente.
--
-- 🚨 A CHAVE É `numero_os`, como na `os_observacao` e no `checklist_item` --
-- e NÃO a solicitação. Amarrar na solicitação deixaria sem onde escrever toda
-- OS que nasceu no ERP, que é a maioria.
--
-- ⚠️ SEM FK PARA A OS: não existe tabela de OS nossa (a OS vive no Harmonit e
-- o cache é do FPSL, outro banco). É o mesmo desenho da `os_observacao` e da
-- `os_passagem`.

BEGIN;

CREATE TABLE IF NOT EXISTS os_campo_da_etapa (
  id           BIGSERIAL PRIMARY KEY,
  numero_os    INTEGER     NOT NULL,
  chave        TEXT        NOT NULL,
  valor        TEXT        NOT NULL,
  atendente_id INTEGER     REFERENCES atendente(id) ON DELETE SET NULL,
  em           TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT os_campo_valor_check CHECK (btrim(valor) <> ''),
  -- ⚠️ Teto curto de propósito: é código de rastreio, não recado. Quem precisa
  -- escrever um parágrafo tem a observação, que aceita 4000.
  CONSTRAINT os_campo_valor_tamanho CHECK (length(valor) <= 120),
  CONSTRAINT os_campo_chave_check CHECK (chave IN ('rastreio', 'devolucao'))
);

COMMENT ON TABLE os_campo_da_etapa IS
  'Campo de texto que a etapa do painel da Operacao pede (rastreio, devolucao). '
  'Uma LINHA POR GRAVACAO: o valor de agora e o mais recente, e o anterior fica '
  'como historico -- codigo de rastreio trocado pode ja ter ido para o cliente.';
COMMENT ON COLUMN os_campo_da_etapa.chave IS
  'rastreio = etapa 677 (Enviar por correio/transportadora), vai ao cliente. '
  'devolucao = etapa 15696 (Aguardando devolucao), CONSULTA INTERNA -- decisao '
  'dele em 11/11, e e por isso que as duas nao sao a mesma chave.';
COMMENT ON COLUMN os_campo_da_etapa.atendente_id IS
  'Quem escreveu. 🚨 Nulo e legitimo: atendente apagado nao pode levar o '
  'registro do codigo (ON DELETE SET NULL).';

-- A leitura do valor de agora: o mais recente por (OS, chave).
CREATE INDEX IF NOT EXISTS idx_campo_etapa_atual
  ON os_campo_da_etapa (numero_os, chave, em DESC, id DESC);

INSERT INTO schema_migracao (versao, aplicada_em, descricao)
VALUES ('099', now(), 'campo de texto por etapa da Operacao: rastreio (677) e devolucao (15696)');

COMMIT;
