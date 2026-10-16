"""Documentacao do Bloco 12 e da senha de 48 h (15/10)."""
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent

MODELO_02 = """
### `nota_leitura` — "visto por" na nota interna (migração 065, 15/10)

🔵 *"confirmação de leitura das notas dentro da conversa ... um icone que ao
clicar mostra que ja leu aquela nota, junto ao carimbo de data e hora, bem
pequeno mesmo"*.

| Tabela | O quê |
|---|---|
| `nota_leitura` | `mensagem_id`, `atendente_id`, `visto_em`. PK `(mensagem_id, atendente_id)`, que é o que faz o carimbo ser o da PRIMEIRA vez |

- 🚨 **O rótulo é "visto por", nunca "leu".** O sistema sabe que a nota esteve
  na tela de alguém; não sabe que a pessoa leu. Dizer "leu" vira prova de algo
  que não se mediu.
- 🚨 **Marca quando a nota APARECE na tela** (`IntersectionObserver`), não
  quando a conversa abre: abrir uma conversa de 200 mensagens e não rolar até o
  fim não é ver a nota de lá atrás.
- 🚨 **Nota anterior a `conversas.LEITURA_DE_NOTA_DESDE` (15/10) não é
  carimbada**, e a consulta devolve `leitura_rastreada = False` por nota. É o
  que permite à tela dizer *"sem registro"* em vez de *"ninguém viu"* — que
  seria uma afirmação falsa sobre o passado.
- ⚠️ A conversa é **coletiva** e não tinha nenhuma noção de leitura por
  mensagem. Quem tem marcador é o chat interno, e lá é marca d'água por sala
  (`chat_membro.lido_ate`), não por mensagem.
- Índice `ix_nota_leitura_atendente (atendente_id, visto_em DESC)` para o
  caminho oposto ("o que esta pessoa já viu"), que ainda não tem tela.

🚨 **O EVENTO NÃO É "A ÚLTIMA MENSAGEM" DA CONVERSA**, e isso vale para duas
consultas de `listar()`: a prévia da lista (`u.conteudo`) e a regra de **sem
dono** (02/10: "a última mensagem tem de ser de `entrada`"). Sem
`m.evento IS NULL` nas duas, convidar alguém numa conversa órfã a **tirava da
fila**, e toda conversa passaria a mostrar "assumiu a conversa" no lugar da
última fala do cliente. Achado pela suíte inteira, não por leitura.
⚠️ A exclusão é do **evento**, não da nota: nota é coisa que uma pessoa
escreveu, e vê-la na prévia informa.
"""

TELAS_06 = """

## ATD_1.2 — "visto por" na nota (Bloco 12, 15/10)

🔵 *"um icone que ao clicar mostra que ja leu aquela nota, junto ao carimbo de
data e hora, bem pequeno mesmo"*.

Um olho pequeno ao lado do carimbo da nota, com o número de pessoas que a
tiveram na tela. Clicando, a lista: nome e hora de cada uma.

- 🚨 **"Visto por", nunca "leu".** O sistema sabe que a nota esteve na tela.
- 🚨 **Marca ao aparecer**, por `IntersectionObserver`, em lote e com 1,2 s de
  espera: rolar a conversa passa por dezenas de notas, e uma requisição por
  nota seria uma rajada.
- **Falhar ao marcar não vira erro na tela:** a pessoa está lendo e não pediu
  nada; o carimbo se perde e a nota é marcada na próxima vez em que aparecer.
- **Nota anterior ao início do registro diz isso**, em vez de "ninguém viu". A
  data mora no backend; repeti-la na tela criaria uma segunda verdade.
- O observador é remontado ao trocar de conversa e quando chega mensagem nova
  (o refresh de 8 s): elemento novo não nasce observado, e sem isso o recurso
  pareceria funcionar — as notas antigas apareceriam certas.

**Provado:** 11 testes em `tests/teste_nota_vista.py` e 9 em
`frontend/src/visto_por_1510.teste.js`.
"""

LIGACOES = """

### A senha passou de 1 dia para 48 h (15/10, fim do dia)

🔵 *"essas senhas pode deixa-las com 48hrs a partir da geracao"*, junto do
pedido de deixar as senhas de todos os ramais prontas num arquivo.

`JANELAS_ACEITAS = 288` (288 × 10 min). Continua valendo o que já estava
escrito: quem muda é a **aceitação**, nunca a janela de geração — é o
`UNIQUE (ramal, janela)` que faz a senha servir uma vez, e janela grande
viraria "um alistamento por ramal a cada 48 h".

⚠️ O custo cresce junto: senha ditada e **não usada** serve por dois dias.
Continua de uso único e continua só alistando.

**`scripts/senhas_dos_ramais.py`** gera o arquivo com a senha de cada ramal
(`--gravar`). Ele **não dá senha a ramal que já está enviando** — usá-la
revogaria o PC que funciona — e lista, com o motivo, quem ficou de fora. O
arquivo diz, dentro dele, que é uma chave e que se apaga depois do mutirão.
"""


def juntar(rel: str, texto: str, marca: str):
    caminho = RAIZ / rel
    atual = caminho.read_text(encoding="utf-8")
    if marca in atual:
        print(f"ja documentado: {rel}")
        return
    caminho.write_text(atual.rstrip("\n") + "\n" + texto, encoding="utf-8")
    print(f"documentado: {rel}")


juntar("docs/02_Modelo_Dados.md", MODELO_02, "nota_leitura")
juntar("docs/06_Conteudo_das_Telas.md", TELAS_06, '"visto por" na nota')
juntar("docs/ligacoes.md", LIGACOES, "de 1 dia para 48 h")
