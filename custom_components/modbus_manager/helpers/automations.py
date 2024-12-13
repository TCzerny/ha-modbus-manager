def create_automation(name, trigger, action):
    """Erstellt eine Automation basierend auf den device_definition."""
    return {
        "name": name,
        "trigger": trigger,
        "action": action
    } 