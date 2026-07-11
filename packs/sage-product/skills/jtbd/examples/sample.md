# Jobs-to-be-Done Examples

## Contents
- Example 1: Project Management Software (full analysis)
- Example 2: Bad JTBD Analysis (anti-pattern)
- Example 3: B2C Quick Analysis (lighter weight)

---

## Example 1: Project Management Software (Full Analysis)

### 1. Job Performer and Context

**Job performer:** Project lead managing a cross-functional product development team (5–15 people)
**Buyer:** VP of Engineering or IT procurement (evaluates cost, security, integration)
**Approver:** CFO or department budget holder
**Audience:** Stakeholders and executives who receive status updates

**Key distinction:** The project lead needs visibility and control. The buyer needs cost per seat, SSO compliance, and consolidation of existing tools.

**Circumstances:**
- Team is distributed across time zones (no hallway conversations)
- Multiple workstreams have dependencies on each other
- During crunch periods when priorities shift rapidly
- When onboarding a contractor mid-project who needs context quickly

**Struggling moment:** "I stayed until 9 PM on a Friday manually compiling a status report from three different tools, and realized half the information was already stale by the time I sent it. I thought — there has to be a better way."

**Current solutions hired:**
- Jira: powerful but complex; non-engineers resist it; configuration overhead is high
- Spreadsheets: flexible but stale within hours; no real-time sync
- Slack threads + memory: fast but nothing documented; context lost when people join
- Weekly status meetings: reliable but costly (5+ hours/week across the team)

### 2. Jobs

**Main functional job:** Coordinate work across a cross-functional team to deliver a project on time

**Related jobs:**
- Report project status to stakeholders
- Manage resource allocation across concurrent projects
- Onboard new team members mid-project

**Emotional jobs:**
- Feel confident that nothing is slipping through the cracks
- Avoid the stress of last-minute surprises when a deadline approaches

**Social jobs:**
- Be seen as an organized, reliable leader by the executive team
- Demonstrate transparency and accountability to stakeholders

### 3. Job Process Map

| Stage | What the performer does | Key friction |
|-------|------------------------|-------------|
| Define | Set project goals, scope, success criteria | Hard to translate business objectives into concrete milestones |
| Locate | Identify available people, skills, prior work | No single view of team capacity across projects |
| Prepare | Break work into tasks, assign owners, set timelines | Estimating effort is guesswork without historical data |
| Execute | Team members work on assigned tasks | People update status in different tools (or not at all) |
| Monitor | Track progress, identify blockers | Blockers surface too late — often at standup, not when they happen |
| Modify | Re-prioritize when scope changes or a dependency breaks | Cascading impact of changes is invisible until damage is done |
| Conclude | Deliver project, conduct retrospective | Lessons learned aren't captured reusably |
| Share | Report status to stakeholders | Manual report assembly takes hours and is always slightly outdated |

### 4. Pains and Gains

**Pains — Challenges:**
- Team members use different tools, creating information silos with no single source of truth
- Dependencies between workstreams are invisible until something breaks
- Remote members miss context shared in impromptu conversations

**Pains — Costliness:**
- Manual status reports: 3 hours/week
- Sync meetings: 5+ hours/week across the team
- New member onboarding: 2+ days of someone's time

**Pains — Common Mistakes:**
- Tasks without clear ownership or due dates get forgotten
- Priority changes miscommunicated, causing wasted effort on deprioritized work

**Pains — Unresolved Problems:**
- Tools don't surface blockers automatically — they require self-reporting
- No way to visualize dependencies and cascading timeline impact

**Gains — Expectations:**
- Auto-update stakeholders on progress without manual reports
- Alert project lead to at-risk items before they become blockers

**Gains — Savings:**
- Reduce status reporting from 3 hours to 15 minutes/week
- Cut sync meetings from 5 hours to 2 hours/week
- Reduce onboarding from 2 days to 2 hours

**Gains — Adoption Factors:**
- < 30 minutes to set up for the team
- Integrates with Slack, Google Calendar, GitHub
- Works with partial team adoption — doesn't require everyone to switch on day one

### 5. Forces of Progress

