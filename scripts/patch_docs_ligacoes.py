"""Atualiza docs/ligacoes.md para a v0.4 (alistamento por senha, 15/10/2026).

Idempotente, com âncora conferida. Uso:
  ./venv/bin/python scripts/patch_docs_ligacoes.py [--conferir]
"""
import sys
from pathlib import Path

ALVO = Path(__file__).resolve().parent.parent / "docs/ligacoes.md"
SO_CONFERIR = "--conferir" in sys.argv

KIT_DE = """O procedimento para instalar em cada operador está no kit `Desktop\\MoviZap-Ligacoes-Kit\\MANUAL.md`
do PC do Iago (ferramentas Preparar, Assinar e Conferir, sobre `scripts/agentes_ligacao.py`).
"""
KIT_PARA = """O procedimento para instalar em cada operador está no kit `Desktop\\MoviZap-Ligacoes-Kit\\MANUAL.md`
do PC do Iago. Desde **15/10 (v0.4) são 2 passos e um arquivo só**: a pessoa
abre `MoviZap-Instalar-Ligacoes.exe` e digita a senha de uso único que ele
dita (`Senha de alistamento.cmd` → `scripts/senha_alistamento.py`). A
conferência continua em `Conferir agentes.cmd` → `scripts/agentes_ligacao.py`.
As ferramentas `Preparar operador` e `Assinar pedido` foram aposentadas
(`fontes/aposentado-v03/` no kit): a chave e o certificado passaram a nascer no
PC da pessoa, no alistamento.
"""

VERSAO_DE = "  └─ movizap-ligacoes.ps1 (v0.3)\n"
VERSAO_PARA = "  └─ MoviZap-Backup-de-Ligacoes.exe → movizap-ligacoes.ps1 (v0.4)\n"

ROTA_DE = """A rota antiga (`movizap.movisat.com.br/api/ligacoes/agente/*`, no processo do
painel) vale só até cada PC concluir o passo 2. Ela sai junto do reinício do
Plano 4.
"""
ROTA_PARA = """A rota antiga de ENVIO (`movizap.movisat.com.br/api/ligacoes/agente/{batimento,enviar}`,
no processo do painel) vale só até cada PC se alistar. Ela sai junto do
reinício do Plano 4 -- mas **`/api/ligacoes/agente/alistar` fica**, e fica no
painel de propósito (ver abaixo).
"""

