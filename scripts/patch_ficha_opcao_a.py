"""A ficha da conversa, desenho A: barra de acoes + cartao da empresa (15/10).

🔵 Pedido dele: *"essa tela dentro da ficha esta redundante e um pouco feia"*
e, depois dos tres mockups, *"Tipo A 100%"*.

O que muda, e nada mais do que isto:
  1. o telefone aparece UMA vez (a linha que eu mesmo acrescentei hoje, no
     Bloco 6, sai -- ela repetia o numero que o topo ja mostra);
  2. nome do contato que E o proprio telefone passa a dizer "sem nome no
     cadastro": ausencia de dado com cara de dado e tela que mente;
  3. as tres consultas (Ligacoes, Contatos, Empresas) saem da pilha vertical e
     viram uma barra horizontal;
  4. a empresa vira CARTAO, com razao social em peso, fantasia como subtitulo e
     CNPJ/e-mail em linha discreta;
  5. Desvincular, que apaga um vinculo, deixa de ter a cara de um botao de
     consulta e vai para o pe, ao lado da contagem de empresas.

⚠️ UMA COISA DO MOCKUP QUE **NAO** FOI FEITA: no desenho A o "Tipo" aparecia
como chip no topo. Aqui ele FICA na lista de dados, porque para quem tem
`podeTrocarTipo` ele e um `<select>` -- um controle, nao um rotulo. Chip no topo
mais select embaixo seria recriar a duplicacao que este desenho existe para
matar.

Idempotente, ancora contada. Nao faz build.
Uso: ./venv/bin/python scripts/patch_ficha_opcao_a.py [--conferir]
"""
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
ALVO = RAIZ / "frontend" / "src" / "telas" / "CaixaDeEntrada.vue"
SO_CONFERIR = "--conferir" in sys.argv

PASSOS: list[tuple[str, str, str]] = []


def passo(nome, velho, novo):
    PASSOS.append((nome, velho, novo))


# ======================================================== 1. o script: computeds
passo("script: o nome que e so o telefone",
      """function fecharOutros() { outrosAbertos.value = false }""",
      """function fecharOutros() { outrosAbertos.value = false }

/* ---- o nome do contato quando NINGUEM digitou um (15/10, desenho A) -------
   🚨 `contato.nome` é DERIVADO quando ninguém o preencheu: o backend usa o
   apelido do WhatsApp (já limpo) ou, não havendo nenhum, o próprio telefone.
   Quando ele é o telefone, mostrá-lo na ficha repete o número que o topo já
   diz e faz **ausência de dado parecer dado**. A ficha passa a dizer o que é.

   ⚠️ Compara só dígitos e exige 10 ou mais: nome curto de números ("2 Irmãos"
   não tem, mas "1000" teria) não pode ser confundido com telefone. */
function soDigitos(valor) {
  return String(valor || '').replace(/\\D/g, '')
}

const contatoSemNome = computed(() => {
  const nome = aberta.value?.empresa?.contato?.nome
  if (!nome || !nome.trim()) return true
  const digitos = soDigitos(nome)
  return digitos.length >= 10 && digitos === soDigitos(aberta.value?.telefone_e164)
})""")

