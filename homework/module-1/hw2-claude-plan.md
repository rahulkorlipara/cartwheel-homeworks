# Homework 2 Plan: Rahul + Claude

## Context
Homework 2 adds two things to the Cartwheel agent:
- **An authenticated HTTP endpoint.** The server, not the chat, decides who the user is.
- **Tracing.** Every request leaves a record in Langfuse showing what the model saw, which tools ran, who called them, and which prompt version was used.

These records become the raw material for Module 2: reviewing traces, finding failure modes, and building judges.

Deliverables (handout: [hw2.md](hw2.md)):
- Code in four places:
  - `observability/instrument.py`: `record_tool_result`, `_set_permission_denied_attributes`
  - `server/app.py`: `create_session`, `post_message`
- Tests in a new `tests/test_observability.py`
- At least 5 traced requests and one prompt-version comparison
- `hw2-traces.json`, containing exactly 2 trace records

Same way of working as HW1. Claude writes all code and runs every command. Rahul makes the judgment calls. One step at a time, and results are shown before anything is recorded. **The video is skipped**, since Rahul is learning, not submitting.

The handout says to **explain the eval concepts in depth**: traces, spans, `gen_ai.*` vs `cartwheel.*`, prompt versioning, and why the server decides identity. **The infrastructure is a checklist**: Docker, tokens, env vars.

**After approval, the first action:** Claude saves this plan as `homework/module-1/hw2-claude-plan.md` and runs `git switch -c hw2`, which branches from `hw1` so the HW1 code is included.

Setup already done:
- `.env` has the Langfuse keys, `TRACELOOP_TRACE_CONTENT=true`, and `CARTWHEEL_MODEL=claude-haiku-4-5`.
- **Docker Desktop is installed** (Rahul, 2026-10-24). Claude checks that `docker compose version` works before Step 6.

---

## Step 1: Concepts (about 15 min)
- **Claude:** Explain these, using diagrams:
  - A trace is a tree of spans. A span is one operation, with a start, an end, and attributes.
  - The path a message takes: you → `/sessions` → token → `/messages` → agent → tools → DB, with spans sent to Langfuse along the way.
  - `gen_ai.*` fields follow an industry standard and are filled in automatically. `cartwheel.*` fields hold app facts that only our code knows.
- **Rahul:** Ask about anything unclear.

## Step 2: Part A, add attributes to tool spans (about 20 min)
- **Claude:** Fill in the two functions in [observability/instrument.py](../../observability/instrument.py), about 12 lines. Each tool span gets:
  - `cartwheel.user_role`
  - `cartwheel.user_id`, as a string
  - `cartwheel.store_id`, for merchants only
  - `cartwheel.permission_denied`, true or false
  - `cartwheel.permission_denied.reason`, only when denied

  These read from the `AuthContext` and from the tool's result, following the existing convention in `agent/auth.py` (`error == "permission_denied"`). The hook `_call` in `agent/agent.py` already calls `record_tool_result` after every tool.
- **Rahul:** Predict the attributes on a tool span when a shopper asks about someone else's order.
- **Check:** there's no test for Part A; it's verified in Langfuse in Step 6.

## Step 3: Part B, create sessions (about 30 min)
- **Claude:** Explain why identity comes from the server. The token is signed with a secret, so neither the chat nor the user can forge "I'm support." Then implement `create_session` in [server/app.py](../../server/app.py):
  - Unknown role → 400.
  - Look up the user with the existing `agent/db.py` helpers; unknown user → 404.
  - Claimed role differs from the stored role → 403.
  - Build an `AuthContext` from the **database** values, store it with its `SQLiteSession` in `_SESSIONS`, and return the session ID and a token signed by the existing `create_token`. The token holds session_id, user_id, role, store_id, and issued_at.
- **Rahul:** Predict what happens for `{"user_id": 1, "role": "support"}`.
- **Check:** `uv run pytest --runxfail -vv tests/test_hw_holes.py -k "create_session_binds"`

