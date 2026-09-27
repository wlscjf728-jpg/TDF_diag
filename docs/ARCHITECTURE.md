# Architecture

## Reference-assisted diagnosis

A faulty scan transfer may corrupt later shifted data. An intermittent fault may also vanish before a repeat test. The design captures mismatch evidence during a controlled diagnosis sequence and retrieves it through a spare path.

1. **Load reference:** a qualified spare chain supplies reference/evidence storage.
2. **Parallel preload:** corresponding target cells receive reference state without depending on serial propagation along a potentially faulty target chain.
3. **Isolate and exercise:** a controlled shift/capture exposes active fault effects.
4. **Compare:** local XOR comparisons identify deviations; OR compression combines chain indications per slice.
5. **Retain/read out:** indications enter the spare path for retrieval and position interpretation.
6. **Encode:** a separate encoder packs nonzero pattern-hit observations into bounded records.

The modules and testbenches expose these phases. They are research building blocks, not a fully integrated autonomous diagnosis SoC.

## Localization granularity

For a full Nsp-chain group, B[k]=1 identifies slice k but not the particular chain:

```text
one indicated slice -> Nsp candidate cells
several indicated slices -> union of those candidates
no indicated slice -> no mismatch observed under this condition
```

Candidates per indication, total suspect count and ground-truth precision are different quantities. Two faults at one slice can share an indication. Internal transfer localization concerns adjacent scan flip-flops; terminal scan-out connections are a separate boundary.

## Modules

| RTL file | Role |
|---|---|
| `top_module.v` | Scan FFs, lock-up latch, comparison slices, spare path and position counter |
| `step2_nsp_top.v` | Multi-bank grouping |
| `compact_production_top.v` | OR-compressed evidence interface |
| `step5_compact_logger.v` | Event encoder |
| `step4_5_lockup_compare.v` | Supporting timing-study structures |

Chain-resolved `b_vec` signals support simulation checking; the externally retrieved group-compressed evidence contains less information.

## Compact records

The encoder processes four pattern-hit vectors over 72 positions:

| Field | Bits | Content |
|---|---:|---|
| Valid | 1 | Record present |
| Position | 7 | Slice index |
| Metadata | 6 | Pattern-hit mask and mixed-pattern information |
| Syndrome | 2 | Pattern classification |

Capacity is 32 records / 512 bits. Overflow signals excess detected events. The encoder is combinational: SRAM persistence, opportunity identifiers, scheduling and retention policy belong to a surrounding system.

## Fault and timing interpretation

Testbenches emulate permanent/intermittent stuck-at and transition-delay effects under specified capture timing. They validate logical evidence behavior rather than measured defect physics.

Supporting timing data compares a 10 ns scan clock with a 20 ns spare clock. Keep FF-to-latch and latch-to-FF checks separate: an aggregate setup budget does not replace either individual timing check.
