"""
DevAgent Enterprise - FastAPI Server
Integrates Google ADK Dev Agent with MongoDB Cross-Chat Memory,
Multi-Model Dynamic Selection & Automatic Fallback, and Real-Time SSE Streaming.
"""

import os
import sys
import uuid
import json
import asyncio
import logging
import re
from typing import Optional, List, Dict, Any
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from sse_starlette.sse import ServerSentEvent, EventSourceResponse
from pydantic import BaseModel, Field

import agent
from google.adk.runners import InMemoryRunner
from google.genai import types

import model_manager
import memory_manager

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("devagent.server")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")

# Shared ADK runner instance
runner: Optional[InMemoryRunner] = None


def get_runner() -> InMemoryRunner:
    global runner
    if runner is None:
        runner = InMemoryRunner(agent=agent.root_agent)
    return runner


@asynccontextmanager
async def lifespan(app: FastAPI):
    global runner
    logger.info("Initializing DevAgent runner and connecting to MongoDB...")
    memory_manager.memory_manager.connect()
    runner = get_runner()
    logger.info("DevAgent Enterprise server started successfully.")
    yield
    logger.info("DevAgent Enterprise server shutting down.")


app = FastAPI(
    title="DevAgent Enterprise API",
    description="Google ADK Multi-Agent Coding Assistant with Cross-Chat Memory & Multi-Model Fallback",
    version="2.0.0",
    lifespan=lifespan
)

# Enable CORS for local dev / frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)



# PYDANTIC SCHEMAS


class CreateConversationRequest(BaseModel):
    title: Optional[str] = "New Conversation"
    model: Optional[str] = None


class UpdateConversationRequest(BaseModel):
    title: Optional[str] = None
    model: Optional[str] = None


class ChatRequest(BaseModel):
    conversation_id: Optional[str] = None
    message: str
    model: Optional[str] = None



# API ROUTES


@app.get("/api/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "DevAgent Enterprise",
        "configured_providers": [p["id"] for p in model_manager.get_configured_providers()],
        "default_model": model_manager.get_default_model()
    }


@app.get("/api/models")
async def get_models():
    """Returns available models grouped by provider, along with the system default model."""
    configured = {p["id"]: p for p in model_manager.get_configured_providers()}
    default_model = model_manager.get_default_model()
    all_models = model_manager.get_all_configured_model_ids()

    return {
        "providers": configured,
        "default_model": default_model,
        "all_models": all_models
    }


@app.get("/api/conversations")
async def list_conversations():
    """Retrieve all conversations ordered by recent activity."""
    try:
        convs = memory_manager.list_conversations()
        return {"conversations": convs}
    except Exception as e:
        logger.error(f"Error listing conversations: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/conversations")
async def create_conversation(req: CreateConversationRequest):
    """Create a new conversation session."""
    try:
        model = req.model or model_manager.get_default_model()
        title = req.title or "New Conversation"
        conv = memory_manager.create_conversation(title=title, model=model)
        return conv
    except Exception as e:
        logger.error(f"Error creating conversation: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/conversations/{conversation_id}")
