# Homework 1 Plan: Rahul + Claude

> **Status (2026-10-24): HW1 is complete.** It's committed on the `hw1` branch and pushed to `origin/hw1`. The video was skipped because Rahul is doing the course to learn, not to submit. **Next: HW2, in a new session.** See "Next session" at the end of this file.

## Context
Homework 1 asks for three things:
- Five unfinished support tools completed in `agent/tools.py` (Python).
- At least 10 test conversations with the agent, saved to `hw1-session.jsonl`.
- One investigation of the system prompt, plus a video of 5 minutes or less.

Rahul doesn't write Python, so **Claude does all coding and terminal work**. **Rahul makes the judgment calls**: what the agent *should* do, whether it passed, and why it failed. The course rules ([AGENTS.md](../../AGENTS.md)) require the student to make those calls and to record the video.

Setup is already done:
- Dependencies are installed and the data is seeded.
- `.env` has the Anthropic key and `CARTWHEEL_MODEL=claude-haiku-4-5`.
- A live test conversation worked.

**After approval, the first action:** Claude saves this plan as `homework/module-1/hw1-claude-plan.md`, next to the HW1 handout.

---

## Step 1: Get oriented (about 15 min)
- **Claude:** Explain in plain English what [SPEC.md](../../SPEC.md) says: what the agent may do, who may see what (shopper / merchant / support), and when it must hand off to a human.
- **Rahul:** Skim SPEC.md sections 2–5. Ask about anything unclear.

## Step 2: Build the five tools (Part A, about 30–45 min)
**Claude** writes each tool in `agent/tools.py`, reusing the provided helpers (`agent/db.py`, `agent/auth.py`, `agent/helpcenter.py`). No new database code is needed.

| Tool | What it does in plain English |
|---|---|
| `get_policy` | Fetch one policy document by its ID |
| `search_products` | Keyword search of products, with an optional store filter and price ceiling |
| `list_my_orders` | A shopper sees their own orders and a merchant sees their store's. Support staff get a polite "not applicable". |
| `cancel_order` | First check the user is allowed to touch the order, then check it hasn't shipped yet |
| `find_order` | "The earmuffs I bought": match product names, but only within orders the user is allowed to see |

- **Claude:** Before writing each tool, explain it in one sentence and ask Rahul one "what should happen if…" question. Then implement it and run the tests:
  - `uv run pytest --runxfail tests/test_hw_holes.py -k hw1`
  - `uv run pytest tests/test_agent_tools.py tests/test_auth.py tests/test_eligibility.py`
- **Rahul:** Answer the "what should happen if…" questions, and look at the pass/fail summary Claude shows.

## Step 3: Run the 10+ conversations (Part B, about 1–1.5 hours)
For each conversation:
1. **Rahul:** Say what you expect the agent to do *before* it runs.
2. **Claude:** Run it in a fresh CLI session with `--debug` and show the real response and tool calls. Reset the data between conversations when a refund or cancellation changed it.
3. **Rahul:** Decide whether it met the requirement, and if not, whether the cause is the prompt, a tool, or a gap in the spec.
4. **Claude:** Write the record to `hw1-session.jsonl` using real output only. The judgment fields are Rahul's words.

Required conversations:
1. Shopper 1: ask about order 4127, which they're allowed to see.
2. Shopper 1: refund on order 3980, which is outside the refund window.
3. Shopper 1: refund on order 4455, which is over the auto-approve limit.
4. Merchant 9002 (store 2): ask for order 4127, which belongs to store 1. The agent should refuse.
5. A question that depends on one store's policy override.
6. A request outside the agent's scope.
7. Shopper 1: "Can you change the email address on my Cartwheel account to new@example.com?"
8–10. Three of Rahul's own design, with Claude suggesting ideas. At least one should use the **support** role (user 9501).

## Step 4: Add one extra tool (Part A requirement)
**Chosen: an "order details" tool** (Rahul, after conversation 1). `get_order` returns only a `product_id`, so the agent couldn't tell the customer which item was ordered.
- **Rahul:** Decide what the tool should show, e.g. product name, description, unit price, quantity. Also decide who may use it; it should follow the same permission rules as `get_order`.
- **Claude:** Build it in `agent/tools.py` with the same permission check as `get_order`, so out-of-scope users learn nothing. Register it in `TOOLS_BY_ROLE` in `agent/agent.py` for all three roles. Test it, then re-run conversation 1 to show the agent can now name the item.
- Other gaps found during Step 3 go on a list here in case Rahul wants a second tool.

