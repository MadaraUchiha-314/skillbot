- Make the CLI interaction a much better experience by introducing colors and TUI libraries
- Create an ASCII art for skillbot which gets shown on init
- Do different highlighting of agent chat vs user chat
- Make them aligned on different sides of the terminal
- When the agent is responding (network call is happening), show a loader or thinking icon
- Whem the agent response, by default only show `status.message`
    - But add an option where the user can press a button combination to see the traces (present in artifacts)
    - User should be able to collapse and expand the traces
    - All the traces and message should be pretty-printed
- Show different icons for both user and agent

- Add commands like 
    - /skills to show the loaded skills
    - /agent.config to show the config of the current agent
    - /exit to exit the chat
    - /logs to show all the debug, info, error logs
    - /memories to show the memory for the user
    - /start to start the agent server, if it's not already running
    - /stop to stop the agent server, if it's running

- Let's not have 2 separate commands for `start` and `chat`
    - Let's just make it `start`
    - `start` will start the server in the background and open up the cli chat
    - add an option --background to just start the server in the background and not have the chat interface on cli

- Remove streamlit as a channel
- We will make everything available through the cli

- Do a cleanup and remove all unused code

- Move all user facing strings to a json file and refer it from there.
    - This will help in transalations better

- Introduce an error code system and document all the error codes

- Use an SQLite Implementation of the task store and store the task related stuff in the same path as the checkpointer

- All the data related to a session should be queryable through the task store

- All error logs should be logged to a <taskId>-<timestamp>.txt
    - Find the appropriate path to where the task related data is stored

- When the A2A server receives a task, if a taskId doesn't exist, then create a task and then pass it to the agent
    - The agent should should always deal with a task

- Also make sure that the console logs don't get printed on the console when the CLI is loaded or while chatting