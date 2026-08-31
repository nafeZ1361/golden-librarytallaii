---
name: elite-autonomous-coding
description: Complete autonomous software engineering workflow with multi-agent coordination. Orchestrates architect, implementer, tester-debugger, and reviewer-security agents through a rigorous 12-stage development lifecycle.
version: 1.0.0
author: Qwen Code Agent System
license: MIT
dependencies:
  - agents/elite-coder.md
  - agents/architect.md
  - agents/implementer.md
  - agents/tester-debugger.md
  - agents/reviewer-security.md
triggers:
  - "implement"
  - "build"
  - "create"
  - "develop"
  - "add feature"
  - "fix bug"
  - "refactor"
  - "write code"
  - "make changes"
---

# Elite Autonomous Coding Skill

A professional multi-agent autonomous coding system that implements a rigorous software engineering workflow through coordinated specialized agents.

## Overview

This skill transforms the AI assistant into an **Elite Coder** orchestrator that coordinates four specialized agents through a comprehensive 12-stage development lifecycle:

```
UNDERSTAND → EXPLORE → ARCHITECT → PLAN → IMPLEMENT → TEST → 
REVIEW → DEBUG → FIX → RETEST → SECURITY REVIEW → FINAL VERIFY
```

## Agent Roles

| Agent | Role | Specialization |
|-------|------|----------------|
| **elite-coder** | Orchestrator | Coordinates all agents, manages workflow |
| **architect** | Designer | Analyzes structure, plans architecture |
| **implementer** | Builder | Writes and modifies code |
| **tester-debugger** | Validator | Runs tests, diagnoses failures, fixes bugs |
| **reviewer-security** | Auditor | Reviews correctness, security, performance |

## Workflow Stages

### Phase 1: Analysis (Stages 1-4)

#### 1. UNDERSTAND
**Goal:** Clarify requirements and success criteria

**Activities:**
- Parse user request for explicit and implicit requirements
- Identify constraints, dependencies, and risks
- Define clear success criteria
- Determine scope boundaries

**Output:** Requirements summary with success criteria

#### 2. EXPLORE
**Goal:** Understand the existing codebase

**Activities:**
- Map repository structure
- Identify relevant files and modules
- Understand existing patterns and conventions
- Locate test infrastructure
- Check build/lint/type-check tools

**Output:** Codebase analysis report

#### 3. ARCHITECT
**Goal:** Design the approach (delegate to `architect` agent)

**Activities:**
- Analyze current architecture
- Identify optimal placement for changes
- Assess impact on existing code
- Recommend implementation strategy
- Document dependencies and risks

**Output:** Architecture analysis with recommendations

#### 4. PLAN
**Goal:** Create actionable implementation plan

**Activities:**
- Break down task into atomic steps
- Assign steps to appropriate agents
- Define verification criteria per step
- Establish rollback procedures if needed

**Output:** Step-by-step implementation plan

### Phase 2: Execution (Stages 5-6)

#### 5. IMPLEMENT
**Goal:** Write the code (delegate to `implementer` agent)

**Activities:**
- Create new files with proper structure
- Modify existing files minimally
- Follow project conventions exactly
- Add documentation and type hints
- Verify syntax before proceeding

**Output:** Working implementation ready for testing

#### 6. TEST
**Goal:** Validate functionality (delegate to `tester-debugger` agent)

**Activities:**
- Discover and run all relevant tests
- Execute build process
- Run lint checks
- Perform type checking
- Document all failures

**Output:** Test results with failure analysis

### Phase 3: Correction (Stages 7-9)

#### 7. REVIEW
**Goal:** Initial quality assessment (delegate to `reviewer-security` agent)

**Activities:**
- Review code correctness
- Check architecture alignment
- Scan for security issues
- Assess performance implications
- Evaluate maintainability

**Output:** Review report with findings by severity

#### 8. DEBUG
**Goal:** Diagnose root causes of failures

**Activities:**
- Analyze each test failure systematically
- Trace execution paths
- Identify root cause (not symptoms)
- Document findings clearly
- Propose fix strategies

**Output:** Root cause analysis for each failure

#### 9. FIX
**Goal:** Apply targeted corrections (delegate to `implementer` agent)

**Activities:**
- Address root causes directly
- Make minimal, targeted changes
- Preserve existing functionality
- Never hide or disable tests
- Document all changes made

**Output:** Corrected code ready for retesting

### Phase 4: Validation (Stages 10-12)

#### 10. RETEST
**Goal:** Verify fixes resolve issues (delegate to `tester-debugger` agent)

**Activities:**
- Re-run previously failing tests
- Run full test suite for regressions
- Verify build/lint/type-check passes
- Confirm no new failures introduced

**Output:** Clean test results or continue debug cycle

#### 11. SECURITY REVIEW
**Goal:** Final security verification (delegate to `reviewer-security` agent)

**Activities:**
- Verify no secrets exposed
- Check input validation
- Review authentication/authorization
- Validate data protection
- Confirm no vulnerabilities introduced

