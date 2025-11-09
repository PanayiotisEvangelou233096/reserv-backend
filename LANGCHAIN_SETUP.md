# Langchain & OpenAI API Setup Guide

This guide will help you set up Langchain integration with OpenAI for the Restaurant Planner.

## Prerequisites

- OpenAI account
- Credit card (OpenAI requires payment for API usage)
- Python 3.8+

## Step 1: Create OpenAI Account

1. Go to [OpenAI Platform](https://platform.openai.com/)
2. Click **"Sign up"** or **"Log in"**
3. Complete the registration process
4. Verify your email address

## Step 2: Add Payment Method

1. Go to [OpenAI Billing](https://platform.openai.com/account/billing)
2. Click **"Add payment method"**
3. Enter your credit card information
4. Set up billing limits (recommended: $5-10 for testing)

**Note**: OpenAI charges per API call. GPT-3.5-turbo is very affordable (~$0.002 per 1K tokens).

## Step 3: Create API Key

1. Go to [OpenAI API Keys](https://platform.openai.com/api-keys)
2. Click **"Create new secret key"**
3. Give it a name (e.g., "Restaurant Planner")
4. **Copy the key immediately** - you won't be able to see it again!
5. Save it securely

## Step 4: Configure Environment Variables

1. Open your `.env` file in the `backend` folder
2. Add your OpenAI API key:

```env
OPENAI_API_KEY=sk-your-actual-api-key-here
```

**Important**: Never commit your API key to version control!

## Step 5: Install Dependencies

The required packages are already in `requirements.txt`:

```bash
cd backend
pip install -r requirements.txt
```

This will install:
- `langchain>=0.1.0`
- `openai>=1.6.1`
- `langchain-openai>=0.0.2`

## Step 6: Test the Integration

1. Start the Flask server:
   ```bash
   python app.py
   ```

2. Test the AI chat endpoint:
   ```bash
   curl -X POST http://localhost:5000/api/ai/chat \
     -H "Content-Type: application/json" \
     -d '{
       "restaurant_id": "YOUR_RESTAURANT_ID",
       "message": "What are your opening hours?"
     }'
   ```

3. Check the server logs for:
   - ✅ "Langchain service initialized successfully"
   - ❌ Any error messages

## Step 7: Verify in Frontend

1. Start the frontend:
   ```bash
   cd frontend
   npm run dev
   ```

2. Navigate to a restaurant
3. Click "AI Assistant"
4. Ask a question
5. You should receive an AI response!

## API Usage & Costs

### Model Used
- **GPT-3.5-turbo**: Fast, affordable, perfect for this use case
- Cost: ~$0.002 per 1K tokens (very cheap!)

### Estimated Costs
- Menu recommendations: ~500-1000 tokens per request (~$0.001-0.002)
- Reservation recommendations: ~300-600 tokens per request (~$0.0006-0.0012)
- Chat messages: ~200-500 tokens per request (~$0.0004-0.001)

**Example**: 1000 requests ≈ $1-2

### Monitoring Usage

1. Go to [OpenAI Usage Dashboard](https://platform.openai.com/usage)
2. Monitor your API usage
3. Set up usage limits in billing settings

## Troubleshooting

### Error: "OpenAI API key not configured"
- Check that `OPENAI_API_KEY` is set in `.env`
- Restart the Flask server after adding the key
- Verify the key starts with `sk-`

### Error: "Insufficient quota"
- Check your OpenAI account billing
- Ensure payment method is active
- Check usage limits in billing settings

### Error: "Invalid API key"
- Verify the key is correct
- Check for extra spaces or characters
- Generate a new key if needed

### Error: "Rate limit exceeded"
- You're making too many requests too quickly
- Wait a few seconds and try again
- Consider implementing rate limiting

## Fallback Behavior

If OpenAI API is not configured or fails:
- Menu recommendations: Returns top items from menus
- Reservation recommendations: Returns common dinner times
- Chat: Returns a message directing users to contact the restaurant

The application will continue to work without OpenAI, but AI features will be limited.

## Security Best Practices

1. **Never commit API keys** to version control
2. **Use environment variables** for all secrets
3. **Rotate API keys** periodically
4. **Set usage limits** in OpenAI dashboard
5. **Monitor usage** regularly
6. **Use separate keys** for development and production

## Next Steps

After setting up:
1. ✅ Test AI chat in the frontend
2. ✅ Test menu recommendations
3. ✅ Test reservation recommendations
4. ✅ Monitor API usage
5. ✅ Adjust prompts if needed (in `langchain_integration.py`)

## Advanced Configuration

### Change Model

Edit `langchain_integration.py`:

```python
self.llm = ChatOpenAI(
    model_name="gpt-4",  # Use GPT-4 (more expensive but better)
    temperature=0.7,
    openai_api_key=Config.OPENAI_API_KEY
)
```

### Adjust Temperature

- Lower (0.1-0.3): More focused, deterministic
- Higher (0.7-1.0): More creative, varied responses

### Customize Prompts

Edit the prompts in `langchain_integration.py` to customize AI behavior.

## Support

- [OpenAI Documentation](https://platform.openai.com/docs)
- [Langchain Documentation](https://python.langchain.com/)
- [OpenAI Support](https://help.openai.com/)

