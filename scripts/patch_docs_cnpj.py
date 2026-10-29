# -*- coding: utf-8 -*-
"""Patch 29/10 (parte 5): os textos que passaram a mentir com o CNPJ alfanumerico.

🚨 `M12` -- tela (e documento) que mente e defeito. As duas frases abaixo eram
VERDADE as 9h de hoje: o servidor recusava documento mascarado. Depois que ele
colou `WQ0P6GLD000108` a regra mudou -- a `validacao` passou a mandar mais que
o `tipo`, e o servidor CANONIZA em vez de recusar. Quem lesse o documento
aprenderia o contrario.
"""
import pathlib
import sys

RAIZ = pathlib.Path("/home/claude/movizap_painel")


def trocar(caminho: pathlib.Path, velho: str, novo: str, rotulo: str) -> None:
    texto = caminho.read_text(encoding="utf-8")
    if novo in texto:
        print(f"  = {rotulo}: ja aplicado")
        return
    if texto.count(velho) != 1:
        sys.exit(f"  ! {rotulo}: achei {texto.count(velho)} ocorrencias, "
                 f"esperava 1 -- PAREI sem gravar nada")
    caminho.write_text(texto.replace(velho, novo), encoding="utf-8")
    print(f"  + {rotulo}")


d = RAIZ / "docs" / "02_Modelo_Dados.md"
print(d.name)
trocar(d, """🚨 **E o que vai gravado é o valor LIMPO, não o mascarado:** `cpf`/`cnpj` são
`double` no servidor, e `"111.444.777-35"` não passa por `float()` — gravar
mascarado faria a rota recusar um CPF correto. A prova está em
`tests/teste_formato_novo.py`.""",
       """🚨 **O QUE VAI GRAVADO É A FORMA CANÔNICA — sem pontuação, em maiúscula — e
a `validacao` manda mais que o `tipo`.** O campo CNPJ é `double` no Bitrix, e a
regra do `double` é `float()`: ela recusava **`WQ0P6GLD000108`**, que é um CNPJ
**válido** da nossa própria base (Pastelaria Velasco).
🚨 **O CNPJ É ALFANUMÉRICO desde 2026:** 12 posições com letra ou dígito + 2
dígitos de verificação, e o valor de cada caractere na conta do DV é o **ASCII
menos 48** (`0`–`9` dão o próprio número, `A` dá 17) — então o CNPJ antigo é um
caso particular da mesma conta.
🔵 **Decisão dele, 29/10:** *"deve permitir todos os formatos para CNPJ bem como
alfanuméricos"* e *"podem colar somente numero ou . e - e / tbm"*. Colar
`WQ0P6GLD000108`, `WQ.0P6.GLD/0001-08` ou só dígitos dá o mesmo valor gravado.
⚠️ **`placa` NÃO é canonizada**, de propósito: o campo do Suporte é *"Veículo e
Placa — um por linha"*, e `SAVEIRO ABC1234` é resposta certa. Lá a regra é só
mensagem na tela, que **procura** a placa dentro do texto.
⚠️ O servidor garante o **formato** (quantos caracteres); o **dígito
verificador** é frase na tela. Mudar isso é régua, e régua é decisão dele.
As provas estão em `tests/teste_formato_novo.py`.""",
       "docs/02: o CNPJ alfanumerico")

s = RAIZ / "docs" / "06_Conteudo_das_Telas.md"
print(s.name)
trocar(s, """🚨 **O QUE VAI GRAVADO É O VALOR LIMPO, NÃO O MASCARADO.** `cpf` e `cnpj` são
`double` no servidor, e `"111.444.777-35"` não passa por `float()`: gravar
mascarado faria a rota **recusar um CPF correto**. O teste
`test_cpf_mascarado_e_recusado_pelo_servidor` existe para que essa ligação
nunca se desfaça por engano.""",
       """🚨 **O QUE VAI GRAVADO É A FORMA CANÔNICA**, sem pontuação e em maiúscula —
e quem manda nisso é a `validacao` do campo, não o `tipo`. **Esta frase mudou
de lado no fim do dia, e o motivo foi um achado dele** — ver o bloco do CNPJ
alfanumérico, no fim desta entrada.""",
       "docs/06: a frase que mudou de lado")

trocar(s, """4. **Decidir o `problemaId`** — sem ele o botão de criar OS não nasce, e sem OS
   o card não sai da coluna "Sem OS" do `PNL_1.1`.""",
       """4. **Decidir o `problemaId`** — sem ele o botão de criar OS não nasce, e sem OS
   o card não sai da coluna "Sem OS" do `PNL_1.1`.

### 🚨 O CNPJ ALFANUMÉRICO — achado dele, colando na tela

🔵 *"tentei colar WQ0P6GLD000108, deve permitir todos os formatos para CNPJ bem
como alfanuméricos, como os novos formatos"* · *"podem colar somente numero ou
. e - e / tbm"*.

🚨 **O defeito era meu, e era de suposição: eu tratei CNPJ como número.** Desde
2026 o CNPJ tem **12 posições alfanuméricas + 2 dígitos**, e o valor de cada
caractere na conta do DV é o **ASCII menos 48** — `0`–`9` dão o próprio número
e `A` dá 17, então o CNPJ antigo passa pela **mesma** conta. Fiz a verificação
à mão antes de mexer: **`WQ0P6GLD000108` tem DV `08` e a conta devolve `08`**.
É CNPJ **válido**, está na nossa base (Pastelaria Velasco) — e as **duas**
pontas o recusavam:

| Onde | Como recusava |
|---|---|
| a tela | regex de `\\d` na máscara e no DV → o botão **Buscar ficava travado** |
| 🚨 **o servidor** | o campo CNPJ é `double` no Bitrix, e `float("WQ0P6GLD000108")` estoura → o envio responderia *"informe um número"* **num CNPJ correto** |

**O conserto, nos dois lados:**
- a **`validacao` do campo passou a valer mais que o `tipo`** — quando o campo
  diz qual documento é, é o documento que manda, não o tipo herdado do Bitrix;
- máscara **posicional** (`WQ.0P6.GLD/0001-08`), não "de número";
- DV pela regra nova, com a repetição total (`00000000000000`) ainda fora —
  ela passaria no módulo 11;
- **todos os formatos de colagem** dão o mesmo valor gravado: só dígitos, com
  ponto, com barra, com traço, com espaço, maiúsculo ou minúsculo;
- o **casamento da busca é canônico dos dois lados** — na base há documento com
  letra e a pontuação varia, então comparar texto cru perderia o cliente por
  causa de um ponto.

⚠️ **E um defeito meu que veio no mesmo pacote: a placa.** Eu canonizava o
campo *"Veículo e Placa — um por linha"*, então `SAVEIRO ABC1234` virava
`SAVEIROABC1234`. Agora a placa **não é reescrita**: a conferência **procura**
uma placa dentro do texto, e `SAVEIRO BRANCA` (sem placa) é que recebe o aviso.

⚠️ **Um teste mudou de lado**, e isso está escrito dentro dele: a primeira
versão provava que o servidor **recusava** documento mascarado. Agora prova que
ele **canoniza**. O servidor segue garantindo o **formato** (quantos
caracteres); o **dígito verificador** é frase na tela, e passar a recusar por DV
no servidor é mudança de régua — 🔴 decisão dele.""",
       "docs/06: o bloco do CNPJ alfanumerico")

print()
print("ok")