## Step 4: Part C, the traced message endpoint (about 30–45 min)
- **Claude:** Explain the root span, and prompt versioning: a hash of the system prompt template, so traces can later be grouped by the prompt that produced them. Then implement `post_message`:
  - Use the existing `_authorize` (401/403/404).
  - Get the server-stored `AuthContext` and history, and call `build_agent(ctx, model=body.model)`.
  - Compute `prompt_version()`, which hashes only the template, so it stays the same for every user.
  - Open the span `cartwheel.session_message` with `cartwheel.user_role`, `cartwheel.user_id`, `cartwheel.prompt_version`, and `cartwheel.scenario_id` when it's non-empty.
  - Record `gen_ai.input.messages` before the run and `gen_ai.output.messages` after it, in OTel message JSON, both only when `TRACELOOP_TRACE_CONTENT` is true. The docstring says so; the handout lists the attributes without that condition.
  - Run `Runner.run(..., max_turns=MAX_TURNS)` and return `{session_id, reply, prompt_version}`.
- **Rahul:** Before it runs, say which of these attributes would let you later find every trace that ran a given prompt.
- **Check:** only the offline tests in Step 5; the live check is in Step 6.

## Step 5: Part D, authentication tests (about 20 min)
- **Claude:** Write `tests/test_observability.py`, following the style of the existing `tests/test_hw_holes.py` with its `world` fixture. Tests:
  1. User 1 claims `merchant` (stored role `shopper`) → 403.
  2. A token for session A, used on session B → 403.
  3. Maybe more: unknown user → 404, unknown role → 400, missing or tampered token → 401. These are about 10 lines each.

  None of them need Langfuse, Docker, or a model key.
- **Rahul:** Look at the test names and the pass/fail summary.
- **Checks:**
  - `uv run pytest --runxfail tests/test_hw_holes.py -k hw2`
  - `uv run pytest tests/test_observability.py`
  - `uv run pytest`. The one known failure, `test_m2_run_judge_persists_store_predictions_for_prevalence`, needs Langfuse. With Langfuse running it now fails with "Langfuse returned no traces for the Module 2 slice": it needs Module 2 scenario traces, so expect it to stay failing until HW3/HW4.

## Step 6: Part E, run the stack and read traces (about 1–1.5 hours)
**Checklist (plumbing):**
- [ ] Rahul installs and opens Docker Desktop.
- [ ] `docker compose -f observability/docker-compose.yml up -d`. The first pull takes a few minutes.
- [ ] `uv run uvicorn server.app:app --port 8010`, run in the background.
- [ ] Rahul logs in at http://localhost:3000 as `student@example.com` / `cartwheel-dev-pass`.

**The requests:** at least 5 from `hw1-session.jsonl`, each in a session for the matching user. Suggested set, covering all 3 roles and one permission denial:

| # | User | Request (from HW1) | Why it's useful |
|---|---|---|---|
| 1 | shopper 1 | status of order #4127 | simple allowed tool call |
| 2 | shopper 1 | refund on #4455 | refund threshold path |
| 3 | merchant 9002 | details of order #4127 (store 1) | likely a **permission denial** |
| 4 | support 9501 | approve the $240 refund on #4455 | support role, queued refund |
| 5 | shopper 1 | the speaker dispute | escalation (the Part C fix from HW1) |

Reset the data with `uv run python -m seed.generate` between requests that change orders.

**For each trace:**
- **Claude:** Send the request with curl and show the response (session_id, reply, prompt_version). Then pull the trace from the Langfuse API and walk through the span tree with Rahul:
  - The root span's attributes
  - The model spans: model, messages, tokens
  - The tool spans: `execute_tool`, tool name, args and result, and the `cartwheel.*` fields
  - That every span shares one trace ID
- **Rahul:** Read the trace in the Langfuse UI. Per [verify-verdicts-against-spec], Claude also checks each reply against SPEC and flags anything wrong. This is a preview of Module 2's trace review.

