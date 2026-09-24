from __future__ import annotations
import copy
import random
import re

import httpx
import numpy as np
import base64
from io import BytesIO
from server import PromptServer
from aiohttp import web
from pprint import pprint
from PIL import Image
from PIL.PngImagePlugin import PngInfo
import os
from typing import TYPE_CHECKING, Any, Literal
from dataclasses import dataclass, field
from pydantic.json_schema import JsonSchemaValue

# For type checking only. Torch is not installed at runtime
if TYPE_CHECKING:
    import torch


@dataclass
class ChatSession:
    messages: list[dict] = field(default_factory=list)
    model: str = ""


# Dictionary global per session_id
CHAT_SESSIONS: dict[str, ChatSession] = {}

# Function to filter enabled options
def _filter_enabled_options(options: dict[str, Any] | None) -> dict[str, Any] | None:
    """Return only the options whose 'enable_*' flag is True."""
    if not options:
        return None
    enablers = [
        "enable_mirostat",
        "enable_mirostat_eta",
        "enable_mirostat_tau",
        "enable_num_ctx",
        "enable_repeat_last_n",
        "enable_repeat_penalty",
        "enable_temperature",
        "enable_seed",
        "enable_stop",
        "enable_tfs_z",
        "enable_num_predict",
        "enable_top_k",
        "enable_top_p",
        "enable_min_p",
    ]
    out: dict[str, Any] = {}
    for enabler in enablers:
        if options.get(enabler, False):
            key = enabler.replace("enable_", "")
            out[key] = options[key]
    return out or None


def _build_headers(api_key: str | None) -> dict[str, str]:
    """Build request headers with optional Bearer token."""
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    return headers


_ENV_VAR_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _resolve_api_key(api_key_env: str) -> str | None:
    """Resolve the API token from an environment variable referenced by name."""
    name = (api_key_env or "").strip()
    if not name:
        return None
    if not _ENV_VAR_NAME_RE.match(name):
        raise Exception(
            f"'{name}' is not a valid environment variable name. The LLM Connectivity node no longer "
            "stores the API token in the workflow, because ComfyUI embeds every widget value into saved "
            "workflows and into the metadata of images produced by the workflow. Set the token in the "
            "ComfyUI server environment (e.g. export COMFYUI_LLAMA_API_KEY=...) and enter the variable "
            "name here. If this field still contains an old token, replace it with the variable name "
            "(or clear it) and rotate any token that was embedded in old workflows or images."
        )
    value = os.environ.get(name, "").strip()
    if not value:
        raise Exception(
            f"Environment variable '{name}' (API token source for the LLM Connectivity node) is not set or is "
            f"empty. Export it in the ComfyUI server environment before starting ComfyUI, e.g. export {name}=<your-token>."
        )
    return value


def _map_options_to_openai(opts: dict[str, Any] | None) -> dict[str, Any]:
    """Map node option names to OpenAI-compatible parameter names."""
    if not opts:
        return {}
    mapping = {
        "temperature": "temperature",
        "top_p": "top_p",
        "top_k": "top_k",
        "seed": "seed",
        "stop": "stop",
        "repeat_penalty": "presence_penalty",
        "num_predict": "max_tokens",
        "min_p": "min_p",
    }
    result = {}
    for key, value in opts.items():
        if key in mapping:
            openai_key = mapping[key]
            result[openai_key] = value
        else:
            # Pass through unknown options (some servers support them)
            result[key] = value
    return result


@PromptServer.instance.routes.post("/llm/get_models")
async def get_models_endpoint(request):
    data = await request.json()

    url = data.get("url", "").rstrip("/")
    api_key_env = data.get("api_key_env", "")
    raw_api_key = data.get("api_key", "")

    try:
        headers = _build_headers(_resolve_api_key(api_key_env) or (raw_api_key or None))
    except Exception as e:
        return web.json_response(
            {"error": str(e)},
            status=400,
        )

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"{url}/v1/models", headers=headers)
            resp.raise_for_status()
            body = resp.json()

        models_list = body.get("data", [])
        models = [m.get("id", "") for m in models_list if m.get("id")]
        return web.json_response(models)
    except Exception as e:
        return web.json_response(
            {"error": str(e)},
            status=500,
        )


