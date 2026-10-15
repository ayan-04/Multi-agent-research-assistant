from src.budget import Budget
from src.config import Settings
from src.errors import BudgetExceededError


def test_charge_stops_at_the_cap():
    budget = Budget(Settings(max_llm_calls=1, max_searches=1, max_fetches=1, max_embed_calls=1))
    budget.charge("llm")
    budget.charge("search")
    budget.charge("fetch")
    budget.charge("embed")
    try:
        budget.charge("llm")
        raised = False
    except BudgetExceededError:
        raised = True
    assert raised
    assert budget.llm_calls == 1


def test_unknown_kind_is_rejected():
    budget = Budget(Settings())
    try:
        budget.charge("teleport")
        raised = False
    except ValueError:
        raised = True
    assert raised
