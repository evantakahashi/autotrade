# tests/test_proposer.py
import json
from unittest.mock import MagicMock, patch
from src.research.proposer import Proposer, parse_proposal

def test_parse_proposal_valid_json():
    llm_output = """Based on the analysis, I propose increasing the trend weight.

```json
{
  "config_diff": {"weights": {"trend": 0.40, "fundamentals": 0.15}},
  "hypothesis": "Increase trend weight to better capture momentum signals"
}
```"""
    result = parse_proposal(llm_output)
    assert result["config_diff"]["weights"]["trend"] == 0.40
    assert "hypothesis" in result

def test_parse_proposal_no_json():
    result = parse_proposal("I think we should try something different")
    assert result is None

def test_proposer_returns_valid_proposal():
    mock_response = MagicMock()
    mock_response.content = [MagicMock()]
    mock_response.content[0].text = """```json
{
  "config_diff": {"weights": {"trend": 0.40, "fundamentals": 0.15}},
  "hypothesis": "Increase trend weight"
}
```"""
    with patch("src.research.proposer.anthropic") as mock_anthropic:
        mock_client = MagicMock()
        mock_anthropic.Anthropic.return_value = mock_client
        mock_client.messages.create.return_value = mock_response

        proposer = Proposer()
        result = proposer.propose("test context summary")
        assert result is not None
        assert "config_diff" in result
        assert "hypothesis" in result

def test_proposer_retries_on_invalid():
    # First response is invalid, second is valid
    invalid_response = MagicMock()
    invalid_response.content = [MagicMock()]
    invalid_response.content[0].text = "I'm not sure what to suggest"

    valid_response = MagicMock()
    valid_response.content = [MagicMock()]
    valid_response.content[0].text = '```json\n{"config_diff": {"weights": {"trend": 0.40, "fundamentals": 0.15}}, "hypothesis": "test"}\n```'

    with patch("src.research.proposer.anthropic") as mock_anthropic:
        mock_client = MagicMock()
        mock_anthropic.Anthropic.return_value = mock_client
        mock_client.messages.create.side_effect = [invalid_response, valid_response]

        proposer = Proposer(max_retries=2)
        result = proposer.propose("test context")
        assert result is not None