class LLMSaveContext:
    def __init__(self):
        self._base_dir = os.path.dirname(os.path.realpath(__file__)) + os.path.sep + "saved_context"

    @classmethod
    def INPUT_TYPES(s):
        return {"required":
                    {"context": ("STRING", {"forceInput": True},),
                     "filename": ("STRING", {"default": "context"})},
                }

    RETURN_TYPES = ()
    FUNCTION = "save_context"

    OUTPUT_NODE = True
    CATEGORY = "LLM"

    def save_context(self, filename, context=None):
        safe_name = os.path.basename(filename)
        if not safe_name:
            raise ValueError("Invalid filename")
        path = self._base_dir + os.path.sep + safe_name
        metadata = PngInfo()

        metadata.add_text("context", ','.join(map(str, context)))

        image = Image.new('RGB', (100, 100), (255, 255, 255))

        image.save(path + ".png", pnginfo=metadata)

        return {"ui": {"context": context}}


class LLMLoadContext:
    def __init__(self):
        self._base_dir = os.path.dirname(os.path.realpath(__file__)) + os.path.sep + "saved_context"

    @classmethod
    def INPUT_TYPES(s):
        input_dir = os.path.dirname(os.path.realpath(__file__)) + os.path.sep + "saved_context"
        files = [f for f in os.listdir(input_dir) if os.path.isfile(os.path.join(input_dir, f)) and f != ".keep"]
        return {"required":
                    {"context_file": (files, {})},
                }

    CATEGORY = "LLM"

    RETURN_NAMES = ("context",)
    RETURN_TYPES = ("STRING",)
    FUNCTION = "load_context"

    def load_context(self, context_file):
        safe_name = os.path.basename(context_file)
        if not safe_name:
            raise ValueError("Invalid filename")
        with Image.open(self._base_dir + os.path.sep + safe_name) as img:
            info = img.info
            res = info.get('context', '')
        return (res,)


class LLMOptionsV2:
    def __init__(self):
        pass

    @classmethod
    def INPUT_TYPES(s):
        seed = random.randint(1, 2 ** 31)
        return {
            "required": {
                "enable_mirostat": ("BOOLEAN", {"default": False}),
                "mirostat": ("INT", {"default": 0, "min": 0, "max":2, "step": 1, "tooltip": "Whether to use Mirostat sampling. (0 = disabled, 1 = Mirostat 1, 2 = Mirostat 2.0)"}),

                "enable_mirostat_eta": ("BOOLEAN", {"default": False}),
                "mirostat_eta": ("FLOAT", {"default": 0.1, "min": 0, "step": 0.1, "tooltip": "Mirostat's learning rate parameter."}),

                "enable_mirostat_tau": ("BOOLEAN", {"default": False}),
                "mirostat_tau": ("FLOAT", {"default": 5.0, "min": 0, "step": 0.1, "tooltip": "Mirostat's target entropy parameter."}),

                "enable_num_ctx": ("BOOLEAN", {"default": False}),
                "num_ctx": ("INT", {"default": 2048, "min": 0, "max": 2 ** 31, "step": 1, "tooltip": "Sets the size of the context window used to generate the next token."}),

                "enable_repeat_last_n": ("BOOLEAN", {"default": False}),
                "repeat_last_n": ("INT", {"default": 64, "min": -1, "max": 64, "step": 1, "tooltip": "Sets how far back for the model to look back to prevent repetition."}),

                "enable_repeat_penalty": ("BOOLEAN", {"default": False}),
                "repeat_penalty": ("FLOAT", {"default": 1.1, "min": 0, "max": 2, "step": 0.05, "tooltip": "Sets how strongly to penalize repetitions."}),

                "enable_temperature": ("BOOLEAN", {"default": False}),
                "temperature": ("FLOAT", {"default": 0.8, "min": -10, "max": 10, "step": 0.05, "tooltip": "Increasing the temperature will make the model answer more creatively."}),

                "enable_seed": ("BOOLEAN", {"default": False}),
                "seed": ("INT", {"default": seed, "min": 0, "max": 2 ** 31, "step": 1, "tooltip": "Sets the random number seed for generation."}),

                "enable_stop": ("BOOLEAN", {"default": False}),
                "stop": ("STRING", {"default": "", "multiline": False, "tooltip": "When this pattern is encountered the model will stop generating text and return."}),

                "enable_tfs_z": ("BOOLEAN", {"default": False}),
                "tfs_z": ("FLOAT", {"default": 1, "min": 1, "max": 1000, "step": 0.05}),

                "enable_num_predict": ("BOOLEAN", {"default": False}),
                "num_predict": ("INT", {"default": -1, "min": -2, "max": 2048, "step": 1, "tooltip": "Maximum number of tokens to predict when generating text."}),

                "enable_top_k": ("BOOLEAN", {"default": False}),
                "top_k": ("INT", {"default": 40, "min": 0, "max": 100, "step": 1, "tooltip": "Reduces the probability of generating nonsense."}),

                "enable_top_p": ("BOOLEAN", {"default": False}),
                "top_p": ("FLOAT", {"default": 0.9, "min": 0, "max": 1, "step": 0.05, "tooltip": "Works together with top-k for diverse text."}),

                "enable_min_p": ("BOOLEAN", {"default": False}),
                "min_p": ("FLOAT", {"default": 0.0, "min": 0, "max": 1, "step": 0.05, "tooltip": "Minimum probability for a token relative to the most likely token."}),

                "debug": ("BOOLEAN", {"default": False, "tooltip": "For debugging purposes of the custom nodes."}),
            },
        }

    RETURN_TYPES = ("LLM_OPTIONS",)
    RETURN_NAMES = ("options",)
    FUNCTION = "llm_options"
    CATEGORY = "LLM"
    DESCRIPTION = "Various settings for advanced configuration of inference. Parameters are mapped to OpenAI-compatible API."

    def llm_options(self, **kargs):

        if kargs['debug']:
            print("--- LLM options v2 dump\n")
            pprint(kargs)
            print("---------------------------------------------------------")

        return (kargs,)


