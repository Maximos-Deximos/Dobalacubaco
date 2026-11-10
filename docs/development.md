# Guia de desenvolvimento


## Requisitos

- Olamma
- Python3

# Configuração do projeto

## Ollama

[Instalar Ollama](https://github.com/ollama/ollama)

Instalar modulo qwen3.5:4b

## Ambiente virtual
cd local/do/projeto

### Criar ambiente virtual
```text
python3 -m venv .venv
```
### Entrar no ambiente virtual

Bash/zsh
```text
source .venv/bin/activate
```
fish
```text
source .venv/bin/activate.fish
```
pwsh
```text
<venv>/bin/Activate.ps1
```
cmd.exe
```text
C:\> <venv>\Scripts\activate.bat
```
PowerShell
```text
PS C:\> <venv>\Scripts\Activate.ps1
```

## Commits
Utilizaremos conventional commits
exemplo:
`git commit -m "feat: add railguards ao agente de I.A"`

## Branches

- `main` - código estável
- `dev-*` - novas funcionalidades do agente
- `fix-*` - para fixes
- `feat-*` - para novas features especificas

## Ambiente virtual
Blibliotecas utilizadas:
- ollama         | Integra a I.A
- playwright     | Automação de navegador
- pydantic       | Validação de dados
- sqlalchemy     | ORM
- python-dotenv  | Configuração de ambiente
- fastapi        | API
- uvicorn        | API
- pytest         | Testar agente
- pytest-asyncio | Testar agente
