# LangGraph Customer Support Agent on Bedrock AgentCore

A LangGraph ReAct-style customer support agent (FAQ lookup + order status tools) deployed to
**Amazon Bedrock AgentCore Runtime**
## What it does

- `lookup_faq(query)` — keyword-matches against a small hardcoded FAQ set
  (return policy, refunds, shipping, account/password, contact info), with a
  graceful fallback when nothing matches well. Deliberately simple keyword
  matching, not a RAG/Knowledge Base pipeline.
- `get_order_status(order_id)` — looks up an order in a small SQLite table
  (`orders.db`, auto-created and seeded on first run — see `db.py`),
  normalizing case/whitespace, validating ID shape, and returning a clear
  "not found" message for unknown IDs. The schema carries a few extra
  realistic fields (customer name, order date, carrier, estimated delivery,
  items) beyond a bare status string.
- The agent asks for a missing order ID instead of guessing, resumes that
  request once the user supplies it (multi-turn, via a LangGraph
  checkpointer keyed by `thread_id`), and can call both tools together for
  combined requests (e.g. "I want to return order #A1023").
- A seeded order ID (`ERR001`) deliberately raises inside the tool, to
  demonstrate LangGraph's built-in `handle_tool_errors` path end-to-end
  rather than crashing the graph.

## Architecture

Standard LangGraph ReAct shape — one LLM node, one tool node, looping until
the model has enough to answer:

```
__start__ → agent ⇄ tools
              ↓
           __end__
```

- **`agent` node** (`graph.py`) — the only node that calls the LLM
  (`ChatBedrockConverse`, via `langchain-aws`), bound to both tools. Decides
  each turn whether it has enough information to answer or needs a tool.
- **`tools` node** — LangGraph's prebuilt `ToolNode`, built with
  `handle_tool_errors=True` so a tool exception becomes a message the agent
  can react to instead of crashing the graph.
- **Checkpointer** (`MemorySaver`) — keyed by `thread_id`, this is what
  makes multi-turn slot-filling work: the follow-up turn that supplies a
  missing order ID resumes the same conversation rather than starting fresh.
- **`agentcore_app.py`** — a thin `BedrockAgentCoreApp` wrapper. AgentCore
  Runtime's container contract (`/invocations`, `/ping`) is already built
  into `BedrockAgentCoreApp`; this file only registers the entrypoint
  function and hands requests to the same `invoke_agent()` helper the local
  test API uses, so the graph itself never had to change to run on
  AgentCore.

## Repository layout

```
├── config.py                  # MODEL_ID / MODEL_PROVIDER placeholders + logging setup
├── tools.py                    # lookup_faq, get_order_status
├── db.py                        # SQLite schema + seed data for orders (orders.db)
├── graph.py                     # LangGraph graph + shared invoke_agent()/save_diagram() helpers
├── agentcore_app.py             # BedrockAgentCoreApp wrapper + entrypoint
├── local_api.py                 # FastAPI local test API (no AgentCore needed)
├── pyproject.toml, requirements.txt, uv.lock   # dependencies
├── Dockerfile, .dockerignore    # AgentCore Runtime container image (linux/arm64)
├── graph_diagram.mmd/.png       # graph shape, regenerate with `python graph.py`
└── tests/
    └── sample_conversations.py   # 5 scripted local conversations
```

`orders.db` is created automatically on first import of `db.py` — it's
gitignored and safe to delete to reset to the seed data.

## Local setup

Using `uv` (this project's `.venv` was created with it — `uv.lock` pins
everything):

```bash
uv sync                                          # installs dependencies
uv add --dev bedrock-agentcore-starter-toolkit   # the `agentcore` CLI (dev/deploy/invoke)
source .venv/bin/activate
```
Before running anything that calls the model, fill in `config.py`:

```python
MODEL_ID = "anthropic.claude-3-5-sonnet-..."   # or an inference-profile ARN — see Deployment
MODEL_PROVIDER = "anthropic"                    # required if MODEL_ID is an ARN
```

and make sure the model is enabled for your account in the Bedrock console
(**Model access**), with your AWS credentials/region configured
(`aws configure`).

## Local testing

Run the scripted conversations directly against the compiled graph (no
AgentCore CLI or deployment needed):

```bash
python -m tests.sample_conversations
```

This tests, in order:
1. FAQ-only query
2. Order-status-only query
3. Missing order ID → the agent asks for it → follow-up turn supplies it
4. A combined query requiring both tools
5. The simulated tool failure (`ERR001`)

### Local Testing (no AgentCore needed)

For quick manual testing without the AgentCore CLI, `local_api.py` exposes
the same agent as a plain FastAPI HTTP API (via the shared `invoke_agent`
helper in `graph.py`, so behavior matches `agentcore_app.py` exactly):

```bash
uvicorn local_api:app --reload
```

Then open **http://127.0.0.1:8000/docs** for FastAPI's interactive Swagger
UI — you can send `POST /chat` requests from the browser, or:

```bash
curl -X POST http://127.0.0.1:8000/chat \
    -H "Content-Type: application/json" \
    -d '{"prompt": "I want to return my order"}'
# -> {"response": "...", "thread_id": "<generated-uuid>"}

curl -X POST http://127.0.0.1:8000/chat \
    -H "Content-Type: application/json" \
    -d '{"prompt": "A1023", "thread_id": "<paste-the-uuid-above>"}'
```

Reusing `thread_id` across calls continues the same conversation (e.g. to
answer a follow-up after the agent asks for an order ID).

## AWS terminology used below

Terms specific to this project's deployment, for reference before the steps
that use them:

- **Bedrock** — AWS's managed service for calling foundation models (Claude,
  Nova, etc.) via a single API, instead of hosting/serving models yourself.