class LLMConnectivityV2:
    def __init__(self):
        pass

    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "url": ("STRING", {
                    "multiline": False,
                    "default": "http://127.0.0.1:11434",
                    "tooltip": "The URL of the OpenAI-compatible API server (e.g., http://localhost:11434 for Ollama /v1 proxy)."
                }),
                "api_key_env": ("STRING", {
                    "default": "",
                    "multiline": False,
                    "tooltip": "Name of the environment variable holding the API token (e.g. COMFYUI_LLAMA_API_KEY), exported in the ComfyUI server environment. The token itself is never stored in the workflow or in saved image metadata. Leave empty if no authentication is required."
                }),
                "model": ((), {"tooltip": "Select a model for inference from the available models on the server."}),
                "keep_alive": ("INT", {"default": 5, "min": -1, "max": 120, "step": 1, "tooltip": "Configures how long the server keeps the model loaded in memory. -1 = indefinitely, 0 = unload immediately"}),
                "keep_alive_unit": (["minutes", "hours"],),
            },
        }

    RETURN_TYPES = ("LLM_CONNECTIVITY",)
    RETURN_NAMES = ("connection",)
    FUNCTION = "llm_connectivity"
    CATEGORY = "LLM"
    DESCRIPTION = "Provides connection to an OpenAI-compatible API server. The API token is read from a server environment variable (see api_key_env), so it never appears in the workflow or in saved image metadata. Use the refresh button to load the model list."

    def llm_connectivity(self, url, api_key_env, model, keep_alive, keep_alive_unit):
        data = {
            "url": url.rstrip("/"),
            "api_key": _resolve_api_key(api_key_env) or "",
            "model": model,
            "keep_alive": keep_alive,
            "keep_alive_unit": keep_alive_unit,
        }

        return (data,)