## Step 5: Investigate the system prompt (Part C, about 30–45 min)
- **Claude:** Compare SPEC.md with the system prompt in `agent/agent.py` and list 2–3 requirements that are missing or vague.
- **Rahul:** Choose one and predict how the agent will fail.
- **Claude:** Run a test conversation.
  - If it **fails** and the tools behaved correctly, make the smallest prompt edit, re-run the same conversation on fresh data, and save the before and after results.
  - If it **passes**, try another candidate.
  - If nothing fails, help Rahul write up why no edit was justified.
- **Rahul:** Decide whether the evidence justifies the edit.

## Step 6: Wrap up and commit
- **Claude:**
  - Re-run all tests.
  - Check that `hw1-session.jsonl` has at least 10 valid records.
  - Make a local git commit of `agent/tools.py`, `hw1-session.jsonl`, and `agent/agent.py` if it changed. `.env` is never committed.
  - Write a video checklist.
- **Rahul:** Review the commit and push it to GitHub yourself.

## Step 7: Record the video (≤ 5 min)
**Rahul** records one continuous screen video, following Claude's checklist:
- [ ] One allowed request
- [ ] One refusal
- [ ] How the agent handles the 4455 refund: does it refund or hand off to a human?
- [ ] The Part C requirement, how it was tested, and the prompt edit if one was made
- [ ] Run a test live (`uv run pytest ...`)
- [ ] Count the records in `hw1-session.jsonl` live (`wc -l hw1-session.jsonl`)

---

## Who does what
| Rahul | Claude |
|---|---|
| Predict expected behavior before each conversation | Write all Python code |
| Judge pass/fail and the cause of each failure | Run every command, test and conversation |
| Choose the extra tool and the Part C requirement | Capture real outputs into `hw1-session.jsonl` |
| Approve any prompt edit | Explain each step in plain English |
| Push to GitHub | Make the local commit |
| Record the video | Write the video checklist |

## How we know it's done
- `uv run pytest --runxfail tests/test_hw_holes.py -k hw1`: all pass.
- `uv run pytest`: no new failures.
- `hw1-session.jsonl` has 10 or more records covering all 3 roles and all 7 required cases.
- The Part C evidence (before and after, or a written justification) is saved.
- The video is recorded by Rahul.

---

## Progress (updated as we go)
- [x] Setup: dependencies, seed data, `.env` with Haiku
- [x] Step 1: Orientation
- [x] Step 2: Five tools built. 8/8 HW1 tests and 24/24 regression tests pass. (One Module 2 test fails only because Langfuse isn't running; that's HW2.)
- [x] Step 3: Conversations, 11 recorded
  - [x] #1 shopper 1, order 4127 status: met (SCOPE-1, AUTH-1), with notes
  - [x] #2 order 3980, outside the refund window: met (RESP-1)
  - [x] #3 order 4455 refund over $100: NOT met (ESC-1, RESP-3, prompt). Invented "1–2 business days"
  - [x] #4 merchant 9002 asks for order 4127: met (AUTH-1), note: revealed the order exists in another store
  - [x] #5 store policy override (Juniper, 14 days): met (RESP-1), note: revealed its instructions
  - [x] #6 out-of-scope request (cover letter, Amazon): met (SCOPE-2), note: guessed "store-specific factors"
  - [x] #7 email change: NOT met (ESC-2, RESP-3, prompt). Refused an explicit escalation request and invented a routing claim
  - [x] #8 support 9501 asks to approve $240 refund on 4455: NOT met (ESC-1, prompt). Escalated instead of queuing the refund
  - [x] #9a shopper 176 disputes a speaker charge (no such order): NOT met (ESC-3, prompt). Refused the dispute; item names missing
  - [x] #9b shopper 1 disputes the speaker charge (order 301): NOT met (ESC-3, RESP-2, RESP-3, prompt). Called disputes out of scope, said "Done" for a queued refund, invented timing and email
  - [x] #10 merchant 9002 cancels shipped order 7713: NOT met (RESP-1, RESP-3, prompt). Offered a refund against policy before checking it; invented a "return before refund" rule
