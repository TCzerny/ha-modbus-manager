# Template read groups

`read_group` is an optional advanced property on a register definition. It defines a Modbus transaction boundary for the RegisterOptimizer; it has no effect on an entity's identity, value decoding, polling interval, writes, or `mm_group`.

`mm_group` is existing template organization metadata. Modbus Manager exposes it as
an entity state attribute and also uses it for selected template/configuration
filtering; it is not an optimizer input. Reusing it as a transaction boundary
would change read behavior for existing templates that use the same logical
grouping label. Keep `read_group` separate when a device needs an explicit
Modbus-read boundary.

By default, registers without `read_group` retain the normal automatic optimization: adjacent compatible registers can be merged. When `read_group` is present, it must be a non-empty string.

Two adjacent definitions may be merged only when both omit `read_group`, or both specify the same value. A grouped and ungrouped definition never merge, and different groups never merge. All normal requirements (address adjacency, slave ID, input type, function code, and maximum read size) still apply.

Use this only for documented or hardware-verified transaction-boundary quirks, such as firmware that rejects an otherwise valid contiguous FC03 read. It is not a polling or aesthetic grouping mechanism.

```yaml
sensors:
  - name: "Value A"
    address: 100
    data_type: float32
    count: 2
    read_group: "device_block_a"
  - name: "Value B"
    address: 102
    data_type: float32
    count: 2
    read_group: "device_block_a" # may merge with Value A
  - name: "Value C"
    address: 104
    data_type: float32
    count: 2
    read_group: "device_block_c" # starts a new request
```
