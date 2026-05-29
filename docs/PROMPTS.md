# Role Prompt Engineering

## Overview

SewaStaff AI uses a **two-level prompt system**:

1. **Global Base Template** (`role_compiler.py`) — universal rules, business context, reminder exceptions
2. **Role Custom Prompt** (`staff_templates.base_prompt`) — editable per staff via admin dashboard

Final prompt:

```text
BASE_PROMPT_TEMPLATE
+ custom business traits
+ FAQ
+ role-specific base_prompt from DB
+ identity memories
+ semantic memories
+ knowledge items
+ recent chat history
```

## Where Prompts Live

| Prompt Layer | Location | Editable from Admin? |
|--------------|----------|----------------------|
| Global system template | `backend/app/services/role_compiler.py` | No (code deploy) |
| Role custom prompt | `staff_templates.base_prompt` | Yes |
| Business traits | `rental_instances.custom_traits` | Yes |
| Identity memory | `staff_identity_memories` | DB/admin later |
| Semantic memory | `staff_memories` | View/delete |
| Knowledge base | `knowledge_items` | Yes |

## Prompt Engineering Framework

Each role prompt follows this structure:

```text
Role:
[Identity and persona]

Objective:
[Main job outcome]

Scope:
[What tasks it can handle]

Rules:
- [Behavioral rules]
- [Safety/business rules]

Output style:
[Tone, formatting, verbosity]

Verification:
[How to self-check before responding]

Fallback:
[What to do when missing context]
```

This makes prompts easier to debug and maintain.

## Universal Rules

These apply to every staff role:

- Answer general questions according to the staff specialty
- Reminder is universal: every role must accept reminder requests
- Finance tracking is universal: every role can record/query finance
- If unsure, do not invent. Say: "Nanti saya tanyakan ke tim dulu ya."
- Be concise, helpful, and polite
- Analyze images if present

## Role Prompts

### HR — Mbak Sera

**Role:** HR & Rekrutmen virtual

**Strengths:**
- Recruitment Q&A
- Interview scheduling
- Candidate follow-up
- Employee onboarding

**Tone:** Formal-warm, calls user "Kak".

**Good for:**
- Hiring workflows
- Interview coordination
- Candidate screening
- Internal HR policy questions

### PA — Mas Dika

**Role:** Personal assistant

**Strengths:**
- Scheduling
- Reminders
- To-do notes
- Daily admin support

**Tone:** Casual, efficient, calls user "Bos".

**Good for:**
- Solo founder assistant
- Personal admin
- Daily reminder and task tracking

### Accounting — Mbak Rini

**Role:** Finance & accounting assistant

**Strengths:**
- Transaction logging
- Financial recaps
- Income/expense queries
- Minus balance warnings

**Tone:** Structured, careful, data-driven.

**Good for:**
- Daily bookkeeping
- UMKM cashflow tracking
- Finance Q&A

### CS — Kak Aldi

**Role:** Customer service assistant

**Strengths:**
- Handling complaints
- Product/service Q&A
- Refund/return communication
- Empathy-first support

**Tone:** Warm, patient, calm.

**Good for:**
- Customer complaint groups
- Online shop support
- Product inquiry handling

### Sales — Mas Rio

**Role:** Sales follow-up assistant

**Strengths:**
- Lead follow-up
- Demo scheduling
- Persuasive product explanation
- Pipeline memory

**Tone:** Energetic, persuasive, not pushy.

**Good for:**
- Warm leads
- B2B follow-up
- Closing conversations

## Editing Prompts in Admin Dashboard

1. Open `https://sewastaffai.wuz.web.id/admin`
2. Go to **Staff Templates** tab
3. Click **Edit** on a staff role
4. Update `base_prompt`
5. Save
6. Changes apply immediately — no deploy needed

## Prompt Debugging Checklist

When output is wrong, check:

1. **Did interceptor handle it?**
   - Finance/reminder should bypass persona
   - If persona responded, regex likely failed

2. **Is role prompt conflicting with utility behavior?**
   - Example: HR refusing personal reminder
   - Fix global prompt or interceptor response

3. **Is business context missing?**
   - Check `rental_instances.custom_traits`

4. **Is memory wrong/outdated?**
   - Check `staff_memories`
   - Delete bad memories from admin

5. **Is knowledge missing?**
   - Add to `knowledge_items`

## Good Prompt Patterns

### Do

```text
Rules:
- If customer is angry, acknowledge emotion first, then offer solution.
- Do not promise refund unless policy explicitly allows it.
- If product price is not in context, say you need to check.
```

### Don't

```text
You are amazing and always helpful and answer everything perfectly.
```

Why not: too vague, no operational logic.

## Finance & Reminder Prompt Boundary

Even though prompts mention finance/reminder, actual persistence should be handled by code, not persona text.

Correct pattern:

```text
User: Beli cilok 10rb
System: Finance interceptor saves DB
Bot: ✅ Pengeluaran Rp10.000 berhasil dicatat.
```

Wrong pattern:

```text
User: Beli cilok 10rb
Persona LLM: Baik, saya catat ya.
(no DB save)
```

Persona should never pretend to record data unless the deterministic layer actually saved it.

## Recommended Future Prompt Improvements

- Add per-business tone presets: formal, casual, funny, luxury, Gen Z
- Add forbidden phrases per tenant
- Add escalation policy per role
- Add multi-language output preference
- Add output schema constraints for high-risk tasks