# ====================================================== 2. o topo e a barra
passo("template: topo + barra de acoes horizontal",
      """            <p class="gaveta__topo">
              <strong>{{ aberta.nome_whatsapp || 'Sem nome no WhatsApp' }}</strong>
              <span class="apagado pequeno mono">{{ aberta.telefone_e164 }}</span>
            </p>

            <!-- 🔵 15/10, Bloco 5: as LIGAÇÕES deste número, últimos 7
                 dias. Modal, e não gaveta: é consulta de um minuto, e a
                 gaveta já é a ficha. -->
            <button
              class="botao botao--pequeno botao--contorno"
              type="button"
              @click="verLigacoes"
            >
              <i class="bi bi-telephone" aria-hidden="true"></i>
              Ligações
            </button>

            <!-- Empresas do grupo desta pessoa. Consulta, não escolha: o
                 número identifica quem fala, não a empresa do assunto.
                 🔵 07/10: escondido para TÉCNICO — técnico é pessoa, não se
                 liga a empresa (decisão dele). -->
            <button
              v-if="!ehTecnico"
              class="botao botao--pequeno botao--contorno"
              type="button"
              :aria-expanded="empresasAbertas"
              @click="verEmpresas"
            >
              <i class="bi bi-buildings" aria-hidden="true"></i>
              {{ empresasAbertas ? 'Ocultar empresas' : 'Empresas vinculadas' }}
            </button>
""",
      """            <p class="gaveta__topo">
              <strong>{{ aberta.nome_whatsapp || 'Sem nome no WhatsApp' }}</strong>
              <span class="apagado pequeno mono">{{ aberta.telefone_e164 }}</span>
            </p>

            <!-- ══ AS CONSULTAS, EM UMA BARRA (desenho A, 15/10) ═══════════
                 🔵 *"essa tela dentro da ficha esta redundante e um pouco
                 feia"* → três botões empilhados, do mesmo peso e cada um numa
                 linha, numa gaveta que já luta por altura (`max-height: 45%`).
                 Em barra eles gastam uma linha, e não três.

                 🚨 SÓ CONSULTA MORA AQUI. "Desvincular" apaga um vínculo e
                 está no pé do cartão, de propósito: ação destrutiva não pode
                 ter a mesma cara de um botão de ler.

                 ⚠️ Rótulo CURTO ("Contatos", "Empresas") porque em barra o
                 espaço é lateral; o `title` carrega o nome inteiro, que é o que
                 o leitor de tela anuncia. -->
            <div class="gaveta__acoes">
              <!-- 🔵 15/10, Bloco 5: as LIGAÇÕES deste número, últimos 7 dias.
                   Modal, e não gaveta: é consulta de um minuto. -->
              <button
                class="botao botao--pequeno botao--contorno"
                type="button"
                title="Ligações deste número nos últimos 7 dias"
                @click="verLigacoes"
              >
                <i class="bi bi-telephone" aria-hidden="true"></i>
                Ligações
              </button>

              <!-- 🔵 15/10, Bloco 6: os outros contatos da MESMA empresa. Só
                   aparece havendo empresa: sem ela o modal só teria "este
                   número não está no cadastro", que a própria ficha já diz. -->
              <button
                v-if="aberta.empresa && aberta.empresa.cliente && !ehTecnico"
                class="botao botao--pequeno botao--contorno"
                type="button"
                title="Outros contatos desta empresa"
                @click="verOutrosContatos"
              >
                <i class="bi bi-person-lines-fill" aria-hidden="true"></i>
                Contatos
              </button>

              <!-- Empresas do grupo desta pessoa. Consulta, não escolha: o
                   número identifica quem fala, não a empresa do assunto.
                   🔵 07/10: escondido para TÉCNICO — técnico é pessoa, não se
                   liga a empresa (decisão dele). -->
              <button
                v-if="!ehTecnico"
                class="botao botao--pequeno botao--contorno"
                type="button"
                :aria-expanded="empresasAbertas"
                :title="empresasAbertas
                  ? 'Ocultar as empresas deste número'
                  : 'Todas as empresas que este número alcança'"
                @click="verEmpresas"
              >
                <i class="bi bi-buildings" aria-hidden="true"></i>
                {{ empresasAbertas ? 'Ocultar' : 'Empresas' }}
              </button>
            </div>
""")

