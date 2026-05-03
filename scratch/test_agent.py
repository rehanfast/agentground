import os
from dotenv import load_dotenv
load_dotenv()
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_classic.agents import create_tool_calling_agent, AgentExecutor
from langchain_core.tools import tool

@tool
def dummy_tool(x: int) -> int:
    """Dummy tool"""
    return x + 1

llm = ChatGoogleGenerativeAI(
    model="gemini-3-flash-preview",
    google_api_key=os.getenv("GOOGLE_API_KEY"),
    temperature=0.0
)

tools = [dummy_tool]
prompt = ChatPromptTemplate.from_messages([
    SystemMessage(content="You are a helpful assistant."),
    ("human", "{input}"),
    MessagesPlaceholder(variable_name="agent_scratchpad"),
])
lc_agent = create_tool_calling_agent(llm, tools, prompt)
executor = AgentExecutor(agent=lc_agent, tools=tools, handle_parsing_errors=True)

try:
    print(executor.invoke({"input": "Use the dummy tool with 5"}))
except Exception as e:
    print("ERROR:", repr(e))