**Push** (what's driving the desire to change):
- Status reporting is 3 hours of pure waste every week
- Blockers discovered too late — always at standup, never when they happen
- Every project post-mortem says "we need better visibility" and nothing changes

**Pull** (what the better future looks like):
- Imagined opening one dashboard and seeing exactly where every workstream stands
- Imagined getting an alert before a blocker causes a delay, not after

**Anxiety** (what holds them back from switching):
- "What if the team refuses to use it and we're back to spreadsheets in a month?"
- "Migrating in-progress projects seems risky — what if we lose data or context?"
- "The last tool we tried took 3 months to configure and we abandoned it"

**Habit** (inertia of the current way):
- The current spreadsheet-and-Slack workflow is bad but familiar — everyone knows where things are
- Sunk cost: team has spent years building templates and conventions in the current tools
- "At least meetings work — we can always just add another sync"

**Biggest lever:** Anxiety about migration and team adoption is the primary blocker. Most project leads *want* to switch but can't stomach the risk of mid-project disruption. A solution that works with partial adoption (no big-bang migration required) would unlock the most demand.

### 6. Desired Outcome Statements (selected high-priority)

| Stage | Desired Outcome | Imp | Sat | Opp |
|-------|----------------|-----|-----|-----|
| Monitor | Minimize the time it takes to identify a blocked task | 9 | 3 | 15 |
| Modify | Minimize the likelihood of missing a cascading impact when a deadline changes | 9 | 2 | 16 |
| Share | Minimize the time it takes to assemble an accurate status report | 8 | 3 | 13 |
| Prepare | Increase the accuracy of effort estimates for new tasks | 8 | 3 | 13 |
| Locate | Minimize the time it takes to determine a team member's current availability | 7 | 3 | 11 |
| Execute | Minimize the likelihood that two team members unknowingly duplicate work | 7 | 4 | 10 |

### 7. Prioritization

**Top pains:** (1) Cascading dependency blindness — highest impact, hardest to workaround. (2) Blocker detection lag — acute, daily. (3) Status reporting overhead — 3 hours/week of pure waste.

**Must-haves:** Auto-surfacing blockers, dependency visualization. **Nice-to-haves:** Historical velocity data, AI-suggested task assignments.

---

## Example 2: Bad JTBD Analysis (Anti-Pattern)

**Job performer:** Not specified
**Main job:** "Use AI-powered project management"
**Emotional jobs:** "Feel modern"
**Pains:** "Current tools are old." "UX is bad."
**Gains:** "Better dashboards." "AI features." "Mobile app."

### What's wrong

- **No performer.** Who are we solving for? Each role has different jobs.
- **The "job" is a solution.** "Use AI-powered project management" bakes in the technology. Strip "AI-powered" and ask what they're trying to *accomplish*. This is classic supply-side thinking — describing the product, not the customer's struggle.
- **"Dashboards" and "mobile app" are features.** What would the dashboard help them *do*?
- **Pains are vague.** "Tools are old" is not actionable. How old? What can't they do? What's the cost?
- **Gains are generic.** "Better UX" — every product promises this. It differentiates nothing.
- **No struggling moment.** What event triggered the need for change? Without one, there's no demand — just a wish list.
- **No forces analysis.** What anxiety prevents them from switching? What habit keeps them stuck? These are the levers that actually unlock adoption.
- **Competition is undefined.** What do they use today? Product categories aren't competition — customers define competition by what serves their progress.

### How to fix

Ask "What are you trying to accomplish?" not "What features do you want?" Apply the "5 Whys": "I need AI" → Why? → "To predict risks" → Why? → "To avoid missed deadlines" → The job is "deliver projects on time."

---

## Example 3: B2C Quick Analysis — Home Cooking App

**Job performer:** Home cook preparing weeknight dinners for a family of 3–5.
**Buyer:** Same person. **Audience:** Family members eating the meal.

**Main job:** Prepare a healthy weeknight dinner that the family will eat.

**Circumstances:** After a full workday, 30–45 minutes available. One family member has dietary restrictions. Fridge is half-empty and shopping isn't happening today.

**Emotional jobs:** Feel like a good parent providing nutritious meals. Avoid guilt of ordering takeout again.
**Social jobs:** Have family members compliment the meal.

**Key pains:**
- Meal planning takes mental energy the cook doesn't have after work
- Recipes assume ingredients the cook doesn't have
- Recipe steps need to be glanceable, not paragraph-length — kids interrupt constantly

**Key gains:**
- Suggest meals based on what's already in the fridge
- 15-minute and 30-minute options for different energy levels
- Adapt portions automatically for different family sizes

This analysis is lighter than Example 1 — no desired outcome statements, no full process map. That's appropriate for early-stage consumer discovery. Deepen with outcome statements when prioritizing a roadmap.
