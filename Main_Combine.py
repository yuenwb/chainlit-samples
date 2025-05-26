# from __future__ import annotations as _annotations

import asyncio
import os
import httpx
from dataclasses import dataclass
from typing import Any


from pydantic_ai import Agent, ModelRetry, RunContext    # insall pydantic-ai-slim[openai]
from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.providers.openai import OpenAIProvider
import chainlit as cl

os.environ["OPENROUTER_API_KEY"] = "xxxx"       # For OpenRouter model access
os.environ["WEATHER_API_KEY"] = "yyyy"           # For Tomorrow.io weather API
os.environ["GEO_API_KEY"] = "zzzzz"               # For geolocation (maps.co)

# Setup the model using pydantic_ai with OpenRouter
model = OpenAIModel(
    "google/gemini-2.0-flash-lite-001",
    # "openai/gpt-3.5-turbo",
    provider=OpenAIProvider(
        base_url="https://openrouter.ai/api/v1",
        api_key=os.getenv("OPENROUTER_API_KEY"),
        http_client=httpx.AsyncClient(verify=False)
    )
)

# ChatBot AI Agent
chat_agent = Agent(
    model=model,
    system_prompt="You are a helpful bot, you always reply in Traditional Chinese",
    default_params={
        "temperature": 0,
        "stream": True,
        "tools": []  # Prevents validation error
    }
    
)

# Weather AI Agent Deps and Tools
@dataclass
class Deps:
    client: httpx.AsyncClient
    weather_api_key: str | None
    geo_api_key: str | None

weather_agent = Agent(
    model=model,
    # 'Be concise, reply with one sentence.' is enough for some models (like openai) to use
    # the below tools appropriately, but others like anthropic and gemini require a bit more direction.
    system_prompt=(
        'Be concise, reply with one sentence.'
        'Use the `get_lat_lng` tool to get the latitude and longitude of the locations, '
        'then use the `get_weather` tool to get the weather.'
    ),
    deps_type=Deps,
    retries=2,
    instrument=True,
    default_params={
        "temperature": 0,
        "tools": ["get_lat_lng", "get_weather"]  # 🛠 list your tools explicitly
    }
    
)

@weather_agent.tool
async def get_lat_lng(
    ctx: RunContext[Deps], location_description: str
) -> dict[str, float]:
    """Get the latitude and longitude of a location.

    Args:
        ctx: The context.
        location_description: A description of a location.
    """
    if ctx.deps.geo_api_key is None:
        # if no API key is provided, return a dummy response (London)
        return {'lat': 51.1, 'lng': -0.1}

    params = {
        'q': location_description,
        'api_key': ctx.deps.geo_api_key,
    }
    #with logfire.span('calling geocode API', params=params) as span:
    r = await ctx.deps.client.get('https://geocode.maps.co/search', params=params)
    r.raise_for_status()
    data = r.json()
    # span.set_attribute('response', data)

    if data:
        return {'lat': data[0]['lat'], 'lng': data[0]['lon']}
    else:
        raise ModelRetry('Could not find the location')

@weather_agent.tool
async def get_weather(ctx: RunContext[Deps], lat: float, lng: float) -> dict[str, Any]:
    """Get the weather at a location.

    Args:
        ctx: The context.
        lat: Latitude of the location.
        lng: Longitude of the location.
    """
    if ctx.deps.weather_api_key is None:
        # if no API key is provided, return a dummy response
        return {'temperature': '21 °C', 'description': 'Sunny'}

    params = {
        'apikey': ctx.deps.weather_api_key,
        'location': f'{lat},{lng}',
        'units': 'metric',
    }
    #with logfire.span('calling weather API', params=params) as span:
    r = await ctx.deps.client.get(
        'https://api.tomorrow.io/v4/weather/realtime', params=params
    )
    r.raise_for_status()
    data = r.json()
    # span.set_attribute('response', data)

    values = data['data']['values']
    # https://docs.tomorrow.io/reference/data-layers-weather-codes
    code_lookup = {
        1000: 'Clear, Sunny',
        1100: 'Mostly Clear',
        1101: 'Partly Cloudy',
        1102: 'Mostly Cloudy',
        1001: 'Cloudy',
        2000: 'Fog',
        2100: 'Light Fog',
        4000: 'Drizzle',
        4001: 'Rain',
        4200: 'Light Rain',
        4201: 'Heavy Rain',
        5000: 'Snow',
        5001: 'Flurries',
        5100: 'Light Snow',
        5101: 'Heavy Snow',
        6000: 'Freezing Drizzle',
        6001: 'Freezing Rain',
        6200: 'Light Freezing Rain',
        6201: 'Heavy Freezing Rain',
        7000: 'Ice Pellets',
        7101: 'Heavy Ice Pellets',
        7102: 'Light Ice Pellets',
        8000: 'Thunderstorm',
    }
    return {
        'temperature': f'{values["temperatureApparent"]:0.0f}°C',
        'description': code_lookup.get(values['weatherCode'], 'Unknown'),
    }


# detech intention
async def detect_intent_with_llm(user_input: str) -> str:
    classification_prompt = (
        "請你判斷以下使用者的輸入是否是與天氣有關的問題，"
        "如果是請只回傳 `weather`，否則請只回傳 `chat`，不要回傳其他內容。\n\n"
        f"使用者輸入：{user_input}"
    )

    result = await chat_agent.run(classification_prompt)
    return result.output.strip().lower()

# Below code could straming
@cl.on_message
async def on_message(message: cl.Message):
    msg = cl.Message(content="")
    await msg.send()

    agent_type = await detect_intent_with_llm(message.content)

    if agent_type == "chat":
        async with chat_agent.iter(message.content) as run:
            async for node in run:
                if chat_agent.is_model_request_node(node):
                    async with node.stream(run.ctx) as stream:
                        async for event in stream:
                            if hasattr(event, 'delta') and hasattr(event.delta, 'content_delta'):
                                msg.content += event.delta.content_delta
                                await msg.update()
    elif agent_type == "weather":
        async with httpx.AsyncClient(verify=False) as client:
            deps = Deps(
                client=client,
                weather_api_key=os.getenv("WEATHER_API_KEY"),
                geo_api_key=os.getenv("GEO_API_KEY"),
            )
            result = await weather_agent.run(message.content, deps=deps)
            msg.content = result.output
            await msg.update()
    else:
        # msg.content = "⚠️ 抱歉，我無法判斷你的問題屬於哪一類，請再試一次。"
        msg.content = "⚠️ Sorry, I can't determine which category your question belongs to. Please try again."
        await msg.update()
