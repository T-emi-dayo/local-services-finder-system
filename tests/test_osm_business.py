from utils.llm_helper import generate_text_response
from src.models.FinalResponse import FinalResponse

result = generate_text_response(prompt="Who is the best striker at Barcelona",
                                outputschema= FinalResponse)
print(result)