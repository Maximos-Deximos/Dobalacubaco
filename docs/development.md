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

# Etapas de desenvolvimento

### Etapa 1 - Fundação
- Add config.py, logging_config.py, .env.example.
- Add Pydantic schemas e SQLAlchemy models; create_all na primeira run.
- Add doctor CLI skeleton.
### Etapa 2 - Memoria de perfil
- Implementar database.py, user_repository.py.
- Implementar commando de perfil init/show/set.
- Testes de unidade e persistencia de perfil
### Etapa 3 - Browser + detecção
- Implementar BrowserManager, PageInspector, FormDetector.
- Criar fixtures HTML de editais.
- Testes de detecção.
### Etapa 4 - Mapeamento de I.A
- Implementar OllamaClient, prompts.py, response_parser.py.
- Add mapeamento de contingência determinístico.
- Tests com respostas fictícias.
### Etapa 5 - Segurança + aprovação
- Implementar permission.py, validator.py, approval.py.
- Add sensitive-field handling e regras de dominio.
- Tests de caminhos rejeitados.
### etapa 6 - Orchestração + CLI end-to-end
- Implementar state.py, planner.py, executor.py, controller.py, form_filler.py, cli.py.
- Implementar fill e comandos de historico.
- Persistir snapshots de campos e status de execução.
### Milestone 7 - Integração + hardening
- Testes end-to-end de fixtures.
- Verificar envio, regreas de dominios, timeouts, e falhas graciosas em Ollama.