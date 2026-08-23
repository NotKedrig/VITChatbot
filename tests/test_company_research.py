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