## Step 7: Part F, compare two prompt versions (about 20 min)
- **Claude:**
  1. Save the current prompt (`46c341cfbd32`).
  2. Run request #5 (the dispute) in a new session on fresh seed data.
  3. Stop the server and swap in the HW1 "before" prompt (`6d58f2092b4d`, without the dispute fix).
  4. Restart, reseed, and run the same request as the same user on the same model.
  5. Show that the two `cartwheel.prompt_version` values differ.
  6. Restore the prompt and restart. Confirm `git diff agent/agent.py` is empty.
- **Rahul:** Compare the two traces, which also show the HW1 Part C fix in trace form. Explain in your own words why the hash matters for later evals.

## Step 8: Trace record (about 15 min)
- **Rahul:** Pick 2 traces you can explain from the root span to the final reply.
- **Claude:** Write `hw2-traces.json` using real values from Langfuse only: `trace_id`, `permalink`, `prompt_version`, `user_role`, `user_id`, `tool_order`, and `final_status`. Also count the spans for one trace, to understand the structure (this replaces the video item).

## Step 9 (deferred): Extend Studio
**Decision (Rahul, 2026-10-26): use the Langfuse UI as the trace viewer for now**, to get familiar with it the way the course intends. Custom viewers (Studio links, the Step 1 HTML page) are not part of the HW2 workflow. Revisit later if the plan changes. Langfuse was started early, during Step 3, so Rahul can explore it while the endpoints are being built.

## Step 10: Wrap up and commit
- **Claude:** Re-run all tests, check `hw2-traces.json` (exactly 2 records with the required fields), commit the four files and this plan to `hw2`, and update the progress memory.
- **Rahul:** Review the commit, then push.

---

## Who does what
| Rahul | Claude |
|---|---|
| Install Docker Desktop | Write all code and tests |
| Predict behavior and answer the check questions | Run every command, the server, and the requests |
| Read traces in Langfuse and judge the replies | Pull trace data and walk through the span trees |
| Choose the 2 traces for `hw2-traces.json` | Write `hw2-traces.json` from real data |
| Decide on the Studio extension | Explain each concept in plain English |
| Push to GitHub | Make the local commit |

## How we know it's done
- `uv run pytest --runxfail tests/test_hw_holes.py -k hw2`: passes.
- `uv run pytest tests/test_observability.py`: passes.
- `uv run pytest`: no new failures. The Langfuse-dependent test should now pass too.
- 5 or more traced requests are visible in Langfuse, with the root span and tool span attributes checked.
- Two different `cartwheel.prompt_version` hashes from the controlled comparison, and the prompt restored afterwards.
- `hw2-traces.json` has exactly 2 valid records.
- The four files are committed on `hw2`.

