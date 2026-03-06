---
id: email-basic
description: Basic email management on campus email system
whenToUse: When an agent needs to read, send, search, reply to, or forward emails
tags:
  - email
  - communication
  - campus
---

## Email Management

### Searching for Emails
1. Use `email.search` with a keyword query to find emails by subject, sender, or content
2. Check the inbox first before composing — the answer may already be there
3. Note the `email_id` from search results for further actions

### Reading Emails
1. Use `email.read` with the `email_id` to get the full email contents
2. Pay attention to sender, timestamp, and any action items mentioned

### Replying and Forwarding
1. Use `email.reply` with the `email_id` and your response body
2. Include relevant context from the original email in your reply
3. Use `email.forward` to send an email to a different recipient — include a note explaining why

### Composing New Emails
1. Use `email.send` with `to`, `subject`, and `body` fields
2. Keep subject lines concise and descriptive
3. Address the recipient by name when possible

### Tips
- Always search before composing — avoid duplicate messages
- When replying, reference specific details from the original email
- Forward emails only when the new recipient needs the full thread context
- Check search results carefully — queries match subject, sender, and body
