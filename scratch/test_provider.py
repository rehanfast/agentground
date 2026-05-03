import sys, os
from dotenv import load_dotenv
load_dotenv()
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from backend.app.provider_adapters import make_llm, invoke_llm
from langchain.schema.messages import HumanMessage

api_key = os.getenv("GOOGLE_API_KEY")
llm = make_llm("google", "https://generativelanguage.googleapis.com/v1beta", "google/gemma-4-31b-it", api_key)
res = invoke_llm(llm, [HumanMessage(content="Say 'test working'")])
print("Result:", res)
