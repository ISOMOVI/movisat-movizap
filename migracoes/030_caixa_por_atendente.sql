-- ============================================================================
-- MoviZap — migração 030: a caixa de e-mail tem dono
--
-- 🚨 ANTECIPADA DO BLOCO 6 POR UM MOTIVO CONCRETO. O usuário avisou em 25/08
-- que outra pessoa vai entrar no painel "depois de hoje". Medido antes de
-- escrever isto: os 5 atendentes têm perfil que dá `EML_1.1`, e
-- `GET /api/email/mensagens` NÃO FILTRA POR CONTA -- então o próximo login
-- abriria a caixa do owner inteira, 336 mensagens, para quem entrasse.
--
-- Não é crash, não trava o acesso: é pior, porque funciona.
--
-- ----------------------------------------------------------------------------
-- O MODELO É O QUE O USUÁRIO DESCREVEU EM 25/08
--
--   "se estou logado nela, é a caixa 1, a outra aba deve adicionar outras
--    caixas mesmo que sejam iguais também, passando pelo auth, normal"
--
-- Ou seja: a caixa pertence a QUEM A CONECTOU, e duas pessoas podem conectar
-- o MESMO endereço -- cada uma com o seu consentimento e o seu refresh token.
-- A Erika liga o `sac@` na aba 2 dela; a Karla pode ligar o mesmo `sac@` na
-- dela. São duas linhas.
--
-- 🚨 POR ISSO O UNIQUE DE `endereco` SAI. Ele foi escrito em 14/08 quando só
-- havia uma caixa, e é ele que impediria a segunda pessoa a conectar o mesmo
-- endereço -- com erro de banco, no meio do OAuth, sem explicação na tela.
-- No lugar entra UNIQUE (atendente_id, endereco): a mesma pessoa não conecta
-- a mesma caixa duas vezes, que é a duplicidade que realmente atrapalha.
--
-- ⚠️ O CUSTO, DECLARADO: duas pessoas com o mesmo endereço = duas contas
-- sincronizadas = a mesma mensagem guardada duas vezes (o UNIQUE de
-- `email_mensagem` é por `(conta_id, id_externo)`, e continua certo assim).
-- É o preço de "cada um vê a que logou", e o usuário escolheu esse modelo
-- sabendo que as caixas podem ser iguais. Se um dia o volume incomodar, o
-- conserto é caixa compartilhada com tabela de acesso -- e aí é decisão dele,
-- não otimização minha.
--
-- ----------------------------------------------------------------------------
-- QUEM FICA COM A CAIXA QUE JÁ EXISTE
--
-- Uma só hoje: `iago@movisat.com.br`. Ela casa por e-mail com o atendente 121,
-- que é o dono -- exatamente o "se estou logado nela, é a caixa 1". O segundo
-- UPDATE é a rede: caixa que não casar com ninguém vai para o owner, porque
-- caixa sem dono ficaria invisível para todo mundo depois do filtro entrar.
-- ============================================================================

ALTER TABLE email_conta ADD COLUMN IF NOT EXISTS atendente_id bigint
    REFERENCES atendente(id);

COMMENT ON COLUMN email_conta.atendente_id IS
    'Quem conectou esta caixa. É por aqui que a EML_1.1 decide o que mostrar. '
    'Duas pessoas podem conectar o mesmo endereço: são duas linhas.';

UPDATE email_conta c
   SET atendente_id = a.id
  FROM atendente a
 WHERE lower(a.email) = lower(c.endereco)
   AND c.atendente_id IS NULL;

UPDATE email_conta
   SET atendente_id = (SELECT id FROM atendente
                        WHERE owner AND ativo ORDER BY id LIMIT 1)
 WHERE atendente_id IS NULL;

ALTER TABLE email_conta ALTER COLUMN atendente_id SET NOT NULL;

ALTER TABLE email_conta DROP CONSTRAINT IF EXISTS email_conta_endereco_key;
ALTER TABLE email_conta ADD CONSTRAINT ux_email_conta_dono
    UNIQUE (atendente_id, endereco);

-- A tela lê "as minhas caixas ativas" a cada carregamento.
CREATE INDEX IF NOT EXISTS ix_email_conta_atendente
    ON email_conta (atendente_id) WHERE ativa;

INSERT INTO schema_migracao (versao, aplicada_em, descricao)
VALUES ('030', now(), 'caixa de e-mail pertence a quem a conectou');
