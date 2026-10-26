# Regulatory notes

**Not legal advice. Laws and regulator rules change and differ by product; verify every row against official sources and with counsel before relying on it.** The laws named below are the main ones I would check first; I have not verified current text. All data in this project is synthetic.

The *settings* columns are read from each country pack in `components/country_packs/countries/` and are checked against those files by a test (`tests/test_regulatory_doc.py`), so they cannot drift.

| Country | Pack | Region (pack) | Deployment type | Log prompts | Retention (days) | Monthly budget (USD) |
|---|---|---|---|---|---|---|
| Philippines | ph | southeastasia | regional | false | 30 | 10 |
| Singapore | sg | southeastasia | regional | false | 30 | 10 |
| Indonesia | id | southeastasia | regional | false | 30 | 10 |
| Thailand | th | southeastasia | regional | false | 30 | 10 |
| Japan | jp | japaneast | regional | false | 30 | 10 |

Residency caveat: the packs declare a region and `regional` deployment, but today every model call runs on a `GlobalStandard` deployment in `southeastasia` (see ADR-003). The packs state the intent; the infrastructure does not yet enforce it.

| Country | Data protection law to check | Insurance or financial regulator to check | Points to verify |
|---|---|---|---|
| Philippines | Data Privacy Act of 2012, National Privacy Commission | Insurance Commission | Consent, breach notification, cross-border transfer, claim handling timelines |
| Singapore | Personal Data Protection Act 2012, PDPC | Monetary Authority of Singapore | Notification of breaches, outsourcing and AI governance guidance for financial institutions |
| Indonesia | Personal Data Protection Law (Law No. 27 of 2022) | Financial Services Authority (OJK) | Data localisation rules for electronic systems, cross-border transfer conditions |
| Thailand | Personal Data Protection Act B.E. 2562 (2019), PDPC | Office of the Insurance Commission | Consent and sensitive-data rules (health data), cross-border transfer |
| Japan | Act on the Protection of Personal Information (APPI), PPC | Financial Services Agency (FSA) | Special-care-required personal information (health), third-party and cross-border provision, customer-protection guidelines for insurers |

## Philippines
Notes on the settings: prompts are not logged; telemetry is kept 30 days. Check the Data Privacy Act's requirements for processing health information and for transferring personal data abroad before using real data.

## Singapore
Notes on the settings: as above. Check PDPA obligations for AI-assisted decisions and the regulator's guidance on outsourcing and model risk.

## Indonesia
Notes on the settings: as above. Indonesia is the market most likely to need in-country processing; ADR-003 describes what would have to change.

## Thailand
Notes on the settings: as above. Health information is sensitive under the PDPA; keep prompt logging off.

## Japan
APPI and the Financial Services Agency (FSA) are the starting points. The Japan pack asks for `japaneast`, which is why it is the one market where a real regional deployment would be built first. Answers use polite form (です/ます), checked by the evaluation harness.
