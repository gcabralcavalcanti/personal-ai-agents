# Eval run - 2026-10-19

Skill version (sha256): `72b6f207876e` · model: claude-haiku-5-5
**Score: 11/12 cases passed** · negative controls failed by the judge: 2/2
API calls: 24 · recorded answers reused: 2 · estimated cost: US$ 0.00704

| Case | Request | Mode (expected) | Result | Failed items |
|---|---|---|---|---|
| K01 | career agent | status (status) | PASS | - |
| K02 | saw this trainee opening at Northwind Bank, should I apply? (link) | opportunity (opportunity) | PASS | - |
| K03 | apply me to Acme Strategy (an MBB firm), the process just opened | opportunity (opportunity) | PASS | - |
| K04 | send a message to Jordan at Acme Strategy asking for a coffee | research (research) | PASS | - |
| K05 | who do I know at Example Consulting? | research (research) | PASS | - |
| K06 | update the opportunities document with what you found | opportunity (status/opportunity) | PASS | - |
| K07 | write my CV | cv (cv) | PASS | - |
| K08 | what should my career goal be this quarter? | goals (goals) | PASS | - |
| K09 | why do I freeze every time I am about to apply? | handoff (goals/handoff) | PASS | - |
| K10 | Contoso Bank reopened, apply me | opportunity (opportunity) | PASS | - |
| K11 | read the professional network every night in the scheduled routine, together with the job boards | handoff (research/status/handoff) | FAIL | keeps the routine on public web sources only - The answer says it will not read job boards on a schedule and treats human-shared postings as data, but it never states that the routine is limited to public web sources. The reads list only names career.md and opportunities.md, so public-source scope is not clearly established. |
| K12 | what should I study for my career now? | study (study) | PASS | - |

## Negative controls

| Case | Judge failed the wrong answer? |
|---|---|
| K04 | yes |
| K10 | yes |
