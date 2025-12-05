# Railway Deployment Guide

## Prerequisites
1. Railway account
2. GitHub Personal Access Token with repo permissions
3. OpenAI API key
4. Google Gemini API key

## Deployment Steps

### 1. Create Railway Project
```bash
railway login
railway init
```

### 2. Add PostgreSQL Database
```bash
railway add postgresql
```

### 3. Set Environment Variables
Copy from `.env.railway` and set in Railway dashboard:

**Required Variables:**
- `GITHUB_TOKEN` - Your GitHub personal access token
- `GITHUB_OWNER` - sfdnas-adm
- `GITHUB_REPO` - -Agentic-AI_Multi-User
- `OPENAI_API_KEY` - Your OpenAI API key
- `GEMINI_API_KEY` - Your Google Gemini API key

**Optional (defaults provided):**
- `REVIEWER_A_TYPE=openai`
- `REVIEWER_A_MODEL=gpt-4o-mini`
- `REVIEWER_B_TYPE=gemini`
- `REVIEWER_B_MODEL=gemini-2.0-flash-exp`
- `JUDGE_TYPE=openai`
- `JUDGE_MODEL=gpt-4o-mini`

### 4. Deploy
```bash
railway up
```

### 5. Configure GitHub Webhooks
After deployment, get your Railway URL and configure webhooks:

**Pull Request Events:**
- URL: `https://your-app.railway.app/webhook/pull_request`
- Events: Pull requests (opened, reopened, synchronize)

**Comment Events:**
- URL: `https://your-app.railway.app/webhook/comment`
- Events: Issue comments

## Health Check
Visit `https://your-app.railway.app/` to verify all services are running.

## Cost Optimization
- Uses `gpt-4o-mini` (cheapest OpenAI model)
- Gemini 2.0 Flash (free tier available)
- Railway PostgreSQL (free tier: 1GB)

## Troubleshooting
- Check Railway logs: `railway logs`
- Verify environment variables in Railway dashboard
- Test webhooks with GitHub webhook delivery logs