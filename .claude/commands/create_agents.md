# Claude Multi-Agent Setup Command (Comprehensive)

> **Purpose:** Analyze your project structure and automatically create 2-3 specialized agents that work in parallel with QA oversight, designed specifically for your architecture and best practices.

You are going to analyze my entire project and create a specialized multi-agent system tailored specifically to this codebase's architecture, patterns, and workflow. This isn't generic - I want agents designed specifically around how MY project actually works.

---

## DEEP ANALYSIS PHASE

Start by comprehensively examining:

1. **Project Structure & Architecture**
   - Walk through directory structure
   - Identify core modules/subsystems
   - Find architectural patterns being used
   - Note any design decisions in README, docs, or code comments
   - Examine configuration files: package.json, docker-compose.yml, .env examples, webpack/build configs, tsconfig, etc.
   - Look at established naming conventions and folder organization patterns

2. **Technology Stack & Constraints**
   - Primary languages and frameworks
   - Database/ORM patterns
   - API architecture (REST, GraphQL, etc.)
   - Data flow patterns
   - External integrations (TikTok Shop, Amazon, Shopify, Stripe, etc.)
   - Authentication/authorization approach
   - Any custom tooling or scripts

3. **Development Workflow**
   - How code typically flows through the project
   - Test patterns and coverage
   - Deployment process
   - Code review standards (if documented)
   - Performance considerations
   - Scaling concerns

4. **Codebase Patterns & Standards**
   - Error handling patterns
   - Logging approaches
   - Type safety (TypeScript interfaces, validation patterns)
   - Data transformation patterns
   - State management patterns
   - Any established "rules" about how things should be done
   - Naming conventions
   - File organization principles

5. **Project Vision & Non-Functional Requirements**
   - What is this system meant to do?
   - Performance targets
   - Reliability/uptime requirements
   - Scalability needs
   - Security considerations
   - User base and scale expectations

---

## AGENT IDENTIFICATION PHASE

Based on your specific architecture, identify 2-4 (MAXIMUM) specialized agent roles. Only create an agent if it genuinely makes sense for the project - don't force it if one agent is sufficient.

Consider these questions:
- **What are the most time-consuming task types** in this codebase? (e.g., API integration work, data transformation, complex business logic)
- **What naturally divides the work** into distinct phases or domains?
- **Which tasks could run in parallel** without blocking each other?
- **Where would specialization provide the most value** (deeper context, specific patterns)?
- **What types of work have distinct success criteria** that could be validated independently?

**Example patterns from production systems:**
- **E-commerce backends**: Often split into [API/Integration Agent] + [Data/ETL Agent] + [QA Validator]
- **Data platforms**: [Data Pipeline Agent] + [Analytics Agent] + [QA Validator]
- **SaaS products**: [Feature Development Agent] + [Integration Agent] + [QA Validator]
- **Simple projects**: Just you as orchestrator + [QA Validator]

---

## AGENT SPECIFICATION PHASE

For EACH agent you identify, create a comprehensive SKILL.md file in `.claude/agents/[agent-name]/SKILL.md` with:

### 1. Frontmatter (YAML)
```yaml
---
name: [descriptive-agent-name]
type: agent-skill
description: [one-line description of purpose]
model: 
user-invoked: false
claude-invoked: true
context: fork
agent: specialized-agent
invocation-trigger: [when should this agent be used?]
can-parallelize: [true/false - can this run at same time as other agents?]
---
```

### 2. Agent Purpose & Responsibilities
Write a detailed section explaining:
- **Core Purpose**: What problem does this agent solve?
- **Scope**: What's IN scope? What's OUT of scope?
- **Success Criteria**: How do you know the agent completed the task successfully?
- **Expertise Required**: What specific knowledge/patterns should this agent deeply understand?
- **Project Context**: Include relevant architectural patterns, conventions, and "rules" this agent must follow

### 3. Task Delegation Guide
Explain:
- **When to delegate**: Specific task types that trigger this agent
- **What information to provide**: What context/files should be passed to agent
- **Expected output format**: How will the agent report results back?
- **Validation points**: What should be checked before considering task complete?

