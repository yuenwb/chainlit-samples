import os
from pydantic_ai import Agent    # insall pydantic-ai-slim[openai]
from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.providers.openai import OpenAIProvider
import httpx

os.environ["OPENROUTER_API_KEY"] = "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"

model = OpenAIModel(
    'google/gemini-2.0-flash-lite-001',
    provider=OpenAIProvider(
        base_url='https://openrouter.ai/api/v1',
        api_key=os.getenv("OPENROUTER_API_KEY"),
        http_client=httpx.AsyncClient(verify=False)
    ),
)

simple_agent = Agent(
    model=model,
    # 'Be concise, reply with one sentence.' is enough for some models (like openai) to use
    # the below tools appropriately, but others like anthropic and gemini require a bit more direction.
    system_prompt=(
        'Please answer everything in traditional chinese'
    ),
)
result_sync = simple_agent.run_sync('What is the capital of Italy?')
print(result_sync.output)
