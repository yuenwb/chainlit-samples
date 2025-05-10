from pydantic_ai import Agent    # insall pydantic-ai-slim[openai]
from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.providers.openai import OpenAIProvider
import os
import httpx
import chainlit as cl

os.environ["OPENROUTER_API_KEY"] = "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"

# Setup the model using pydantic_ai with OpenRouter
model = OpenAIModel(
    "google/gemini-2.0-flash-lite-001",
    # "openai/gpt-3.5-turbo",
    provider=OpenAIProvider(
        base_url="https://openrouter.ai/api/v1",
        api_key=os.getenv("OPENROUTER_API_KEY"),
        http_client=httpx.AsyncClient(verify=False),
    )
)

# Add default parameters like temperature inside the Agent
agent = Agent(
    model=model,
    system_prompt="You are a helpful bot, you always reply in Traditional Chinese",
    default_params={
        "temperature": 0,
        "stream": True,
        "tools": []  # Prevents validation error
    }
    
)

# Below code could straming
@cl.on_message
async def on_message(message: cl.Message):
    msg = cl.Message(content="")
    await msg.send()

    async with agent.iter(message.content) as run:
        async for node in run:
            if agent.is_model_request_node(node):
                async with node.stream(run.ctx) as stream:
                    async for event in stream:
                        if hasattr(event, 'delta') and hasattr(event.delta, 'content_delta'):
                            msg.content += event.delta.content_delta
                            await msg.update()

"""
# Below code is not straming
@cl.on_message
async def on_message(message: cl.Message):
    response = await agent.run(message.content)
    await cl.Message(content=response.output).send()
"""