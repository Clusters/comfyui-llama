import random
import re
import base64

import httpx
import numpy as np
from io import BytesIO
from pprint import pprint
from PIL import Image


# Collection of deprecated V1 nodes updated for OpenAI-compatible API.

def _build_headers(api_key: str | None) -> dict[str, str]:
    """Build request headers with optional Bearer token."""
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    return headers


class LLMVisionDeprecated:
    DEPRECATED = True
    def __init__(self):
        pass

    @classmethod
    def INPUT_TYPES(s):
        seed = random.randint(1, 2 ** 31)
        return {
            "required": {
                "images": ("IMAGE",),
                "query": ("STRING", {
                    "multiline": True,
                    "default": "describe the image"
                }),
                "debug": (["enable", "disable"],),
                "url": ("STRING", {
                    "multiline": False,
                    "default": "http://127.0.0.1:11434"
                }),
                "api_key": ("STRING", {
                    "default": "",
                    "multiline": False,
                    "tooltip": "API token for authentication. Leave empty if not required."
                }),
                "model": ((), {}),
                "keep_alive": ("INT", {"default": 5, "min": -1, "max": 60, "step": 1}),
                "format": (["text", "json", ''],),
                "seed": ("INT", {"default": seed, "min": 0, "max": 2 ** 31, "step": 1}),
            },
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("description",)
    FUNCTION = "llm_vision"
    CATEGORY = "LLM (deprecated)"

    def llm_vision(self, images, query, debug, url, api_key, model, seed, keep_alive, format):
        images_b64 = []

        for (batch_number, image) in enumerate(images):
            i = 255. * image.cpu().numpy()
            img = Image.fromarray(np.clip(i, 0, 255).astype(np.uint8))
            buffered = BytesIO()
            img.save(buffered, format="PNG")
            img_bytes = base64.b64encode(buffered.getvalue()).decode("utf-8")
            images_b64.append(img_bytes)

        response_format = format if format == "json" else None

        # Build messages with images for vision
        content_parts = [{"type": "text", "text": query}]
        for img_b64 in images_b64:
            content_parts.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{img_b64}"}
            })

        body = {
            "model": model,
            "messages": [{"role": "user", "content": content_parts}],
            "seed": seed,
        }

        if response_format:
            body["response_format"] = {"type": response_format}

        headers = _build_headers(api_key if api_key else None)

        url_base = url.rstrip("/")

        if debug == "enable":
            print(f"""[LLM Vision]
request query params:

- query: {query}
- url: {url_base}/v1/chat/completions
- model: {model}
- seed: {seed}
- format: {response_format}

""")

        try:
            with httpx.Client(timeout=120) as client:
                resp = client.post(f"{url_base}/v1/chat/completions", headers=headers, json=body)
                resp.raise_for_status()
                response = resp.json()
        except Exception as e:
            raise Exception(f"API request failed: {e}")

        if debug == "enable":
            print("[LLM Vision]\nResponse:\n")
            pprint(response)

        result_text = response["choices"][0]["message"]["content"]
        return (result_text,)


class LLMGenerateDeprecated:
    DEPRECATED = True
    def __init__(self):
        pass

    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "prompt": ("STRING", {
                    "multiline": True,
                    "default": "What is Art?"
                }),
                "debug": (["enable", "disable"],),
                "url": ("STRING", {
                    "multiline": False,
                    "default": "http://127.0.0.1:11434"
                }),
                "api_key": ("STRING", {
                    "default": "",
                    "multiline": False,
                    "tooltip": "API token for authentication. Leave empty if not required."
                }),
                "model": ((), {}),
                "keep_alive": ("INT", {"default": 5, "min": -1, "max": 60, "step": 1}),
                "format": (["text", "json", ''],),
                "filter_thinking": ("BOOLEAN", {"default": True}),
            },
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("response",)
    FUNCTION = "llm_generate"
    CATEGORY = "LLM (deprecated)"

    def llm_generate(self, prompt, debug, url, api_key, model, keep_alive, format, filter_thinking):

        response_format = format if format == "json" else None

        body = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
        }

        if response_format:
            body["response_format"] = {"type": response_format}

        headers = _build_headers(api_key if api_key else None)
        url_base = url.rstrip("/")

        if debug == "enable":
            print(f"""[LLM Generate]
request query params:

- prompt: {prompt}
- url: {url_base}/v1/chat/completions
- model: {model}

            """)

        try:
            with httpx.Client(timeout=120) as client:
                resp = client.post(f"{url_base}/v1/chat/completions", headers=headers, json=body)
                resp.raise_for_status()
                response = resp.json()
        except Exception as e:
            raise Exception(f"API request failed: {e}")

        if debug == "enable":
            print("[LLM Generate]\nResponse:\n")
            pprint(response)

        result_text = response["choices"][0]["message"]["content"]

        if filter_thinking:
            result_text = re.sub(r"<(?:think|thinking)>.*?</(?:think|thinking)>\s*", "", result_text, flags=re.DOTALL | re.IGNORECASE).strip()

        return (result_text,)