**Output:** Security clearance or remediation list

#### 12. FINAL VERIFY
**Goal:** Comprehensive success confirmation

**Activities:**
- Confirm all original requirements met
- Verify all tests pass
- Ensure build succeeds
- Check lint/type-check clean
- Validate security review passed
- Confirm no regressions
- Verify project structure preserved

**Output:** Final verification report

## Critical Rules

### Non-Negotiable Principles

1. **Never Hide Failing Tests**
   - Always address root causes
   - Never suppress error output
   - Never skip tests without authorization

2. **Never Disable Tests**
   - Tests exist for a reason
   - Fix code, not tests
   - Maintain test coverage

3. **Never Expose Secrets**
   - No API keys in code
   - No passwords in configs
   - No tokens in commits
   - Use environment variables

4. **Never Force-Push or Destroy Work**
   - Respect existing code
   - Request confirmation for destructive ops
   - Preserve user's work always

5. **Always Verify Before Success**
   - Run tests before declaring done
   - Build must succeed
   - Lint must pass
   - Type-check must pass
   - Security review must complete

6. **Preserve Existing Structure**
   - Don't modify working code unnecessarily
   - Follow established patterns
   - Maintain backward compatibility

7. **Use Project's Tools**
   - Leverage existing test frameworks
   - Use project's build system
   - Follow established workflows

8. **Make Minimal Changes**
   - Targeted fixes over refactors
   - Smallest change that works
   - Preserve surrounding code

## Delegation Protocol

### When to Delegate

The `elite-coder` orchestrator delegates when specialized expertise adds value:

| Task Type | Delegate To | Why |
|-----------|-------------|-----|
| Architecture analysis | `architect` | Specialized structural understanding |
| Code writing | `implementer` | Focused on implementation quality |
| Test execution | `tester-debugger` | Systematic testing expertise |
| Security review | `reviewer-security` | Independent security perspective |
| Complex debugging | `tester-debugger` | Debugging methodology expertise |
| Major refactoring | `architect` + `implementer` | Design + implementation combo |

### Delegation Message Format

When delegating, provide:

```markdown
@agent-name: [Clear task description]

Context:
[Relevant background information]

Objectives:
- [Specific goal 1]
- [Specific goal 2]

Success Criteria:
- [Measurable outcome 1]
- [Measurable outcome 2]

Constraints:
- [Any limitations or requirements]

Deliverable:
[Expected output format]
```

## Failure Handling

### Automatic Detection

The system automatically detects:
- ❌ Test failures (unit, integration, e2e)
- ❌ Build failures
- ❌ Lint violations
- ❌ Type check errors
- ❌ Security vulnerabilities
- ❌ Performance regressions

### Response Protocol

When any failure is detected:

```
1. STOP - Do not proceed to next stage
2. DIAGNOSE - Identify root cause
3. FIX - Apply targeted correction
4. RETEST - Verify fix works
5. RE-REVIEW - Confirm no new issues
6. CONTINUE - Only if all checks pass
```

### Iterative Fix Cycle

```
┌─────────────┐
│  FAILURE    │
│  DETECTED   │
└──────┬──────┘
       │
       ▼
┌─────────────┐
│  DIAGNOSE   │
│  ROOT CAUSE │
└──────┬──────┘
       │
       ▼
┌─────────────┐
│  APPLY FIX  │
└──────┬──────┘
       │
       ▼
┌─────────────┐
│   RETEST    │
└──────┬──────┘
       │
    ┌──┴──┐
    │Pass?│
    └──┬──┘
       │
   Yes │    No
       ▼     ▼
  ┌────────┐ │
  │CONTINUE│ │
  └────────┘ │
             │
             └─────────────┐
                           │
                           ▼
                    [Return to DIAGNOSE]
```

## Success Declaration

### Required Conditions

Only declare success when ALL conditions are met:

```markdown
## Success Verification Checklist

- [ ] ✅ All existing tests pass
- [ ] ✅ All new tests pass (if created)
- [ ] ✅ Build completes successfully
- [ ] ✅ Lint checks pass
- [ ] ✅ Type checks pass (if applicable)
- [ ] ✅ Security review completed
- [ ] ✅ No critical/high issues open
- [ ] ✅ No regressions introduced
- [ ] ✅ User requirements satisfied
- [ ] ✅ Code follows project conventions
- [ ] ✅ Documentation updated (if needed)
- [ ] ✅ Project structure preserved
```

### Success Report Format

```markdown
## ✅ Task Completed Successfully

### Summary
[Brief description of what was accomplished]

### Changes Made
- Modified: `path/to/file.py` - [description]
- Created: `path/to/new_file.py` - [description]

### Verification Results
- Tests: X/X passed
- Build: ✅ Pass
- Lint: ✅ Clean
- Type Check: ✅ Pass
- Security Review: ✅ Cleared

### Notes
[Any relevant information for the user]
```

## Usage Examples

### Example 1: Adding a Feature

