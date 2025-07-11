import os
import sys
from typing import Optional

from dotenv import load_dotenv
from fastapi import WebSocket
from loguru import logger

from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineParams, PipelineTask
from pipecat.processors.aggregators.openai_llm_context import OpenAILLMContext
from pipecat.serializers.plivo import PlivoFrameSerializer
from pipecat.services.cartesia import CartesiaTTSService
from pipecat.services.deepgram.stt import DeepgramSTTService
from pipecat.services.openai import OpenAILLMService
from pipecat.transports.network.fastapi_websocket import (
    FastAPIWebsocketParams,
    FastAPIWebsocketTransport,
)

load_dotenv()
logger.remove(0)
logger.add(sys.stderr, level="DEBUG")

from constants.propmt import INITIAL_BOT_MESSAGE, SYSTEM_INSTRUCTION, FALLBACK_INTRODUCTION_TRIGGER

from pipecat.services.gladia.stt import GladiaSTTService
from pipecat.services.gladia.config import (
    GladiaInputParams,
    LanguageConfig,
    Language
)




async def run_bot(websocket_client: WebSocket, stream_id: str, call_id: Optional[str]):
    logger.info(f"Starting fallback bot for stream: {stream_id}")
    print(f"Bot activated as fallback - primary number was not answered")

    # Ensure all parameters are strings and not None to avoid serialization issues
    auth_id = os.getenv("PLIVO_AUTH_ID") or ""
    auth_token = os.getenv("PLIVO_AUTH_TOKEN") or ""
    call_id = call_id or f"call_{stream_id}"

    serializer = PlivoFrameSerializer(
        stream_id=stream_id,
        call_id=call_id,
        auth_id=auth_id,
        auth_token=auth_token,
    )

    transport = FastAPIWebsocketTransport(
        websocket=websocket_client,
        params=FastAPIWebsocketParams(
            audio_in_enabled=True,
            audio_out_enabled=True,
            add_wav_header=False,
            vad_analyzer=SileroVADAnalyzer(),
            serializer=serializer,
        ),
    )

    # Ensure required API keys are not None
    openai_api_key = os.getenv("OPENAI_API_KEY")
    gladia_api_key = os.getenv("GLADIA_API_KEY")
    deepgram_api_key = os.getenv("DEEPGRAM_API_KEY")
    cartesia_api_key = os.getenv("CARTESIA_API_KEY")
    
    if not openai_api_key:
        raise ValueError("OPENAI_API_KEY environment variable is required")
    if not cartesia_api_key:
        raise ValueError("CARTESIA_API_KEY environment variable is required")

    llm = OpenAILLMService(api_key=openai_api_key)

    # Use Gladia STT if available, otherwise fallback to Deepgram STT
    if gladia_api_key:
        logger.info("Using Gladia STT service")
        stt = GladiaSTTService(
            api_key=gladia_api_key,
            model="solaria-1",
            audio_passthrough=True,
            params=GladiaInputParams(
                language_config=LanguageConfig(
                    languages=[Language.EN, Language.FR],
                    code_switching=True
                ),
            )
        )
    elif deepgram_api_key:
        logger.info("Using Deepgram STT service (Gladia not available)")
        stt = DeepgramSTTService(api_key=deepgram_api_key)
    else:
        raise ValueError("Either GLADIA_API_KEY or DEEPGRAM_API_KEY environment variable is required")

    tts = CartesiaTTSService(
        api_key=cartesia_api_key,
        voice_id="71a7ad14-091c-4e8e-a314-022ece01c121",  # British Reading Lady
    )

    # Initialize conversation with fallback context
    messages = [
        {"role": "system", "content": SYSTEM_INSTRUCTION},
        FALLBACK_INTRODUCTION_TRIGGER,
        INITIAL_BOT_MESSAGE
    ]

    context = OpenAILLMContext(messages)
    context_aggregator = llm.create_context_aggregator(context)

    pipeline = Pipeline(
        [
            transport.input(),  # Websocket input from client
            stt,  # Speech-To-Text
            context_aggregator.user(),
            llm,  # LLM
            tts,  # Text-To-Speech
            transport.output(),  # Websocket output to client
            context_aggregator.assistant(),
        ]
    )

    task = PipelineTask(
        pipeline,
        params=PipelineParams(
            audio_in_sample_rate=8000,
            audio_out_sample_rate=8000,
            allow_interruptions=True,
        ),
    )

    @transport.event_handler("on_client_connected")
    async def on_client_connected(transport, client):
        # Kick off the conversation with fallback introduction
        logger.info("Client connected to fallback bot - introducing bot")
        messages.append({"role": "system", "content": "Please introduce yourself now as the caller has been connected to you as a fallback."})
        await task.queue_frames([context_aggregator.user().get_context_frame()])

    @transport.event_handler("on_client_disconnected")
    async def on_client_disconnected(transport, client):
        logger.info("Client disconnected from fallback bot")
        await task.cancel()

    # We use `handle_sigint=False` because `uvicorn` is controlling keyboard
    # interruptions. We use `force_gc=True` to force garbage collection after
    # the runner finishes running a task which could be useful for long running
    # applications with multiple clients connecting.
    runner = PipelineRunner(handle_sigint=False, force_gc=True)

    await runner.run(task)
