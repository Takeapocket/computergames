from scripts.tournament import format_markdown_matrix, parse_ai_list


def test_parse_ai_list_strips_spaces():
    assert parse_ai_list("random, greedy,greedy_risk") == ["random", "greedy", "greedy_risk"]


def test_parse_ai_list_rejects_empty_entry():
    import pytest

    with pytest.raises(ValueError):
        parse_ai_list("random,,greedy")


def test_format_markdown_matrix_contains_headers_and_diagonal():
    ais = ["random", "greedy"]
    matrix = {
        "random": {"greedy": 25.0},
        "greedy": {"random": 75.0},
    }

    output = format_markdown_matrix(ais, matrix)

    assert "| AI | random | greedy |" in output
    assert "| random | - | 25.0% |" in output
    assert "| greedy | 75.0% | - |" in output


def test_format_markdown_matrix_handles_missing_cell_as_dash():
    ais = ["random", "greedy", "greedy_risk"]
    matrix = {
        "random": {"greedy": 12.0, "greedy_risk": 8.0},
        "greedy": {"random": 88.0, "greedy_risk": 42.0},
        "greedy_risk": {"random": 92.0, "greedy": 58.0},
    }

    output = format_markdown_matrix(ais, matrix)

    assert "| greedy_risk | 92.0% | 58.0% | - |" in output
