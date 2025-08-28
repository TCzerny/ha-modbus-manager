import os
import yaml

TEMPLATE_DIR = "custom_components/modbus_manager/device_templates"

def load_templates():
    templates = {}
    for filename in os.listdir(TEMPLATE_DIR):
        if filename.endswith(".yaml"):
            path = os.path.join(TEMPLATE_DIR, filename)
            with open(path, "r") as f:
                try:
                    data = yaml.safe_load(f)
                    name = data.get("name")
                    registers = data.get("registers", [])
                    if name and isinstance(registers, list):
                        templates[name] = registers
                except yaml.YAMLError as e:
                    print(f"Fehler beim Parsen von {filename}: {e}")
    return templates
