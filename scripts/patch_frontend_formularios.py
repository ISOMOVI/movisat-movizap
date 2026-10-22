"""Patch: o frontend dos formulários.

  · `router/index.js`            -- a rota da FRM_1.1 (registro e roteador
                                    andam juntos; o `teste_router.py` prende);
  · `estado/notificacoes.js`     -- o campo do quarto selo, DECLARADO;
  · `componentes/Notificador.vue`-- quem o preenche, no mesmo ritmo de 8 s;
  · `componentes/MenuLateral.vue`-- o selo no item e na soma do grupo;
  · `telas/Notificacoes.vue`     -- o interruptor por pessoa (CFG_11.1);
  · `telas/Geral.vue`            -- a conta de somar sempre (CFG_7.1), NO FIM.

🚨 Cada emenda confere a âncora antes de escrever e sai sem gravar se não
achar. Rodar duas vezes não duplica.
"""
import sys
from pathlib import Path

RAIZ = Path("/home/claude/movizap_painel/frontend/src")


def emendar(caminho: Path, ancora: str, novo: str, marca: str) -> None:
    texto = caminho.read_text(encoding="utf-8")
    if marca in texto:
        print(f"{caminho.name}: {marca!r} ja estava")
        return
    if ancora not in texto:
        sys.exit(f"{caminho.name}: NAO achei a ancora de {marca!r} -- nada escrito")
    if texto.count(ancora) != 1:
        sys.exit(f"{caminho.name}: ancora de {marca!r} aparece "
                 f"{texto.count(ancora)} vezes -- ambigua")
    caminho.write_text(texto.replace(ancora, novo, 1), encoding="utf-8")
    print(f"{caminho.name}: {marca!r} emendado")


# ============================================================== router
ROUTER = RAIZ / "router" / "index.js"
emendar(ROUTER,
        "import ChatInterno from '../telas/ChatInterno.vue'",
        "import ChatInterno from '../telas/ChatInterno.vue'\n"
        "import Solicitacoes from '../telas/Solicitacoes.vue'",
        "import Solicitacoes from")

emendar(
    ROUTER,
    """  // ---- CAD: cadastro ----""",
    """  // 🔵 22/10: a FRM_1.1, o que chega pelos formularios proprios.
  // 🚨 REGISTRO E ROTEADOR ANDAM JUNTOS: tela registrada no backend e ausente
  // daqui aparece no menu e leva para "nao encontrada" -- aconteceu em 06/08
  // com a ATD_5.1, e o `teste_router.py` compara os dois lados desde entao.
  {
    path: '/solicitacoes',
    name: 'FRM_1.1',
    component: Solicitacoes,
    meta: { codigo: 'FRM_1.1', titulo: 'Solicitações' },
  },

  // ---- CAD: cadastro ----""",
    "FRM_1.1")

# ====================================================== estado/notificacoes
emendar(
    RAIZ / "estado" / "notificacoes.js",
    "  email_nao_lidos: 0,",
    """  email_nao_lidos: 0,
  /* 🔵 22/10: as solicitações de formulário ainda `nova`, para o quarto selo
     do menu. Vem da MESMA resposta de 8 em 8 s -- selo que pisca em dois
     relógios mostra soma que não bate com as partes.

     🚨 DECLARADO AQUI, como o do e-mail: campo que só existe depois da
     primeira resposta faz o menu desenhar `undefined` no primeiro quadro. */
  solicitacoes_novas: 0,""",
    "solicitacoes_novas")

# ========================================================= Notificador.vue
emendar(
    RAIZ / "componentes" / "Notificador.vue",
    "  notificacoes.email_nao_lidos = r.email_nao_lidos || 0",
    """  notificacoes.email_nao_lidos = r.email_nao_lidos || 0
  /* 🚨 CAMPO NOVO NÃO ENTRA SOZINHO: esta função COPIA campo a campo, e em
     22/10 um campo que a rota devolvia e esta linha não copiava ficou valendo
     zero na tela com as duas suítes verdes. */
  notificacoes.solicitacoes_novas = r.solicitacoes_novas || 0""",
    "solicitacoes_novas")