### 4. Agent-Specific Instructions
Include the agent's operating guidelines:
- **Core Constraints**: Non-negotiable rules (e.g., "always validate against schema", "never modify X without approval")
- **Patterns to Follow**: Specific code patterns, naming conventions, architectural rules from your codebase
- **Tools & Resources**: Files, documentation, or patterns it needs to reference
- **Edge Cases**: Known gotchas or special handling needed

### 5. Integration Points
- **How does it interact with other agents?** (sequential, parallel, reporting)
- **What should be returned to main Claude?** (succinct summary vs. detailed results)
- **When to escalate**: What situations require human/orchestrator intervention?

---

## MANDATORY QA VALIDATOR AGENT

**You MUST always create this agent. No exceptions.**

```yaml
---
name: qa-validator
type: agent-skill
description: Validates implementations against architecture, patterns, and project rules
model: haiku # Always Haiku for cost efficiency
user-invoked: false
claude-invoked: true
context: fork
agent: quality-assurance
invocation-trigger: After any major implementation from other agents
can-parallelize: false
---
```

### QA Agent Responsibilities:
- **Pattern Validation**: Does code follow established patterns in this codebase?
- **Architecture & Vision Compliance**: Does it align with the system design AGENT_KNOWLEDGE\ARCHITECTURE.md and vision AGENT_KNOWLEDGE\VISION.md
- **Rules Verification**: Against any documented AGENT_KNOWLEDGE\RULES.md
- **Completeness Check**: Is nothing missing? All edge cases handled?
- **Integration Points**: Will this work correctly with existing code?
- **Type Safety**: Are types/interfaces correctly defined and used?
- **Error Handling**: Proper error handling and edge case coverage?
- **Performance**: Any obvious performance concerns?
- **Security**: Any security issues or vulnerabilities?
- **Documentation**: Are changes documented if needed?
- **Test Coverage**: Should this have tests? If so, are they included?

The QA Agent receives:
- What was implemented
- Project architecture documentation
- Established patterns to validate against
- Any specific "rules" or standards

The QA Agent returns:
- **Status**: Pass/Fail/Conditional
- **Findings**: Specific issues or concerns (if any)
- **Required Changes**: What must be fixed before approval
- **Recommendations**: Nice-to-have improvements
- **Approval Statement**: "This is production-ready" or "Requires fixes: [list]"

---

## CLAUDE.MD UPDATE REQUIREMENTS

After creating agents, update your `CLAUDE.md` file with:

### 1. New "Available Agents" Section
```markdown
## Available Agents

Your specialized agent team includes:

### [Agent Name 1]
- **Purpose**: [What it does]
- **Primary Responsibility**: [Main focus]
- **Model**: Sonnet 4.5
- **When to Use**: [Task types that trigger this agent]
- **Parallel Capable**: Yes/No
- **Reporting Style**: [How it reports results]

### [Agent Name 2]
- **Purpose**: [What it does]
- [... same fields ...]

### QA Validator
- **Purpose**: Validates implementations against architecture and rules
- **Primary Responsibility**: Quality assurance and compliance verification
- **Model**: Haiku 4.5
- **When to Use**: After any major implementation (code generation, architecture changes, complex logic)
- **Parallel Capable**: No (must be sequential)
- **Reporting Style**: Pass/Fail with detailed findings
```

