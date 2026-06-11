"""
Local Services Finder - Agent Graph

Flow:
  resolve_intent → orchestrate_tools → [cleanup →] rank_and_synthesize → END

Conditional edge after orchestrate_tools:
  synthesis_reason == "not_found" → skip cleanup, go straight to rank_and_synthesize
  otherwise                       → cleanup → rank_and_synthesize

All nodes catch their own exceptions and set synthesis_reason accordingly,
so rank_and_synthesize always executes and always returns a meaningful response.
"""

import logging
from typing import Any, Dict

from langgraph.graph import StateGraph, END

from src.agent.state import AgentState
from src.agent.nodes.IntentResolutionNode import resolve_intent
from src.agent.nodes.ToolOrchestrationNode import orchestrate_tools
from src.agent.nodes.CleanupNode import cleanup
from src.agent.nodes.RankingSynthesisNode import rank_and_synthesize
from src.models.FormConfig import FormConfig

logger = logging.getLogger(__name__)


def _route_after_tools(state: AgentState) -> str:
    reason = state.synthesis_reason
    if reason == "not_found":
        logger.info("ROUTE | orchestrate_tools -> rank_and_synthesize (no candidates found)")
        return "rank_and_synthesize"
    logger.info("ROUTE | orchestrate_tools -> cleanup")
    return "cleanup"


def build_graph() -> StateGraph:
    graph = StateGraph(AgentState)

    graph.add_node("resolve_intent", resolve_intent)
    graph.add_node("orchestrate_tools", orchestrate_tools)
    graph.add_node("cleanup", cleanup)
    graph.add_node("rank_and_synthesize", rank_and_synthesize)

    graph.set_entry_point("resolve_intent")
    graph.add_edge("resolve_intent", "orchestrate_tools")
    graph.add_conditional_edges(
        "orchestrate_tools",
        _route_after_tools,
        {"cleanup": "cleanup", "rank_and_synthesize": "rank_and_synthesize"},
    )
    graph.add_edge("cleanup", "rank_and_synthesize")
    graph.add_edge("rank_and_synthesize", END)

    return graph.compile()


class LSFAgent:
    def __init__(self):
        logger.info("Initializing LSF Agent...")
        self.graph = build_graph()
        logger.info("LSF Agent ready")

    def run(self, config: FormConfig) -> Dict[str, Any]:
        logger.info("=" * 60)
        logger.info("GRAPH | Starting LSF Agent run")
        logger.info(f"  service='{config.service_type}' | city='{config.location_city}' | area='{config.location_area}'")
        initial_state = AgentState(config=config)

        try:
            final_state: dict = self.graph.invoke(initial_state.model_dump())
        except Exception as e:
            logger.error(f"GRAPH | Run failed: {e}", exc_info=True)
            raise

        candidates = final_state.get("final_candidates", [])
        logger.info("=" * 60)
        logger.info(f"GRAPH | Run complete — {len(candidates)} final candidate(s) returned")
        logger.info("=" * 60)

        return {
            "final_candidates": candidates,
            "summary": final_state.get("summary", ""),
            "sources": final_state.get("sources", []),
        }


def run_agent(config: FormConfig) -> Dict[str, Any]:
    return LSFAgent().run(config)
