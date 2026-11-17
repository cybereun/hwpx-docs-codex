---
name: hwpx-security
description: Hangul security around HWPX automation — the file-access prompt (접근 허용 창) when scripts open files, batching so the user answers once, the optional official Hancom module that the user installs, and the status of password and distribution-document post-steps. Use for 한글 접근 허용 창, 보안 승인 모듈, 문서 암호.
---

# Hangul security

## The file-access prompt

Hangul 2024 asks "한글을 이용하여 위 파일에 접근하려는 시도 ..." (접근 허용 / 모두 허용) when an automation script
OPENS an existing file (render, verify, round trip). Making or reading an HWPX with `hd build`, `hd read`, `hd md`,
`hd html` needs no Hangul and shows no prompt.

- Only the user answers it. Never click it by code, never change Hangul security settings, never install or
  register a DLL for the user.
- The scripts open all files of one batch in ONE Hangul and wait up to 300 s for the answer
  (`HANGUL ACCESS PROMPT ...`). With no answer they close it (= deny) and stop the batch.
- Before each render or check batch, tell the user in one line: how many files, and that one "모두 허용" click is
  expected.

## Optional: no prompt (the user does it)

Hancom publishes an official automation security module (developer.hancom.com/hwpautomation, section
"보안 승인 모듈"). The user downloads it from that page, puts the DLL in a folder, adds a REG_SZ value under
`HKEY_CURRENT_USER\Software\HNC\HwpAutomation\Modules` (name: any, data: the DLL's full path) and sets the
environment variable `HWPX_DOCS_SECURITY_MODULE` (old name `HWPX_DOCS_MODULE`) to that value name. Then each session
calls `RegisterModule("FilePathCheckDLL", <name>)` right after it starts Hangul and logs `security module: on`; with
no variable or no registry value it logs `security module: off`. OFF by default; the registry is only read. The README section "접근 허용 창 없애기 (선택)" has
the steps and the risk: with the module, any automation script can open or save files without asking.

## Passwords and distribution documents (C11)

`hd secure` protects an HWPX with Hangul's own commands through COM (a post-step). No cipher is written or
reverse-engineered here; Hangul does the protecting.

- Password: `hd secure in.hwpx out.hwpx --password-env NAME` (the user sets the environment variable NAME).
- Distribution document: add `--distribute [--no-print] [--no-copy]`.
- Hide personal data (no Hangul, no password): `hd secure in.hwpx out.hwpx --mask-private` replaces resident
  numbers (back 7 digits), phone numbers, e-mail addresses and card numbers in the text with `*`. It is a text
  replacement, not encryption. Hangul's selective protection (C11.03) and DRM (C11.05) are not available through COM.
- NEVER take a password as an argument, in chat for a command line, in a file or in a log. Use only an environment
  variable that the user names. Never ask for or use the user's real passwords in tests: a test sets a throwaway
  value inside its own process and deletes its files.
- It opens the input in Hangul, so tell the user: "Hangul batch: n files, 모두 허용 한 번". One hidden Hangul per batch.
- A protected file (password or distribution) cannot be read, checked or drawn without Hangul. `hd read` and the
  other commands print `PROTECTED: ...` and exit with code 4 (no traceback); `hd preview` draws one placeholder page;
  `hd secure --info file.hwpx` reports the protection with no Hangul. To work on the content, the user opens the file
  in Hangul and saves an unprotected copy.
- Do not change Hangul's own security settings or the registry.
- A spec or Markdown file that you did not write can name any file on the disk in `pic.src`, `ole.src`, a picture `fill` or
  `![](path)`; the builder embeds it. Before you build from a received spec, list those paths and ask the user about any
  path outside the spec's folder.
- No spec key protects a document: protection is always this post-step on a built file. Cell protection (`protect`,
  `editable`, skill hwpx-table) only marks cells; it is not a password.
- Before a file goes out: `hd textstyle scan file.hwpx` finds the PC user name, user folder paths and author names that
  Hangul writes into a file it saved (track change and memo authors, OLE source paths). `--fix` changes the file IN PLACE:
  copy the file first and run `hd textstyle scan --fix` on the copy, never on the user's only copy.