# ================================================== 3. o cartao da empresa
passo("template: a empresa vira cartao",
      """            <template v-if="aberta.empresa && aberta.empresa.cliente">
              <dl class="gaveta__dados">
                <dt>Empresa</dt>
                <dd>
                  {{ aberta.empresa.cliente.nome }}
                  <span v-if="!aberta.empresa.cliente.ativo" class="chip chip--erro">inativo</span>
                </dd>
                <template v-if="aberta.empresa.cliente.nome_fantasia">
                  <dt>Nome fantasia</dt>
                  <dd>{{ aberta.empresa.cliente.nome_fantasia }}</dd>
                </template>
                <template v-if="aberta.empresa.cliente.documento">
                  <dt>CNPJ/CPF</dt>
                  <dd class="mono">{{ documentoLegivel(aberta.empresa.cliente.documento) }}</dd>
                </template>
                <template v-if="aberta.empresa.cliente.email">
                  <dt>E-mail</dt>
                  <dd>{{ aberta.empresa.cliente.email }}</dd>
                </template>
                <!-- ⚠️ NÃO mostrar `contato.papeis` aqui. Os papéis existem no
                     banco desde a migração 001, vieram do modelo do ERP e não
                     acionam nada; anunciá-los na ficha promete recurso que não
                     existe, sobre um eixo que não é do atendimento. -->
                <dt>Contato</dt>""",
      """            <template v-if="aberta.empresa && aberta.empresa.cliente">
              <!-- ══ A EMPRESA, EM CARTÃO (desenho A, 15/10) ═══════════════
                   Antes eram quatro pares rótulo/valor com o MESMO peso --
                   "Empresa", "Nome fantasia", "CNPJ/CPF", "E-mail" --, e o
                   fato mais útil da ficha (de quem é a conversa) não se
                   distinguia do rótulo ao lado. Aqui a razão social tem peso,
                   a fantasia é subtítulo, e CNPJ e e-mail descem para uma
                   linha de apoio: a mesma informação, em menos altura e com
                   onde olhar primeiro. -->
              <div class="gaveta__cartao">
                <p class="gaveta__razao">
                  {{ aberta.empresa.cliente.nome }}
                  <span v-if="!aberta.empresa.cliente.ativo" class="chip chip--erro">inativo</span>
                </p>
                <p v-if="aberta.empresa.cliente.nome_fantasia" class="gaveta__fantasia">
                  {{ aberta.empresa.cliente.nome_fantasia }}
                </p>
                <div v-if="aberta.empresa.cliente.documento || aberta.empresa.cliente.email"
                     class="gaveta__meta pequeno">
                  <span v-if="aberta.empresa.cliente.documento">
                    <i class="bi bi-hash" aria-hidden="true"></i>
                    <span class="mono">{{ documentoLegivel(aberta.empresa.cliente.documento) }}</span>
                  </span>
                  <span v-if="aberta.empresa.cliente.email">
                    <i class="bi bi-envelope" aria-hidden="true"></i>
                    {{ aberta.empresa.cliente.email }}
                  </span>
                </div>
              </div>

              <dl class="gaveta__dados">
                <!-- ⚠️ NÃO mostrar `contato.papeis` aqui. Os papéis existem no
                     banco desde a migração 001, vieram do modelo do ERP e não
                     acionam nada; anunciá-los na ficha promete recurso que não
                     existe, sobre um eixo que não é do atendimento. -->
                <dt>Contato</dt>""")

# =================================== 4. o nome do contato e o fim das repeticoes
passo("template: nome derivado deixa de repetir o telefone",
      """                <dd v-else>{{ aberta.empresa.contato.nome }}</dd>
                <!-- 🔵 15/10, Bloco 6: o TELEFONE do contato, que este <dl>
                     nunca mostrou, e o caminho para os outros contatos da
                     mesma empresa.
                     ⚠️ `principal` primeiro: é a ordem que o backend devolve
                     (`contato_telefone ORDER BY principal DESC`). -->
                <dd v-if="(aberta.empresa.contato.telefones || []).length"
                    class="gaveta__fones pequeno">
                  <span v-for="t in aberta.empresa.contato.telefones.slice(0, 2)"
                        :key="t.id" class="mono">
                    {{ t.e164 }}
                    <span v-if="t.tem_whatsapp === false"
                          class="chip chip--aviso chip--pequeno">sem WhatsApp</span>
                  </span>
                  <span v-if="aberta.empresa.contato.telefones.length > 2" class="apagado">
                    +{{ aberta.empresa.contato.telefones.length - 2 }}
                  </span>
                </dd>
                <dd>
                  <button
                    class="botao botao--pequeno botao--contorno"
                    type="button"
                    @click="verOutrosContatos"
                  >
                    <i class="bi bi-person-lines-fill" aria-hidden="true"></i>
                    Outros contatos
                  </button>
                </dd>""",
      """                <!-- 🚨 15/10: NOME DERIVADO NÃO SE MOSTRA COMO NOME. Sem
                     ninguém ter digitado um, o backend usa o apelido do
                     WhatsApp ou o próprio telefone -- e aí a ficha repetia o
                     número que o topo já diz, fazendo falta de cadastro
                     parecer cadastro. Foi o que ele viu: o mesmo número três
                     vezes na mesma tela. -->
                <dd v-else-if="contatoSemNome" class="apagado">
                  sem nome no cadastro
                </dd>
                <dd v-else>{{ aberta.empresa.contato.nome }}</dd>""")

