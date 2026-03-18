# Push to GitHub

## Instructions

Push all committed changes to the GitHub repo using the project's GITHUB_TOKEN from .env (not system credentials).

### Steps

1. Load the GITHUB_TOKEN from .env:
```bash
export $(grep '^GITHUB_TOKEN=' .env | xargs)
```

2. Set the remote URL with the token embedded:
```bash
git remote set-url origin https://${GITHUB_TOKEN}@github.com/tylerlubbenbio/dagster.git
```

3. Push to main:
```bash
git push origin main
```

4. Reset the remote URL to remove the token (security):
```bash
git remote set-url origin https://github.com/tylerlubbenbio/dagster.git
```

5. Report the result to the user.

### Notes
- Always uses the GITHUB_TOKEN from .env, never system git credentials
- Repo: tylerlubbenbio/dagster
- Branch: main
- If there are uncommitted changes, ask the user if they want to commit first
