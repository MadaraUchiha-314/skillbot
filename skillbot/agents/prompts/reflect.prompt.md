# Reflect on Task Progress

You are reflecting on the progress of a task execution. Review the conversation history and the results of the actions taken so far.

## Task

{{task_description}}

## Instructions

Analyze the execution results and determine:

1. **Completeness**: Has the task been fully completed? Are all requirements met?
2. **Quality**: Is the output of sufficient quality?
3. **Issues**: Were there any errors or problems that need to be addressed?
4. **Next Steps**: If the task is not complete, what should be done next?
5. **Response**: Compose a final, user-facing response that directly addresses the user's original message. This is the message the user will see. It should be clear, helpful, and conversational — do NOT include internal reasoning, JSON, or metadata.

**Important:** If the user's input is a greeting, casual conversation, simple question, or any message that does not require multi-step action, and the agent has already provided an appropriate response, mark the task as **complete**. Only mark a task as incomplete if there are concrete, actionable steps remaining that the agent has not yet performed.

Respond with a JSON object:

```json
{
    "task_complete": true/false,
    "response": "The final message to show the user",
    "reasoning": "Brief explanation of your assessment",
    "issues": ["List of any issues found"],
    "next_steps": ["List of next steps if not complete"]
}
```
