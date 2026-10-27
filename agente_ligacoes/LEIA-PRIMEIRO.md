# O fonte do agente de Ligações — a cópia que existe no repositório

🚨 **ESTA PASTA EXISTE PORQUE O FONTE VIVIA EM UM LUGAR SÓ.** Até 26/10, o
agente que roda nos PCs dos operadores — o `.exe` que faz o backup das
gravações do MicroSIP — tinha o código **apenas** em
`C:\Users\Lenovo\Desktop\MoviZap-Ligacoes-Kit\fontes\`, na máquina dele. Nada
no repositório, nada na VPS.

⚠️ **É a mesma classe de problema de 22/10**, quando o insumo que destravou os
formulários (o `mapa_bruto.json` dos 15 do Bitrix) existia só no diretório
temporário de uma sessão. A lição de lá vale aqui: **o passo 0 é preservar o
fonte**, antes de qualquer coisa.

E a pergunta dele que achou isto foi *"tudo documentado?"* — a mesma que, em
22/10, encontrou três pontas fora do repositório.

## O que está aqui, e o que NÃO está

| aqui | o quê |
|---|---|
| `movizap-ligacoes.ps1` | **o agente**. Lê o `MicroSIP.ini`, acha a pasta das gravações, envia ligação e áudio para a VPS, faz o batimento e a limpeza local |
| `instalar.ps1` | o alistamento de um PC: senha de uso único, certificado de cliente (mTLS), tarefa agendada, e — desde o 0.7 — **a pergunta sobre a pasta** |
| `desinstalar.ps1` | a saída limpa |
| `compilar.ps1` · `Compilar.cmd` | o build, com o `csc.exe` que já vem no Windows (sem ps2exe, sem admin) |
| `instalador.cs` · `lancador.cs` | os dois executáveis. 🚨 **A versão que o Windows mostra sai do `AssemblyVersion` daqui**, não do `$VERSAO` do `.ps1` — em 26/10 isso fez o `.exe` sair como `0.6.0.0` carregando scripts `0.7` |

**Não está aqui, de propósito:**
- o **`.exe` compilado** — binário não entra no repositório; o sha de cada
  versão está no `docs/ligacoes.md`;
- o `config.json` de cada PC (contém a **chave do ramal**, cifrada por DPAPI do
  usuário);
- o `aposentado-v03/` e os `*.bak_*` do kit, que são histórico local.

## 🚨 Esta cópia não é a que compila

O `Compilar.cmd` roda **no kit, no Desktop dele** — é lá que o `.exe` nasce, e é
de lá que ele sai para as pessoas. Esta pasta é **preservação e leitura**: para
alguém que não estava aqui achar o código depois, e para o `git log` guardar o
que mudou entre versões.

⚠️ **Então as duas podem divergir**, e é por isso que o `docs/ligacoes.md`
registra **bytes e sha256** de cada `.exe` publicado: é o sha que diz qual
fonte está rodando, não a data do arquivo.

## Como ler o agente (a ordem que faz sentido)

1. o cabeçalho do `movizap-ligacoes.ps1` — ele explica as decisões dele, com
   data;
2. `Achar-Ini` e `Ler-MicroSIP` — **onde** ele procura as gravações, e a ordem
   de precedência (desde o 0.7: vps › escolhida › ini › relativa › busca);
3. `Caminho-Permitido` — 🚨 **as travas, que moram no PC e não na VPS**: a VPS
   pode *mandar* um caminho, mas quem diz se ele é aceitável é o agente. Um
   agente que confia na VPS para isso é um agente que obedece a VPS invadida;
4. `Avisos` — o que ele conta sobre si (gravação desligada, pasta inexistente,
   disco cheio), que é o que o vigia das 08:10/18:10 lê;
5. `Batimento` — desde o 0.7, **de ida e de volta**: manda o diagnóstico e
   **obedece** a `config.pastas` que a VPS responde.

📘 O resto — versões, shas, o que cada uma mudou, e as etapas de instalação —
está em `docs/ligacoes.md`.