class LLMGenerateAdvanceDeprecated:
    DEPRECATED = True
    saved_context = None

    def __init__(self):
        pass

    @classmethod
    def INPUT_TYPES(s):
        seed = random.randint(1, 2 ** 31)
        return {
            "required": {
                "prompt": ("STRING", {
                    "multiline": True,
                    "default": "What is Art?"
                }),
                "debug": ("BOOLEAN", {"default": False}),
                "url": ("STRING", {
                    "multiline": False,
                    "default": "http://127.0.0.1:11434"
                }),
                "api_key": ("STRING", {
                    "default": "",
                    "multiline": False,
                    "tooltip": "API token for authentication. Leave empty if not required."
                }),
                "model": ((), {}),
                "system": ("STRING", {
                    "multiline": True,
                    "default": "You are an art expert, gracefully describing your knowledge in art domain.",
                    "title": "system"
                }),
                "seed": ("INT", {"default": seed, "min": 0, "max": 2 ** 31, "step": 1}),
                "top_k": ("INT", {"default": 40, "min": 0, "max": 100, "step": 1}),
                "top_p": ("FLOAT", {"default": 0.9, "min": 0, "max": 1, "step": 0.05}),
                "temperature": ("FLOAT", {"default": 0.8, "min": 0, "max": 1, "step": 0.05}),
                "num_predict": ("INT", {"default": -1, "min": -2, "max": 2048, "step": 1}),
                "tfs_z": ("FLOAT", {"default": 1, "min": 1, "max": 1000, "step": 0.05}),
                "keep_alive": ("INT", {"default": 5, "min": -1, "max": 60, "step": 1}),
                "keep_context": ("BOOLEAN", {"default": False}),
                "format": (["text", "json", ''],),
                "filter_thinking": ("BOOLEAN", {"default": True}),
            }, "optional": {
                "context": ("STRING", {"forceInput": True}),
            }
        }

    RETURN_TYPES = ("STRING", "STRING",)
    RETURN_NAMES = ("response", "context",)
    FUNCTION = "llm_generate_advance"
    CATEGORY = "LLM (deprecated)"

    def llm_generate_advance(self, prompt, debug, url, api_key, model, system, seed, top_k, top_p, temperature, num_predict,
                                tfs_z, keep_alive, keep_context, format, filter_thinking, context=None):

        response_format = format if format == "json" else None

        # Build messages array
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        body = {
            "model": model,
            "messages": messages,
            "seed": seed,
            "top_k": top_k,
            "top_p": top_p,
            "temperature": temperature,
            "max_tokens": num_predict if num_predict > 0 else None,
        }

        # Clean up None values
        body = {k: v for k, v in body.items() if v is not None}

        if response_format:
            body["response_format"] = {"type": response_format}

        headers = _build_headers(api_key if api_key else None)
        url_base = url.rstrip("/")

        if debug:
            print(f"""[LLM Generate Advance]
request query params:

- prompt: {prompt}
- url: {url_base}/v1/chat/completions
- model: {model}
- body: {body}
""")

        try:
            with httpx.Client(timeout=120) as client:
                resp = client.post(f"{url_base}/v1/chat/completions", headers=headers, json=body)
                resp.raise_for_status()
                response = resp.json()
        except Exception as e:
            raise Exception(f"API request failed: {e}")

        if debug:
            print("[LLM Generate Advance]\nResponse:\n")
            pprint(response)

        result_text = response["choices"][0]["message"]["content"]
        ctx_value = response["choices"][0].get("finish_reason", "stop")

        if keep_context:
            self.saved_context = str(ctx_value)

        if filter_thinking:
            result_text = re.sub(r"<(?:think|thinking)>.*?</(?:think|thinking)>\s*", "", result_text, flags=re.DOTALL | re.IGNORECASE).strip()

        return (result_text, str(ctx_value),)


NODE_CLASS_MAPPINGS = {
    "LLMVisionDeprecated": LLMVisionDeprecated,
    "LLMGenerateDeprecated": LLMGenerateDeprecated,
    "LLMGenerateAdvanceDeprecated": LLMGenerateAdvanceDeprecated,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "LLMVisionDeprecated": "LLM Vision (deprecated)",
    "LLMGenerateDeprecated": "LLM Generate (deprecated)",
    "LLMGenerateAdvanceDeprecated": "LLM Generate Advance (deprecated)",
}
