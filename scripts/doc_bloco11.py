"""Documentacao do Bloco 11 — o log de acoes na conversa (15/10)."""
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent

MODELO_02 = """
### `mensagem.evento` — o log de ações da conversa (migração 064, 15/10)

🔵 *"log dentro da conversa interno apenas sobre ações de transfernecia,
inserir pessoas, etc, pode ser em Nota interna do Movizap"*.

| Campo | O quê |
|---|---|
| `mensagem.evento` | `text`, nulo em mensagem comum. Lista fechada no CHECK `ck_evento_conhecido`: `assumiu`, `entrou`, `convidou`, `saiu`, `removeu`, `devolveu`, `transferiu`, `encerrou`, `vinculou`, `desvinculou`, `mudou_tipo`, `bloqueou`, `desbloqueou` |

- 🚨 **É COLUNA, E NÃO UM `tipo` NOVO.** O CHECK `ck_nota_e_interna` amarra
  `tipo = 'nota'` a `direcao = 'interna'` **nos dois sentidos**: um
  `tipo = 'sistema'` interna seria recusado, e afrouxar esse CHECK abriria a
  porta para uma nota vazar como mensagem de saída. O evento **é** nota
  interna, com uma marca a mais — e `ck_evento_e_nota_interna` garante isso no
  banco, não na confiança do código.
- 🚨 **`autor = 'sistema'`**, nunca `'atendente'`: a frase foi escrita pelo
  sistema, em nome de quem agiu. Quem agiu vai em `atendente_id`.
- 🚨 **Evento não se edita nem se apaga.** A recusa mora em
  `conversas._minha_nota`, o único caminho de editar e apagar nota. Ela é
  obrigatória porque o `atendente_id` do evento é de quem agiu — sem a recusa
  explícita, essa pessoa passaria no teste "só quem escreveu pode editar".
- ⚠️ **Nada retroativo**, decisão declarada: transferência, encerramento e
  convite dariam para reconstituir, mas **vínculo e tipo não têm histórico**, e
  log pela metade com data inventada engana mais do que log que começa hoje.
- ⚠️ **Não conta como não lida**: só `direcao = 'entrada'` conta, e nota nunca
  contou.
- Índice parcial `ix_mensagem_evento (conversa_id, id) WHERE evento IS NOT NULL`,
  para quem quiser só o log de um atendimento.

🚨 **A armadilha que isto custou, medida em 15/10 com `faulthandler`:** gravar o
evento pedindo uma **conexão nova** dentro de um `with banco.cursor()` ainda
aberto **trava para sempre**. A `INSERT INTO mensagem` tem FK para `conversa` e
precisa de trava na linha da conversa, que a transação do chamador já segura:
uma sessão espera a outra, que espera a primeira, e o Postgres não vê deadlock
porque só há **um** esperando. Não é o pool (`max_size=8`, `timeout=10`: falta
de conexão daria erro em 10 s). Por isso `registrar_evento` aceita `cur`, e
quem chama de dentro de uma transação **tem de passar**. Com `cur`, um erro no
log abortaria a transação da ação inteira — daí o **SAVEPOINT**: falha de log
desfaz só o log.
"""

TELAS_06 = """

## ATD_1.2 — o log de ações na conversa (Bloco 11, 15/10)

🔵 *"ao final proponha log dentro da conversa interno apenas sobre ações de
transfernecia, inserir pessoas, etc, pode ser em Nota interna do Movizap"*.

Treze ações passam a deixar **uma linha** na conversa, no ponto do tempo em que
aconteceram: assumir, entrar, convidar, sair, remover alguém, devolver à fila,
transferir, encerrar, vincular, desvincular, mudar o tipo, bloquear e
desbloquear.

🚨 **LINHA, NÃO BALÃO.** Como balão o log entraria no fio com o mesmo peso do
que o cliente escreveu, ganharia o menu de editar e apagar, e a conversa viraria
metade conversa e metade log. Como linha discreta (ícone, quem fez, o que fez,
hora à direita) ele se lê de relance e se ignora de relance.

- **A frase vem do servidor**, nunca montada na tela: montá-la aqui faria o
  mesmo log ter dois textos quando esta tela mudasse, e o histórico não se
  reescreve junto com o frontend.
- **Evento que a tela não reconhece ainda aparece**, com um ponto no lugar do
  ícone. Tela que esconde o que não entende mente por omissão.
- **Sem os fios do separador de dia**: separador de dia aparece uma vez por
  dia; evento, várias vezes por atendimento. Com dois traços cada, o fio da
  conversa viraria uma escada.
- No celular a hora sai da linha — ali o que importa é o que aconteceu.
- **Transferência agora deixa rastro mesmo sem resumo.** A nota de resumo
  (23/09) só é gravada quando há resumo; até hoje, transferir sem escrever nada
  não deixava nenhuma marca na conversa. O evento e a nota de resumo são coisas
  diferentes e os dois continuam: a nota é o texto que quem assume precisa ler,
  o evento é o log.

**Provado:** 14 testes em `tests/teste_eventos_conversa.py` (cada ação, a
recusa de editar e apagar o evento, nota comum continuando editável, não contar
como não lida) e 8 em `frontend/src/eventos_1510.teste.js`.

⚠️ **Um teste que eu tive de desfazer:** a primeira versão chamava
`conversas.bloquear()`, que fala com a **API do WhatsApp de verdade** — a suíte
ficou pendurada nas retentativas de rede e o `timeout` teve de derrubar. Pior:
ia além de ler produção, ia tentar bloquear um número. Hoje o teste prova que
os dois eventos existem para o banco, e diz por escrito que quem prova o resto
é bloquear um número na tela.
"""


def juntar(rel: str, texto: str, marca: str, ancora: str | None = None):
    caminho = RAIZ / rel
    atual = caminho.read_text(encoding="utf-8")
    if marca in atual:
        print(f"ja documentado: {rel}")
        return
    if ancora:
        if atual.count(ancora) != 1:
            raise SystemExit(f"ancora {atual.count(ancora)}x em {rel}")
        novo = atual.replace(ancora, texto + "\n" + ancora, 1)
    else:
        novo = atual.rstrip("\n") + "\n" + texto
    caminho.write_text(novo, encoding="utf-8")
    print(f"documentado: {rel}")


juntar("docs/02_Modelo_Dados.md", MODELO_02, "mensagem.evento")
juntar("docs/06_Conteudo_das_Telas.md", TELAS_06, "o log de ações na conversa")