### 2. Your Role as Orchestrator & QA'er
```markdown
## Your Role: Master Orchestrator & Quality Lead

You are NOT doing all the work. You are:
1. **Task Orchestrator**: Understanding what needs to be done and routing to appropriate agents
2. **Quality Gatekeeper**: Ensuring nothing ships without QA validation
3. **Context Manager**: Maintaining coherent understanding across agent work
4. **Escalation Point**: Handling edge cases and making final decisions
5. **Progress Coordinator**: Sequencing work and managing dependencies

### Delegation Decision Tree

**Ask yourself: "Is this simple?"**
- YES → Do it yourself (reading, small edits, planning, understanding)
- NO → Go to next question

**Ask yourself: "Does this fit a specialized agent's domain?"**
- YES → Delegate to that agent
- NO → Handle it yourself or create new agent

**Ask yourself: "Is this a major implementation?"**
- YES → After agent completes, ALWAYS run QA Validator
- NO → Proceed with caution, use judgment

### When YOU Handle It Personally
- Quick fixes and small changes (< 5 minutes of work)
- Understanding existing code and architecture
- Making orchestration decisions
- Writing documentation or comments
- Reviewing agent outputs and making judgment calls
- Reading code to find context

### When to Delegate
- Complex data transformations → [Data/ETL Agent]
- External API integrations → [Integration Agent]
- Feature implementation → [Feature Agent]
- Any major changes → QA Validator for final check

### The Validation Loop (CRITICAL)
1. Clarify what needs to be done
2. Delegate to appropriate agent (or handle if simple)
3. Receive implementation from agent
4. **ALWAYS route major work through QA Validator**
5. QA Validator reports findings
6. Address any issues raised
7. Move forward with confidence

### Agent Invocation Protocol
When delegating to an agent, provide:
- Clear task description
- Relevant context (which files, what patterns matter)
- Success criteria
- Any constraints or rules to follow
- Related codebase snippets if needed

When receiving results, check:
- Does the output match what was requested?
- Have relevant patterns been followed?
- Before shipping → Always QA validate critical work

---

## Project-Specific Agent Rules

[Document any agent-specific rules for YOUR project]
- [Rule 1]: [Explanation]
- [Rule 2]: [Explanation]
- etc.

These override generic instructions when there's a conflict.
```

### 3. Maintenance & Evolution
Add a section:
```markdown
## Maintaining Your Agents

### When to Add a New Agent
- New subsystem clearly separates from existing agents
- Task type would benefit from dedicated specialization
- Parallelization opportunity not currently captured

### When to Remove/Merge Agents
- Agent responsibilities naturally overlap
- Specialized context isn't providing value
- Simpler to handle directly

### Quarterly Agent Review
- Are agents earning their cost (context overhead vs. benefit)?
- Are there new task patterns that warrant specialization?
- Should any agent scopes be adjusted?
- Is QA validation catching important issues?
```

---

## DELIVERABLES CHECKLIST

Before you're done:

- [ ] **Analyzed project structure** - understand architecture deeply
- [ ] **Identified 2-4 agents** (or fewer if appropriate)
- [ ] **Created QA Validator agent** - with comprehensive validation criteria
- [ ] **Created specialized agents** - with task-specific instructions
- [ ] **Each agent has SKILL.md file** in `.claude/agents/[name]/SKILL.md`
- [ ] **Each SKILL.md includes**: Frontmatter, Purpose, Responsibilities, Invocation Guide, Agent Instructions, Integration Info
- [ ] **Updated CLAUDE.md** with "Available Agents" section
- [ ] **Updated CLAUDE.md** with "Your Role as Orchestrator" section
- [ ] **Updated CLAUDE.md** with validation loop documentation
- [ ] **Updated CLAUDE.md** with "When to Delegate" decision tree
- [ ] **Documented project-specific agent rules** in CLAUDE.md
- [ ] **Agent files are PRODUCTION READY** - no TODOs or placeholders

---

## SUCCESS CRITERIA

Your multi-agent system is successful when:

1. **Agents are targeted** - Each agent has a clear, focused purpose specific to THIS project
2. **No overlap** - Agent responsibilities are distinct and clear
3. **Clear delegation** - You immediately know which agent to use for any task
4. **QA is reliable** - QA Validator catches real issues against project rules
5. **Parallel execution works** - Independent agents don't block each other
6. **Documentation is complete** - CLAUDE.md is your reference for orchestration
7. **Cost-efficient** - Haiku for QA means you're not overspending on validation
8. **You stay in control** - You orchestrate, agents execute, you approve

---

## AFTER YOU COMPLETE THIS

Once agents are created:
1. Test them with small tasks first
2. Iterate on agent scopes based on real usage
3. Refine CLAUDE.md based on what you learn
4. Build muscle memory on when to delegate vs. handle yourself
5. Monitor whether agents are earning their value

Good luck! You're building a specialized AI team trained on YOUR codebase.