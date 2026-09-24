-- ============================================================================
-- MoviZap — migração 053: e-mail de atendente é único
--
-- 🚨 ACHADO DA AUDITORIA DE 24/09. A entrada pelo Google casa por
-- `google_sub OR lower(email)`, e o e-mail NÃO era único (só o login era).
-- Com o `admin` criando contas desde a 051, dois cadastros com o mesmo e-mail
-- deixavam a conta ambígua: a entrada pegava uma linha ao acaso e, ao gravar
-- o `sub` nela, podia bater no índice único do `google_sub` e derrubar a
-- entrada do dono. Não dava owner a ninguém, mas podia tirar o acesso dele.
--
-- Medido antes de escrever: nenhum e-mail repetido na base. Se houver, este
-- índice falha ao criar -- ruidoso e reversível, que é o lado certo.
-- ============================================================================

CREATE UNIQUE INDEX ux_atendente_email ON atendente (lower(email))
    WHERE email IS NOT NULL;

INSERT INTO schema_migracao (versao, aplicada_em, descricao)
VALUES ('053', now(), 'e-mail de atendente passa a ser unico');
