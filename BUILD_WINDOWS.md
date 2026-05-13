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

### 3. Instalar o browser do Playwright

```powershell
poetry run playwright install chromium
```

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

O executável fica em:

```
dist\consig-bot.exe
```

Tamanho esperado: **200-300 MB** (normal — o browser do Playwright está embutido).

---

## Montar o pacote para o usuário final

### Estrutura desejada

```
consig-bot-windows\
  consig-bot.exe        ← de dist\
  executar.bat          ← da raiz do repo
  config.json           ← copia de config.example.json com logins reais
  entrada\              ← pasta vazia (planilhas vão aqui)
  saida\                ← pasta vazia (resultados aparecem aqui)
```

### Comandos para montar

Na raiz do repo, no PowerShell:

```powershell
$out = "consig-bot-windows"
New-Item -ItemType Directory -Force $out, "$out\entrada", "$out\saida" | Out-Null
Copy-Item dist\consig-bot.exe $out\
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
| Antivírus bloqueia o `.exe` | PyInstaller onefile sem assinatura | Adicione exceção, ou use `--onedir` (rode `pyinstaller pyinstaller.spec --onedir ...`) |
| `.exe` abre e fecha rápido | Erro no `config.json` | Rode pelo `executar.bat` (tem `pause`) ou pelo `cmd` manualmente |
| `playwright: command not found` no passo 3 | `poetry install` falhou | Volte ao passo 2 e veja o erro |
| `.exe` muito grande | Esperado — browser embutido | Use `--onedir` se quiser uma pasta em vez de um único arquivo (mesmo tamanho total, mas startup mais rápido) |

---

## Notas técnicas

- O `.exe` lê `config.json` e as pastas `entrada/saida/logs/checkpoint` **ao lado dele** (não embutidos).
- Primeira execução pode demorar 10-20s descompactando o onefile na pasta temp.
- Captcha do Econsig: renderização inline funciona melhor no **Windows Terminal** (sixel) que no `cmd.exe` antigo. No cmd, o fallback abre a imagem no visualizador padrão do Windows.
- Para diminuir false positive de antivírus em distribuição ampla: assine o executável com um certificado de code-signing.
