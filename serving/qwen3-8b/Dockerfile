# Pinned by digest. --default-chat-template-kwargs (Qwen3 <think>-off) needs vLLM >=0.14.
FROM vllm/vllm-openai:v0.20.2@sha256:70a098d90dbab428a001d9e852fc0fc8d67da5beb03e7851a22247653bf35923

# Bake weights so cold start loads ~16GB from local disk, not HuggingFace.
RUN python3 -c "from huggingface_hub import snapshot_download; snapshot_download('Qwen/Qwen3-8B', local_dir='/models/qwen3-8b')" \
 && rm -rf /root/.cache/huggingface
ENV HF_HUB_OFFLINE=1

# served-model-name must equal the backend's hosted/qwen3-8b or every call 404s.
ENTRYPOINT ["/bin/sh", "-c", ": \"${HOSTED_API_KEY:?HOSTED_API_KEY must be set}\"; exec vllm serve /models/qwen3-8b --served-model-name qwen3-8b --host 0.0.0.0 --port ${PORT:-8080} --max-model-len 8192 --gpu-memory-utilization 0.90 --default-chat-template-kwargs '{\"enable_thinking\": false}' --api-key \"${HOSTED_API_KEY}\""]
