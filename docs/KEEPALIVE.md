# Cyclic writes (`keepalive`)

Some devices only follow a written value while they keep receiving writes. A typical case is external battery management: the inverter returns to its own control once no write arrives within a device-side timeout. A normal control writes once, so it silently loses effect after that timeout, and its read-back may still show the written value.

`keepalive` is opt-in per control. Templates without it keep the normal write-once behavior.

## Template

```yaml
keepalive_groups:
  battery:
    name: "External battery control"   # name of the group switch
    interval: 15                       # seconds between rounds (minimum 5)
    min_write_spacing_ms: 1000         # gap between two writes of the same round (default 1000)
    max_failures: 3                    # consecutive failed rounds or read-back mismatches before the group stops (default 3)

controls:
  - type: number
    name: "Battery Max Discharge Power"
    unique_id: "battery_max_discharge_limit"
    address: 1040
    data_type: float32
    count: 2
    swap: word
    keepalive:
      group: battery
      release: stop                    # stop (default): just stop writing | write: send release_value once on switch off
      release_value: 10000             # required for release: write
      clamp_max_to_register: battery_soc   # optional: never write more than this register's latest value
      clamp_min_to_register: some_register # optional: never write less than this register's latest value
      clamp_max_age: 60                # optional: max age of the clamp source in seconds (default 60)
      mismatch_tolerance: 5            # optional: absolute tolerance for the read-back check
```

`keepalive` works on `number`, `select` and `switch` controls on holding registers. Clamps work on `number` controls. Clamp sources are `unique_id`s of the same device (with or without `{PREFIX}_`).

## Behavior

- Each group gets a **switch** (`<prefix>_<group>_keepalive`) and a **status sensor** (`…_status`: `off`, `active` or `stopped`, with counters as attributes).
- Setting a control writes it once as before, including the normal read-back verify, and stores the value as the group's setpoint.
- While the group switch is **on**, all stored setpoints of the group are rewritten every `interval` seconds, spaced by `min_write_spacing_ms`. Cyclic writes use the normal write path (same encoding, same I/O lock) without the number entity's read-back verify.
- The switch **starts off** after every restart, and setpoints are never restored from the recorder. Turning the switch off clears the setpoints; set the controls again before turning it back on.
- Before each round, the latest polled value of each control is compared with the last written value. A mismatch is logged and counted. A clean read resets the count. `max_failures` consecutive mismatches of one control, or `max_failures` consecutive rounds with failed writes, stop the group.
- If a clamp source is unavailable or older than `clamp_max_age`, the group stops instead of writing a guessed value.
- If the link is down or the integration unloads, the group stops. No final write is sent; the device falls back through its own timeout.
- Turning the switch off stops the writes. Only controls with `release: write` get one release write, and only while the link is up.
- Turning the switch off while the group is already off or stopped writes nothing and keeps any values set in the meantime.
- Home Assistant shutdown, unloading the entry, and removing or disabling the group switch all stop the group without writing.
- A write that is already on the wire is never aborted. A stopped group is caught by the check under the I/O lock right before sending.
- The minimum gap applies to all keepalive writes of a hub, across groups.
- Turning the switch on while the link is down or the last poll failed is refused with an error.
- A stop clears the stored values, including a stop after a single failed poll. Set the values again before turning the switch back on.

## Notes for template authors

- Put clamp sources in a scan group that polls more often than `clamp_max_age`, otherwise the group stops on every round.
- With the Home Assistant core Modbus backend a dead device is often only noticed through failed writes (`max_failures`), because the hub can report "connected" while reads fail.

- Choose `interval` well below the device timeout. Some devices ignore writes that come in quick succession; use `min_write_spacing_ms` for that.
- Several writers on the same device (another integration, an automation) can keep each other's values alive through a shared timeout. Document this in the device README.
- A read-back may show the effective value instead of the written one (for example a power limit that reads 999.1 W after writing 1000 W). Set `mismatch_tolerance` if the default tolerance (half the `step`, at least 0.5 % of the value) is too tight.
