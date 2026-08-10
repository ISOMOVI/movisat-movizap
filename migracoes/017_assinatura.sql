-- ============================================================================
-- MoviZap — migração 017: assinatura de e-mail por atendente
--
-- Decisão do usuário em 10/08: *"no cadastro do atendente um campo para
-- subirmos a assinatura que será utilizada nos e-mails enviados daquele
-- usuário"*. E: o e-mail sempre sai do endereço do cadastro do atendente.
--
-- ----------------------------------------------------------------------------
-- 🚨 A ASSINATURA DO GMAIL NÃO SE APLICA AQUI
--
-- O Gmail insere a assinatura no COMPOSITOR DA WEB. A API envia exatamente o
-- MIME que a gente monta -- nada é acrescentado por ela. Sem esta coluna, todo
-- e-mail enviado pelo painel sairia pelado, e ninguém entenderia por quê:
-- "mas está configurada no Gmail".
--
-- ----------------------------------------------------------------------------
-- POR QUE HTML, E NÃO UM EDITOR NO PAINEL
--
-- `assinatura_html` guarda o HTML colado da assinatura que a pessoa já usa --
-- com logo, links e formatação. Um editor de texto rico no painel teria que
-- reproduzir o que o Gmail já faz melhor, e a assinatura sairia diferente da
-- que o cliente está acostumado a ver.
--
-- ----------------------------------------------------------------------------
-- A IMAGEM: CAMINHO, NUNCA BYTES
--
-- 🚨 `assinatura_imagem` guarda o CAMINHO do arquivo no disco, como a tabela
-- `midia` faz. Guardar bytes no banco engorda backup e dump para sempre --
-- e a lição de 10/08 (32,7 MB de base64 tirados do webhook_evento) é recente
-- demais para repetir na semana seguinte.
--
-- ⚠️ A imagem viaja EMBUTIDA no e-mail (anexo inline, referenciado por CID),
-- não por link. Link `https://` depende do destinatário liberar imagens
-- externas -- e muita gente vê um quadrado vazio. `data:` URI o Gmail remove.
-- ============================================================================

ALTER TABLE atendente ADD COLUMN IF NOT EXISTS assinatura_html text;
COMMENT ON COLUMN atendente.assinatura_html IS
    'HTML colado da assinatura. A do Gmail não se aplica a envio por API.';

ALTER TABLE atendente ADD COLUMN IF NOT EXISTS assinatura_imagem text;
COMMENT ON COLUMN atendente.assinatura_imagem IS
    'Caminho do arquivo no disco (nunca os bytes). Viaja embutida no e-mail '
    'como anexo inline (CID) -- link externo o destinatário pode não carregar.';

INSERT INTO schema_migracao (versao, aplicada_em, descricao)
VALUES ('017', now(), 'Assinatura de e-mail por atendente');