- **Model access** — a per-account, per-region opt-in step in the Bedrock
  console; a model must be explicitly enabled before it can be invoked.
- **Application inference profile** — a Bedrock resource that wraps a
  foundation model behind its own ARN. Some models can only be invoked
  through a profile rather than by their bare model ID directly (an
  account/region capacity detail, not a code choice).
- **AgentCore Runtime** — the managed service this project deploys to: it
  runs the packaged agent container, handling session isolation and scaling
  so the agent code doesn't have to.
- **Agent Runtime** vs. **Runtime Endpoint** — the Runtime is the deployed
  resource (tied to a container image); an Endpoint (e.g. `DEFAULT`) is a
  named, invokable pointer to one *version* of that Runtime — similar in
  spirit to a Lambda alias pointing at a specific Lambda version.
- **Execution role** — the IAM role the deployed agent *runs as* inside
  AgentCore Runtime. Distinct from whatever IAM user/role a developer uses
  locally to build/push the image or invoke the runtime — permissions
  granted to one do not apply to the other.
- **ECR (Elastic Container Registry)** — AWS's Docker image registry; the
  built agent image is pushed here before AgentCore Runtime can use it.
- **ARN (Amazon Resource Name)** — the unique identifier for any AWS
  resource (a role, a model, an inference profile, a runtime, ...), always
  in the form `arn:aws:<service>:<region>:<account-id>:<resource>`.

## Deployment

1. **Enable a Bedrock model.** If it isn't invokable by
   a bare model ID in your account (an "on-demand throughput isn't
   supported" error, or the console only offers it via a cross-region
   profile), create an **application inference profile** instead
   (Bedrock console → **Inference and Assessment**) and use its ARN.

2. **Set the model in `config.py`:**
   ```python
   MODEL_ID = "arn:aws:bedrock:<region>:<account-id>:application-inference-profile/<profile-id>"
   MODEL_PROVIDER = "anthropic"  # or "amazon", etc. — required alongside an ARN, since
                                  # ChatBedrockConverse can't infer the provider from an ARN
                                  # the way it can from a bare "anthropic.claude-..." string
   ```

3. **Build and push the image, then create the runtime (Console).** Build
   the container (see below), push it to ECR, then Bedrock console →
   **AgentCore → Agent Runtimes → Create agent runtime** → point it at the
   image. This also creates an execution role for the runtime
   (`AmazonBedrockAgentCoreRuntimeDefaultServiceRole-*`).

4. **Grant that execution role Bedrock access.** The role AgentCore creates
   does not automatically include permission to call your model/inference
   profile — add an inline permission for that: IAM console → Roles → the
   `AmazonBedrockAgentCoreRuntimeDefaultServiceRole-*` role → **Add
   permissions → Create inline policy** → JSON tab → paste:
   ```json
   {
     "Version": "2012-10-17",
     "Statement": [
       {
         "Sid": "InvokeViaInferenceProfile",
         "Effect": "Allow",
         "Action": ["bedrock:GetInferenceProfile", "bedrock:InvokeModel", "bedrock:InvokeModelWithResponseStream"],
         "Resource": "arn:aws:bedrock:<region>:<account-id>:application-inference-profile/<profile-id>"
       },
       {
         "Sid": "InvokeUnderlyingModel",
         "Effect": "Allow",
         "Action": ["bedrock:InvokeModel", "bedrock:InvokeModelWithResponseStream"],
         "Resource": "arn:aws:bedrock:<region>::foundation-model/<base-model-id>"
       }
     ]
   }
   ```
   (Drop the first statement if invoking a bare model ID directly rather
   than through a profile.)

5. **Verify** — invoke the deployed runtime with boto3:
   ```python
   import boto3, json, uuid
   client = boto3.client("bedrock-agentcore", region_name="<region>")
   response = client.invoke_agent_runtime(
       agentRuntimeArn="<your runtime ARN>",
       runtimeSessionId=str(uuid.uuid4()),
       payload=json.dumps({"prompt": "What is your return policy?"}),
       qualifier="DEFAULT",  # or your endpoint's name, if you created a custom one
   )
   print(response["response"].read().decode())
   ```
   Reuse the same `runtimeSessionId` (this project's `thread_id`) across
   calls to continue a conversation — e.g. to send a follow-up after the
   agent asks for a missing order ID. The identity calling this needs
   `bedrock-agentcore:InvokeAgentRuntime` — a separate permission from
   anything granted to the execution role above.

### Building the container image

```bash
docker build --platform linux/arm64 -t <account-id>.dkr.ecr.<region>.amazonaws.com/<repo>:<tag> .
docker push <account-id>.dkr.ecr.<region>.amazonaws.com/<repo>:<tag>
```

AgentCore Runtime requires `linux/arm64` images. The Dockerfile installs
only the core dependencies from `pyproject.toml` (not the `local` extra used
by `local_api.py`), since `bedrock_agentcore` already brings in the
uvicorn/starlette it needs to serve `agentcore_app.py`'s entrypoint on port
8080.

### IAM / access prerequisites

- The runtime's execution role needs `BedrockAgentCoreFullAccess` (or an
  equivalent scoped policy) **plus** the Bedrock model/inference-profile
  invoke permissions from step 4 above — the former does not cover the
  latter, since `bedrock` and `bedrock-agentcore` are separate IAM action
  namespaces.
- Whoever pushes the image needs ECR push permissions, and whoever invokes
  the runtime needs `bedrock-agentcore:InvokeAgentRuntime` — both are
  separate from the runtime's own execution role.
- The target model must be set in `config.py` and its access enabled in the
  Bedrock console under **Model access** (with an inference profile created
  if the model isn't directly invokable) before deployment.