# Build do executável no Windows

Passo a passo para gerar `consig-bot.exe` em uma máquina Windows e empacotar para o usuário final.

## Pré-requisitos (uma vez só)

### 1. Python 3.12

- Baixe em https://www.python.org/downloads/
- **IMPORTANTE**: marque "Add Python to PATH" no instalador
- Verifique no PowerShell:
  ```powershell
  python --version
  ```
  Deve mostrar `Python 3.12.x`.

### 2. Poetry

Abra PowerShell e rode:

```powershell
(Invoke-WebRequest -Uri https://install.python-poetry.org -UseBasicParsing).Content | python -
```

Feche e reabra o PowerShell. Verifique:

```powershell
poetry --version
```

### 3. Git

- Baixe em https://git-scm.com/download/win
- Aceite as opções padrão durante a instalação

---

## Build (toda vez que quiser gerar nova versão)

Abra PowerShell na pasta onde quer trabalhar e rode os comandos **na ordem**:

### 1. Clonar o repositório

```powershell
git clone <URL-do-repo> consig-bot
cd consig-bot
```

Se já clonou antes:

```powershell
cd consig-bot
git pull
```

### 2. Instalar dependências do projeto

```powershell
poetry install
```

Demora ~2 minutos na primeira vez.

### 3. Instalar o browser do Playwright (dentro do pacote, para embarcar no .exe)

```powershell
$env:PLAYWRIGHT_BROWSERS_PATH = "0"
poetry run playwright install chromium
```

> **CRÍTICO**: a variável `PLAYWRIGHT_BROWSERS_PATH=0` faz o Chromium ser instalado **dentro do pacote `playwright`** (em vez do default `%LOCALAPPDATA%\ms-playwright\`). Sem isso, o PyInstaller não embarca o browser e o `.exe` falha em runtime com `BrowserType.launch: Executable doesn't exist at ...\chrome-win\chrome.exe`.

Baixa ~130 MB do Chromium. Demora ~1 minuto.

### 4. Gerar o executável

```powershell
poetry run pyinstaller pyinstaller.spec --clean --noconfirm
```

Demora 3-5 minutos. Muita linha rolando — é normal. Sucesso quando aparece:

```
Building EXE from EXE-00.toc completed successfully.
```

### 5. Conferir o resultado

A saída agora é uma **pasta** (build onedir — startup ~10x mais rápido que onefile):

```
dist\consig-bot\
  consig-bot.exe         ← bootloader (~5 MB)
  _internal\             ← Python + libs + Chromium (~400 MB)
```

Tamanho total esperado: **~400 MB**. NÃO mover o `consig-bot.exe` pra fora da pasta — ele precisa do `_internal\` ao lado.

---

## Montar o pacote para o usuário final

### Estrutura desejada

```
consig-bot-windows\
  consig-bot.exe        ← de dist\consig-bot\
  _internal\            ← de dist\consig-bot\ (pasta inteira)
  executar.bat          ← da raiz do repo
  config.json           ← copia de config.example.json com logins reais
  entrada\              ← pasta vazia (planilhas vão aqui)
  saida\                ← pasta vazia (resultados aparecem aqui)
```

### Comandos para montar

Na raiz do repo, no PowerShell:

```powershell
$out = "consig-bot-windows"
Copy-Item -Recurse dist\consig-bot $out
New-Item -ItemType Directory -Force "$out\entrada", "$out\saida" | Out-Null
Copy-Item executar.bat $out\
Copy-Item config.example.json "$out\config.json"
```

Depois abra `consig-bot-windows\config.json` no Notepad e preencha os campos `auth` reais dos sistemas.

### Distribuir

Zipa a pasta `consig-bot-windows` e manda para o usuário.

---

## Como o usuário final usa

1. Descompacta o ZIP em qualquer pasta
2. Edita `config.json` (uma vez — login dos sistemas)
3. Coloca a(s) planilha(s) em `entrada\`
4. Dá duplo-clique em `executar.bat`
5. Resultados aparecem em `saida\`

---

## Problemas comuns

| Sintoma | Causa | Solução |
|---------|-------|---------|
| `poetry: command not found` | PATH não recarregado | Feche e reabra o PowerShell |
| Erro "Microsoft Visual C++ ..." em `poetry install` | Faltam tools de build | Instale [Visual Studio Build Tools](https://visualstudio.microsoft.com/visual-cpp-build-tools/) |
| Antivírus bloqueia o `.exe` | PyInstaller sem assinatura | Adicione exceção no Windows Defender pra pasta `consig-bot-windows\` |
| `.exe` abre e fecha rápido | Erro no `config.json` | Rode pelo `executar.bat` (tem `pause`) ou pelo `cmd` manualmente |
| `.exe` não acha `_internal\` | Bootloader separado da pasta | NÃO mover o `consig-bot.exe` pra fora da pasta — `_internal\` precisa ficar ao lado |
| `playwright: command not found` no passo 3 | `poetry install` falhou | Volte ao passo 2 e veja o erro |
| `.exe` quebra com `BrowserType.launch: Executable doesn't exist at ...\chrome-win\chrome.exe` | Browser instalado fora do pacote | Refaça passo 3 com `$env:PLAYWRIGHT_BROWSERS_PATH = "0"` ANTES do `playwright install`, depois passo 4 |
| `.exe` muito grande | Esperado — browser embutido | Use `--onedir` se quiser uma pasta em vez de um único arquivo (mesmo tamanho total, mas startup mais rápido) |

---

## Notas técnicas

- O `.exe` lê `config.json` e as pastas `entrada/saida/logs/checkpoint` **ao lado dele** (não embutidos).
- Build é **onedir** — startup ~1-3s em qualquer hardware (não extrai temp toda vez como onefile).
- A pasta `_internal\` contém Python + libs + Chromium. **Não mexer**.
- Captcha do Econsig: renderização inline funciona em Windows Terminal moderno. No `cmd.exe` antigo, cai pra block-char unicode (legível).
- Para diminuir false positive de antivírus em distribuição ampla: assine o executável com um certificado de code-signing.
