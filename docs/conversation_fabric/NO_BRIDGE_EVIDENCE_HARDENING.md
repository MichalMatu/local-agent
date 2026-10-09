# No-Bridge evidence hardening — narrow source-only review

This draft stacks on the prior no-Bridge result/history readers.
It deliberately changes **no running executor**, browser extension or
ChatGPT conversation transport.

Additional fail-closed review checks:

- Only **one** bounded read-only exact-head test command may be represented
  as a reported test result; a task with extra unguarded commands is outside
  the narrow evidence reader's acceptance scope.
- A reported clean PASS is denied if any separate verification-stage
  evidence is present unexpectedly. The reader supports only the task
  format explicitly checked by the existing tests.
- The reported task status must belong to a closed, short vocabulary,
  rather than reflecting arbitrary remote content into an operator-visible
  status string.
- The recursive Git tree response must itself report the SHA obtained
  from the independently pinned commit's tree; relevant Contents blobs
  must also match the corresponding tree entry SHA.

The history reader now also fetches every scoped task without a result at
the pinned commit and verifies its exact binding, branch, source-head guard
and read-only scope before listing it as unconfirmed. A missing result from
an unrelated branch can no longer masquerade as relevant pending work.

Additional negative tests cover unknown/private-looking status text,
untrusted second commands, failed extra verification data, substituted
Git tree identities, and cross-branch or unguarded pending task records. These checks do not produce a cryptographic
attestation of Mac command execution; source provenance remains an
operator and GitHub responsibility.

The entire path remains opt-in, GET-only and review-only. No fallback to
automatic retry, Send, ACK, migration activation or legacy-worker retirement.
Full exact-head Mac validation and independent review remain acceptance gates.
