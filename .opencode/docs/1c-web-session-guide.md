# 1C Web Session Guide — Playwright MCP

Skill: `/1c-web-session`. Source: RooLee10/1c-web-session (MIT).

## Purpose

Automate 1C:Enterprise web client via Playwright MCP. Use for:
- Session management (start/restart/end)
- Section navigation
- Creating/editing reference items and documents
- Filling forms and table sections
- Generating test data via UI
- Scenario testing

## When NOT to Use

Playwright is expensive (high tokens, unreliable navigation). Prefer:
- `1c-ai-debug` MCP for data read/write (CRUD, queries, metadata)
- Playwright only when no other way (screenshots, specific UI behavior)

## Key Patterns

### Input: Clipboard Paste (NOT fill/type)
Standard Playwright `fill` / `type` methods don't work in 1C web client.
Always use clipboard paste:
```javascript
// Set clipboard and paste
await page.evaluate(text => navigator.clipboard.writeText(text), value);
await field.click();
await page.keyboard.press('Control+A');
await page.keyboard.press('Control+V');
```

### Form Element IDs
1C form IDs are incremental (form26, form40). Use suffix selectors:
```javascript
// Correct: suffix selector
'[id$="_FieldName_DLB"]'   // input field
'[id$="_FieldName"]'        // static element
// Wrong: hardcoded IDs
'#form26_Name_DLB'          // breaks when form ID changes
```

### Navigation Cache
Use `1c-nav.json` to cache section navigation paths. Avoids repeated full navigation:
- Read cache before navigating
- Write cache after successful navigation
- Invalidate on structure changes

### DLB Suffix Buttons
1C button elements use `_DLB` suffix for dropdowns/lookup buttons:
- `[id$="_FieldName_DLB"]` — the clickable button
- Click DLB to open picker/dropdown for reference fields

### Dialog Handling
Standard dialogs appear after actions:
```javascript
// Wait for dialog
await page.waitForSelector('.v8-dialog', { timeout: 5000 });
// Or wait for specific element
await page.waitForSelector('[id$="_OK"]');
```

### JS Verification
Verify state via JS execution:
```javascript
const result = await page.evaluate(() => {
    return window.v8Form?.GetValue('FieldName');
});
```

## Session URL

Default web client URL: `http://YOUR_EDT_SERVER:8080/arqa/` (onec-web-25)
or `http://YOUR_EDT_SERVER:8081/arqa/` (onec-web-24).

Per-project URL configured in project CLAUDE.md.

## Chained browser_run_code Optimization

For sequential operations, chain multiple actions in single `browser_run_code` call
instead of separate tool calls — reduces token overhead significantly.

## References

- Skill SKILL.md: `.claude/skills/1c-web-session/SKILL.md`
- Optimization patterns: `.claude/skills/1c-web-session/references/optimization.md`
- Nav scanner: `.claude/skills/1c-web-session/references/scan-nav.js`
