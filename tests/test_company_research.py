import pytest
from unittest.mock import MagicMock, patch

from app.agents.company_research import company_research_node
from app.graph.state import AgentState
from app.rag.citations import Citation

@pytest.fixture
def mock_answer_with_rag():
    with patch("app.agents.company_research.answer_with_rag") as mock_rag:
        yield mock_rag

def test_company_research_normal(mock_answer_with_rag):
    mock_rag_result = MagicMock()
    mock_rag_result.answer = "Novatech requires a 7.0 CGPA."
    
    # Mock some citations
    c1 = Citation(
        citation_number=1,
        chunk_id="chk1",
        doc_id="novatech",
        title="Novatech Eligibility",
        text_snippet="Requires 7.0 CGPA",
        full_text="Requires 7.0 CGPA",
        similarity_score=0.9,
        chunk_index=0,
        char_start=0,
        char_end=15,
        chunking_strategy="fixed_size"
    )
    mock_rag_result.citations = [c1]
    mock_rag_result.retrieved_chunks = [MagicMock()] # Just for formatting
    mock_answer_with_rag.return_value = mock_rag_result
    
    # We must patch format_inline to prevent it crashing on our MagicMock chunk
    with patch("app.rag.citations.format_inline", return_value="Sources: [1] Novatech"):
        state: AgentState = {
            "messages": [{"role": "user", "content": "What is the CGPA requirement for Novatech?"}]
        }
        
        result = company_research_node(state)
        
        assert "messages" in result
        agent_reply = result["messages"][0]["content"]
        assert "Novatech requires a 7.0 CGPA." in agent_reply
        assert "Sources: [1] Novatech" in agent_reply
        
        assert "citations" in result
        assert len(result["citations"]) == 1
        assert result["citations"][0]["doc_id"] == "novatech"
        
        assert result["last_agent_output"] == agent_reply


def test_company_research_no_context(mock_answer_with_rag):
    mock_rag_result = MagicMock()
    mock_rag_result.answer = "I do not have sufficient information to answer this."
    mock_rag_result.citations = []
    mock_answer_with_rag.return_value = mock_rag_result
    
    state: AgentState = {
        "messages": [{"role": "user", "content": "Tell me about a random company not in DB."}]
    }
    
    result = company_research_node(state)
    
    agent_reply = result["messages"][0]["content"]
    assert "sufficient information" in agent_reply
    assert len(result["citations"]) == 0


def test_company_research_failure(mock_answer_with_rag):
    mock_answer_with_rag.side_effect = Exception("DB Connection Error")
    
    state: AgentState = {
        "messages": [{"role": "user", "content": "Help"}]
    }
    
    result = company_research_node(state)
    
    agent_reply = result["messages"][0]["content"]
    assert "couldn't search the knowledge base" in agent_reply
    assert len(result["citations"]) == 0


def test_company_research_dynamic_collection_selection(mock_answer_with_rag):
    """Test that the collection name can be dynamically overridden via config."""
    mock_rag_result = MagicMock()
    mock_rag_result.answer = "Dynamic response"
    mock_rag_result.citations = []
    mock_rag_result.retrieved_chunks = []
    
    # We must set a safe MagicMock for the llm_response to prevent msgpack failures 
    # when the runtime_metadata dict is serialized
    llm_resp = MagicMock()
    llm_resp.model_name = "mock"
    llm_resp.model_version = "1.0"
    llm_resp.cached = True
    mock_rag_result.llm_response = llm_resp
    
    mock_answer_with_rag.return_value = mock_rag_result
    
    state: AgentState = {
        "messages": [{"role": "user", "content": "Hello"}]
    }
    
    # 1. Test explicit collection_name
    config = {"configurable": {"collection_name": "vitian_kb_semantic"}}
    company_research_node(state, config=config)
    
    # Verify answer_with_rag was called with "vitian_kb_semantic"
    mock_answer_with_rag.assert_called_with(
        question="Hello",
        collection_name="vitian_kb_semantic",
        temperature=0.0,
        use_cache=True
    )
    
    # 2. Test chunking_strategy fallback
    config2 = {"configurable": {"chunking_strategy": "fixed_size"}}
    company_research_node(state, config=config2)
    
    # Verify it builds the collection name correctly
    mock_answer_with_rag.assert_called_with(
        question="Hello",
        collection_name="vitian_kb_fixed_size",
        temperature=0.0,
        use_cache=True
    )