async def get_conversation(conversation_id: str):
    """Get conversation details and full message history."""
    try:
        conv = memory_manager.get_conversation(conversation_id)
        if not conv:
            raise HTTPException(status_code=404, detail="Conversation not found")
        messages = memory_manager.get_messages(conversation_id)
        return {
            "conversation": conv,
            "messages": messages
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching conversation {conversation_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.patch("/api/conversations/{conversation_id}")
async def update_conversation(conversation_id: str, req: UpdateConversationRequest):
    """Rename conversation or change default model."""
    try:
        success = memory_manager.update_conversation(
            conversation_id=conversation_id,
            title=req.title,
            model=req.model
        )
        if not success:
            raise HTTPException(status_code=404, detail="Conversation not found")
        conv = memory_manager.get_conversation(conversation_id)
        return conv
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating conversation {conversation_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/conversations/{conversation_id}")
async def delete_conversation(conversation_id: str):
    """Delete conversation and all its messages."""
    try:
        success = memory_manager.delete_conversation(conversation_id)
        return {"deleted": success, "conversation_id": conversation_id}
    except Exception as e:
        logger.error(f"Error deleting conversation {conversation_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/memory")
async def search_memory(query: str, exclude_id: Optional[str] = None):
    """Search relevant cross-chat memory snippets."""
    try:
        context = memory_manager.get_cross_chat_context(
            query=query,
            exclude_conversation_id=exclude_id
        )
        return {
            "query": query,
            "context": context
        }
    except Exception as e:
        logger.error(f"Error querying memory: {e}")
        raise HTTPException(status_code=500, detail=str(e))



# SSE STREAMING CHAT ENDPOINT


@app.post("/api/chat")
async def chat_stream(req: ChatRequest, background_tasks: BackgroundTasks):
    """
    Main SSE endpoint for running DevAgent with:
    1. Cross-chat memory lookup and injection.
    2. Message persistence in MongoDB.
    3. Multi-model execution with automatic fallback on 429/rate-limit.
    4. Real-time agent transfer, tool execution, and code review streaming.
    """
    conversation_id = req.conversation_id or str(uuid.uuid4())
    user_message = req.message.strip()

    if not user_message:
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    conv = memory_manager.get_conversation(conversation_id)
    if not conv:
        # Auto-create if not existing
        conv = memory_manager.create_conversation(
            conversation_id=conversation_id,
            title=user_message[:40] + ("..." if len(user_message) > 40 else ""),
            model=req.model or model_manager.get_default_model()
        )

    # 1. Retrieve cross-chat context from other conversations
    cross_context = memory_manager.get_cross_chat_context(
        query=user_message,
        exclude_conversation_id=conversation_id
    )

    # 2. Persist user message in MongoDB
    memory_manager.save_message(
        conversation_id=conversation_id,
        role="user",
        content=user_message
    )

    # 3. Build fallback chain
    target_model = req.model or conv.get("model") or model_manager.get_default_model()
    fallback_chain = model_manager.get_fallback_chain(target_model)

    async def _internal_stream():
        # Emit initial start event
        yield ServerSentEvent(
            event="start",
            data=json.dumps({
                "conversation_id": conversation_id,
                "requested_model": target_model,
                "has_cross_chat_memory": bool(cross_context),
                "fallback_chain": fallback_chain
            })
        )

        if cross_context:
            yield ServerSentEvent(
                event="memory_context",
                data=json.dumps({
                    "info": "Retrieved relevant context from previous conversations.",
                    "snippet": cross_context[:300] + ("..." if len(cross_context) > 300 else "")
                })
            )

        # Build prompt for ADK Agent
        if cross_context:
            prompt_for_agent = (
                f"[RELEVANT CONTEXT FROM PREVIOUS CONVERSATIONS]:\n"
                f"{cross_context}\n\n"
                f"[USER TASK]:\n"
                f"{user_message}"
            )
        else:
            prompt_for_agent = user_message

        # Execution with Model Fallback
        success = False
        final_model_used = target_model
        accumulated_text = []
        executed_tools = []
        last_error_msg = ""

        # Make sure session exists in runner
        active_runner = get_runner()
        sess = await active_runner.session_service.get_session(
            app_name=active_runner.app_name,
            user_id="user",
            session_id=conversation_id
        )
        if sess is None:
            await active_runner.session_service.create_session(
                app_name=active_runner.app_name,
                user_id="user",
                session_id=conversation_id
            )

        for attempt_idx, current_model in enumerate(fallback_chain):
            try:
                logger.info(f"Executing turn with model: {current_model} (attempt {attempt_idx + 1}/{len(fallback_chain)})")
                agent.set_agent_model(current_model)
                final_model_used = current_model

                yield ServerSentEvent(
                    event="status",
                    data=json.dumps({
                        "status": "thinking",
                        "model": current_model,
                        "attempt": attempt_idx + 1
                    })
                )

                # Run ADK agent turn
                async for event in active_runner.run_async(
                    user_id="user",
                    session_id=conversation_id,
                    new_message=types.Content(
                        role="user",
                        parts=[types.Part.from_text(text=prompt_for_agent)]
                    )
                ):
                    author = event.author or "DevAgent"

                    # 1. Agent transfer event
                    if event.actions and event.actions.transfer_to_agent:
                        yield ServerSentEvent(
                            event="transfer",
                            data=json.dumps({
                                "from_agent": author,
                                "to_agent": event.actions.transfer_to_agent
                            })
                        )

                    # 2. Escalate event (Approval loop complete)
                    if event.actions and event.actions.escalate:
                        yield ServerSentEvent(
                            event="escalate",
                            data=json.dumps({
                                "agent": author,
                                "escalate": True,
                                "message": "Approval check passed: escalating from loop."
                            })
                        )

                    # 3. Content parts (text, tool calls, tool responses)
                    if event.content and event.content.parts:
                        for part in event.content.parts:
                            # Tool call
                            if hasattr(part, "function_call") and part.function_call:
                                fc = part.function_call
                                tool_name = getattr(fc, "name", "unknown")
                                tool_args = dict(getattr(fc, "args", {})) if hasattr(fc, "args") else {}
                                executed_tools.append({"tool": tool_name, "agent": author})
                                yield ServerSentEvent(
                                    event="tool_call",
                                    data=json.dumps({
                                        "agent": author,
                                        "tool": tool_name,
                                        "args": tool_args
                                    })
                                )

                            # Tool response
                            if hasattr(part, "function_response") and part.function_response:
                                fr = part.function_response
                                tool_name = getattr(fr, "name", "unknown")
                                resp_content = getattr(fr, "response", {})
                                yield ServerSentEvent(
                                    event="tool_result",
                                    data=json.dumps({
                                        "agent": author,
                                        "tool": tool_name,
                                        "response": resp_content
                                    })
                                )

                            # Text chunks
                            if hasattr(part, "text") and part.text:
                                text_val = part.text
                                # Check if reviewer verdict
                                if author == "reviewer_agent":
                                    verdict = "APPROVED" if text_val.strip().upper().startswith("APPROVED") else "CHANGES_REQUIRED"
                                    yield ServerSentEvent(
                                        event="review_verdict",
                                        data=json.dumps({
                                            "agent": author,
                                            "verdict": verdict,
                                            "feedback": text_val
                                        })
                                    )
                                else:
                                    accumulated_text.append(text_val)
                                    yield ServerSentEvent(
                                        event="token",
                                        data=json.dumps({
                                            "agent": author,
                                            "text": text_val
                                        })
                                    )

                # Finished successfully with this model
                success = True
                break

            except Exception as exc:
                last_error_msg = str(exc)
                logger.warning(f"Error during agent execution with {current_model}: {exc}")

                is_rate_limit = model_manager.is_rate_limit_error(exc)
                has_next_fallback = (attempt_idx + 1) < len(fallback_chain)

                if (is_rate_limit or "quota" in last_error_msg.lower() or "429" in last_error_msg or "tier" in last_error_msg.lower()) and has_next_fallback:
                    next_model = fallback_chain[attempt_idx + 1]
                    logger.warning(f"Triggering automatic fallback from {current_model} to {next_model}")

                    yield ServerSentEvent(
                        event="fallback",
                        data=json.dumps({
                            "from_model": current_model,
                            "to_model": next_model,
                            "reason": f"Provider limit / capacity issue on {current_model}. Automatically switching to {next_model}..."
                        })
                    )
                    # Smart backoff: extract wait seconds if provided, capped reasonably
                    wait_time = 2.5
                    m_sec = re.search(r"try again in ([\d\.]+)s", last_error_msg)
                    if m_sec:
                        try:
                            wait_time = max(2.0, min(float(m_sec.group(1)), 5.0))
                        except Exception:
                            pass
                    await asyncio.sleep(wait_time)
                    continue
                else:
                    logger.error(f"Fatal error or no further fallback models: {exc}")
                    yield ServerSentEvent(
                        event="error",
                        data=json.dumps({
                            "error": last_error_msg,
                            "failed_model": current_model
                        })
                    )
                    break

        # Process completion: save message if generated or if tools were executed
        full_reply = "".join(accumulated_text).strip()
        if not full_reply and executed_tools:
            full_reply = f"Operation completed using tools: {', '.join([t['tool'] for t in executed_tools])}."

        if success or full_reply:
            was_fallback = (final_model_used != target_model)

            # Save assistant message in MongoDB
            try:
                memory_manager.save_message(
                    conversation_id=conversation_id,
                    role="assistant",
                    content=full_reply or "Task completed.",
                    model=final_model_used,
                    model_used=final_model_used,
                    metadata={
                        "was_fallback": was_fallback,
                        "original_model": target_model,
                        "tools_called": [t["tool"] for t in executed_tools]
                    }
                )
            except Exception as save_err:
                logger.error(f"Error saving assistant message: {save_err}")

            # Trigger background memory update for cross-chat index
            background_tasks.add_task(
                memory_manager.update_conversation_memory,
                conversation_id=conversation_id
            )

            # Emit final done event
            yield ServerSentEvent(
                event="done",
                data=json.dumps({
                    "conversation_id": conversation_id,
                    "model_used": final_model_used,
                    "was_fallback": was_fallback,
                    "original_model": target_model,
                    "tools_called_count": len(executed_tools),
                    "full_text": full_reply or "Task completed."
                })
            )
        else:
            yield ServerSentEvent(
                event="done",
                data=json.dumps({
                    "conversation_id": conversation_id,
                    "error": last_error_msg,
                    "success": False
                })
            )

    async def sse_generator():
        try:
            async for sse_event in _internal_stream():
                yield sse_event
        except Exception as stream_err:
            logger.exception("Unhandled error in sse_generator: %s", stream_err)
            yield ServerSentEvent(
                event="error",
                data=json.dumps({"error": str(stream_err), "conversation_id": conversation_id})
            )
            yield ServerSentEvent(
                event="done",
                data=json.dumps({
                    "conversation_id": conversation_id,
                    "error": str(stream_err),
                    "success": False
                })
            )

    return EventSourceResponse(sse_generator())



# STATIC FILES & ROOT UI

FRONTEND_DIST = os.path.join(BASE_DIR, "frontend", "dist")
FRONTEND_ASSETS = os.path.join(FRONTEND_DIST, "assets")

if os.path.exists(FRONTEND_ASSETS):
    app.mount("/assets", StaticFiles(directory=FRONTEND_ASSETS), name="assets")

os.makedirs(STATIC_DIR, exist_ok=True)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
@app.get("/{full_path:path}")
async def serve_index(full_path: str = ""):
    if full_path.startswith("api"):
        raise HTTPException(status_code=404, detail="API route not found")

    react_index = os.path.join(FRONTEND_DIST, "index.html")
    if os.path.exists(react_index):
        specific_file = os.path.join(FRONTEND_DIST, full_path)
        if full_path and os.path.isfile(specific_file):
            return FileResponse(specific_file)
        return FileResponse(react_index)

    static_index = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(static_index):
        return FileResponse(static_index)

    return JSONResponse({
        "message": "DevAgent Enterprise API is online. Frontend not found."
    })


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="127.0.0.1", port=8000, reload=False)
