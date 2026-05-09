## V1 Release

These nodes are deprecated, please replace them in your workflows with the V2+ equivalents.

### LLM Vision (deprecated)

A node that queries input images through a vision-capable model via `/v1/chat/completions`.

![pic](.meta/OllamaVision.png)

Use any vision-capable model available on your API server.

### LLM Generate (deprecated)

A simple text generation node using `/v1/chat/completions`.

![pic](.meta/OllamaGenerate.png)

### LLM Generate Advance (deprecated)

Text generation with fine-tuned parameters and context preservation for chaining.

All options are mapped to OpenAI-compatible API parameters. See [LLM Options](README.md#llm-options) in the main README for the parameter mapping table.

![pic](.meta/generate-advance.png)
