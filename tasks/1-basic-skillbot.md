- Create an agentic bot that uses "LLM" and "skills" as the centerpiece of it's architecture
- "LLM" is the brain
- "skills" represents capabilities and expertise provided to the agent
    - Documentation for skills: https://agentskills.io/llms.txt
    - Go through the complete documentation to understand what skills are, their structure etc
- The input to the agent is an entity called "Task"
    - Model the task after the A2A task: https://a2a-protocol.org/latest/sdk/python/api/a2a.types.html#a2a.types.Task
- Once the agent receives a Task, it goes through the following agent loop:
    - START
    - Find Relevant Skills
        - Finding a relevant skill can be done using any search techniques.
            - LLM call with all the skill name and descriptions loaded
            - Vector search
                - Not supported as of now. Will be implemented later
            - BM25
                - Not supported as of now. Will be implemented later
    - Load Skills
        - Since LLMs "plan" by suggesting tool calls, when a skill is loaded, all "scripts" for that skills are loaded as "tools" and bound to the LLM before invoke
    - Load Memories
        - Loads memories for this user
    - Create a Plan to complete the task with loaded skills
        - A plan.prompt.md should be created with the prompt for "planning"
        - LLM call with the "skills" loaded and the "scripts" bound as "tools"
    - Execute Plan
    - Reflect on the result of executing the plan
        - A reflect.prompt.md should be created with the prompt for "reflection"
        - LLM call with message history
    - Create Memories
        - Creates memories once a task is complete.
        - Memories are stored in the context of the user
    - Summarize Current Task Progress
        - As task execution continues the messages will grow and so will the context window
        - This step 
- If at the end of reflection, it's deemed that the task is complete, then we goto Create Memories
- Else we go back to "Summarize" and then go back to "Find Relevant Skills"

- VERY IMP NOTE: The above is the "framework" or the "structure" to create any agent within the skillbot ecosystem
    - Create an abstraction to represent the structure of the agent defined above
- The default agent (`supervisor`) is the instance of this framework/structure defined above

- Communication b/w the user and the agent
    - All communications with the agent will happen using the A2A protocol
        - Docs: https://a2a-protocol.org/latest/
        - A2A Python SDK: https://a2a-protocol.org/latest/sdk/python/api/
    - When skillbot starts, it runs an A2A server which listens to any incoming messages etc
        - The PORT can be configured in `skillbot.config.json`

- `skillbot.config.json`
    - default location: `~/.skillbot`

- Template for `skillbot.config.json`
```json5
{
    "type": "skillbot.config",
    "services": {
        "supervisor": {
            "type": "agent",
            "port": 7744,
            "config": "<skill-bot-root-dir>/supervisor/agent-config.json"
        },
        // NOTE: Currently gateway is not implemented
        "gateway": {
            "type": "gateway",
            "port": 7745
        }
    },
    "model-providers": {
        "openai": {
            "api-key": "",
            "base-url": ""
        }
    }
}
```

- `agent-config.json` defines all the configurations related to the agent
```json5
{
    // Directory for the agent to store execution logs, memories etc
    "model": {
        "provider": "" // Provider name: openai, anthropic etc,
        "name": "", // Name of the model. Example: gpt-5.2
    },
    "skill-discovery": "llm", // Allowed values are "llm", "vector", "bm25"
    "prompts": {
        "find-skills": "./find-skills.prompt.md",
        "plan": "./plan.prompt.md",
        "reflect": "./reflect.prompt.md",
        "create-memories": "./create-memories.prompt.md",
        "summarize": "./summarize.prompt.md"
    },
    "tools": {

    },
    "skills": {

    }
}
```
- Create default prompts for all prompts listed above

- Memories
    - All memories are stored in the scope of the user
    - Memories are stored as markdown files `memory-<user-id>.md`
    - Structure of memories:
        - 

- CLI Tool
    - skillbot init
        - Creates `<skill-bot-root-dir>/skillbot.config.json`
            - Takes an argument called `--root-dir` for custom path to `<skill-bot-root-dir>/skillbot.config.json`
            - If provided the config will be created there
            - Else it will be created at the default location `~/.skillbot`
    - skillbot start
        - Starts the services required for skillbot
        - Currently this means starting the agents configured in `skillbot.config.json`
        - Notify the user what all services have been started at what ports
            - Give URLs so that user can navigate to them
    - skillbot chat
        - Starts an interactive chat session with the user
            - Currently this will be text based
            - Add a streamlit ui for the chat interface in `skillbot/streamlit`
            - The streamlit can be independently run or through `skillbot chat --interface streamlit` command
        - A user-id is ALWAYS required to start this
            - provided as `--user-id`
        - Workspace
            - A place where all the data related to the user and sessions are stored
            - Default will be `<skill-bot-root-dir>/users/<user-id>/`
                - Memory.md will be stored here
                - `<skill-bot-root-dir>/users/<user-id>/tasks/<task-id>/`
                    - All things related to task will be stored here
                    - For e.g. checkpoint related to task will be stored here.
        - This communicates with the `supervisor` using A2A protocol
        - The agent that will be invoked is the `supervisor`

- Folder Structure

```
skillbot
    - agents
        - supervisor.py
    - framework
        - agent.py
    - cli
        - cli.py
    - tools
```

- Libraries and Frameworks
    - Use LangGraph for creating the graph for the agent
        - https://reference.langchain.com/python/langgraph
    - Use SQLite Checkpointer
        - https://reference.langchain.com/python/langgraph.checkpoint.sqlite/aio/AsyncSqliteSaver
    - Use FastAPI for the server

- Updates after initial bootstrap:
    - Add logging to each langgraph node or tool call enter and exit
        - Add response from the LLM also in the log
    - I need to hot-reload the service while development. Add command to do that in README.md
    - Since we have a step of "Create Memories" after the "reflection" step, we are not able to get the actual response to the user. What we see are the AIMessages from these "internal" steps
    - Generate the final output that should be provided to the user as part of the reflect step
        - Currently the reflect step just determines whether the task is complete or not
        - May be explicitly capture the task's output/result in AgentState
        - This final reult is what needs to be the final "status.message" in A2A Message sent back
    - In the streamlit ui, add a collapsible section in each response of the agent
        - This section will have the list of messages from AgentState
        - Pass these as "artifacts" field in the A2A response to a message
