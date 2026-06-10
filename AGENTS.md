# Athena Agent Commands

This workspace is for Chu Van Mai's daily Rocket.Chat to WorkAI workflow.

On initialization, always run the equivalent of `/caidatagent`: read both
`instructions.md` and `.agent_rules.md` before doing any workflow task. If a
user or tool refers to `instruction.md`, treat that as `instructions.md` unless
an actual `instruction.md` file exists.

## Commands

The commands below are strict workflow commands. Execute only the listed scope
for the command the user requested, then stop.

### /caidatagent

Purpose: load the local agent rules.

Steps:
1. Read `instructions.md`.
2. Read `.agent_rules.md`.
3. Summarize the active identity, workflow, command boundaries, and safety
   rules.
4. Stop.

Do not run sync scripts, create task files, or submit anything.

### /tonghop

Purpose: scan Rocket.Chat and list candidate daily work items, preserving previous approvals.

Steps:
1. Run `python sync_rocket.py` to sync Rocket.Chat into `chat_raw.json`.
2. Read `chat_raw.json` and extract work items using Rules A-H from `instructions.md` and `.agent_rules.md`.
3. Read `approved_tasks.json` (if it exists). Filter the items: exclude tasks previously rejected by the user, keep tasks already mapped to projects, and only add new tasks.
4. List the updated work items in chat, including source room for each item.
5. Ask the user to review (remove unneeded items) and provide exact WorkAI project names for any new items.
6. Save the final reviewed list (including mapped projects and tracking rejected items) to `approved_tasks.json`.
7. Allocate durations with a total of 8.0h for the valid tasks.
8. Stop.

Do not write `memorytask.md`, do not write `tasks.json`, and do not run
`submitter.py`.

### /taoviec

Purpose: create detailed task content and save it to `memorytask.md`.

Prerequisite: `/tonghop` has completed and the user has provided exact project
names (saved in `approved_tasks.json`).

Steps:
1. Read the approved work-item list from `approved_tasks.json`.
2. For each task, write:
   - Title using `[Action] - [Objective]`, at least 50 characters.
3. Save all tasks to `memorytask.md`.
4. Stop.

Do not run `sync_rocket.py`, do not write `tasks.json`, and do not run
`submitter.py`.

### /nhapviec

Purpose: submit prepared tasks to WorkAI.

Prerequisite: `memorytask.md` exists and contains task content.

Steps:
1. Read `memorytask.md`.
2. Parse it into task objects.
3. Add metadata to every task: `"status": "Done"`, `"sprint": "latest"`,
   and `"date": "YYYY-MM-DD"`.
4. Write `tasks.json`.
5. Ask the user for final confirmation.
6. After confirmation, run `python submitter.py`.
7. Report the result and remind the user to manually adjust allocated hours in
   WorkAI.
8. Stop.

Do not run `sync_rocket.py` and do not rewrite `memorytask.md`.

## Safety

- Never print passwords, tokens, credentials, private user IDs, or `.env`
  secrets.
- Keep credentials, raw chats, and script operations local to
  `F:\prototype\Agent`.
- Never guess WorkAI project names. Ask the user for exact mappings.
