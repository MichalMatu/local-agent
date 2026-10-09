# Operator status-github — read-only task history without Chat Bridge

This incremental change builds on the offline operator CLI in #249 and the
commit-pinned, source-only agent-control history reader in #246/#247.

The command is **disabled by default** and requires a separately established
GitHub credential in the LOCAL_AGENT_FABRIC_GITHUB_TOKEN process environment.
Never pass the credential in an argument or commit it to a file.

```sh
python -m scripts.no_bridge_manual status-github \
  --task-id-prefix local-agent-m8-pr248 \
  --pinned-control-sha "<INDEPENDENT_AGENT_CONTROL_SHA>" \
  --pinned-source-sha "<EXACT_CHECKED_SOURCE_SHA>" \
  --agent-binding "<CANONICAL_LOCAL_AGENT_BINDING>" \
  --work-branch "work/<EXPECTED_BRANCH>" \
  --allow-readonly-network
```

The reader only performs GET requests against a pinned Git commit/tree and
bounded .agent/tasks + .agent/results records. Matching result artifacts are
reconciled to task IDs and SHA-256 task digests. Missing results are shown as
unconfirmed, not as failed/succeeded commands or permission to retry.
If a completed test reports zero exit and passing stages but the Local Agent
truncated its output under the result size policy, the projection is
reported_incomplete_evidence_for_review, separate from a failed test or a
fully retained reported_pass_for_review. The user may inspect the separately
retained durable result to establish the precise limitation.

The JSON response contains only selected task IDs, commit/work-branch
identities, reported review outcomes and deny-only booleans. The field
write_disabled_in_task_record means exactly that the recorded task declared
allow_write=false; command_effects_independently_verified is permanently
false. A shell command's actual effects cannot be inferred from a task flag. Raw command
output, task command bodies, environment values and GitHub tokens are never
returned. A task result remains a *reported repository artifact*, not a
cryptographic attestation of actual Mac execution.

No browser/ChatGPT call, Send, terminal ACK, autonomous task dispatch,
legacy extension retirement, Git write, or Local Agent restart occurs.
The operator must independently authenticate every pin and binding; old
offline legacy DOM effect producers remain a global blocker for any real
same-parent transport takeover.

Tests include refusal without --allow-readonly-network, missing credential,
mocked pinned history invocation and token-safe redacted JSON output. This
remains a draft stacked after #249; exact-head Mac verification and external
security review are required.
