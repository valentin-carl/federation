import copy
from typing import Dict, Any, Optional


def getCurrentStep(workflow: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    # TODO turn workflow to optional and handle None case
    if len(workflow.get("steps")) == 0:
        return None
    minId = 1e12
    minStep = None
    for step in workflow["steps"]:
        if step["id"] < minId:
            minId = step["id"]
            minStep = step
    assert minStep is not None
    return minStep

def updateWorkflow(workflow: Dict[str, Any]) -> Dict[str, Any]:
    # TODO turn workflow to optional and handle None case
    workflow = copy.deepcopy(workflow)
    steps = workflow["steps"]
    steps.remove(getCurrentStep(workflow))
    workflow["steps"] = steps
    return workflow

def getNextStep(workflow: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    return getCurrentStep(updateWorkflow(workflow))
