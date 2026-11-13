# Dobalacubaco
Projeto hackathon

todo: adicionar objetivo/resumo do projeto

# Objetivo

todo: add objetivo

# Requisitos

- Python3
- Ollama (opcional, usado por padrão para chat e embeddings locais)
- Uma chave de API, caso queira usar um provedor externo

# Instalação

git clone (https://github.com/Maximos-Deximos/projeto)

## Configuração do Ollama (padrão local)

- Instalar modulo qwen3.5:4b

## Provedores externos de IA

O agente funciona com qualquer um dos provedores abaixo, configurado no `.env`:

| `AI_PROVIDER` | Chat | Embeddings |
| ------------- | ---- | ---------- |
| `ollama`      | Sim  | Sim        |
| `openai`      | Sim  | Sim        |
| `openrouter`  | Sim  | Não        |
| `groq`        | Sim  | Não        |
| `deepseek`    | Sim  | Não        |
| `anthropic`   | Sim  | Não        |
| `gemini`      | Sim  | Sim        |

Exemplo com OpenAI:

```env
AI_PROVIDER=openai
AI_MODEL=gpt-4o-mini
AI_API_KEY=sk-...
# Embeddings continuam locais por padrão
AI_EMBED_PROVIDER=ollama
AI_EMBED_MODEL=bge-m3
```

Exemplo com Anthropic (o provedor não oferece embeddings):

```env
AI_PROVIDER=anthropic
AI_MODEL=claude-3-5-haiku-latest
AI_API_KEY=sk-ant-...
AI_EMBED_PROVIDER=ollama
```

Para desativar a busca semântica e usar apenas a busca lexical:

```env
AI_EMBED_PROVIDER=none
```

As chaves específicas de cada provedor também são aceitas:
`OPENAI_API_KEY`, `OPENROUTER_API_KEY`, `GROQ_API_KEY`, `DEEPSEEK_API_KEY`,
`ANTHROPIC_API_KEY`, `GEMINI_API_KEY` e `GOOGLE_API_KEY`.

Ao usar um provedor externo, os trechos enviados ao modelo saem da máquina.
Mantenha `AI_EMBED_PROVIDER=ollama` se quiser que a indexação continue local.

As variáveis antigas `OLLAMA_MODEL`, `OLLAMA_EMBED_MODEL` e `OLLAMA_TIMEOUT`
continuam aceitas como valores padrão.

## Histórico de conversa

As perguntas e respostas do chat ficam salvas no banco SQLite local por área de
trabalho. Ao fechar e abrir a aplicação novamente, a conversa é restaurada:

- na TUI, a aba **Conversa** recarrega as mensagens antigas e usa as últimas
  trocas como contexto; `Ctrl+L` ou o botão **Limpar** removem a conversa salva
  após confirmação;
- no REPL (`chat repl`), o início informa quantas mensagens foram restauradas,
  `/history [N]` mostra as antigas (`/history all` mostra todas) e `/clear`
  apaga o histórico;
- `chat ask` também retoma a conversa anterior e grava a nova pergunta/resposta.

`RAG_HISTORY_TURNS` controla apenas quantas trocas são enviadas ao modelo como
contexto. O histórico completo permanece salvo até ser limpo ou até a área de
trabalho ser excluída.

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