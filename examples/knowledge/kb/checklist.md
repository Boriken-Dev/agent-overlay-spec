---
template: mustache
---
# Review checklist for {{caller.role}}

Depth: {{options.depth}}.

{{#context.areas}}
- Check {{.}}
{{/context.areas}}
{{^context.areas}}
- Ask which areas to check.
{{/context.areas}}
