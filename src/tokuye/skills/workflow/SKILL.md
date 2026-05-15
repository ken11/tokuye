---
name: workflow
description: Step-by-step work process for investigating, planning, implementing, and finalizing code changes in a repository. Load this skill when starting any development task.
---

# Workflow

## Step 0. Baseline setup (critical: run strictly top-to-bottom, sequentially)

These steps have dependencies. Do not run them in parallel or all at once. Execute one by one and confirm each succeeds before proceeding.

1. Run `repo_summarize` to create/update the repository summary
2. Run `manage_code_index` to refresh the FAISS index

"Confirm completion" means verifying the tool execution succeeded and treating its output as the prerequisite input for the next step.

## Step 1. Investigation

- Use `search_code_repository` first to identify relevant files and line ranges
- Use `read_lines` for reading
  - If the line range is known: read only that range
  - If the line range is unknown: use `read_lines` in ~50-line chunks as "paging" until you locate the target
- Respect existing design intent when proposing changes

## Step 2. Execution plan

- Present a numbered plan (short, in execution order)
- Include: what changes, scope of impact, risks, and alternatives

## Step 3. User approval

- Do not implement until the user approves the plan
- Ask the fewest questions possible; include hypotheses and what you need to confirm

## Step 4. Implementation

- Use `create_branch` to create a work branch
- Use `replace_exact` / `insert_after_exact` / `insert_before_exact` for edits
  - Always read the target block verbatim with `read_lines` before calling these tools
- Use `write_file` for new files or when a full file rewrite is needed
  - Treat `write_file` as full-file replacement (or new file creation)
  - When overwriting an existing file, verify imports/definitions/file-end sections to avoid accidental deletions
- Update `manage_code_index` as needed

## Step 5. Finalization

- Use `commit_changes` with an informative commit message
- Return a short summary: what changed, why, how to verify, and any caveats

## Step 6. Follow-up changes (critical: resync before starting)

Before any follow-up iteration, resync to the current repo state. Do not skip.

1. Re-run `repo_summarize`
2. Re-run `generate_repo_description_tool`
3. Re-run `manage_code_index`

After resync: mini plan → approval → minimal diffs → refresh `manage_code_index` if needed → `commit_changes`
