import argparse
import json
import traceback

import uvicorn
from bot import run_bot
from fastapi import FastAPI, WebSocket, Request
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger
from starlette.responses import HTMLResponse

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for testing
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def health_check():
    """Health check endpoint"""
    return {"status": "Bot server is running", "message": "WebSocket available at /ws"}


@app.get("/test-callback")
async def test_callback():
    """Test endpoint to verify callback setup"""
    return {"status": "success", "message": "Callback endpoint is working"}


@app.post("/test-callback") 
async def test_callback_post(request: Request):
    """Test POST callback"""
    form_data = await request.form()
    data = dict(form_data)
    print(f"Test callback received: {data}")
    return {"status": "success", "data": data}


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for bot communication - called from your existing application's Stream element"""
    await websocket.accept()

    try:
        # Plivo sends a start event when the stream begins
        start_data = websocket.iter_text()
        start_message = json.loads(await start_data.__anext__())

        print("Received start message:", start_message, flush=True)

        # Extract stream_id and call_id from the start event
        start_info = start_message.get("start", {})
        stream_id = start_info.get("streamId")
        call_id = start_info.get("callId")

        # Ensure stream_id is not None or empty
        if not stream_id:
            logger.error("No streamId found in start message")
            await websocket.close()
            return

        # Ensure call_id is not None - provide a default if missing
        if call_id is None or call_id == "":
            call_id = f"call_{stream_id}"
            logger.warning(f"No callId found in start message, using default: {call_id}")

        print(f"Bot WebSocket connection accepted for stream: {stream_id}, call: {call_id}")
        print("Bot is now handling the call as primary number was not answered")
        
        await run_bot(websocket, stream_id, call_id)
    
    except Exception as e:
        logger.error(f"Error in WebSocket connection handler: {e}")
        try:
            await websocket.close()
        except:
            pass


if __name__ == "__main__":
    print("🤖 Starting Plivo Fallback Bot Server")
    print("📡 WebSocket endpoint: /ws")
    print("🔗 Connect from your existing application's <Stream> element")
    uvicorn.run(app, host="0.0.0.0", port=8765)
