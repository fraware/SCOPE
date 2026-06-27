# PF-Core obligation export example

Sample output from `adapters/pf_core/export_obligation.py` after issuing a protocol-draft grant.

Generate live output:

```bash
scope export pf \
  --grant examples/protocol_change_review/scope_grant.json \
  --out dist/pf_obligation.json
```

Or from Python:

```python
from adapters.pf_core.export_obligation import export_pf_obligation
import json

obligation = export_pf_obligation(json.load(open("scope_grant.json")))
```

See `pf_obligation.json` in this directory for the expected shape.
