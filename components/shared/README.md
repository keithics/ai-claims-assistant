# shared

Pricing, redaction and common schemas. No I/O. Importable by every component.

## Public interface

- `cost_usd(deployment, input_tokens, cached_tokens, output_tokens, prices) -> Decimal`: cost of one model call in USD. `input_tokens` is the total input including cached tokens; `cached_tokens` is the cached part and is billed at the cached rate, the rest at the input rate. Prices are per 1M tokens and passed in as `Mapping[str, ModelPrice]`; they come from `country_packs/models.yaml`, never from code.
- `ModelPrice`: frozen dataclass with `input_per_1m`, `cached_input_per_1m`, `output_per_1m` (all `Decimal`).
- `UnknownDeploymentError`: a `ValueError` raised for a deployment with no price; the message lists the known ones. Negative tokens, or cached above input, also raise `ValueError`.
- `redact(text) -> str`: masks emails, policy numbers, claim IDs, national IDs and phone numbers with `[EMAIL]`, `[POLICY]`, `[CLAIM_ID]`, `[NATIONAL_ID]`, `[PHONE]`. Idempotent, and safe on Japanese, Thai and Indonesian text (digits and letters are matched as ASCII, so they are found next to CJK or Thai characters without spaces). Dev logging goes through this; non-dev envs never log prompts at all.

### What `redact` recognises

| Kind | Pattern |
|------|---------|
| Email | `name@domain.tld` |
| Policy number | `POL-<digits>` or `POL-XX-<digits>` (5 to 12 digits). Synthetic format, an assumption since the repo defines none |
| Claim ID | two capital letters, hyphen, 3 to 6 digits, for example `PH-1042` (any prefix, so new markets work) |
| National ID | PH PhilSys (12 digits, or `4-7-1`), SG NRIC/FIN (`S1234567D`), ID NIK (16 digits), TH (13 digits, or `1-4-5-2-1`), JP My Number (12 digits, spaces or hyphens allowed) |
| Phone | international (`+63 917 123 4567`), domestic with trunk 0 (PH, ID, TH mobiles, JP such as `090-1234-5678` or `03-1234-5678`), SG 8-digit numbers starting 6, 8 or 9 |

Known limits: Thai or other non-ASCII digits are not matched; names and addresses are not detected; a 12-digit number starting with 0 is treated as a phone number, not an ID.