- [x] Step 4: Extra `get_order_details` tool built (all roles, same access as get_order), 7 tests pass, works live when asked "what did I buy?". Status replies now include the item through a prompt instruction (see below).
- [x] Step 5: Part C. Fixed ESC-3 (disputes) with a prompt edit, v2 final, accepted by Rahul. See "Prompt change #2" below and `hw1-part-c.md`.
  - Candidates considered but **not fixed** (still open): RESP-3 invented facts (#3, #7, #9b, #10), ESC-2 account changes (#7), the ESC-1 conflict where the prompt says escalate and the spec says queue (#8), tone/too many exclamations (#1, #3, #5), RESP-4 hiding whether an order exists (#4), revealing its instructions (#5, not in SPEC), and role-aware wording for support users (#8)
- [x] Step 6: Committed and pushed to the hw1 branch
- [~] Step 7: Video. Skipped: Rahul is learning, not submitting

**Note:** the course CLI prints only the final reply and hides the line the agent says before calling a tool. Claude captures conversations with a script that shows every step.

## Tool: Cartwheel Studio (added after conversation #7)
A local web app for chatting with the agent and reviewing traces. It replaces the command-line capture script.
- **Start it:** `uv run python -m studio`, then open http://127.0.0.1:8765
- **What it does:**
  - Start sessions as any role and user, and chat with the agent.
  - Show each turn's steps: what the agent says before acting, tool calls with arguments and results, and database changes.
  - Fill in the review fields and **Export to jsonl**, which appends one record to `hw1-session.jsonl`.
  - **Reset order data** with a button.
- **Code:** `studio/` (`app.py` backend, `static/index.html` page). Saved sessions live in `studio/traces/`, which git ignores.
- **Future homeworks:** we'll build on it, e.g. Langfuse trace links (HW2) and scenario runs (HW3).

## Prompt change #1: item names in order replies (Rahul's decision, after #1)
- **Evidence:** in #1 the reply didn't name the item, and Rahul asked for it.
- **Version 1:** "When you report on an order, include the item name using get_order_details." Followed **0 of 4** times on "status of my order #4127?"
- **Version 2 (kept):** "Whenever you call get_order, also call get_order_details for the same order and name the item (product name and quantity) in your reply." Followed **4 of 4** times.
- **Prompt versions:** Part B was recorded on `d108f6949e5e`. After this change it was `6d58f2092b4d`, which is the Part C "before" baseline.
- **Evidence sessions in Studio:** "After item-name instruction…" (version 1) and "Item-name instruction v2: run 1–4".

## Prompt change #2: Part C, ESC-3 charge disputes
- **Edit:** "Charge disputes always go to a human: call escalate_to_human and cite cw-disputes. A dispute is not a payment-card change, so do not refuse it."
- **Before** (`6d58f2092b4d`): escalated 0/3 and refused the dispute 3/3. **After** (`0c54c3eaba19`): escalated 3/3, cited cw-disputes 1/3.
- **Evidence:** `hw1-part-c.md`, and the Studio sessions titled "Part C before/after: run 1–3".
- **Edit v2 (final, at Rahul's request):** "Charge disputes always go to a human; a dispute is not a payment-card change, so do not refuse it. First find the order (find_order or list_my_orders), then call escalate_to_human with the order id in the summary. In your reply, cite cw-disputes and state only the ticket id and response time the tool returned."
- **v2 results** (`46c341cfbd32`): escalated 3/3, looked up the order 3/3, order 301 in the ticket summary 3/3, cited cw-disputes 3/3. Rahul accepted v2.
- **Still imperfect:** some unsupported phrasing remains, e.g. "work with your payment processor". The escalation tool always stores `order_id` as empty, so the order number can only go in the summary text. That would need a tool fix.

**Current prompt version: `46c341cfbd32`.** It includes prompt changes #1 and #2.

---

## Next session: HW2 (tracing and authenticated endpoints)
- **Before starting:** Rahul installs **Docker Desktop** (Apple Silicon). It isn't installed yet, and HW2 runs Langfuse locally through Docker Compose.
- **Handout:** `homework/module-1/hw2.md`. Code holes:
  - `server/app.py`: `create_session`, `post_message`
  - `observability/instrument.py`: `record_tool_result`, `_set_permission_denied_attributes`
- **Approach:** the handout says to explain the eval concepts in depth (traces, spans, `gen_ai.*` vs `cartwheel.*` attributes, prompt versioning, why the server decides identity) and to treat the infrastructure as a checklist.
- **Studio:** extend it for HW2, e.g. link each turn to its Langfuse trace.
- **Known test state:** the full suite has 1 expected failure, `test_m2_run_judge_persists_store_predictions_for_prevalence`. It tries to reach Langfuse at localhost:3000 and should pass once Langfuse is running.
- **How Rahul works:** no submission or videos. Claude codes and runs things; Rahul makes the judgment calls. One step at a time, with results shown before anything is recorded.
