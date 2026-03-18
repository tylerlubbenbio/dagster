# Git Workflow Best Practices

## Branch Strategy

### Branch Types
```
main              → Production-ready code (protected)
develop           → Integration branch (optional)
feature/*         → New features and pipelines
fix/*             → Bug fixes
hotfix/*          → Urgent production fixes
refactor/*        → Code restructuring
docs/*            → Documentation updates
```

### Workflow

#### Starting New Work
```bash
# Update main
git checkout main
git pull origin main

# Create feature branch
git checkout -b feature/chat-pipeline

# Or for bug fixes
git checkout -b fix/emoji-encoding-issue
```

#### Making Changes
```bash
# Make your changes...

# Stage and commit with structured message
git add .
git commit -m "feat: add chat history extraction pipeline"

# Push to remote
git push origin feature/chat-pipeline
```

#### Creating Pull Request
1. Push feature branch to GitHub
2. Open PR from feature branch → `main`
3. CI checks run automatically
4. Address any failed checks
5. Request review
6. Merge after approval

#### After Merge
```bash
# Switch back to main
git checkout main

# Pull latest changes
git pull origin main

# Delete local feature branch
git branch -d feature/chat-pipeline

# Delete remote branch (if not auto-deleted)
git push origin --delete feature/chat-pipeline
```

---

## Structured Commit Messages (Conventional Commits)

### Format
```
<type>(<scope>): <description>

[optional body]

[optional footer]
```

### Types
- `feat`: New feature (new pipeline, endpoint, integration)
- `fix`: Bug fix
- `refactor`: Code restructuring (no functionality change)
- `docs`: Documentation changes
- `style`: Code formatting (no logic change)
- `test`: Adding or updating tests
- `chore`: Maintenance (dependencies, config, cleanup)
- `build`: Build system changes
- `ci`: CI/CD pipeline changes
- `perf`: Performance improvements

### Examples
```bash
# New feature
git commit -m "feat: add Salesforce opportunity extraction"

# Bug fix
git commit -m "fix: handle null values in chat history"

# With scope
git commit -m "feat(chat): add message content extraction"

# Breaking change
git commit -m "feat!: restructure pipeline architecture

BREAKING CHANGE: Pipeline scripts moved to api/ directory"

# Multiple files
git commit -m "refactor: extract config loading to utility module"

# Documentation
git commit -m "docs: add Dagster deployment guide"
```

---

## Branch Protection Rules

### Protect `main` Branch
In GitHub Settings → Branches → Branch protection rules:

1. **Require pull request reviews**
   - At least 1 approval

2. **Require status checks to pass**
   - emoji-check
   - python-validation
   - dagster-validation
   - file-structure-check

3. **Require branches to be up to date**
   - Ensures no merge conflicts

4. **Do not allow force push**
   - Prevents history rewriting

5. **Do not allow deletion**
   - Protects main branch

---

## CI/CD Pipeline

### Automatic Checks on Push
- Emoji detection (blocks Dagster-breaking characters)
- Python linting (flake8)
- Code formatting (black)
- Dagster validation
- File structure validation
- Commit message format

### Automatic Checks on PR
- PR title format (conventional commits)
- Branch name convention
- PR size warning (>1000 lines)
- Checklist reminder comment

---

## Quick Reference

### Daily Workflow
```bash
# 1. Start feature
git checkout -b feature/my-feature

# 2. Make changes and commit
git add .
git commit -m "feat: descriptive message"

# 3. Push to remote
git push origin feature/my-feature

# 4. Open PR on GitHub
# 5. Wait for CI checks
# 6. Get approval
# 7. Merge to main
# 8. Delete branch
```

### Useful Commands
```bash
# See current branch
git branch

# See status
git status

# See recent commits
git log --oneline -5

# Undo last commit (keep changes)
git reset --soft HEAD~1

# Discard local changes
git checkout -- .

# Update branch with main
git checkout main
git pull
git checkout feature/my-feature
git merge main
```

---

## GitHub Actions Workflows

### Files Created
- `.github/workflows/ci.yml` - Main CI pipeline
- `.github/workflows/pr-validation.yml` - PR-specific checks
- `.github/PULL_REQUEST_TEMPLATE.md` - PR template

### What Each Workflow Does

**CI Pipeline (`ci.yml`):**
- Emoji detection (BLOCKS build)
- Python linting
- Code formatting check
- Dagster validation
- Commit message validation (warning only)
- File structure validation

**PR Validation (`pr-validation.yml`):**
- PR title format check
- PR size warning
- Branch name validation
- Auto-comment with checklist

---

## Troubleshooting

### CI Check Failed: Emoji Found
```bash
# Find files with emojis
grep -r "😀\|🎯\|✅\|❌" --include="*.py" .

# Or use VS Code search with regex
# Search: [\u{1F600}-\u{1F6FF}]
```

### CI Check Failed: File Structure
- Move test files to `_TESTING/`
- Move docs to `AGENT_KNOWLEDGE/docs/` or `docs/`
- No README.md in subdirectories

### CI Check Failed: Python Linting
```bash
# Run locally
flake8 . --exclude=.venv,venv,_ARCHIVED

# Auto-fix formatting
black . --exclude='/(\.venv|venv|_ARCHIVED)/'
```

### Merge Conflicts
```bash
# Update your branch with latest main
git checkout feature/your-branch
git fetch origin
git merge origin/main

# Resolve conflicts in editor
# Then:
git add .
git commit -m "fix: resolve merge conflicts"
git push origin feature/your-branch
```
