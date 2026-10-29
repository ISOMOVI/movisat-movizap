# -*- coding: utf-8 -*-
"""Patch 29/10 (parte 3): os tres pedidos dele de hoje a tarde, e o docs/02.

  1. docs/02 -- a migracao 079 documentada (o `teste_modelo_documentado`
     reprovou, e esta certo: modelo que nao esta no documento e modelo que
     ninguem acha);
  2. BUSCAR CLIENTE PELO CNPJ -- *"ao colocar CPF CNPJ, ter botao de buscar
     pelo CNPJ para preenchimento automatico da base do harmonit"*;
  3. a rota publica dessa busca.

🚨 A BUSCA NAO CHAMA O HARMONIT, E ISSO E DE PROPOSITO -- duas razoes:
   · a pagina e PUBLICA, e uma rota publica que fala com o ERP ao vivo seria
     um caminho da internet para dentro dele;
   · a base do Harmonit ja esta espelhada aqui (`cliente`, 960 linhas, pela
     `CFG_3.1`), entao a resposta sai do nosso banco, em milissegundos.

🚨 E ELA DEVOLVE SO O NOME. Nem documento, nem e-mail, nem id: quem preenche o
formulario esta confirmando a empresa dele, nao consultando a nossa carteira.
Mesmo assim e um oraculo -- "este CNPJ e cliente?" --, e por isso tem teto de
consultas por hora e exige o carimbo de abertura da pagina.
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


# ---------------------------------------------------------------------------
# 1. docs/02
# ---------------------------------------------------------------------------
d = RAIZ / "docs" / "02_Modelo_Dados.md"
print(d.name)
trocar(d, """⚠️ `situacao_erro` segue a régua do `agendamento.endereco_os_erro` (073): nulo
com `situacao_em` nulo = não tentou; nulo com data = deu certo.""",
       """⚠️ `situacao_erro` segue a régua do `agendamento.endereco_os_erro` (073): nulo
com `situacao_em` nulo = não tentou; nulo com data = deu certo.

## Migração 079 — o formato novo do formulário público

🔵 Pedido dele, 29/10, sobre o Suporte: *"ajuste ele no novo formato 'etapas,
logo, cor, placas, etc'"*. O desenho é o de 23/10 (blocos 1, 3, 5 e 6 do
plano, em `Desktop\\Formularios_Movisat_Design.md`).

`formulario.formato` — `varchar(10)`, **não anulável**, CHECK em
`classico | novo`, padrão **`classico`**.
🚨 **Nasce `classico` nos 15**, e ligar é decisão dele: o formato novo muda a
tela que a internet vê, e ele valida formulário por formulário no navegador.
Hoje só o **SUPORTE** está em `novo`.

`formulario.etapas` — `jsonb`, **anulável**:
`[{"titulo": ..., "campos": [nosso_nome, ...]}]`. Nulo = rolo único, que é o
caso dos outros 14.
🚨 **Os campos são citados pelo `nosso_nome`**, não pelo nome do Bitrix — é o
único dos dois que uma pessoa revisa. Quem traduz para o nome de origem é a
rota pública (`main._etapas_publicas`), porque `nosso_nome` **não sai** para a
internet.
🚨 **A carga recusa etapa errada dos dois lados:** campo citado que não existe
**e** pergunta que ficou fora de toda etapa. O segundo é o perigoso — a
pergunta simplesmente não apareceria, e o formulário seguiria aceitando envio
com uma pergunta a menos.
⚠️ Onde o formulário tiver `page` (15 delas nos outros), **é ela que manda**: o
Suporte não tem nenhuma, e por isso as 4 etapas dele são agrupamento nosso.

