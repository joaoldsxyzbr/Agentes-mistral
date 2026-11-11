import io
from typing import Annotated, Literal

import pandas as pd
from pydantic import Field

from mistralai import agents

_df: pd.DataFrame | None = None
_df_name: str | None = None

_OPS = {
    "==": lambda s, v: s == v,
    "!=": lambda s, v: s != v,
    ">": lambda s, v: s > v,
    ">=": lambda s, v: s >= v,
    "<": lambda s, v: s < v,
    "<=": lambda s, v: s <= v,
    "contains": lambda s, v: s.astype(str).str.contains(str(v), case=False, na=False),
    "in": lambda s, v: s.isin(v if isinstance(v, list) else [v]),
}

AggFunc = Literal["sum", "mean", "median", "min", "max", "count", "nunique", "std"]


def _require_loaded() -> pd.DataFrame:
    if _df is None:
        raise agents.ToolError(
            "Nenhum CSV carregado. Use o conector do Google Drive para ler o arquivo e passe o "
            "conteúdo para load_csv."
        )
    return _df


@agents.tool
async def load_csv(
    content: Annotated[str, Field(description="Conteúdo CSV completo, lido do Google Drive.")],
    name: Annotated[str, Field(description="Nome para referenciar o arquivo depois.")] = "dados",
) -> str:
    """Carrega um CSV do Google Drive para análise. Perguntas seguintes usam este arquivo."""
    global _df, _df_name
    _df = pd.read_csv(io.StringIO(content))
    _df_name = name
    return (
        f"Carregado {name}: {len(_df)} linhas, {len(_df.columns)} colunas. "
        "Use describe_columns para ver os detalhes."
    )


@agents.tool
async def describe_columns() -> str:
    """Descreve as colunas do CSV carregado: nome, tipo, nulos e valores de exemplo."""
    frame = _require_loaded()
    lines = [f"Arquivo: {_df_name}", ""]
    for column in frame.columns:
        series = frame[column]
        sample = series.dropna().head(3).tolist()
        lines.append(
            f"- {column} ({series.dtype}): {int(series.isna().sum())} nulos; ex.: {sample}"
        )
    lines.append("")
    lines.append(f"Total: {len(frame)} linhas.")
    return "\n".join(lines)


@agents.tool
async def filter_rows(
    column: Annotated[str, Field(description="Coluna a filtrar.")],
    operator: Annotated[str, Field(description="Operador: ==, !=, >, >=, <, <=, contains ou in.")],
    value: Annotated[str | list[str] | int | float, Field(description="Valor de comparação.")],
) -> str:
    """Filtra as linhas do CSV carregado por uma condição e devolve um resumo do resultado."""
    frame = _require_loaded()
    if column not in frame.columns:
        raise agents.ToolError(
            f"Coluna {column!r} não existe. Colunas: {list(frame.columns)}"
        )
    if operator not in _OPS:
        raise agents.ToolError(f"Operador {operator!r} não suportado. Use: {sorted(_OPS)}")
    series = frame[column]
    mask = _OPS[operator](series, value)
    matched = frame[mask]
    return (
        f"{len(matched)} de {len(frame)} linhas casam com {column} {operator} {value!r}. "
        f"Prévia: {matched.head(5).to_dict(orient='records')}"
    )


@agents.tool
async def group_aggregate(
    group_by: Annotated[str, Field(description="Coluna para agrupar.")],
    agg_column: Annotated[str, Field(description="Coluna numérica a agregar.")],
    agg_func: Annotated[
        AggFunc | list[AggFunc],
        Field(description="Uma função ou uma lista: sum, mean, median, min, max, count, nunique ou std."),
    ] = "sum",
) -> str:
    """Agrupa o CSV carregado por uma coluna e calcula um ou mais agregados sobre outra."""
    frame = _require_loaded()
    for name in (group_by, agg_column):
        if name not in frame.columns:
            raise agents.ToolError(f"Coluna {name!r} não existe. Colunas: {list(frame.columns)}")
    funcs = agg_func if isinstance(agg_func, list) else [agg_func]
    for func in funcs:
        if func not in AggFunc.__args__:
            raise agents.ToolError(f"Agregado {func!r} não suportado. Use: {list(AggFunc.__args__)}")
    grouped = frame.groupby(group_by)[agg_column].agg(funcs)
    if isinstance(grouped, pd.Series):
        grouped = grouped.to_frame()
    return grouped.sort_values(by=list(grouped.columns)[0], ascending=False).head(20).to_string()


agent = agents.Agent(
    model="mistral-large-4",
    name="analista-dados",
    instructions=(
        "Você é um analista de dados conversacional. O usuário cola um link de um arquivo CSV "
        "do Google Drive e faz perguntas em linguagem simples sobre os dados.\n\n"
        "Fluxo:\n"
        "1. Use o conector do Google Drive (google_drive_mcp) para achar o arquivo do link.\n"
        "2. Leia o conteúdo do CSV com as ferramentas do conector.\n"
        "3. Passe o conteúdo para load_csv.\n"
        "4. Use describe_columns para entender as colunas antes da primeira pergunta.\n"
        "5. Responda com filter_rows e group_aggregate, citando números reais.\n\n"
        "Nunca invente números: toda resposta vem do resultado de uma ferramenta. Lembre-se do "
        "arquivo carregado e de tudo que já foi discutido — o usuário não precisa repetir o link "
        "nem re-explicar o contexto entre perguntas. Se uma coluna não existir, liste as que "
        "existem; se um operador não for suportado, diga quais são."
    ),
    connectors=[agents.connector("google_drive_mcp")],
    tools=[load_csv, describe_columns, filter_rows, group_aggregate],
)
