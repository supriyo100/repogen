import importlib.metadata
packages = [
    "langgraph",
    "langchain_community",
    "langchain_core",
    "tavily-python",
    "wikipedia",
    "langchain-google-genai",
    "langchain-groq",
    "langchain-openai",
    "regex",
    "openpyxl",
    "structlog",
    "pypdf",
    "faiss-cpu",
    "tiktoken",
    "langchain",
    "langchainhub"
       ]
for pkg in packages:
    try:
        version = importlib.metadata.version(pkg)
        print(f"{pkg}=={version}")
    except importlib.metadata.PackageNotFoundError:
        print(f"{pkg} (not installed)")