-- ===========================================================================
-- 065 — "VISTO POR" na nota interna (Bloco 12, 15/10)
-- ---------------------------------------------------------------------------
-- 🔵 Pedido dele: *"verifique a possibilidade de confirmação de leitura das
-- notas dentro da conversa ... um icone que ao clicar mostra que ja leu aquela
-- nota, junto ao carimbo de data e hora, bem pequeno mesmo"*. Aprovado em
-- 15/10 ("o 3 pode seguir").
--
-- 🚨 O RÓTULO É "VISTO POR", E NÃO "LEU". O sistema sabe que a nota ESTEVE NA
-- TELA de alguém; não sabe que a pessoa leu. Esta é a ressalva que eu não
-- contorno: um recurso que afirma "leu" transforma uma suposição em prova, e
-- alguém vai cobrar com base nisso.
--
-- 🚨 MARCA QUANDO A NOTA APARECE NA TELA, não quando a conversa é aberta.
-- Abrir uma conversa de 200 mensagens e não rolar até o fim não é ver a nota
-- que está lá atrás -- e carimbar isso seria inventar o dado.
--
-- ⚠️ NOTA ANTERIOR A HOJE NÃO TEM REGISTRO, e a tela tem de DIZER ISSO. Lista
-- vazia numa nota de setembro significa "não havia registro", nunca "ninguém
-- viu" -- e é por isso que o backend devolve, por nota, se ela é do tempo em
-- que se registra.
--
-- ⚠️ A conversa é COLETIVA e não tinha nenhuma noção de leitura por mensagem.
-- Quem tem marcador é o chat interno, e lá é marca d'água por sala
-- (`chat_membro.lido_ate`), não por mensagem. Por isso tabela nova, e por isso
-- ela só vale para NOTA.
-- ===========================================================================

CREATE TABLE IF NOT EXISTS nota_leitura (
  mensagem_id   bigint      NOT NULL REFERENCES mensagem(id) ON DELETE CASCADE,
  atendente_id  bigint      NOT NULL REFERENCES atendente(id) ON DELETE CASCADE,
  visto_em      timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (mensagem_id, atendente_id)
);

-- A PK já serve a "quem viu esta nota". Este índice serve ao caminho oposto,
-- que vem depois: "o que esta pessoa já viu".
CREATE INDEX IF NOT EXISTS ix_nota_leitura_atendente
    ON nota_leitura (atendente_id, visto_em DESC);

INSERT INTO schema_migracao (versao, aplicada_em, descricao)
VALUES ('065', now(), 'visto por: quem teve a nota interna na tela (Bloco 12)');

-- ----------------------------------------------------------------------------
-- DESFAZER, se precisar:
--   DROP TABLE nota_leitura;          -- 🚨 isto APAGA o registro de quem viu
--   DELETE FROM schema_migracao WHERE versao = '065';
-- ----------------------------------------------------------------------------