class LLMGenerateV2:
    def __init__(self):
        self.saved_context = None

    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "system": ("STRING", {
                    "multiline": True,
                    "default": "You are an AI artist.",
                    "tooltip": "System prompt - use this to set the role and general behavior of the model."
                }),
                "prompt": ("STRING", {
                    "multiline": True,
                    "default": "What is art?",
                    "tooltip": "User prompt - a question or task you want the model to answer or perform."
                }),
                "think": ("BOOLEAN", {"default": False, "tooltip": "If enabled, the model will do a thinking process before answering. Some models don't support this feature and the generation will fail."}),
                "keep_context": ("BOOLEAN", {"default": False, "tooltip": "If enabled, the model will keep the context of the conversation for the next generation."}),
                "format": (["text", "json"], {"tooltip": "Output format. 'json' returns structured JSON response."}),

            },
            "optional": {
                "connectivity": ("LLM_CONNECTIVITY", {"forceInput": False, "tooltip": "Set a server connection for the generation."},),
                "options": ("LLM_OPTIONS", {"forceInput": False, "tooltip": "Connect an Options node for advanced inference configuration."},),
                "images": ("IMAGE", {"forceInput": False, "tooltip": "Provide images for vision tasks. Make sure the selected model supports vision."},),
                "context": ("LLM_CONTEXT", {"forceInput": False, "tooltip": "Optionally set an existing context for multi-turn conversations."},),
                "meta": ("LLM_META", {"forceInput": False, "tooltip": "Chain multiple Generate nodes. Connectivity and options are passed along."},),
            }
        }

    RETURN_TYPES = ("STRING", "STRING", "LLM_CONTEXT", "LLM_META",)
    RETURN_NAMES = ("result", "thinking", "context", "meta",)
    FUNCTION = "llm_generate_v2"
    CATEGORY = "LLM"
    DESCRIPTION = "Text generation via OpenAI-compatible API. Supports vision, multi-turn conversations, and advanced options."

    def llm_generate_v2(self, system, prompt, think, keep_context, format, context=None, options=None, connectivity=None, images=None, meta=None):

        if connectivity is None and meta is None:
            raise Exception("Required input connectivity or meta.")

        if connectivity is None and meta.get('connectivity') is None:
            raise Exception("Required input connectivity or connectivity in meta.")

        if meta is not None:
            if connectivity is not None:
                meta["connectivity"] = connectivity
            if options is not None:
                meta["options"] = options
        else:
            meta = {"options": options, "connectivity": connectivity}

        url = meta['connectivity']['url']
        api_key = meta['connectivity'].get('api_key', '')
        model = meta['connectivity']['model']

        debug_print = True if meta['options'] is not None and meta['options']['debug'] else False

        response_format = format if format == "json" else None

        if context is not None and isinstance(context, str):
            string_list = context.split(',')
            context = [int(item.strip()) for item in string_list]

        if keep_context and context is None:
            context = self.saved_context

        request_options = _filter_enabled_options(options)
        openai_params = _map_options_to_openai(request_options)

        images_b64 = None
        if images is not None:
            images_b64 = []
            for (batch_number, image) in enumerate(images):
                i = 255. * image.cpu().numpy()
                img = Image.fromarray(np.clip(i, 0, 255).astype(np.uint8))
                buffered = BytesIO()
                img.save(buffered, format="PNG")
                img_bytes = base64.b64encode(buffered.getvalue())
                images_b64.append(str(img_bytes, 'utf-8'))

        # Build messages array for /v1/chat/completions
        messages = []
        if system:
            messages.append({"role": "system", "content": system})

        user_content: list[dict] | str
        if images_b64 is not None and len(images_b64) > 0:
            user_content = [{"type": "text", "text": prompt}]
            for img_b64 in images_b64:
                user_content.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{img_b64}"}
                })
        else:
            user_content = prompt

        messages.append({"role": "user", "content": user_content})

        body = {
            "model": model,
            "messages": messages,
            **openai_params,
        }

        if response_format:
            body["response_format"] = {"type": response_format}

        if debug_print:
            print(f"""
--- LLM generate v2 request (OpenAI /v1/chat/completions): 

url: {url}/v1/chat/completions
model: {model}
system: {system[:50]}...
prompt: {prompt[:50]}...
images: {0 if images_b64 is None else len(images_b64)}
options: {openai_params}
format: {response_format}
---------------------------------------------------------
""")

        headers = _build_headers(api_key if api_key else None)

        try:
            with httpx.Client(timeout=120) as client:
                resp = client.post(f"{url}/v1/chat/completions", headers=headers, json=body)
                resp.raise_for_status()
                response = resp.json()
        except Exception as e:
            raise Exception(f"API request failed: {e}")

        if debug_print:
            print("\n--- LLM generate v2 response:")
            pprint(response)
            print("---------------------------------------------------------")

        choice = response["choices"][0]
        message = choice.get("message", {})
        result_text = message.get("content", "")

        # Extract thinking tags from content if present (some models include them inline)
        thinking_text = None
        if think and result_text:
            match = re.search(r"<(?:think|thinking)>(.*?)</(?:think|thinking)>", result_text, re.DOTALL)
            if match:
                thinking_text = match.group(1).strip()

        # Use finish_reason or empty list as context proxy
        ctx_value = choice.get("finish_reason", "stop")

        if keep_context:
            self.saved_context = ctx_value
            if debug_print:
                print("saving context to node memory.")

        return result_text, thinking_text, str(ctx_value), meta


