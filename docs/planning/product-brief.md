# Product Brief: SewaStaff AI

## 1. Idea in One Sentence
SewaStaff AI is a WhatsApp-native virtual staff rental service that provides constrained, conversational AI personas (HR, PA, Sales) inside WhatsApp groups for Indonesian small businesses and founders.

## 2. Target User
- Primary user: Solopreneur, online shop owner, or small agency founder in Indonesia.
- Secondary user: The founder's existing human team members.
- Buying user (if different): Primary user.
- Why this user matters first: They have high operational pain (slow response = lost money) but lack the technical skill to build or maintain complex AI automations. They already live in WhatsApp.

## 3. Pain / Problem
- What painful problem happens today? Founders spend too much time on repetitive operational chats (answering FAQs, screening CVs, basic finance tracking).
- How often does it happen? Daily.
- What is the cost of doing nothing? Burnout, lost sales due to slow responses, disorganized administration.
- Why is this painful enough to solve now? The volume of WhatsApp messages scales linearly with business growth, creating an immediate bottleneck.

## 4. Current Alternatives
- What do users do today instead? Hire cheap human admins or ignore messages.
- Why are current alternatives insufficient? Humans need management, sleep, and make mistakes. Hiring is a heavy commitment.
- Why not just use manual workflow / WhatsApp Business auto-reply? Auto-replies are dumb and frustrating for customers. Complex chatbot builders are too hard to set up.

## 5. Core Value Proposition
- Main promise: Rent an AI staff member who works 24/7 directly inside your WhatsApp group.
- Fastest visible win for the user: Creating a group, adding the AI, and seeing it handle a repetitive task immediately.
- Why this would be compelling: It feels like hiring a real person ("Mbak Sera HR"), not configuring a software tool. Zero learning curve for the interface (just WhatsApp).

## 6. Narrow MVP
- What is the smallest version that is still useful? 5 pre-defined roles (HR, PA, Sales Follow-up, Reminder, light Finance) accessed via dedicated WhatsApp groups.
- Must have: Reactive-only responses (no broadcast), multi-tenant isolation per group, rate-limited pacing (anti-ban), image recognition (vision), simple web onboarding.
- Nice to have later: Document/audio parsing, custom role builder, proactive analytics, payment gateway integration.
- Explicit cuts for v1: n8n workflow builder, complex dashboard analytics, video/voice note processing, proactive broadcasting, manual handoff UI (handled naturally in the group).

## 7. Business Model Pressure Test
- Who pays? The business owner.
- Why would they pay? It replaces the cost/hassle of an entry-level admin.
- What makes this economically sensible? Cost of Gemini Flash inference + WhatsApp session is pennies per month. Selling at Rp99k/group/month provides massive margins.
- What proof would validate willingness to pay? Users successfully creating a group and keeping the AI active past the free trial.

## 8. Operational Reality
- Human-in-the-loop needed where? The owner is already in the WhatsApp group. If the AI fails or asks for help, the owner steps in naturally by replying.
- What can go wrong operationally? WhatsApp bans the unofficial number. Solution: Queue pacing and multiple sessions.
- What process cannot be fully automated yet? Number provisioning/scanning (must be done manually by admins to add session capacity).

## 9. Technical Risk Snapshot
- Hardest part technically: WhatsApp webhook event normalization and deduplication.
- Biggest unknown: How quickly Meta's anti-ban AI adapts to the pacing delays.
- Biggest integration risk: WAHA API stability and session drops.

## 10. Go / No-Go Summary
- Why this idea is worth continuing: It has a clear distribution model, aligns perfectly with Indonesian cultural habits (WhatsApp groups), and solves a tangible business pain with a highly profitable margin structure.
- Why it may not be worth continuing: If unofficial WhatsApp bans become completely unavoidable despite pacing.
- Recommendation: GO. Build the FastAPI core, prioritize the queue, and launch with a small set of curated roles.
