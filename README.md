# ComfyUI LLM

Custom [ComfyUI](https://github.com/comfyanonymous/ComfyUI) Nodes for interacting with any **OpenAI-compatible API** server (`/v1/...` endpoints).

Integrate the power of LLMs into ComfyUI workflows easily — text generation, vision tasks, multi-turn conversations, and structured output.

> Originally created by [Stav Sapir](https://github.com/stavsap) as [comfyui-ollama](https://github.com/stavsap/comfyui-ollama). This fork migrates to OpenAI-compatible API endpoints with broader server support.

<a href="https://www.buymeacoffee.com/stavsapq" target="_blank"><img src="https://cdn.buymeacoffee.com/buttons/default-orange.png" alt="Buy Me A Coffee" height="40" width="174"></a>

![pic](.meta/basic-example.jpg)

## Supported Servers

Any server that exposes an OpenAI-compatible `/v1/...` API:

| Server | Base URL Example | Notes |
|--------|-----------------|-------|
| **Ollama** (built-in /v1 proxy) | `http://127.0.0.1:11434` | No API key needed by default |
| **LM Studio** | `http://127.0.0.1:1234` | Local inference |
| **vLLM** | `http://127.0.0.1:8000` | High-throughput serving |
| **OpenAI** | `https://api.openai.com` | Requires API key |
| **LiteLLM proxy** | `http://127.0.0.1:4000` | Unified proxy for many providers |

## Installation

### Install the custom nodes

Use ComfyUI's built-in extension manager to install the nodes. Search for `comfyui-llama` by `Clusters`.

**Or**

If you prefer [ComfyUI-Manager](https://github.com/ltdrdata/ComfyUI-Manager), search for `comfyui-llama` and select the one by `clusters`

![pic](.meta/manager-install.png)

**Or**

1. git clone into the `custom_nodes` folder inside your ComfyUI installation or download as zip and unzip the contents to `custom_nodes/comfyui-llama`.
2. `pip install -r requirements.txt`
3. Start/restart ComfyUI

## Nodes

### LLM Generate

A node for text generation via OpenAI-compatible `/v1/chat/completions`. Supports system prompts, vision tasks (images), multi-turn context, and JSON structured output.

Inputs:

-   **LLM Connectivity** (optional)
-   **LLM Options** (optional)
-   **images** (optional) — for vision-capable models
-   **context** (optional) — context from another LLM Generate node
-   **meta** (optional) — passes connectivity and options from a previous LLM Generate node

**Notes:**

-   For this node to be operational, **LLM Connectivity** or **meta** must be provided.
-   If **images** are used in a meta chain, all images need to be passed as well to subsequent nodes.

### LLM Chat

A node for **conversational interaction** using `/v1/chat/completions`. It manages full conversation history natively and supports chained sequences of chat nodes.

-   **Functionality:** Designed specifically for multi-turn conversations.
-   **Key Features:**
    -   Conversation history is handled natively within the node instance.
    -   Dedicated history outputs for **chaining multiple chat nodes**.
    -   Option to **reset** the current conversation history on demand.

Inputs:

-   **LLM Connectivity** (optional)
-   **LLM Options** (optional)
-   **images** (optional) — for vision-capable models
-   **meta** (optional) — passes connectivity and options from another LLM Chat node
-   **history** (optional) — passes history ID from another LLM Chat node

Outputs:

-   **result**: The generated text
-   **thinking**: Extracted thinking/reasoning text (if model outputs `<think>` tags)
-   **meta**: Metadata to pass to the next LLM Chat node
-   **history**: History ID to pass to the next LLM Chat node

### LLM Connectivity

Configures the connection to your API server.

| Field | Description |
|-------|-------------|
| **url** | Base URL of the OpenAI-compatible API server (e.g., `http://127.0.0.1:11434`) |
| **api_key_env** | Name of the environment variable (exported in the ComfyUI server environment) holding the Bearer token. Leave empty if no auth is required. |
| **model** | Model name/ID available on the server |
| **keep_alive** | How long to keep the model loaded in memory (-1 = forever, 0 = unload immediately) |

#### Authentication (API token)

The API token is **not stored in the workflow**. ComfyUI embeds every node's widget values into saved workflow files and into the metadata of every image produced by the workflow, so keeping the token in a node would expose it to anyone who receives an image. Instead, export the token in the ComfyUI server environment and enter the **variable name** in the `api_key_env` field:

```bash
export COMFYUI_LLAMA_API_KEY="your-token-here"
```

Then set `api_key_env` on the LLM Connectivity node to `COMFYUI_LLAMA_API_KEY`. Any variable name works, which also lets you use different tokens for different servers.

> **Existing workflows:** Workflows saved with an older version contain the token in the connectivity node (and in the metadata of images produced with them). After upgrading, put the environment variable name in the `api_key_env` field instead of the token, and **rotate any token that was previously exposed**.

### LLM Options

Advanced inference parameters mapped to OpenAI-compatible API names:

| Node Option | Mapped To | Description |
|-------------|-----------|-------------|
| `temperature` | `temperature` | Creativity of output |
| `top_p` | `top_p` | Nucleus sampling threshold |
| `top_k` | `top_k` | Top-k sampling |
| `seed` | `seed` | Reproducibility seed |
| `stop` | `stop` | Stop sequences |
| `repeat_penalty` | `presence_penalty` | Repetition penalty |
| `num_predict` | `max_tokens` | Max tokens to generate |

**Note**: Each option has an enable/disable toggle. Only enabled options are sent in the API request. The `debug` flag enables CLI debug output (not part of the API).

### Deprecated nodes

Old V1 nodes are still available, please replace them with the above ones. Here's the [documentation of V1](V1_nodes.md) nodes.

## Usage Example

Please see the `example_workflows` folder or use ComfyUI's template browser.

The custom Text Nodes in the examples can be found here: https://github.com/pythongosssss/ComfyUI-Custom-Scripts
