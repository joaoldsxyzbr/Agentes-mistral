# dev-expert

Agente especialista em programação, UI/UX e segurança, construído com o Mistral Agents SDK.
Você cola código, descreve uma tela, pergunta conceitos ou aponta um repositório/PR/issue do
GitHub — e recebe análise prática, sem execução arbitrária de código.

## Ferramentas

| Ferramenta | O que faz |
| --- | --- |
| `review_code` | Revisa código: bugs, segurança, UX e estilo, com foco escolhível |
| `security_check` | Checagem de segurança (OWASP): segredos, injeção, execução dinâmica |
| `ux_critique` | Critica uma descrição de UI/UX com heurísticas de usabilidade |

O conector `github` é o que o agente usa para ler repositórios, PRs e issues; as ferramentas
acima só analisam o que você cola.

## Desenvolvimento

```bash
uv sync
uv run agents chat
```

## Deploy

```bash
agents deploy
```