class LLMChat:
    """
    Text generation via OpenAI-compatible /v1/chat/completions.
    Returns: (result: str, thinking: str|None, meta: dict, history: str)
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "system": (
                    "STRING",
                    {
                        "multiline": True,
                        "default": "You are an AI artist.",
                        "tooltip": "System prompt - use this to set the role and general behavior of the model.",
                    },
                ),
                "prompt": (
                    "STRING",
                    {
                        "multiline": True,
                        "default": "What is art?",
                        "tooltip": "User prompt for the model to answer or perform. For vision tasks, refer to 'this image' etc.",
                    },
                ),
                "think": (
                    "BOOLEAN",
                    {
                        "default": False,
                        "tooltip": "If enabled, the model will do a thinking process before answering.",
                    },
                ),
                "format": (
                    ["text", "json"],
                    {
                        "tooltip": "Output format. 'json' returns structured JSON response."
                    },
                ),
            },
            "optional": {
                "connectivity": (
                    "LLM_CONNECTIVITY",
                    {
                        "forceInput": False,
                        "tooltip": "Set a server connection for the generation.",
                    },
                ),
                "options": (
                    "LLM_OPTIONS",
                    {
                        "forceInput": False,
                        "tooltip": "Connect an Options node for advanced inference configuration.",
                    },
                ),
                "images": (
                    "IMAGE",
                    {
                        "forceInput": False,
                        "tooltip": "Provide images for vision tasks. Make sure the model supports vision.",
                    },
                ),
                "meta": (
                    "LLM_META",
                    {
                        "forceInput": False,
                        "tooltip": "Chain multiple Generate nodes. Connectivity and options are passed along.",
                    },
                ),
                "history": (
                    "LLM_HISTORY",
                    {
                        "forceInput": False,
                        "tooltip": "Optionally set existing history for multi-turn conversations.",
                    },
                ),
                "reset_session": (
                    "BOOLEAN",
                    {
                        "default": False,
                        "tooltip": "Clear the conversation history.",
                    },
                ),
            },
            "hidden": {"unique_id": "UNIQUE_ID"},
        }

    RETURN_TYPES = (
        "STRING",
        "STRING",
        "LLM_META",
        "LLM_HISTORY",
    )
    RETURN_NAMES = (
        "result",
        "thinking",
        "meta",
        "history",
    )
    FUNCTION = "llm_chat"
    CATEGORY = "LLM"
    DESCRIPTION = "Text generation via OpenAI-compatible /v1/chat/completions. Supports vision, multi-turn conversations, and advanced options."

    def llm_chat(
        self,
        system: str,
        prompt: str,
        think: bool,
        unique_id: str,
        format: str,
        options: dict[str, Any] | None = None,
        connectivity: dict[str, Any] | None = None,
        images: list[torch.Tensor] | None = None,
        meta: dict[str, Any] | None = None,
        history: str | None = None,
        reset_session: bool = False,
    ) -> tuple[str | None, str | None, dict[str, Any], str | None]:

        if meta is None:
            if connectivity is None:
                raise ValueError("Either 'connectivity' or 'meta' must be provided.")
            meta = {}

        # Update with provided values (override)
        if connectivity is not None:
            meta["connectivity"] = connectivity
        if options is not None:
            meta["options"] = options
        else:
            meta["options"] = None

        # Final validation
        if "connectivity" not in meta or meta["connectivity"] is None:
            raise ValueError("'connectivity' must be present in meta.")

        url = meta["connectivity"]["url"]
        api_key = meta["connectivity"].get("api_key", "")
        model = meta["connectivity"]["model"]

        debug_print = (
            True if meta["options"] is not None and meta["options"]["debug"] else False
        )

        response_format = "json" if format == "json" else None

        # Build OpenAI-compatible params from options
        request_options = _filter_enabled_options(options)
        openai_params = _map_options_to_openai(request_options)

        images_b64: list[str] | None = None
        if images is not None:
            images_b64 = []
            for batch_number, image in enumerate(images):
                i = 255.0 * image.cpu().numpy()
                img = Image.fromarray(np.clip(i, 0, 255).astype(np.uint8))
                buffered = BytesIO()
                img.save(buffered, format="PNG")
                img_bytes = base64.b64encode(buffered.getvalue()).decode("utf-8")
                images_b64.append(img_bytes)

        if debug_print:
            print(
                f"""
