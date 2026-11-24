"""Small content-addressed cache for repeatable offline evaluation runs."""
import hashlib
import json
import os
from pathlib import Path

from common import DATA

CACHE_DIR = Path(os.getenv("LSF_EVAL_CACHE_DIR", DATA / "llm_cache"))


def cached_call_structured_llm(outputschema, temperature=None, model=None):
    """Drop-in wrapper matching utils.llm_helper.call_structured_llm."""
    from utils.llm_helper import call_structured_llm as real_call
    llm = real_call(outputschema=outputschema, temperature=temperature, model=model)

    class CachedRunnable:
        def invoke(self, prompt):
            prompt_text = prompt if isinstance(prompt, str) else json.dumps(prompt, sort_keys=True, default=str)
            key_data = {"schema": outputschema.__name__, "temperature": temperature,
                        "model": model, "prompt": prompt_text}
            key = hashlib.sha256(json.dumps(key_data, sort_keys=True).encode("utf-8")).hexdigest()
            path = CACHE_DIR / f"{key}.json"
            if path.exists():
                return outputschema.model_validate(json.loads(path.read_text(encoding="utf-8")))
            result = llm.invoke(prompt)
            value = result.model_dump() if hasattr(result, "model_dump") else result
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(value, ensure_ascii=False, default=str), encoding="utf-8")
            return result

    return CachedRunnable()
