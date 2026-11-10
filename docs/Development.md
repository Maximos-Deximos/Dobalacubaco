## Commits
Utilizaremos conventional commits
ex:
```text
git commit -m "feat: add railguards ao agente de I.A"
```

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