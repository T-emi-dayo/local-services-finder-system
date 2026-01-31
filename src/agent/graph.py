"""
LangGraph Assembly - Simplified Security Agent

A streamlined security agent for multiagent systems.
Receives question, hypothesis, geo_focus, and time_horizon from config.
Executes via ReAct agent with tools, returns final_answer, sources, and metadata.
"""

import logging
from typing import Any, Dict
from langchain_core.messages import HumanMessage
from langgraph.graph import StateGraph, END

# Import your custom models
from src.models.FormConfig import FormConfig
from src.agent.nodes.ExtractionAgent import service_agent
from src.agent.nodes.SynthesisNode import synthesize
from src.agent.state import AgentState

logger = logging.getLogger(__name__)

# ============================================================================
# GRAPH BUILDER
# ============================================================================

def build_lsf_agent_graph() -> StateGraph:
    """
    Build the LSF agent graph.
    
    Returns:
        Compiled LangGraph StateGraph
    """
    
    logger.info("Building LSF Agent Graph")
    
    # Create graph
    graph = StateGraph(AgentState)
    
    # Add nodes
    logger.info("   Adding agent node...")
    graph.add_node("agent", service_agent)
    graph.add_node("synthesis", synthesize)
    
    # Add edges
    logger.info("   Adding edges...")
    graph.set_entry_point("agent")
    graph.add_edge("agent", "synthesis")
    graph.add_edge("synthesis", END)
    
    # Compile graph
    logger.info("   Compiling graph...")
    compiled_graph = graph.compile()
    
    logger.info("[OK] Graph built successfully!")
    
    return compiled_graph

# ============================================================================
# AGENT RUNNER
# ============================================================================

class LSFAgent:
    """
    LSF Agent - Main interface.
    
    Handles graph execution and output formatting.
    """
    
    def __init__(self):
        logger.info("Initializing Finance Agent...")
        self.graph = build_lsf_agent_graph()
        logger.info("[OK] LSFAgent ready")
    
    def run(self, config: FormConfig) -> Dict[str, Any]:
        """
        Run the agent with the given config.
        
        Args:
            config: LSF AgentConfig with question, hypothesis, geo_focus, time_horizon.
        
        Returns:
            Dictionary with final_answer, metadata, sources, and state.
        """
        
        logger.info(f"[SEARCH] Running FinanceAgent")
        logger.info(f"   Service: {config.service_type}")
        logger.info(f"   Location City: {config.location_city}")
        logger.info(f"   Location Area: {config.location_area}")
        logger.info(f"   Urgency: {config.urgency}")
        logger.info(f"   Budget: {config.budget}")
        logger.info(f"   Additional Details: {config.additional_details}")
        
        # Initialize simplified state
        initial_state = {
            "config": config,
            "candidates_search_history": [],
            "message_history": [],
            "sources": [],
            "final_response": [],
            "summary": "",
    }
        
        # Run graph
        try:
            logger.info("Executing graph...")
            final_state = self.graph.invoke(initial_state)
            logger.info("[OK] Graph execution complete")
        except Exception as e:
            logger.error(f"[ERROR] Graph execution failed: {e}", exc_info=True)
            raise
        
        # Format output
        output = {
            "final_response": final_state.get("final_answer", ""),
            "metadata": final_state.get("metadata", {}),
            "sources": final_state.get("sources", []),
            "state": final_state,
        }
        
        logger.info(f"[OK] Agent run complete")
        return output

# ============================================================================
# CONVENIENCE FUNCTION
# ============================================================================

def run_agent(config = FormConfig) -> Dict[str, Any]:
    """
    Convenience function to run the finance agent.
    
    Returns:
        Agent final response.
    """
    
    agent = LSFAgent()
    return agent.run(config)