--- LLM chat request (OpenAI /v1/chat/completions): 

url: {url}/v1/chat/completions
model: {model}
system: {system[:50]}...
prompt: {prompt[:50]}...
images: {0 if images_b64 is None else len(images_b64)}
think: {think}
options: {openai_params}
format: {response_format}
---------------------------------------------------------
"""
            )

        # Determine which session to use
        session_key = history if history is not None else unique_id

        # If reset_session is True, reset the session
        if reset_session:
            CHAT_SESSIONS[session_key] = ChatSession()
            if debug_print:
                print(f"Session {session_key} has been reset")

        # If the session doesn't exist, create it
        if session_key not in CHAT_SESSIONS:
            CHAT_SESSIONS[session_key] = ChatSession()

        session = CHAT_SESSIONS[session_key]

        # Update history for return
        history = session_key

        # If there is a system prompt, replace it or add it to the beginning
        if system:
            if session.messages and session.messages[0].get("role") == "system":
                session.messages[0] = {"role": "system", "content": system}
            else:
                session.messages.insert(0, {"role": "system", "content": system})

        # Construct the user message for history (without images)
        user_message_for_history: dict[str, Any] = {
            "role": "user",
            "content": prompt,
        }

        # Add the user message to the history
        session.messages.append(user_message_for_history)

        if debug_print:
            print("\n--- LLM chat session:")
            for message in session.messages:
                pprint(f"{message['role']}> {str(message['content'])[:50]}...")
            print("---------------------------------------------------------")

        # Build the user message with images for API call (deep copy last message)
        messages_for_api = copy.deepcopy(session.messages)

        # If there are images, modify the last user message to include them
        if images_b64 is not None and len(images_b64) > 0:
            last_msg = messages_for_api[-1]
            content_parts: list[dict] = [{"type": "text", "text": last_msg.get("content", prompt)}]
            for img_b64 in images_b64:
                content_parts.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{img_b64}"}
                })
            last_msg["content"] = content_parts

        body = {
            "model": model,
            "messages": messages_for_api,
            **openai_params,
        }

        if response_format:
            body["response_format"] = {"type": response_format}

        headers = _build_headers(api_key if api_key else None)

        try:
            with httpx.Client(timeout=120) as client:
                resp = client.post(f"{url}/v1/chat/completions", headers=headers, json=body)
                resp.raise_for_status()
                response = resp.json()
        except Exception as e:
            raise ValueError(f"API request failed: {e}")

        if debug_print:
            print("\n--- LLM chat response:")
            pprint(response)
            print("---------------------------------------------------------")

        choice = response["choices"][0]
        message = choice.get("message", {})
        result_text = message.get("content", "")

        # Extract thinking tags from content if present
        thinking_text = None
        if think and result_text:
            match = re.search(r"<(?:think|thinking)>(.*?)</(?:think|thinking)>", result_text, re.DOTALL)
            if match:
                thinking_text = match.group(1).strip()

        # Add the assistant message to the history (without images)
        session.messages.append(
            {
                "role": "assistant",
                "content": result_text,
            }
        )

        return (
            result_text,
            thinking_text,
            meta,
            history,
        )


NODE_CLASS_MAPPINGS = {
    "LLMOptionsV2": LLMOptionsV2,
    "LLMConnectivityV2": LLMConnectivityV2,
    "LLMGenerateV2": LLMGenerateV2,
    "LLMSaveContext": LLMSaveContext,
    "LLMLoadContext": LLMLoadContext,
    "LLMChat": LLMChat,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "LLMOptionsV2": "LLM Options",
    "LLMConnectivityV2": "LLM Connectivity",
    "LLMGenerateV2": "LLM Generate",
    "LLMSaveContext": "LLM Save Context",
    "LLMLoadContext": "LLM Load Context",
    "LLMChat": "LLM Chat",
}
