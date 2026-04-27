from pydantic import BaseModel, Field

from agents import Agent

from emet_agents.model_name import resolved_chat_model

HOW_MANY_SEARCHES = 5

INSTRUCTIONS = f"""You plan web searches to fact-check a user's question rigorously.

User input (scope):
- Treat the submission as a **fact-check target**: something to verify with evidence (a question, claim, or mixed text with a checkable core).
- The user may phrase it freely. Decompose it into **verifiable** search queries. If the text mixes in non-factual or off-topic asks, still prioritize queries for assertions that can be checked with public sources.
- If almost nothing is checkable, still output {HOW_MANY_SEARCHES} best-effort queries that get closest to the factual core.

Rules:
- Prefer searches that surface official or primary sources (.gov, .edu, WHO, NIH, Reuters, AP, BBC, institution sites).
- Include diverse queries so results can be cross-checked (multiple independent domains).
- Output exactly {HOW_MANY_SEARCHES} searches.
"""


class WebSearchItem(BaseModel):
    reason: str = Field(description="Why this search matters for verifying the claim.")
    query: str = Field(description="Concise web search query.")


class WebSearchPlan(BaseModel):
    searches: list[WebSearchItem]


planner_agent = Agent(
    name="FactCheckPlanner",
    instructions=INSTRUCTIONS,
    model=resolved_chat_model(),
    output_type=WebSearchPlan,
)
