# Sample Corpus

English-first enterprise documentation used to seed and demo the system.

| File | Topic | Format |
|------|-------|--------|
| `employee-handbook.md` | HR policies (probation, leave, remote work, code of conduct) | Markdown |
| `incident-response-playbook.md` | Security incident procedures (SEV tiers, roles) | Markdown |
| `security-policy.md` | Access control, data classification, retention | Markdown |

All three are authored to exercise the structure-aware chunker (heading hierarchy →
section metadata). An Arabic-language corpus is added in the v1.1 Arabic pass.

Ingest with:

```bash
uv run python scripts/ingest.py data/samples
```