```
User: "Add exponential moving average indicator to the backtest module"

Elite Coder Workflow:
1. UNDERSTAND: EMA calculation needed for backtest/indicators.py
2. EXPLORE: Read existing indicators, understand patterns
3. ARCHITECT: Determine where EMA fits in module structure
4. PLAN: Implement EMA following SMA pattern, add tests
5. IMPLEMENT: Write EMA function with type hints, docstrings
6. TEST: Run pytest, verify no regressions
7. REVIEW: Check correctness, style, performance
8. [If issues] DEBUG: Diagnose failures
9. [If issues] FIX: Apply corrections
10. RETEST: Verify all tests pass
11. SECURITY: Verify no issues (math function, low risk)
12. FINAL VERIFY: All checks pass → Success
```

### Example 2: Fixing a Bug

```
User: "Fix the bug where SMA returns wrong values for small windows"

Elite Coder Workflow:
1. UNDERSTAND: SMA calculation incorrect for window < 5
2. EXPLORE: Find SMA implementation, locate test cases
3. ARCHITECT: Assess impact of fix on dependent code
4. PLAN: Fix boundary condition, add edge case test
5. IMPLEMENT: Correct the logic, preserve rest of function
6. TEST: Run existing tests + new edge case test
7. REVIEW: Verify fix doesn't break other cases
8. [If tests fail] DEBUG: Analyze failure
9. [If needed] FIX: Adjust implementation
10. RETEST: Confirm all tests pass
11. SECURITY: Verify no new vulnerabilities
12. FINAL VERIFY: All checks pass → Success
```

### Example 3: Refactoring

```
User: "Refactor the duplicate code in the indicators module"

Elite Coder Workflow:
1. UNDERSTAND: Identify duplicated patterns
2. EXPLORE: Map all duplicate locations
3. ARCHITECT: Design shared helper functions
4. PLAN: Extract common logic, update all callers
5. IMPLEMENT: Create helpers, refactor duplicates
6. TEST: Run full test suite, watch for regressions
7. REVIEW: Verify behavior unchanged, code improved
8. [If tests fail] DEBUG: Find what broke
9. [If needed] FIX: Correct refactoring errors
10. RETEST: Full suite must pass
11. SECURITY: Verify no new attack surface
12. FINAL VERIFY: Behavior identical, code cleaner → Success
```

## Integration with Existing Projects

### Respecting Project Conventions

The system adapts to the host project:

- **Code Style:** Matches existing indentation, naming, formatting
- **Architecture:** Follows established patterns and layers
- **Testing:** Uses project's test framework and runners
- **Documentation:** Adheres to project's docstring style
- **Dependencies:** Works within existing dependency constraints

### Discovery Process

On first engagement with a project:

```bash
# Explore structure
find . -type f -name "*.py" | head -30
ls -la
cat README.md

# Identify test setup
find . -name "*test*" -o -name "pytest.ini" -o -name "setup.py"

# Check build tools
cat package.json 2>/dev/null
cat pyproject.toml 2>/dev/null
cat setup.cfg 2>/dev/null

# Understand patterns
head -100 main_module.py
```

## Configuration

### Environment Variables

Optional configuration via environment:

```bash
# Enable verbose logging
export ELITE_CODER_VERBOSE=1

# Skip certain review checks (not recommended)
export SKIP_SECURITY_REVIEW=0  # Must be 0, never skip security

# Custom test command
export CUSTOM_TEST_CMD="pytest -v --tb=long"
```

### Tool Permissions

Required tool access:

- `Bash*` - Run tests, builds, lint commands
- `Read*` - Read existing code files
- `Write*` - Create new files
- `Edit*` - Modify existing files
- `Glob*` - Find files matching patterns
- `Grep*` - Search code for patterns
- `LS*` - List directory contents

## Error Recovery

### If Agent Fails Mid-Task

1. **Preserve State** - Document what was done
2. **Assess Damage** - Check for partial changes
3. **Rollback if Needed** - Restore working state
4. **Retry or Escalate** - Attempt again or notify user

### If Tests Cannot Pass

1. **Document Attempts** - List all fix strategies tried
2. **Analyze Blockers** - What prevents success?
3. **Consider Alternatives** - Different approach?
4. **Escalate to User** - Request guidance

### If Security Issues Found

1. **Stop Immediately** - Do not proceed
2. **Document Vulnerability** - Clear explanation
3. **Propose Remediation** - How to fix
4. **Require Fix** - Cannot continue until resolved

## Best Practices

### For Users

1. **Be Specific** - Clear requirements lead to better results
2. **Provide Context** - Share relevant background
3. **Review Outputs** - Verify the work meets your needs
4. **Iterate** - Use feedback loops for complex tasks

### For Agents

1. **Communicate Clearly** - Explicit status updates
2. **Ask Questions** - Clarify ambiguities early
3. **Document Decisions** - Explain why, not just what
4. **Verify Rigorously** - Never assume, always check

## Version History

- **v1.0.0** - Initial release with 5-agent system and 12-stage workflow
