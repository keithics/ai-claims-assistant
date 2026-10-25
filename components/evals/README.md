# evals

Golden set, scorers and runner for the claims assistant. Calls `agent_app` over HTTP; never imports its code.

## Golden set (`golden/golden.jsonl`)

180 cases: 30 per language (en, fil, ceb, id, th, ja), 5 of each case type per language (faq, country_rule, claim_status, claim_filing, code_switch, adversarial).

Fields: `id, language, country, input, expected_answer, expected_source, expected_tool, risk, case_type, reviewed_by_native`.

- `expected_answer` states the facts or behaviour the answer must contain. It is a reference for the judge, not a string to match. Most are in English or the case language, whichever was quicker to write correctly.
- `expected_source` is a policy document id (or null for status, filing and adversarial cases). `expected_tool` is the tool the agent should use; adversarial cases expect `none`.
- Cases are written so that countries differ on purpose (deadlines, excess, waiting periods, police report rules), so a leaked answer from the wrong country scores badly.
- Japanese has casual inputs that must still be answered in polite form (です・ます), plus English product terms inside Japanese sentences.
- Cebuano has no policy documents of its own; those cases are answered from the English and Filipino documents.
- **All cases are machine-written. `reviewed_by_native` is false everywhere.** Have native speakers review the fil, ceb, id, th and ja cases and set the flag only for those they checked.
