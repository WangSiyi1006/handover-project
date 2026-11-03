"""Never-request-handover comparison reference, equivalent to the starter.

It never requests handover. The shared simulator handles initial attachment
and reconnection after RLF. Its displayed score is not an additional grading
baseline or a guaranteed lower bound; A3 remains the grading baseline.
"""

from ..api import Action, Observation


class NoHandoverPolicy:
    def reset(self, config: dict) -> None:
        pass

    def decide(self, observation: Observation) -> Action:
        return {"action": "stay", "target_cell_id": None}
