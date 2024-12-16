"""Automation helper functions for Modbus Manager."""
from typing import Any, Dict, List, Optional

def create_threshold_automation(
    name: str,
    unique_id: str,
    entity_id: str,
    threshold: float,
    above: bool = True,
    for_time: Optional[str] = None,
    message_template: Optional[str] = None,
    actions: Optional[List[Dict[str, Any]]] = None
) -> Dict[str, Any]:
    """Create a threshold-based automation."""
    automation = {
        "id": unique_id,
        "alias": name,
        "trigger": {
            "platform": "numeric_state",
            "entity_id": entity_id,
            "above" if above else "below": threshold
        }
    }
    
    if for_time:
        automation["trigger"]["for"] = for_time
        
    if not actions:
        if not message_template:
            message_template = (
                f"{'Above' if above else 'Below'} threshold: "
                "{{{{ states(trigger.entity_id) }}}} "
                "{{{{ state_attr(trigger.entity_id, 'unit_of_measurement') }}}}"
            )
            
        actions = [{
            "service": "persistent_notification.create",
            "data": {
                "title": name,
                "message": message_template
            }
        }]
        
    automation["action"] = actions
    return automation

def create_value_change_automation(
    name: str,
    unique_id: str,
    entity_id: str,
    to_state: Optional[str] = None,
    from_state: Optional[str] = None,
    for_time: Optional[str] = None,
    actions: Optional[List[Dict[str, Any]]] = None
) -> Dict[str, Any]:
    """Create a state-change based automation."""
    trigger = {
        "platform": "state",
        "entity_id": entity_id
    }
    
    if to_state is not None:
        trigger["to"] = to_state
    if from_state is not None:
        trigger["from"] = from_state
    if for_time:
        trigger["for"] = for_time
        
    automation = {
        "id": unique_id,
        "alias": name,
        "trigger": trigger
    }
    
    if actions:
        automation["action"] = actions
        
    return automation 