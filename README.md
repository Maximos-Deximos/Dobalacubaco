# Dobalacubaco
Projeto hackathon

todo: adicionar objetivo/resumo do projeto

# Objetivo

todo: add objetivo

# Requisitos

- Olamma
- Python3

# Instalação

git clone (https://github.com/Maximos-Deximos/projeto)

## Configuração do Ollama

- Instalar modulo qwen3.5:4b

## Configurar ambiente

- fazer arquivo '.env' na raiz do projeto
- popular '.env' com os conteudos em '.env.example'

## Configurar ambiente virtual
cd local/do/projeto

Create virtual enviroment
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
### Instalar dependências
```text
pip install -r requirements.txt
```

## Usagem

- Rodar `python3 -m app.main` no ambiente virtual para o TUI

# Fluxo da aplicação

```text
+--------------------------------------------------+
|                    USUARIO                       |
+--------------------------------------------------+
                       |
                       v
+--------------------------------------------------+
|                   INTERFACE                      | 
|                                                  |
|  - Enviar URL de website                         |
|  - Providenciar Instruções                       |
|  - Gerenciamento de informações de usuario       |
|  - Revisão de funcionamento de agente            |
|  - Aprovação e envio de edital                   |
+--------------------------------------------------+
                       |
                       v
+--------------------------------------------------+
|            CONTROLADOR DE AGENTE                 |
|                                                  |
|  - Recebe instruções de usuario                  |
|  - Gerencia fluxo de execução                    |
|  - Cordenação de componentes                     |
|  - Controle de estados de execução               |
+--------------------------------------------------+
          |                |               |
          v                v               v
+----------------+ +---------------+ +----------------+
|     AGENTE     | |    MEMORIA    | |   SEGURANÇA    |
|                | |               | |                |
|    Ollama      | |    SQLite     | | Validação      |
|                | |               | | Permissões     |
| Raciocino      | | Dados         | | Restrições     |
| Mapeamento     | | Histórico     | | Aprovações     |
+----------------+ +---------------+ +----------------+
          |
          v
+--------------------------------------------------+
|              AUTOMAÇÃO DE NAVEGADOR              |
|                                                  |
|                 Agente_editais                   |
|                                                  |
|  - Contextualização                              |
|  - Sugestoões                                    |
|  - Chat                                          |
|  - Edição de pdf                                 |
|  - Verificação de propostas (coesão/sintaxe)     |
+--------------------------------------------------+
                       |
                       v
+--------------------------------------------------+
|                    USUÁRIO                       |
+--------------------------------------------------+
```
todo: NOME!