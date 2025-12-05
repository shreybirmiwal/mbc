# Demo APIs Server

A Flask server providing various API endpoints for AI models and utility functions.

## Deployment to Vercel

This server is configured to deploy to Vercel as a serverless function.

### Prerequisites

1. Install Vercel CLI (if deploying via CLI):
   ```bash
   npm i -g vercel
   ```

2. Set up environment variables in Vercel:
   - `OPENROUTER_API_KEY`: Your OpenRouter API key (required for AI routes)
   - `SITE_NAME`: Optional site name for OpenRouter rankings (defaults to "Demo APIs Server")

### Deployment Steps

#### Option 1: Deploy via Vercel Dashboard

1. Go to [vercel.com](https://vercel.com) and sign in
2. Click "New Project"
3. Import your repository or upload the `demo-apis` folder
4. Configure:
   - **Framework Preset**: Other
   - **Root Directory**: `demo-apis` (if deploying from monorepo)
   - **Build Command**: (leave empty)
   - **Output Directory**: (leave empty)
5. Add environment variables:
   - `OPENROUTER_API_KEY`: Your API key
   - `SITE_NAME`: (optional) Your site name
6. Click "Deploy"

#### Option 2: Deploy via CLI

1. Navigate to the `demo-apis` directory:
   ```bash
   cd demo-apis
   ```

2. Run:
   ```bash
   vercel
   ```

3. Follow the prompts to link your project

4. Set environment variables:
   ```bash
   vercel env add OPENROUTER_API_KEY
   vercel env add SITE_NAME
   ```

5. Deploy to production:
   ```bash
   vercel --prod
   ```

### API Endpoints

Once deployed, your endpoints will be available at:
- `https://your-project.vercel.app/mistral` (POST)
- `https://your-project.vercel.app/llama3` (POST)
- `https://your-project.vercel.app/gemini` (POST)
- `https://your-project.vercel.app/generic` (POST)
- `https://your-project.vercel.app/weather` (GET/POST)
- `https://your-project.vercel.app/bitcoin` (GET)
- `https://your-project.vercel.app/fact` (GET)
- `https://your-project.vercel.app/joke` (GET)
- `https://your-project.vercel.app/time` (GET)

### Local Development

To run locally:

```bash
pip install -r requirements.txt
export OPENROUTER_API_KEY="sk-or-..."
python server.py
```

The server will run on `http://localhost:5000`