# ========================================================== MenuLateral.vue
MENU = RAIZ / "componentes" / "MenuLateral.vue"
emendar(
    MENU,
    "const naoLidosEmail = computed(() => notificacoes.email_nao_lidos || 0)",
    """const naoLidosEmail = computed(() => notificacoes.email_nao_lidos || 0)
/* 🔵 22/10: o quarto selo -- solicitações de formulário ainda novas. O número
   já vem travado no backend por quem tem a FRM_1.1 e por quem não desligou o
   aviso na CFG_11.1, então aqui não há regra nenhuma: zero não desenha nada. */
const solicitacoesNovas = computed(() => notificacoes.solicitacoes_novas || 0)""",
    "solicitacoesNovas")

emendar(
    MENU,
    """const somaDoGrupo = computed(
  () => naoLidasWhatsapp.value + naoLidas.value + naoLidosEmail.value)""",
    """const somaDoGrupo = computed(
  () => naoLidasWhatsapp.value + naoLidas.value + naoLidosEmail.value
        + solicitacoesNovas.value)""",
    "+ solicitacoesNovas.value)")

emendar(
    MENU,
    """  if (codigo === 'EML_1.1') return naoLidosEmail.value
  return 0""",
    """  if (codigo === 'EML_1.1') return naoLidosEmail.value
  if (codigo === 'FRM_1.1') return solicitacoesNovas.value
  return 0""",
    "if (codigo === 'FRM_1.1') return solicitacoesNovas.value")

emendar(
    MENU,
    """  if (codigo === 'EML_1.1') {
    return `${naoLidosEmail.value} e-mail(s) não lido(s) na entrada`
  }""",
    """  if (codigo === 'EML_1.1') {
    return `${naoLidosEmail.value} e-mail(s) não lido(s) na entrada`
  }
  if (codigo === 'FRM_1.1') {
    return `${solicitacoesNovas.value} solicitação(ões) nova(s) de formulário`
  }""",
    "solicitação(ões) nova(s) de formulário")

emendar(
    MENU,
    """              + `${naoLidosEmail} no e-mail`\"""",
    """              + `${naoLidosEmail} no e-mail, `
              + `${solicitacoesNovas} em solicitações`\"""",
    "em solicitações`")

# ====================================================== Notificacoes (CFG_11.1)
NOTIF = RAIZ / "telas" / "Notificacoes.vue"
emendar(
    NOTIF,
    "      <!-- 🔵 \"só aparece ao Owner\". A rota também recusa quem não é. -->",
    """      <!-- 🔵 22/10, pedido dele: *"controle de notificações no 'minha conta'
           de cada usuário, igual as demais"*. É por pessoa, como o tom e o
           volume -- e NASCE LIGADO, porque o aviso é o que ele pediu.

           ⚠️ Só aparece para quem TEM a tela: o interruptor esconde um selo,
           nunca dá acesso. Quem não tem a FRM_1.1 recebe zero de qualquer
           forma, e ver aqui um aviso que nunca vai chegar seria `M12`. -->
      <section v-if="temSolicitacoes" class="cartao tela__bloco">
        <div class="cartao__corpo pilha">
          <h2 class="cartao__titulo">Solicitações de formulário</h2>
          <label class="interruptor">
            <input type="checkbox" :checked="avisoSolicitacao"
                   :disabled="salvando" @change="alternarAvisoSolicitacao" />
            <span>{{ avisoSolicitacao ? 'Avisar' : 'Não avisar' }}</span>
          </label>
          <p class="apagado pequeno">
            Ligado, o menu mostra quantas solicitações chegaram pelos
            formulários e ainda estão como novas. Desligado, o número não
            aparece para você — a tela Solicitações continua lá.
          </p>
        </div>
      </section>

      <!-- 🔵 "só aparece ao Owner". A rota também recusa quem não é. -->""",
    "temSolicitacoes")

