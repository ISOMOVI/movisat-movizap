"""Documentacao da senha de 1 dia e do desenho A da ficha (15/10, fim do dia)."""
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent

LIGACOES = """

## A senha de alistamento passou a valer 1 dia (15/10/2026)

🔵 *"dos ramais, podemos prolongar as senhas para 1 dia por enquanto?"* —
autorizado por ele no mesmo dia (*"ok para ajuste das senhas"*).

🚨 **O `.exe` não muda, e nenhum PC precisa ser reinstalado.** A senha é
derivada inteiramente na VPS (`senha_da_janela`); o instalador apenas manda o
que a pessoa digitou e ouve sim ou não. O nginx também não foi tocado.

🚨 **QUEM MUDOU FOI A ACEITAÇÃO, NÃO A JANELA DE GERAÇÃO**, e a diferença é o
ponto todo. `JANELA_S = 86400` pareceria o caminho óbvio e seria defeito grave:
`UNIQUE (ramal, janela)` é o que faz a senha servir uma vez, então uma janela
de um dia viraria **um alistamento por ramal por dia** — e um alistamento que
falhasse depois de a janela queimar (erro de certificado, rede caindo no meio)
deixaria o ramal travado até amanhã, porque "peça outra senha" devolveria a
mesma senha já queimada.

O que está no ar:

| | Antes | Agora |
|---|---|---|
| A senha TROCA a cada | 10 min | **10 min** (igual) |
| A senha é ACEITA por | 20 min (2 janelas) | **24 h** (144 janelas) |
| Uma falha custa | 10 min | **10 min** (igual) |
| Uso | uma vez | **uma vez** (igual) |

⚠️ **O que isso custa, por escrito:** uma senha ditada e **não usada** continua
servindo por até um dia, em vez de 20 minutos. Ela continua de uso único (a
primeira utilização queima a janela), continua **só alistando** (o batimento e
o envio seguem com chave + certificado), e 5 erros seguidos continuam trancando
aquele IP. O risco que cresce é alguém que ouviu a senha alistar o PC errado
antes da pessoa certa — e isso aparece na hora, porque alistar revoga o PC
anterior e o vigia acusa o PC que parou de falar.

⚠️ **Para voltar a 20 minutos é uma linha:** `JANELAS_ACEITAS = 2`.

⚠️ **A ferramenta dele passou a dizer o prazo REAL** (`Vale por 23 h 53 min`).
Enquanto `segundos_restantes()` media só a janela de geração, ela dizia "vale
por 7 min" de uma senha que valia um dia — e ferramenta que mente sobre o
próprio prazo faz pedir senha nova sem precisar.

**Provado:** 15 testes em `tests/teste_ligacoes_alistar.py`, entre eles a senha
de 23 h atrás alistando, a de 25 h sendo recusada, o uso único dentro do dia, e
uma janela queimada **não** trancando a seguinte.
"""

TELAS_06 = """

## ATD_1.2 — a ficha, desenho A (15/10)

🔵 *"essa tela dentro da ficha esta redundante e um pouco feia"* → três mockups
→ *"Tipo A 100%"*.

**O defeito que ele viu:** o mesmo telefone **três vezes** na mesma tela — no
topo, em "Contato" (o nome do contato, derivado, era o próprio número) e na
linha de telefones acrescentada horas antes no Bloco 6. Duas das três eram
minhas, do mesmo dia.

O que está no ar:

1. **O telefone aparece uma vez.** A linha de telefones do Bloco 6 saiu.
2. **Nome derivado não se mostra como nome:** quando `contato.nome` é o próprio
   telefone, a ficha diz **"sem nome no cadastro"**. Ausência de dado com cara
   de dado é tela que mente. A comparação é por dígitos e exige 10 ou mais,
   para não confundir nome com número.
3. **As três consultas dividem uma linha** (`Ligações`, `Contatos`, `Empresas`),
   em vez de três botões soltos numa gaveta que é `flex-direction: column` e
   tem `max-height: 45%`. Rótulo curto na barra, nome inteiro no `title`.
4. **A empresa é um cartão:** razão social com peso, nome fantasia como
   subtítulo, CNPJ e e-mail numa linha de apoio com ícone. Os rótulos "Nome
   fantasia" e "CNPJ/CPF" saíram — o dado fala por si. O e-mail **quebra** em
   vez de cortar com reticências: e-mail cortado não dá para copiar.
5. **Desvincular saiu da pilha das consultas** e foi para o pé, depois de um
   fio, ao lado da contagem de empresas. Eram três botões de ler e um de
   apagar, todos iguais.
6. **O botão `Contatos` só existe havendo empresa** — sem ela o modal só teria
   "este número não está no cadastro", que a ficha já diz em âmbar.

⚠️ **Uma coisa do mockup A que NÃO foi feita:** lá o "Tipo" era chip no topo.
Aqui ele **fica na lista de dados**, porque para quem tem `podeTrocarTipo` ele é
um `<select>` — um controle, não um rótulo. Chip no topo mais campo embaixo
recriaria a duplicação que o desenho existe para matar.

**Provado:** 32 testes em `frontend/src/ficha_1510.teste.js` (a guarda do Bloco
6 que afirmava o contrário foi **reescrita**, não apagada: ela passou a guardar
a decisão nova), suíte de frontend **261 verdes**, e os 4 arquivos de teste que
leem a `CaixaDeEntrada.vue` conferidos à parte.
"""


def juntar(rel: str, texto: str, marca: str):
    caminho = RAIZ / rel
    atual = caminho.read_text(encoding="utf-8")
    if marca in atual:
        print(f"ja documentado: {rel}")
        return
    caminho.write_text(atual.rstrip("\n") + "\n" + texto, encoding="utf-8")
    print(f"documentado: {rel}")


juntar("docs/ligacoes.md", LIGACOES, "senha de alistamento passou a valer 1 dia")
juntar("docs/06_Conteudo_das_Telas.md", TELAS_06, "a ficha, desenho A")
