"""A classe MORTA `botao--acento` do E-mail -- 3 usos, 25/11.

Achada pela 11a conferencia do CSS publicado, no mesmo dia em que ela nasceu.
`botao--acento` nao existe em CSS nenhum: os 3 botoes ja renderizam como
`.botao` base hoje, e esse E o visual de acao principal nesta casa.

Entao a classe SAI, e nada muda na tela: tirar o nome morto nao altera um pixel
e acaba com a classe que promete estilo e nao entrega. Se ele quiser um acento
diferente em "Nova mensagem", "Salvar assinatura" ou "Mandar", e uma variante
que existe, por botao -- decisao dele, nao minha.
"""
import pathlib, shutil, sys
from datetime import datetime

ALVO = pathlib.Path("/home/claude/movizap_painel/frontend/src/telas/Email.vue")
t = ALVO.read_text(encoding="utf-8")
pares = [('class="botao botao--pequeno botao--acento" type="button" @click="novaMensagem"',
          'class="botao botao--pequeno" type="button" @click="novaMensagem"'),
         ('class="botao botao--pequeno botao--acento" type="button" @click="salvarAssinatura"',
          'class="botao botao--pequeno" type="button" @click="salvarAssinatura"'),
         ('class="botao botao--acento" type="button" :disabled="enviando" @click="mandar"',
          'class="botao" type="button" :disabled="enviando" @click="mandar"')]
for de, _p in pares:
    if t.count(de) != 1:
        print(f"ABORTADO: ancora {t.count(de)}x -> {de[:50]}", file=sys.stderr)
        raise SystemExit(1)
novo = t
for de, para in pares:
    novo = novo.replace(de, para, 1)
assert "botao--acento" not in novo
marca = datetime.now().strftime("%Y-%m-%d_%H%M%S")
shutil.copy2(ALVO, ALVO.with_suffix(ALVO.suffix + f".bak_{marca}_acento_morto"))
ALVO.write_text(novo, encoding="utf-8")
print("3 usos de botao--acento removidos (zero mudanca visual)")
