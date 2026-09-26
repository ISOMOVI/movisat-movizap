-- ============================================================================
-- MoviZap — migração 060: o agente de ligações ganha porta própria (Plano 5.1)
--
-- 🔵 Pedido dele (25/09): *"talvez usar uma porta para o serviço? com o shell
-- autenticado? uma saída segura que poderia ter o nginx específico para não
-- misturar outro?"* -- e, nas decisões: há PC FORA do escritório, então o IP
-- não serve de filtro e entra o certificado de cliente (mTLS) por PC.
--
-- O agente passa a falar com `ligacoesmicrosip.movisat.com.br` (nginx próprio,
-- `ssl_verify_client on`) e o app da porta 8010 confere as DUAS provas juntas:
-- a chave (hash) e o certificado, amarrados ao MESMO agente.
--
--   · `cert_sha256`: SHA-256 do certificado (DER) emitido pela CA própria
--     para aquele PC. Único: um certificado é de um agente só.
--   · `cert_validade`: quando ele vence (o alerta avisa 30 dias antes).
--   · `ultimo_ip`: de onde o PC falou por último (escritório ou fora).
--   · `ultimo_aviso`: o diagnóstico do agente que não é erro mas pede olho
--     (gravação automática desligada, disco quase cheio, arquivo pulado).
--
-- 🚨 Só acrescenta. As rotas antigas do painel seguem valendo até o PC dele
-- provar o caminho novo.
-- ============================================================================

BEGIN;

ALTER TABLE agente_ligacao
    ADD COLUMN cert_sha256   text,
    ADD COLUMN cert_validade timestamptz,
    ADD COLUMN ultimo_ip     text,
    ADD COLUMN ultimo_aviso  text;

CREATE UNIQUE INDEX ux_agente_ligacao_cert ON agente_ligacao (cert_sha256)
    WHERE cert_sha256 IS NOT NULL;

ALTER TABLE agente_ligacao
    ADD CONSTRAINT ck_agente_ligacao_cert_hex
    CHECK (cert_sha256 IS NULL OR cert_sha256 ~ '^[0-9a-f]{64}$');

INSERT INTO schema_migracao (versao, aplicada_em, descricao)
VALUES ('060', now(), 'agente de ligacoes: certificado de cliente, ultimo IP e aviso');

COMMIT;
