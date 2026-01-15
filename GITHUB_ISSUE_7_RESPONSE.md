# Response for GitHub Issue #7

---

Hello @goranach,

Thank you for your request regarding `default_entity_id`.

Unfortunately, we cannot directly implement `default_entity_id` because:

1. **No Base Class Support**: The Home Assistant Entity Base Classes (`SensorEntity`, `SwitchEntity`, etc.) do not have a `default_entity_id` attribute. `default_entity_id` is a YAML configuration option specific to the Template integration, not an entity attribute that can be set programmatically.

2. **Different System Architecture**: We use a YAML-based template system that creates entities directly from Modbus registers. The Template integration uses a different architecture and mechanisms that don't apply to our integration.

3. **Standard Home Assistant Behavior**: We intentionally removed any manual setting of `entity_id` in our code to follow Home Assistant's standard behavior. Our implementation follows Home Assistant's entity guidelines:

   **How Home Assistant Generates `entity_id`:**

   - We set `has_entity_name = True` (mandatory for new integrations) in all our entity classes
   - Each entity has a `name` property (e.g., "Battery Voltage") and a `unique_id` (e.g., "SG_battery_voltage")
   - All entities are members of a device (linked via `device_info`)
   - Home Assistant uses the `unique_id` (not the device name + entity name) to generate the `entity_id` in the format `{platform}.{sanitized_unique_id}`
   - The `unique_id` is sanitized (spaces/special characters converted to underscores, lowercase) to create a valid `entity_id`
   - If a conflict exists, Home Assistant appends a number (e.g., `.2`, `.3`) to ensure uniqueness
   - Once registered in the entity registry, the `entity_id` remains stable even across restarts

   **Note:** The `friendly_name` (display name) is generated differently - it combines the device name with the entity name (e.g., "SG (Sungrow SHx Dynamic) Battery Voltage"), but this does not affect the `entity_id`.

**Our Implementation:**

In our code, we follow Home Assistant's entity guidelines:

- All entities have `has_entity_name = True` set
- Each entity's `name` property contains only the data point name (e.g., "Battery Voltage"), not the device name
- Each entity has a `unique_id` that includes the device prefix (e.g., "SG_battery_voltage")
- All entities are linked to a device via `device_info` with the device name format `"{prefix} ({template_name})"` (e.g., "SG (Sungrow SHx Dynamic)")
- We do **not** set `entity_id` manually - Home Assistant generates it automatically from `unique_id`
- The resulting `entity_id` will be `sensor.sg_battery_voltage` (sanitized from the `unique_id`)

**Workaround/Solution:**

You can control the desired `entity_id` by setting the `unique_id` in your template. Note that the prefix is **mandatory** and will always be added to the `unique_id` to distinguish between multiple devices:

```yaml
sensors:
  - name: "Battery Voltage"
    unique_id: "battery_voltage"  # Will become {prefix}_battery_voltage, then sensor.{prefix}_battery_voltage
    address: 3600
    # ...
```

The prefix ensures that entities from different devices (e.g., multiple inverters) have unique identifiers and don't conflict with each other.

**Alternative Consideration:**

If you have a specific use case where you need more control over the `entity_id` format, please describe your requirements, and we can evaluate potential solutions.

Best regards
