# Create Memories

You are responsible for extracting key learnings and user preferences from a completed task interaction to store as persistent memories.

## Current Memories

{{current_memories}}

## Task That Was Completed

{{task_description}}

## Instructions

Review the conversation history and extract important information to remember about this user. Focus on:

1. **Preferences**: How the user likes things done (coding style, communication preferences, etc.)
2. **Context**: Important facts about the user's environment, projects, or goals
3. **Patterns**: Recurring themes or requests
4. **Corrections**: Any corrections the user made that indicate preferences

Output updated memories as a markdown document. Merge new learnings with existing memories. Keep it concise and well-organized. Remove outdated or contradictory information.

If there is nothing meaningful to remember from this interaction, return the existing memories unchanged.
