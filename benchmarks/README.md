# Agent comparison protocol

`compare_agents.py` is a small, network-free harness for comparing Kemi with a
second agent such as Hermes. It intentionally does **not** claim a performance
multiplier. It sends the same four safe, synthetic tasks to both adapters and
reports pass rate, structured-output completeness, median latency, and p95.

## Adapter contract

An adapter is any command that:

1. reads one JSON object from stdin;
2. returns one JSON object on stdout;
3. exits with status `0` on a handled task.

The task includes `id`, `prompt`, and sometimes fixture `observations`. Keep the
same model, temperature, token budget, timeout, and retry policy for both
adapters. Do not point this protocol at targets you are not authorized to test.

```bash
python benchmarks/compare_agents.py \
  --kemi-command 'python /path/to/kemi_adapter.py' \
  --hermes-command 'python /path/to/hermes_adapter.py' \
  --iterations 5 \
  --output benchmark-results.json
```

The report deliberately omits command strings because they can contain local
paths or flags. Review the task-level results before interpreting an aggregate
number. A fair result may show that one agent is faster while the other is more
complete; there is no honest basis for promising “1000x” without reproducible
evidence.
