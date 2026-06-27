# AKTA adapter examples

Sample inputs for `adapters/akta/import_record.py` and `import_trigger.py`.

```python
from adapters.akta.import_record import load_akta_record
from adapters.akta.import_trigger import load_review_trigger

record = load_akta_record("adapters/akta/examples/akta_record.json")
trigger = load_review_trigger("adapters/akta/examples/review_trigger.json")
```

These mirror `examples/protocol_change_review/` fixtures.
