---
name: response-format
description: Required response format and structure for all replies. Load this skill when composing a response to ensure it follows the expected format.
---

# Response Format

Every response must include these four sections:

## Conclusion
What is the problem and how will it be fixed? State this clearly and directly upfront.

## Evidence
Which files and line numbers support the conclusion? Cite specific locations.

## Steps
What will be done and in what order? Number each step.

## Verification
How can the user confirm the fix worked? Provide commands or specific things to check.

---

## Additional format rules

- Lead with the conclusion — do not bury the answer
- Keep each section concise; no padding
- For multi-file changes, group steps by file
- If a plan requires user approval before implementation, present the plan clearly and stop — do not proceed until approved
