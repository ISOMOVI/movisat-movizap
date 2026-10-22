"""O teste do elo que faltava, anexado ao arquivo que ja monta o Notificador.

Vai em `notificacoes_2509.teste.js` e nao num arquivo novo porque e ESTE que
monta o `Notificador` com temporizador falso e a resposta da rota mockada --
o aparato todo ja esta aqui.
"""
import sys

ALVO = "frontend/src/notificacoes_2509.teste.js"

NOVO = '''

// ---- o terceiro selo do menu (22/10) -------------------------------------
//
// 🚨 ESTES TESTES EXISTEM POR UM DEFEITO MEU, no mesmo dia da entrega. O
// `MenuLateral` passou a LER `notificacoes.email_nao_lidos` e a rota passou a
// DEVOLVER o número, mas o `ler()` daqui copia campo a campo e eu esqueci a
// linha do meio: em produção o selo do e-mail ficaria sempre em branco, e a
// soma do grupo fechado sairia sem essa parcela.
//
// ⚠️ AS DUAS SUÍTES FICARAM VERDES COM O SELO MORTO. Os testes do menu setam
// o valor no estado à mão (é o desenho do selo que eles defendem), e nenhum
// teste ligava a resposta da rota ao estado. É a família do `M9` por dentro
// do estado em vez do layout -- e o que pega é ler a cadeia inteira: quem
// devolve → quem grava → quem lê.

describe('o contador de e-mail chega ao estado (o selo do menu)', () => {
  it('copia `email_nao_lidos` da resposta para o estado', async () => {
    await montarEPassar({ ...resposta([]), email_nao_lidos: 61 })
    expect(notificacoes.email_nao_lidos).toBe(61)
  })

  it('zero é valor, não ausência', async () => {
    await montarEPassar({ ...resposta([]), email_nao_lidos: 0 })
    expect(notificacoes.email_nao_lidos).toBe(0)
  })

  it('🚨 rota sem o campo zera, em vez de deixar `undefined` no selo', async () => {
    /* O backend pode estar um passo atrás da tela no meio de uma publicação
       -- é o que o `M16` custou em 22/09. `undefined` no selo desenharia
       "undefined" no menu; zero apaga o selo, que é degradar. */
    notificacoes.email_nao_lidos = 7
    const sem = { ...resposta([]) }
    delete sem.email_nao_lidos
    await montarEPassar(sem)
    expect(notificacoes.email_nao_lidos).toBe(0)
  })

  it('o número muda a cada leitura, não congela na primeira', async () => {
    await montarEPassar({ ...resposta([]), email_nao_lidos: 61 })
    expect(notificacoes.email_nao_lidos).toBe(61)
    respostas['/api/eu/notificacoes'] = { ...resposta([]), email_nao_lidos: 58 }
    vi.advanceTimersByTime(8000)
    await assentar(mount(Notificador))
    expect(notificacoes.email_nao_lidos).toBe(58)
  })
})
'''


def main() -> int:
    texto = open(ALVO, encoding="utf-8").read()
    if "email_nao_lidos" in texto:
        raise SystemExit("ja aplicado")
    try:
        open(ALVO + ".bak_2026-10-22_atendimento", "x", encoding="utf-8").write(texto)
    except FileExistsError:
        pass
    open(ALVO, "w", encoding="utf-8").write(texto.rstrip("\n") + NOVO)
    print(f"ok  {ALVO} (+4 testes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
