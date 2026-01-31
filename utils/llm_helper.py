from langchain_openai import ChatOpenAI
from core.config import Config
from typing import Optional

api_key=Config.OPENAI_API_KEY

# Default model
DEFAULT_MODEL = Config.BASE_MODEL
DEFAULT_TEMP = Config.BASE_TEMPERATURE

def call_llm(temperature: Optional[str] = None,
             model: Optional[str] = None):
    model = model or DEFAULT_MODEL
    llm = ChatOpenAI(model= model, temperature= temperature, api_key= api_key)
    return llm

def call_structured_llm(outputschema,
                       temperature: Optional[str] = None,
                       model: Optional[str] = None):
    model = model or DEFAULT_MODEL
    temperature = temperature or DEFAULT_TEMP
    
    llm = ChatOpenAI(model= model, temperature= temperature, api_key= api_key)
    structured_llm = llm.with_structured_output(schema = outputschema)
    return structured_llm

def call_agent(outputschema,
                        temperature: Optional[str] = None,
                        tools: Optional[str] = None,
                        model: Optional[str] = None):
    
    model = model or DEFAULT_MODEL
    temperature = temperature or DEFAULT_TEMP
    llm = ChatOpenAI(model= model, temperature= temperature, api_key= api_key)
    structured_llm = llm.bind_tools(
        tools,
        response_format=outputschema,
        strict=True,)
    
    return structured_llm

def generate_text_response(prompt: str,
                           outputschema: str,
                           temperature: Optional[str] = None,
                           model: Optional[str] = None):
    model = model or DEFAULT_MODEL
    temperature = temperature or DEFAULT_TEMP
    llm = ChatOpenAI(model= model, temperature= temperature, api_key= api_key)
    structured_llm = llm.with_structured_output(schema = outputschema)
    response = structured_llm.invoke(prompt)
    # text = response.content
    
    return response