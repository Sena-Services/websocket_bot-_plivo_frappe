# Plivo Fallback Bot

This is a simple WebSocket-based fallback bot that activates when your primary number doesn't answer within 30 seconds.

## Quick Setup

### 1. Create .env file
```env
PLIVO_AUTH_ID=your_plivo_auth_id_here
PLIVO_AUTH_TOKEN=your_plivo_auth_token_here
OPENAI_API_KEY=your_openai_api_key_here
CARTESIA_API_KEY=your_cartesia_api_key_here
GLADIA_API_KEY=your_gladia_api_key_here  # Optional
DEEPGRAM_API_KEY=your_deepgram_api_key_here  # Optional fallback
```

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

### 3. Start the bot server
```bash
python server.py
```

### 4. Expose via ngrok
```bash
ngrok http 8765
```

### 5. Update your existing application's XML
In your existing application that generates the XML, modify it to add the Stream element:

```xml
<Response>
  <Record
      action="https://285262b53c31.ngrok-free.app/api/method/crm.integrations.plivo.api.recording_callback"
      fileFormat="mp3"
      redirect="false"
      maxLength="3600"
      startOnDialAnswer="true" />
  <Dial
      action="https://285262b53c31.ngrok-free.app/api/method/crm.integrations.plivo.api.dial_callback"
      timeout="30"
      callerId="+1 917-920-8677">
    <Number>+919677018116</Number>
  </Dial>
  
  <!-- Add this Stream element for fallback bot -->
  <Stream bidirectional="true" keepCallAlive="true" contentType="audio/x-mulaw;rate=8000">
    wss://YOUR_BOT_NGROK_URL/ws
  </Stream>
</Response>
```

Replace `YOUR_BOT_NGROK_URL` with your ngrok URL for this bot server.

## How It Works



## Endpoints

- `GET /` - Health check
- `WebSocket /ws` - Bot communication endpoint  
- `GET/POST /test-callback` - Testing endpoints

## SenaBot Features

- **Educational Assistant** - Specializes in education-related questions
- **Smart Introduction** - Explains it's handling the call as a fallback
- **Multi-language STT** - English/French support with code-switching
- **Voice Activity Detection** - Natural conversation flow

## Testing

```bash
# Test the bot server
curl http://localhost:8765/

# Test with ngrok URL
curl https://your-ngrok-url.ngrok-free.app/
```

## File Structure

```
plivo-telephony-master/
├── server.py          # Main bot server
├── bot.py             # Bot logic and pipeline
├── constants/propmt.py # Bot prompts and instructions
├── requirements.txt    # Dependencies
└── README.md          # This file
```

## Important Notes

- This bot server **only provides the WebSocket endpoint**
- Your existing application **handles the XML generation**
- The bot **activates only when the primary number doesn't answer**
- Make sure to update your existing XML to include the `<Stream>` element
1. **Incoming Call** → Your existing application generates XML
2. **Record** → Starts recording as per your existing logic  
3. **Dial** → Tries to call +919677018116 with 30-second timeout
4. **If No Answer** → Plivo automatically moves to the Stream element
5. **Fallback Bot** → This bot server handles the call via WebSocket