emendar(
    NOTIF,
    "const souOwner = computed(() => Boolean(sessao.usuario?.owner))",
    """const souOwner = computed(() => Boolean(sessao.usuario?.owner))

/* 🔵 22/10: o aviso de solicitação de formulário. O estado de partida vem da
   mesma rota que o Notificador já lê -- `solicitacoes_novas` é zero para quem
   desligou, mas zero também é zero para quem não tem solicitação nenhuma, e
   os dois casos não se distinguem por ali. Por isso o valor vem de
   `/api/eu/notificacoes` só depois de a pessoa mexer: aqui o que importa é o
   que ela escolheu, e a escolha é gravada na hora, como o tom e o volume. */
const temSolicitacoes = computed(
  () => (sessao.telas || []).some((t) => t.codigo === 'FRM_1.1'))
const avisoSolicitacao = ref(true)

async function alternarAvisoSolicitacao() {
  salvando.value = true
  erro.value = ''
  recado.value = ''
  try {
    const r = await api.put('/api/eu/aviso-solicitacao',
                            { ligado: !avisoSolicitacao.value })
    avisoSolicitacao.value = r.aviso_solicitacao
    recado.value = 'Salvo.'
  } catch (e) {
    erro.value = e instanceof ErroDeApi ? e.message : 'Não consegui salvar.'
  } finally {
    salvando.value = false
  }
}""",
    "alternarAvisoSolicitacao")

# ============================================================ Geral (CFG_7.1)
GERAL = RAIZ / "telas" / "Geral.vue"
emendar(
    GERAL,
    """    </section>
  </div>
</template>""",
    """    </section>
      <!-- 🔵 22/10: a conta de somar do formulário público.

         ⚠️ FICA NO FIM DA TELA, pelo mesmo motivo escrito acima: dois testes
         da Geral escolhem a caixa pelo ÍNDICE (`caixas[2]`), e interruptor
         inserido no meio desloca os deles.

         🚨 NASCE DESLIGADO, e desligado NÃO quer dizer "sem defesa": a isca,
         o tempo mínimo de preenchimento e o limite por IP valem sempre. Isto
         aqui é só a pergunta aparecer em TODO envio, em vez de aparecer
         depois de 5 envios do mesmo IP na hora. Decisão dele: *"captcha no
         final pode se legal, mas tbm usam pelo cel então não pode virar
         entrave de processo"*. -->
    <section class="cartao tela__bloco">
      <div class="cartao__corpo pilha">
        <label class="interruptor">
          <input type="checkbox" :checked="desafioSempre" :disabled="salvando"
                 @change="alternarDesafio" />
          <span><strong>Pedir a conta de somar em todo formulário enviado</strong></span>
        </label>
        <p class="apagado pequeno">
          Desligado (o normal), quem preenche um formulário em
          <strong>forms.movisat.com.br</strong> só vê a pergunta depois de 5
          envios do mesmo endereço na mesma hora. Ligado, ela aparece sempre —
          mais atrito para o cliente, inclusive no celular.
        </p>
      </div>
    </section>
  </div>
</template>""",
    "conta de somar")

emendar(
    GERAL,
    """const harmonitLigado = ref(false)""",
    """const harmonitLigado = ref(false)
/* 🔵 22/10: a conta de somar do formulário público. */
const desafioSempre = ref(false)

async function alternarDesafio() {
  salvando.value = true
  recado.value = ''
  try {
    const r = await api.put('/api/config/formulario-desafio',
                            { ligado: !desafioSempre.value })
    // Relê o que o servidor gravou: a confirmação é o estado.
    desafioSempre.value = r.desafio_sempre
    recado.value = desafioSempre.value
      ? 'Ligado: todo envio de formulário passa a pedir a conta.'
      : 'Desligado: a conta volta a aparecer só depois de 5 envios do mesmo IP na hora.'
  } catch (e) {
    erro.value = e instanceof ErroDeApi ? e.message : 'Não consegui mudar.'
  } finally {
    salvando.value = false
  }
}""",
    "alternarDesafio")

emendar(
    GERAL,
    """    } catch {
      harmonitLigado.value = false
    }""",
    """    } catch {
      harmonitLigado.value = false
    }
    // 🚨 EM TRY PRÓPRIO, pelo mesmo motivo do de cima: um interruptor a mais
    // não pode derrubar a leitura da tela inteira.
    try {
      desafioSempre.value = (await api.get('/api/config/formulario-desafio')).desafio_sempre
    } catch {
      desafioSempre.value = false
    }""",
    "formulario-desafio')).desafio_sempre")

print("\\npronto")
