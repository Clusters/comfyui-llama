24-09-2026:

Security fix — the API token is no longer stored in the workflow. ComfyUI embeds every node's widget values into saved workflows and into the metadata of every image produced by the workflow, so a token typed into the connectivity node was leaking into all output images.

- `LLMConnectivityV2`: replaced the `api_key` widget with `api_key_env`, which holds the **name** of an environment variable (exported in the ComfyUI server environment) containing the token, e.g. `COMFYUI_LLAMA_API_KEY`. The token itself is resolved server-side and never appears in the workflow graph or image metadata.
- If a legacy workflow still contains a raw token in this field, a clear error describes the new mechanism instead of reusing the value.
- Model-list refresh (`/llm/get_models`) now resolves the token server-side from the environment variable name; it still accepts `api_key` for the deprecated V1 nodes, which remain unchanged.

**Action required:** rotate any token that was previously stored in workflows or embedded in images, and replace the old `api_key` widget value in saved workflows with the environment variable name.

09-05-2026:

Major refactor — migrated from Ollama API to OpenAI-compatible API (`/v1/...` endpoints). Breaking changes.

- Replaced `ollama` Python client with `httpx` for direct HTTP calls to `/v1/models`, `/v1/chat/completions`
- Added `api_key` field to connectivity node (Bearer token authentication)
- Renamed all classes, methods, and type strings from Ollama/OLLAMA_* to LLM/LLM_*:
  - `OllamaConnectivityV2` → `LLMConnectivityV2`, `OllamaGenerateV2` → `LLMGenerateV2`, `OllamaChat` → `LLMChat`
  - Type strings: `OLLAMA_CONNECTIVITY` → `LLM_CONNECTIVITY`, etc.
- Renamed main module file from `CompfyuiOllama.py` to `ComfyUI_LLM.py`
- Renamed JS extension from `OllamaNode.js` to `LLMNode.js`
- Updated route path: `/ollama/get_models` → `/llm/get_models`
- Updated all example workflows (renamed and updated node types/type strings)

04-10-2025:

- Fixed Ollama cloud model support with new OllamaChat node
- Cloud models authenticate via SSH keys (no API key required)
- Uses `ollama.chat()` method for cloud compatibility

04-08-2025:

- Added `think` option and separate `thinking` output on the Ollama Generate node. This replaces the previous `filter_thinking` workaround.
- Added tooltips and node descriptions.
- Added example workflows. See ComfyUI's template browser in the workflow menu.
- Added a message that appears when the list of models fails to load. User can click the "Reconnect" button on the connectivity node to reload list.
- Deprecate V1 nodes, please replace them in your workflows.

10-07-2025:

Adding user seed to OllamaVision request.

10-06-2025:

Increased temperature limits in OptionsV2.

26-05-2025:

Added toggle to strip thinking from response

22-04-2025:

Fix v2 settings num ctx limit.
Update ollama python 0.4.8.

10-01-2025:

V2 release.

Added nodes:

- OllamaGenerateV2

- OllamaConnectivityV2

- OllamaOptionsV2

09-01-2025

Update python ollama client 0.4.2 -> 0.4.5

04-12-2024:

Fix image base64 to binary issue.

25-11-2024:

Fix some bug in fetching model names.

20-11-2024:

Support step of 1 in `keep_alive`.

16-11-2024:

Support `-1` value in `keep_alive`.

19-10-2024:

Add seed input to OllamaVision node.

09-10-2024:

Add out put format `text` or `json` in all generate nodes.

(should be compatible with existing workflows)

31-08-2024:

Merge change `top_k` and `num_predict` params in **OllamaAdvanced** to be INT instead FLOAT.

30-07-2024

Add 2 new Nodes:

- OllamaSaveContext: will save context from OllamaGenerateAdvance to a `png` file in saved_context folder.
- OllamaLoadContext: will load context for OllamaGenerateAdvance from a `png` files in saved_context folder.
- `context` input in OllamaGenerateAdvance node now can handle string also.

18-06-2024

- Add `keep_context` option in OllamaGenerateAdvance, this flag will preserve context from the current run in the node itself.
- Modify debug flag to be boolean.

24-05-2024

- Add drop down list to select ollama models that currently available in ollama server.

23-05-2024

- Add `keep_alive` option. Controls for how long the selected model will stay loaded into memory following the request (default: 5m).

21-05-2024

- Modify Ollama Generate Advance node, change seed to 'INT' from 'FLOAT'.
