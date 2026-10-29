# -*- coding: utf-8 -*-
"""Patch 29/10 (parte 4): o CNPJ ALFANUMERICO, nos dois lados.

🔵 Achado DELE, colando na tela: *"tentei colar WQ0P6GLD000108, deve permitir
todos os formatos para CNPJ bem como alfanumericos, como os novos formatos"* e
*"podem colar somente numero ou . e - e / tbm"*.

🚨 O DEFEITO ERA MEU, E DE SUPOSICAO: eu tratei CNPJ como numero. Desde 2026 o
CNPJ tem **12 posicoes alfanumericas + 2 digitos**, e o valor de cada
caractere na conta do DV e o **ASCII menos 48** (`0`-`9` dao o proprio numero,
`A` da 17). Medido na nossa base: `WQ0P6GLD000108`, da Pastelaria Velasco, e
um CNPJ alfanumerico com **DV correto** -- e as duas pontas o recusavam:

  · a tela, por regex de `\\d` (botao Buscar ficava travado);
  · o SERVIDOR, porque o campo CNPJ e `double` no Bitrix e
    `float("WQ0P6GLD000108")` estoura -- o envio seria recusado com *"informe
    um numero"* num CNPJ valido.

Este patch mexe em duas funcoes do `movizap/formularios.py`.
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
        sys.exit(f"  ! {rotulo}: achei {texto.count(velho)} ocorrencias do "
                 f"trecho velho, esperava 1 -- PAREI sem gravar nada")
    caminho.write_text(texto.replace(velho, novo), encoding="utf-8")
    print(f"  + {rotulo}")


f = RAIZ / "movizap" / "formularios.py"
print(f.name)

# ---------------------------------------------------------------------------
# 1. A validação do valor: a REGRA manda mais que o tipo
# ---------------------------------------------------------------------------
trocar(f, '''def _um_valor(campo: dict, bruto) -> str:
    tipo = campo["tipo"]
    texto = str(bruto).strip()
''',
       '''# 🚨 O CNPJ ALFANUMÉRICO (2026) OBRIGOU A `validacao` A VALER MAIS QUE O
# `tipo`. O campo "CNPJ" é `double` no Bitrix, e a regra do `double` é
# `float()` -- que recusa `WQ0P6GLD000108`, um CNPJ **válido** da nossa própria
# base (Pastelaria Velasco, DV conferido). Quando o campo diz qual documento
# é, é o documento que manda, não o tipo herdado.
#
# ⚠️ E ACEITA TODOS OS FORMATOS DE COLAGEM, por decisão dele: só dígitos, ou
# com ponto, barra e traço. O que se guarda é sempre a forma canônica -- sem
# pontuação, em maiúscula --, para não existirem duas escritas do mesmo
# documento na mesma coluna.
def _canonico(texto: str, regra: str) -> str:
    if regra == "cnpj":
        return re.sub(r"[^A-Za-z0-9]", "", texto).upper()
    return re.sub(r"\\D", "", texto)


# Quantos caracteres cada documento tem. ⚠️ `placa` NÃO entra: o campo do
# Suporte é *"Veículo e Placa"*, e a pessoa escreve `SAVEIRO ABC1234` --
# cobrar 7 caracteres ali recusaria a resposta certa. Para a placa a regra é
# só mensagem na tela.
_TAMANHO_DO_DOCUMENTO = {"cnpj": 14, "cpf": 11, "cep": 8}


def _um_valor(campo: dict, bruto) -> str:
    tipo = campo["tipo"]
    texto = str(bruto).strip()

    regra = campo.get("validacao")
    if regra in _TAMANHO_DO_DOCUMENTO:
        limpo = _canonico(texto, regra)
        if len(limpo) != _TAMANHO_DO_DOCUMENTO[regra]:
            raise DadoInvalido(
                f"{campo['rotulo']}: informe os "
                f"{_TAMANHO_DO_DOCUMENTO[regra]} caracteres.")
        # ⚠️ O dígito verificador NÃO é conferido aqui, e é escolha: a frase
        # que a pessoa lê é da tela (`validacao_campo.js`), e o servidor
        # garante o FORMATO. Passar a recusar DV aqui é mudança de régua, e
        # régua é decisão dele.
        return limpo
''',
       "formularios.py: a validacao manda mais que o tipo")

# ---------------------------------------------------------------------------
# 2. A busca por documento
# ---------------------------------------------------------------------------
trocar(f, '''    so = re.sub(r"\\D+", "", documento or "")
    if len(so) not in (11, 14):
        raise DadoInvalido("Informe o CNPJ completo, com 14 dígitos.")''',
       '''    # 🚨 ALFANUMÉRICO, e todos os formatos de colagem: `WQ0P6GLD000108`,
    # `WQ.0P6.GLD/0001-08`, só dígitos, com ponto, barra ou traço. Tudo cai na
    # mesma forma canônica -- foi ele quem achou isto colando o CNPJ da
    # Velasco, que a versão só-numérica recusava.
    so = re.sub(r"[^A-Za-z0-9]", "", documento or "").upper()
    if len(so) not in (11, 14):
        raise DadoInvalido("Informe o CNPJ completo, com 14 caracteres.")''',
       "formularios.py: busca aceita CNPJ alfanumerico")

trocar(f, '''    linhas = banco.varios(
        """SELECT nome, nome_fantasia FROM cliente
            WHERE regexp_replace(coalesce(documento, \'\'), \'[^0-9]\', \'\', \'g\') = %s
            ORDER BY ativo DESC, id
            LIMIT 5""", (so,))''',
       '''    # ⚠️ Os DOIS LADOS são comparados na forma canônica: na base há documento
    # com letra (o da Velasco) e a pontuação varia. São 960 linhas -- a
    # varredura é barata, e casar por texto cru perderia o cliente por um
    # ponto.
    linhas = banco.varios(
        """SELECT nome, nome_fantasia FROM cliente
            WHERE upper(regexp_replace(coalesce(documento, \'\'),
                                       \'[^A-Za-z0-9]\', \'\', \'g\')) = %s
            ORDER BY ativo DESC, id
            LIMIT 5""", (so,))''',
       "formularios.py: casamento canonico dos dois lados")

print()
print("ok")