# ============================================= 5. o pe: contagem + desvincular
passo("template: Desvincular desce para o pe do cartao",
      """              </dl>
              <button class="botao botao--pequeno botao--fantasma" type="button" @click="desvincular">
                <i class="bi bi-x-circle" aria-hidden="true"></i> Desvincular
              </button>
            </template>""",
      """              </dl>

              <!-- ⚠️ AÇÃO DESTRUTIVA SEPARADA DAS CONSULTAS (desenho A).
                   "Desvincular" estava na mesma pilha e com o mesmo peso de
                   "Ligações" e "Empresas vinculadas" -- três botões de ler e
                   um de apagar, iguais. Aqui ele fica no pé, depois de um
                   fio, ao lado do fato que dá contexto a ele. -->
              <div class="gaveta__pe">
                <span class="apagado pequeno">
                  {{ empresas.length > 1
                     ? empresas.length + ' empresas vinculadas'
                     : '1 empresa vinculada' }}
                </span>
                <button class="botao botao--pequeno botao--fantasma" type="button"
                        title="Desfaz o vínculo deste número com a empresa"
                        @click="desvincular">
                  <i class="bi bi-x-circle" aria-hidden="true"></i> Desvincular
                </button>
              </div>
            </template>""")

# ====================================================== 6. o estilo do desenho A
passo("estilo: barra, cartao e pe",
      """.gaveta__fones { display: flex; align-items: center; gap: var(--e-2); flex-wrap: wrap; }""",
      """/* ---- desenho A da ficha (15/10) --------------------------------------
   🔵 *"está redundante e um pouco feia"*. A gaveta é `flex-direction: column`,
   então TODO botão solto nela ganhava uma linha inteira; estes três passam a
   dividir uma. `flex-wrap` porque no celular a gaveta vira a tela da conversa
   e três rótulos podem não caber lado a lado. */
.gaveta__acoes {
  display: flex;
  flex-wrap: wrap;
  gap: var(--e-2);
}
.gaveta__acoes .botao { flex: 1 1 auto; justify-content: center; }

/* O cartão da empresa: fundo de superfície dentro da gaveta, que é
   `--superficie-2`. É o contraste que faz o cartão existir sem precisar de
   sombra nem de borda grossa. */
.gaveta__cartao {
  background: var(--superficie);
  border: var(--borda-fina) solid var(--borda);
  border-radius: var(--r-md);
  padding: var(--e-3);
}
.gaveta__razao {
  margin: 0;
  font-weight: var(--peso-forte);
  line-height: var(--entrelinha-apertada);
  overflow-wrap: anywhere;
}
.gaveta__fantasia {
  margin: 1px 0 0;
  font-size: var(--txt-sm);
  color: var(--texto-fraco);
  overflow-wrap: anywhere;
}
.gaveta__meta {
  display: grid;
  gap: 2px;
  margin-top: var(--e-2);
  padding-top: var(--e-2);
  border-top: var(--borda-fina) dashed var(--borda);
  color: var(--texto-fraco);
}
.gaveta__meta span { display: flex; align-items: center; gap: 6px; min-width: 0; }
.gaveta__meta i { color: var(--texto-apagado); flex: none; }
/* ⚠️ `anywhere` e não `ellipsis`: e-mail cortado com reticências não dá para
   copiar, e copiar é o que se faz com um e-mail. */
.gaveta__meta span > :last-child { overflow-wrap: anywhere; min-width: 0; }

.gaveta__pe {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--e-2);
  flex-wrap: wrap;
  padding-top: var(--e-2);
  border-top: var(--borda-fina) solid var(--borda);
}""")


def aplicar():
    texto = ALVO.read_text(encoding="utf-8")
    feitos, pulados = [], []
    for nome, velho, novo in PASSOS:
        if novo in texto:
            pulados.append(nome)
            continue
        n = texto.count(velho)
        if n != 1:
            raise SystemExit(f"ANCORA {n}x em '{nome}': {velho[:80]!r}")
        texto = texto.replace(velho, novo, 1)
        feitos.append(nome)
    if not SO_CONFERIR and feitos:
        ALVO.write_text(texto, encoding="utf-8")
    for n in feitos:
        print(f"  {'conferido' if SO_CONFERIR else 'aplicado'}: {n}")
    for n in pulados:
        print(f"  ja aplicado: {n}")


aplicar()
