# Channel Notification Capability Matrix

## Summary

This task is intentionally **Telegram-first**.

The goal of the first implementation slice is:

1. remove user-visible confirmation after explicit PT resource selection
2. remove user-visible import confirmation on the default hardlink path
3. make the resulting Telegram notifications observable in real smoke

This slice does **not** attempt to deliver feature parity across all channels.

## Current capability snapshot

Based on current code:

- `Telegram`
  - proactive send available
  - existing send path already wired through `TELEGRAM_SEND_TEXT_FUNC_KEY`
- `Feishu`
  - proactive send available
  - `build_feishu_proactive_send_text_func()` exists
- `personal WeChat`
  - proactive send available, but depends on login state
  - `build_personal_wechat_proactive_send_text_func()` exists
- `WeCom`
  - proactive send is **not available yet**
  - `build_shared_private_chat_send_text_func()` raises
    `shared private chat send unsupported for channel: wecom`

## Product decision for this task

- Implement and smoke **Telegram only**
- Do **not** expand this task to Feishu / personal WeChat / WeCom adaptation
- Treat later channel work as separate tasks
- Treat missing WeCom proactive send as a known product gap, not a blocker

## Storage / import boundary

The user also clarified a product direction:

- long-term direction is hardlink-only
- no copy fallback as a desired future behavior

But this must **not** be bundled into the Telegram-first notification slice.

Reason:

- removing copy fallback changes import execution semantics
- it touches `import_to_library`, `import_transfer_execution`, cleanup, and adult archive lifecycle
- that is a separate blast radius from Telegram UX and notification behavior

So for this task:

- keep current internal truth model
- do not redesign copy fallback here
- only remove user-visible friction on the default successful path
