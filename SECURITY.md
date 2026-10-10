# Security policy

Never attach API keys, DPAPI backups, personal inputs or private production reports
to public issues, pull requests or logs. `_SYSTEM/secrets` is local installation
state and must stay outside Git. Rotate credentials immediately if exposed.

Use GitHub's **Report a vulnerability** option under this repository's Security tab
to send a private report. If unavailable, do not post sensitive exploit details in
a public issue; ask the owner for a private reporting channel without including them.

Include affected source version, a minimal synthetic reproduction and the impact.
There is no promised response SLA or supported long-term release branch yet.

AI output is untrusted data. Preserve schema validation, path boundaries, no-network
render workers, bounded provider calls and account-bound credential protection.
The publication scanner is a defense against common leaks, not a guarantee that
every possible secret format will be detected.
