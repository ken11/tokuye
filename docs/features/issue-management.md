# Issue Management

Tokuye provides a convenient way to save and recall issue descriptions across sessions.

## Saving an Issue

Start your message with `# Issue` and the content will be automatically saved to `.tokuye/current_issue.md`:

```
# Issue

## Bug Description
The login form validation is not working properly when the email field is empty.

## Steps to Reproduce
1. Open the login page
2. Leave the email field empty
3. Click Submit

## Expected Behavior
An error message should appear below the email field.
```

The file is saved immediately when you send the message. You can use this to persist the current task description so it survives conversation resets.

## Recalling an Issue

Click the **Recall Issue** button in the TUI to restore the saved issue content into the input area.

This is useful when:

- You reset the conversation and want to re-submit the same issue
- You want to reference the original issue description mid-conversation
- You're starting a new session on the same task

## File Location

The saved issue is stored at:

```
<project_root>/.tokuye/current_issue.md
```

This file is project-specific and persists between Tokuye sessions.