SECAO = """
## Alistamento por senha (v0.4, 15/10/2026)

🔵 *"o .exe deve rodar livre assim, porém validar o atendente do MicroSip com
uma senha que será gerada sempre via algoritmo e é mutável para rodar"*,
*"se trocarem de PC é só executar novamente e me pedir a senha de uso"*,
*"o .exe se deleta automaticamente após ser concluído"* e *"eu apagaria do PC
para evitar engenharia reversa e senha do banco"*.

```
PC da pessoa                                        VPS
  MoviZap-Instalar-Ligacoes.exe
    extrai a carga num temporário
    lê o ramal do MicroSIP.ini
    certreq -new -user  (chave NÃO exportável, nasce aqui)
    POST /api/ligacoes/agente/alistar  ──────────►  ligacoes_alistar.alistar()
      { ramal, senha, pedido (CSR), pc }              confere a senha (HMAC)
                                                      queima a janela (UNIQUE)
                                                      revoga o agente anterior
                                                      gera a chave nova
                                                      assina o certificado
    ◄──────────────────────────  { chave, cert_pem, cert_validade, pc_anterior }
    certutil -repairstore  (liga o cert à chave)
    config.json: chave CIFRADA com DPAPI do usuário
    tarefa "MoviZap - Backup de Ligações"
    Aplicativos instalados + atalho "ver situação"
    apaga o instalador (só em caso de sucesso)
```

**Por que o alistamento entra pelo PAINEL e não pela porta 8010:** o nginx de
`ligacoesmicrosip` exige certificado de cliente, e um PC que está se alistando
ainda **não tem** certificado -- não conseguiria abrir a conexão. Pôr o
alistamento no painel também manteve a promessa do kit: nenhum passo precisa de
root nem toca o nginx.

**A senha** (`movizap/ligacoes_alistar.py`): HMAC-SHA256 de
`MOVIZAP_LIGACOES_SENHA_SEGREDO` (segredo PRÓPRIO, nunca o `jwt_secret`) sobre
`(ramal, janela de 10 min)`, 8 caracteres de um alfabeto sem `I`, `O`, `0` e
`1` -- ela é ditada em voz alta. Duas janelas são aceitas (tolerância de
relógio), então no pior caso vale 20 minutos.

- 🚨 **Não é guardada em lugar nenhum.** É derivada a cada chamada. O que o
  banco guarda é a janela GASTA, em `alistamento_queimado`, com
  `UNIQUE (ramal, janela)` -- é essa constraint que faz a senha servir uma vez.
- 🚨 **O algoritmo vive só na VPS.** O `.exe` manda o que foi digitado e a VPS
  responde sim ou não. Se a derivação rodasse no PC, quem abrisse o executável
  passaria a **fabricar** senhas; como está, decompilá-lo entrega a URL pública
  e nada mais.
- 🚨 **A senha só alista.** Batimento e envio seguem com chave + certificado.
  Se cada execução pedisse senha, a tarefa das 12:00 e 17:30 pararia de
  funcionar -- não há ninguém na frente do PC para digitar.
- Senha errada e ramal sem dono dão **a mesma** resposta: dizer qual é o caso
  entregaria a lista de ramais válidos a quem está adivinhando.
- Tentativa errada cai no `movizap/ratelimit.py`, o mesmo do login (5 falhas em
  5 min, contador em SQLite, chave `ip|alistar:<ramal>` para o erro de um PC
  não trancar o ramal de outro).

**Troca de PC** (decisão dele, 15/10): o alistamento novo **revoga o anterior**
automaticamente -- quem alista de novo está trocando de PC, e dois PCs no mesmo
ramal mandariam em dobro. Quem revoga é `ligacoes.gerar_chave`, que já era
assim. A resposta devolve `pc_anterior`, e o instalador avisa na tela que aquele
PC parou de enviar. Nada se perde: o que já subiu está na VPS, e o PC novo
reenvia o que vê sem duplicar (`UNIQUE (ramal, call_id)` + hash do arquivo).

**A chave no PC** fica cifrada pelo **DPAPI do usuário** (decisão dele, 15/10):
o `config.json` copiado para outra máquina ou outro usuário não se abre. Não
protege contra quem está logado como a pessoa -- nada no PC protegeria --, e
protege contra o caso real: cópia do arquivo. Config da v0.3 (chave em texto
puro) é migrado na primeira passada da v0.4, sem reinstalar nada.

**Os dois executáveis** são compilados pelo `csc.exe` que já vem no Windows
(`fontes/Compilar.cmd`): sem ps2exe, sem instalar nada, sem admin.
`MoviZap-Instalar-Ligacoes.exe` carrega dentro de si o agente, o instalador, o
desinstalador, o LEIA-ME e o lançador, e se apaga no fim.
`MoviZap-Backup-de-Ligacoes.exe` fica instalado e é o que a tarefa executa --
é ele que faz o Gerenciador de Tarefas mostrar **"MoviZap - Backup de
Ligações"** em vez de `powershell.exe`, que era o que as pessoas encerravam.

### Provado em 15/10, no PC dele

| O quê | Resultado |
|---|---|
| Senha derivada | determinística, muda por ramal e por janela, sem `I/O/0/1` |
| Alistamento pela rota HTTP | 200, chave + certificado conferem juntos |
| Mesma senha de novo | 401 "Essa senha já foi usada" |
| Senha errada / ramal sem dono | mesma mensagem, janela não queimada |
| 5 erros seguidos | trava só aquele IP; outro IP alista normalmente |
| Alistamento real do ramal 3404 | agente 17 revogado, agente 431 vivo, cert até 14/10/2028 |
| Tarefa renomeada | `MoviZap Ligacoes` saiu, `MoviZap - Backup de Ligações` roda (resultado 0) |
| DPAPI | `config.json` sem `chave`, só `chave_protegida`; batimento ok pela porta com mTLS |
| Base intacta | 28 ligações e 19 gravações antes e depois |

### Armadilhas do PowerShell medidas neste dia

- `Get-Content -Raw` devolve a string **decorada** (`PSPath`, `PSProvider`...);
  o `ConvertTo-Json` serializa o objeto inteiro e o CSR chega como objeto →
  **422**. Usar `[IO.File]::ReadAllText`.
- No PowerShell 5.1 o corpo da resposta de erro **já foi consumido** pelo
  `Invoke-RestMethod`: `GetResponseStream()` volta vazio e a pessoa veria
  "Nao consegui falar com a VPS (401)" em vez de "Senha inválida ou vencida".
  O corpo vive em `$_.ErrorDetails.Message`.
- Executável que **espera** o PowerShell não consegue se apagar (fica em uso):
  o instalador dispara o PowerShell e sai de cena, e o `del` tenta 30 vezes.
"""

PASSOS = [
    ("linha do kit", KIT_DE, KIT_PARA),
    ("versao no diagrama", VERSAO_DE, VERSAO_PARA),
    ("nota da rota antiga", ROTA_DE, ROTA_PARA),
]

texto = ALVO.read_text(encoding="utf-8")
for nome, de, para in PASSOS:
    if para in texto:
        print(f"ja estava: {nome}")
        continue
    if de not in texto:
        raise SystemExit(f"ANCORA NAO ACHADA ({nome}): {de[:70]!r}")
    if texto.count(de) != 1:
        raise SystemExit(f"ANCORA AMBIGUA ({nome}): {texto.count(de)}x")
    texto = texto.replace(de, para)
    print(f"{'conferido' if SO_CONFERIR else 'aplicado'}: {nome}")

if "## Alistamento por senha (v0.4" in texto:
    print("ja estava: secao do alistamento")
else:
    ancora = "## Achados do ensaio de 25/09 (antes de produção)"
    if ancora not in texto:
        raise SystemExit("ANCORA NAO ACHADA: secao dos achados de 25/09")
    texto = texto.replace(ancora, SECAO.lstrip("\n") + "\n" + ancora)
    print(f"{'conferido' if SO_CONFERIR else 'aplicado'}: secao do alistamento")

if not SO_CONFERIR:
    ALVO.write_text(texto, encoding="utf-8")
    print(f"gravado: {ALVO} ({len(texto.splitlines())} linhas)")
