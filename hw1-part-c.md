# HW1 Part C: ESC-3 (charge disputes)

**Requirement.** ESC-3: disputes always go to a human. Policy `cw-disputes`: buyers can dispute a charge up to 60 days after delivery, and a human support agent always handles disputes, never automatically.

**Gap in the system prompt.** Disputes aren't mentioned. The refusal rules list "payment-card or credential changes", and the agent read a charge dispute as one of those.

**Recorded evidence from Part B.** In #9a and #9b, the agent called a dispute out of scope and never escalated (both not met, ESC-3, problem source prompt).

**Test.** Shopper 1 sends: *"The Bluetooth speaker I bought is defective and the store won't respond. I want to dispute the charge."* Each run starts a fresh session on freshly reset data, 3 runs per prompt version. The only differences between versions are the edits shown, all in the `## Escalation` section of `SYSTEM_PROMPT_TEMPLATE` in `agent/agent.py`.

## Summary

| | Before | Edit v1 | Edit v2 (final) |
|---|---|---|---|
| Called escalate_to_human | 0/3 | 3/3 | 3/3 |
| Looked up the order first | 0/3 | 0/3 | 3/3 |
| Order 301 in ticket summary | 0/3 | 0/3 | 3/3 |
| Cited cw-disputes | 0/3 | 1/3 | 3/3 |
| Refused the dispute | 3/3 | 0/3 | 0/3 |

Edit v1 fixed the refusal. Edit v2 also makes the agent find the order, put the order number in the ticket, cite the policy, and limit its promises to what the tool returned. The escalation tool itself always stores `order_id` as empty, so the order number can only appear in the summary text. Some unsupported phrasing remains in v2, for example "work with your payment processor" in run 2.

## Before any edit (prompt `6d58f2092b4d`)

### Part C before: run 1
Tools: none
Studio session `a7803806fa36`

> I can't help with credit card disputes directly, but I can help you explore refund options through Cartwheel—which might solve this faster.
> 
> Let me first look up your order to check if you're eligible for a refund. Do you have your order ID? If not, I can search for it using the product name.

### Part C before: run 2
Tools: none
Studio session `51b83b6c7587`

> I'm sorry you're dealing with a defective speaker and unresponsive store—that's frustrating.
> 
> I can't help with payment-card chargebacks directly, as that's between you and your card issuer. However, I can help you get a refund through Cartwheel for the defective item, which is often faster and easier.
> 
> To get started, could you share your **order ID**? With that, I can:
> - Check whether the order is eligible for a refund
> - Process a refund if it qualifies
> - Escalate to a human if there's anything blocking it
> 
> You can find your order ID in your order confirmation email or by asking me to list your recent orders.

### Part C before: run 3
Tools: none
Studio session `da761d6badc9`

> I can't help with credit card disputes or chargebacks—that's between you and your card issuer. But I can help you with a refund through Cartwheel, which is usually faster.
> 
> To get started, I need to look up your order. Can you provide your order ID? You can also tell me what the Bluetooth speaker was called, and I can search for it in your recent orders.
> 
> Once I have the order details, I can check if it's eligible for a refund and either process it or escalate to a human agent if needed.

## Edit v1 (prompt `0c54c3eaba19`)

```
Charge disputes always go to a human: call escalate_to_human and cite
cw-disputes. A dispute is not a payment-card change, so do not refuse it.
```

### Part C after: run 1
Tools: `escalate_to_human`
Studio session `3aa0868f9757`

> Got it—I've created a ticket for our disputes team (ticket #151). Someone will be in touch within 24 hours to help you resolve this charge dispute with the defective speaker. 
> 
> In the meantime, keep any documentation you have about the defect and the store's non-response, as that will help speed things along.

### Part C after: run 2
Tools: `escalate_to_human`
Studio session `6fc77723af0a`

> Done! A human specialist will review your dispute within 24 hours (ticket #151). They'll work to resolve this and protect your payment. You should hear from them soon.

### Part C after: run 3
Tools: `escalate_to_human`
Studio session `e6ffa7f0b522`

> I've opened ticket #151 for your dispute (cw-disputes policy). Our team will follow up within 24 hours to investigate the charge and the defective product issue. You should hear from them soon with next steps.
> 
> In the meantime, if you have your order number handy, that would help speed things up!

## Edit v2 (final) (prompt `46c341cfbd32`)

```
Charge disputes always go to a human; a dispute is not a payment-card change,
so do not refuse it. First find the order (find_order or list_my_orders), then
call escalate_to_human with the order id in the summary. In your reply, cite
cw-disputes and state only the ticket id and response time the tool returned.
```

### Part C after-v2: run 1
Tools: `find_order`, `escalate_to_human`
Studio session `5210db61871b`

> Perfect. I've opened a ticket for our dispute team. Here are your details:
> 
> - **Ticket ID:** 151
> - **Response time:** Within 24 hours
> 
> Our team will review your charge dispute for order 301 (the Bluetooth speakers) and investigate the store's response. They'll reach out to you shortly with next steps.
> 
> In the meantime, if you have documentation of your attempts to contact the store, please have that ready. Per our policy (cw-disputes), our team will help resolve this for you.

### Part C after-v2: run 2
Tools: `find_order`, `escalate_to_human`
Studio session `53488a3f85a5`

> Your charge dispute has been escalated. Per our dispute policy (cw-disputes), a human agent will investigate and work with your payment processor to resolve this. 
> 
> **Ticket ID: 151**
> **Response time: 24 hours**
> 
> They'll review the defective product and the store's lack of response. You should hear back within a day.

### Part C after-v2: run 3
Tools: `find_order`, `escalate_to_human`
Studio session `7c6852c189de`

> Your dispute has been escalated to our team. Per our dispute policy (cw-disputes), a human agent will review your case and follow up with you.
> 
> **Ticket ID: 151**  
> **Response time: Within 24 hours**
> 
> Our team will investigate the defective product and your dispute claim. They'll reach out to you shortly with next steps.