## Progress (updated as we go)
- [x] Step 1: Concepts (trace/span tree, request path, gen_ai vs cartwheel; covered at session start)
- [x] Step 2: Part A, tool span attributes (offline check with in-memory spans passed; Langfuse check in Step 6)
- [x] Step 3: Part B, `create_session` (supplied test passes; 403/400/404/200 checked by hand)
- [x] Step 4: Part C, `post_message` (offline check with a fake model: root span attributes, same hash for shopper and merchant, 401/403 auth)
- [x] Step 5: Part D, auth tests (4 tests in tests/test_observability.py pass; full suite 157 passed, 1 known failure)
- [x] Step 6: Part E: 5 traces sent, checked via the API and reviewed by Rahul in the Langfuse UI. The optional Langfuse user/session/tag fields were declined.
- [x] Step 7: Part F, prompt version comparison (46c341cfbd32 vs 6d58f2092b4d; prompt restored)
- [x] Step 8: `hw2-traces.json` (Rahul chose #5 dispute, went well, 8 spans; and #3 merchant denial, most open room for improvement since the reply confirms #4127 exists at another store, possible RESP-4 issue. Run B was considered and dropped because the HW1 prompt fix already covers it)
- [ ] Step 9: Studio extension (optional; deferred by Rahul)
- [x] Step 10: Commit (hw2 suite 1 passed, auth 4 passed, full suite 157 passed with 1 known Module 2 failure; all offline)

## Part E log
- **Trace #1** (shopper 1, "status of my order #4127?"): `f6daa83299bc4ec0133ace2649f76792`. Link: http://localhost:3000/project/cartwheel-dev/traces/f6daa83299bc4ec0133ace2649f76792. Prompt `46c341cfbd32`. Tools: get_order → get_order_details. 7 observations: root, Agent Workflow, the agent span, 2 tool spans, 2 model calls. Tool spans carry `cartwheel.user_role=shopper`, `user_id=1`, `permission_denied=false`, with no reason or store_id.
- **Finding:** with `claude-haiku-4-5` through LiteLLM, the model spans (`openai.response`) record the model name, the input messages and **input** tokens, but the **output message is null and output tokens are missing**. **Cause (confirmed in code):** on the LiteLLM path the SDK records a `GenerationSpanData` (fields: input, output, usage). The integration's `_end_generation_span` reads output and usage only from a `.response` object, which exists only for OpenAI's Responses API, so it skips them. The span sends no `gen_ai.usage.*` attributes at all, so the input token counts shown (543, 1,710) and the cost are **Langfuse's own estimates**, not Anthropic's numbers. The reply is still visible in the trace output (root span, Part C) and in the next model call's input.
- **Finding:** the model spans are named `openai.response` and carry `gen_ai.provider.name = "openai"` even though the model is Anthropic. Both are hardcoded in the OpenLLMetry OpenAI Agents integration (`_hooks.py`, `_start_generation_span`). They describe the SDK layer, not the provider. Use `gen_ai.request.model` to tell which model ran. Lesson: standard field names don't guarantee correct values.
- **Traces #2–#5** (all on prompt `46c341cfbd32`; seed reset before #2, #4, #5). Links are `http://localhost:3000/project/cartwheel-dev/traces/<id>`:
  - #2 shopper 1, refund #4455: `051a08d9ccb2f70406762aecea188018`. Tools: get_order_details, get_order (in parallel). Asked for a refund reason; no refund issued yet.
  - #3 merchant 9002, order #4127: `2333f10f48d9e1610dc6ce8915e4a9c9`. Both tools **denied**: `permission_denied=true`, reason "role 'merchant' (user 9002) may not view order #4127", `store_id=2`. The reply says "it's not from your store", which reveals that the order exists (RESP-4, same as HW1 #4).
  - #4 support 9501, approve $240 on #4455: `fa9a620ddd4d6e08a8332c67de48e402`. Tools: get_order, get_order_details, issue_refund, which returned `queued_for_approval`, refund 575. Correct this time (HW1 #8 escalated instead). The reply adds "The customer will be notified once it's approved", which isn't in any tool result (possible RESP-3).
  - #5 shopper 1, speaker dispute: `2a16cf51c584a91181d5321a1ac46b4c`. Tools: find_order (order 301), escalate_to_human (ticket 151, sla 24h). Cites cw-disputes. "Specialist team" isn't in the tool result (minor).
- The Part E checks pass in all 5: the root span has role, user_id and prompt_version. The tool spans have role and user_id, store_id for the merchant only, and `permission_denied` false or true, with the reason only when denied. Every observation shares the trace ID. Each response returned session_id, reply and prompt_version.
- **Part F, prompt comparison** (shopper 1, speaker dispute, same model, fresh seed and empty history for each run):
  - Run A, current prompt **`46c341cfbd32`**: trace `0ce458b7f29359c3671b40557f948896`. find_order → escalate_to_human (ticket 151, 24h). Cites cw-disputes.
  - Run B, HW1 "before" prompt **`6d58f2092b4d`** (the 4-line dispute instruction removed; the hash matched HW1's record exactly): trace `4dbe7ecba3ed6993606fe7f477ae6b83`. find_order → get_order_details, **no escalation**. It steered the shopper away from disputing ("I can issue a refund directly … without needing to dispute with your card issuer") and asked follow-up questions.
  - The prompt was restored and the server restarted; `git diff agent/agent.py` is empty and the version is back to `46c341cfbd32`.
