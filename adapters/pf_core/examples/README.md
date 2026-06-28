# PF-Core obligation export example

Sample output from `adapters/pf_core/export_obligation.py` after issuing a protocol-draft grant.

Contract version: `pf-core-v0.5`. See [docs/pf_core_bridge.md](../../docs/pf_core_bridge.md).

## Generate live output

After running a grant workflow (e.g. [examples/stale_grant_attempt/](../../examples/stale_grant_attempt/) or [examples/institutional_pilot/](../../examples/institutional_pilot/)):

```bash
scope export pf \
  --grant examples/institutional_pilot/scope_grant.json \
  --out dist/pf_obligation.json \
  --validate
```

Optional live contract validation:

```bash
export PF_CORE_REPO_PATH=/path/to/pf-core
scope export pf --grant examples/institutional_pilot/scope_grant.json \
  --out dist/pf_obligation.json --validate --live
```

## Python API

```python
from adapters.pf_core.export_obligation import export_pf_obligation
import json

obligation = export_pf_obligation(json.load(open("scope_grant.json")))
```

## Sample shape

See `pf_obligation.json` in this directory for a representative obligation layout. Regenerate from a live grant for current contract fields and signature metadata.