`formulario_campo.validacao` — `varchar(16)`, **anulável**, CHECK em
`cpf | cnpj | placa | telefone | email | cep`.
🚨 **Existe porque o tipo do Bitrix não diz o bastante:** 30 dos 239 campos são
`double` e são CNPJ, CPF, RG e quantidade. Sem esta coluna não há máscara nem
dígito verificador.
🚨 **NÃO é barreira.** Quem recusa o envio é `formularios.validar`; esta coluna
diz à tela qual máscara pôr e qual frase mostrar.
🚨 **E o que vai gravado é o valor LIMPO, não o mascarado:** `cpf`/`cnpj` são
`double` no servidor, e `"111.444.777-35"` não passa por `float()` — gravar
mascarado faria a rota recusar um CPF correto. A prova está em
`tests/teste_formato_novo.py`.
🚨 **As três são reescritas a cada carga** (como `painel`, ao contrário de
`ativo`): o mapa vive no `scripts/carregar_formularios.py`.""",
       "docs/02: a migracao 079")

# ---------------------------------------------------------------------------
# 2. A busca por documento
# ---------------------------------------------------------------------------
f = RAIZ / "movizap" / "formularios.py"
print(f.name)
trocar(f, """def novo_desafio() -> dict:""",
       '''# ----------------------------------------------------------------------------
# Buscar o cliente pelo documento (29/10)
# ----------------------------------------------------------------------------
# 🔵 Pedido dele: *"ao colocar CPF CNPJ, ter botao de buscar pelo CNPJ para
# preenchimento automatico da base do harmonit"*.
#
# 🚨 NÃO FALA COM O HARMONIT. A base dele já está espelhada aqui (`cliente`,
# pela `CFG_3.1`), e esta rota é alcançável por QUALQUER UM na internet -- uma
# chamada ao vivo daqui seria um caminho de fora para dentro do ERP. A resposta
# sai do nosso banco.
#
# 🚨 DEVOLVE SÓ O NOME. Nem documento, nem e-mail, nem id: quem preenche está
# confirmando a empresa dele, não consultando a nossa carteira.
#
# 🚨 E AINDA ASSIM É UM ORÁCULO ("este CNPJ é cliente?"), por isso tem teto por
# hora (`BUSCAS_POR_HORA`) e exige o carimbo de abertura da página.
BUSCAS_POR_HORA = 20

# ⚠️ 8 dos 960 clientes têm `documento` com 14 zeros -- é preenchimento de
# fachada da base, não CNPJ. Sem esta guarda, quem digitasse zeros casaria com
# oito empresas de verdade.
_DOCUMENTO_DE_FACHADA = "0" * 14


def cliente_por_documento(documento: str, ip: str | None = None) -> dict:
    """`{achou, nome, varios}` -- e nada mais que isso.

    ⚠️ "Não achou" NÃO é erro: a maior parte de quem preenche o formulário
    público não é cliente nosso ainda, e dizer "falhou" ali seria mentira.
    """
    so = re.sub(r"\\D+", "", documento or "")
    if len(so) not in (11, 14):
        raise DadoInvalido("Informe o CNPJ completo, com 14 dígitos.")
    if ip and ratelimit.quantos_eventos(f"busca|{ip}") >= BUSCAS_POR_HORA:
        raise DadoInvalido("Muitas consultas seguidas. Tente mais tarde.")
    if ip:
        ratelimit.registrar_evento(f"busca|{ip}")
    if set(so) == {"0"} or so == _DOCUMENTO_DE_FACHADA:
        return {"achou": False}

    # ⚠️ O documento é comparado SÓ POR DÍGITO dos dois lados: na base há 1
    # registro com letra e a máscara varia. São 960 linhas -- a varredura é
    # barata, e casar por texto cru perderia o cliente por causa de um ponto.
    linhas = banco.varios(
        """SELECT nome, nome_fantasia FROM cliente
            WHERE regexp_replace(coalesce(documento, \'\'), \'[^0-9]\', \'\', \'g\') = %s
            ORDER BY ativo DESC, id
            LIMIT 5""", (so,))
    if not linhas:
        return {"achou": False}
    # 🚨 MAIS DE UM COM O MESMO DOCUMENTO EXISTE (10 pares na base). A tela diz
    # que há mais de um em vez de escolher calada.
    return {"achou": True, "nome": linhas[0]["nome"],
            "varios": len(linhas) > 1}


def novo_desafio() -> dict:''',
       "formularios.py: cliente_por_documento")

# ---------------------------------------------------------------------------
# 3. A rota
# ---------------------------------------------------------------------------
m = RAIZ / "movizap" / "main.py"
print(m.name)
trocar(m, '''@app.get("/api/publico/desafio")''',
       '''@app.post("/api/publico/formulario/{slug}/cliente")
def cliente_do_formulario_publico(slug: str, request: Request,
                                  documento: str = Form(...),
                                  abertura: str = Form("")):
    """O botão *Buscar* do CNPJ. 🔵 Pedido dele, 29/10.

    🚨 Devolve `{achou, nome, varios}` e NADA ALÉM -- ver
    `formularios.cliente_por_documento`, que explica por que não chama o
    Harmonit e por que tem teto por hora.

    ⚠️ Exige o carimbo de abertura da página, como o envio: quem chama por fora
    da nossa página é exatamente quem não queremos consultando a base.
    """
    ip = ratelimit.ip_do_cliente(request)
    try:
        formularios_mod.definicao(slug)
    except formularios_mod.FormularioNaoExiste:
        raise HTTPException(status_code=404, detail="Formulário não encontrado.")
    formularios_mod.conferir_abertura(abertura)
    return formularios_mod.cliente_por_documento(documento, ip=ip)


@app.get("/api/publico/desafio")''',
       "main.py: rota da busca por documento")

print()
print("ok")
