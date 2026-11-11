from typing import Annotated, Literal

from pydantic import Field

from mistralai import agents

Focus = Literal["all", "bugs", "security", "ux", "style"]


@agents.tool
async def review_code(
    code: Annotated[str, Field(description="Código a revisar.")],
    focus: Annotated[Focus, Field(description="Foco: all, bugs, security, ux ou style.")] = "all",
) -> str:
    """Revisa código: bugs, segurança, UX e estilo. Devolve uma lista de achados."""
    findings: list[str] = []
    lines = code.splitlines()
    if not lines:
        return "Nada a revisar: código vazio."

    joined = "\n".join(lines)
    lowered = joined.lower()

    if focus in ("all", "security"):
        for pattern in ("api_key", "apikey", "secret", "password", "token", "bearer "):
            if pattern in lowered:
                findings.append(
                    f"Segurança: possível segredo no código ({pattern!r}); mova para variável de ambiente."
                )
        for pattern in ("eval(", "exec(", "os.system(", "subprocess."):
            if pattern in lowered:
                findings.append(
                    f"Segurança: execução dinâmica com {pattern!r}; evite input não tratado."
                )
        for pattern in ("select * from", "insert into", "update ", "delete from"):
            if pattern in lowered and ("+" in joined or "f\"" in lowered or "f'" in lowered):
                findings.append(
                    "Segurança: possível injeção de SQL por concatenação; use query parametrizada."
                )

    if focus in ("all", "bugs"):
        for number, line in enumerate(lines, start=1):
            stripped = line.strip()
            if stripped.startswith("#") and len(stripped) > 2:
                continue
            if " == None" in line or " != None" in line:
                findings.append(f"Bug provável na linha {number}: compare com `is None`.")
            if "except:" in line:
                findings.append(f"Estilo na linha {number}: `except:` pega-tudo; liste as exceções.")
            if "TODO" in line.upper():
                findings.append(f"Pendente na linha {number}: {stripped}")

    if focus in ("all", "ux"):
        if "input(" in lowered and "int(" not in lowered and "float(" not in lowered:
            findings.append("UX: `input()` sem conversão de tipo; valide antes de usar.")
        if "print(" in lowered and "input(" in lowered:
            findings.append("UX: mistura de leitura e escrita no terminal; separe entrada e saída.")

    if focus in ("all", "style"):
        for number, line in enumerate(lines, start=1):
            if len(line) > 88:
                findings.append(f"Estilo: linha {number} passa de 88 colunas.")
            if line != line.rstrip():
                findings.append(f"Estilo: espaço no fim da linha {number}.")

    if not findings:
        return "Nenhum achado no foco escolhido."
    return f"{len(findings)} achado(s):\n" + "\n".join(f"- {finding}" for finding in findings)


@agents.tool
async def security_check(
    code: Annotated[str, Field(description="Código a verificar.")],
) -> str:
    """Checagem de segurança (OWASP): segredos, injeção, execução dinâmica."""
    return await review_code(code, focus="security")


@agents.tool
async def ux_critique(
    description: Annotated[str, Field(description="Descrição da tela ou do fluxo de UI.")],
) -> str:
    """Critica uma descrição de UI/UX com heurísticas de usabilidade."""
    findings: list[str] = []
    lowered = description.lower()
    if "senha" in lowered or "password" in lowered:
        findings.append("UX: campo de senha deve mascarar a entrada e ter botão de mostrar/ocultar.")
    if "formulário" in lowered or "form" in lowered:
        findings.append("UX: valide no cliente e no servidor; mostre o erro perto do campo.")
    if "tabela" in lowered or "lista" in lowered:
        findings.append("UX: limite o que a tela mostra por vez e ofereça busca paginação.")
    if not findings:
        findings.append("UX: descreva a tela com mais detalhe para uma crítica útil.")
    return f"{len(findings)} ponto(s):\n" + "\n".join(f"- {finding}" for finding in findings)


agent = agents.Agent(
    model="mistral-large-4",
    name="dev-expert",
    instructions=(
        "Você é um especialista em programação, UI/UX e segurança. O usuário cola código, "
        "descreve uma tela ou pergunta conceitos, e você responde com análise prática.\n\n"
        "Fluxo:\n"
        "1. Código colado: use review_code (e security_check para o foco em segurança).\n"
        "2. Descrição de tela: use ux_critique.\n"
        "3. Repositório, PR ou issue: use o conector do GitHub para ler.\n"
        "4. Escreva ou refatore código quando pedirem.\n\n"
        "Regra: toda crítica vem da análise, não de achismo — cite a linha ou o trecho. "
        "Se um trecho não couber na resposta, diga o que faltou ver."
    ),
    connectors=[agents.connector("github")],
    tools=[review_code, security_check, ux_critique],
)
