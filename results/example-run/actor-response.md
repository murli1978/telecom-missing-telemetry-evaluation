**1. What is established by the evidence?**  
| Observation | Time | Source | Detail |
|-------------|------|--------|--------|
| Batch **B‑8821** accepted | 09:02:11 UTC | `billing-feed-gateway` | `records_received=10240`, `records_rejected=0` |
| Normalizer job started for batch | 09:05:43 UTC | `invoice-normalizer` | `worker_pool=norm-prod-3` |
| Telemetry collector reported export errors | 09:06–09:14 UTC | `telemetry-collector` | `export_errors=observed`, queue capacity reached |
| Exception‑store lookup for batch B‑8821 & source reference `INV‑SRC‑77831` returned zero matches | 09:15:00 UTC | `billing-exception-store` | `matching_exception_records=0` |
| Portal‑invoice‑API returned *invoice_not_found* for ACCT‑1042 / 2026‑04 | 09:19:11 UTC | `portal-invoice-api` | `http_status=200` |
| Portal‑invoice‑API returned *invoice_found* for ACCT‑1042 / 2026‑03 | 09:19:54 UTC | `portal-invoice-api` | `http_status=200` |
| No normalizer completion event for batch B‑8821 in the logs | – | – | – |
| No query to the canonical invoice store for `INV‑SRC‑77831` | – | – | – |

**2. Plausible explanations (no ranking unless evidence supports it)**  

| Hypothesis | Supporting evidence | Notes |
|------------|---------------------|-------|
| The normalizer job for batch B‑8821 never finished before the portal query. | No completion event logged; telemetry export errors may have delayed export of events. | The job could still be running or stuck. |
| The invoice record was exported to the canonical store but the portal query used the wrong key (account + period) or a stale cache. | Portal found March invoice but not April; the April invoice may exist under a different key. | Portal‑API may not be using the source reference. |
| The invoice was not generated because an earlier step (e.g., source‑system mapping) failed, but the exception store did not record it. | Zero matches in exception store; exception store is not exhaustive. | Failure could be silent. |
| The invoice was generated but not yet committed to the canonical store at the time of the portal query. | Telemetry export errors indicate export queue reached capacity; some events may have been delayed. | The record could appear later. |
| The invoice was generated for a different account or billing period due to a mapping error. | Portal found March invoice; April invoice might be under a different account/period. | Requires checking canonical store. |

**3. What does the zero‑match exception‑store lookup tell us, and what does it not tell us?**  

*Tells us:*  
- No exception records were written for the combination of batch B‑8821 and source reference `INV‑SRC‑77831` at the time of the lookup.  
- The exception store did not capture any failure for that specific key.

*Does not tell us:*  
- Whether the invoice processing succeeded or failed.  
- Whether the exception store is complete or if failures were omitted.  
- Whether the normalizer job finished or if the invoice was still in flight.  

**4. Single best first diagnostic check (concrete, read‑only)**  

> **Query the canonical invoice store for the source reference `INV‑SRC‑77831`.**  
> Inspect the returned record (if any) for:  
> - `account_id`  
> - `billing_period`  
> - `commit_time` (or equivalent timestamp)  
> - `status` or disposition flag  

**5. Interpretation of possible outcomes**

| Outcome | Interpretation |
|---------|----------------|
| **a. Record found with account ACCT‑1042 and period 2026‑04** | The invoice exists in the canonical store but the portal is not retrieving it—likely a portal‑query or caching issue. Verify portal query logic and cache invalidation. |
| **b. Record found under a different account or period** | A mapping or assignment error occurred during normalization. Investigate the mapping rules for batch B‑8821 and source reference `INV‑SRC‑77831`. |
| **c. No record found** | The invoice has not yet been committed to the canonical store (processing still in flight) or was never generated. Next read‑only check: query the normalizer job status for batch B‑8821 (e.g., via job‑status API or logs) to confirm completion. If the job is still running, wait; if it has failed, investigate failure logs. |

**6. Actions to avoid until the relevant state is verified**  

- Do **not** replay the batch or reset consumer offsets.  
- Do **not** purge or reset the export queue.  
- Do **not** manually create or modify invoices.  
- Do **not** change account‑mapping configurations.  
- Do **not** restart services or perform system restarts.  
- Do **not** force a consumer rebalance or refresh the portal cache.  

These actions could alter the data state or mask the underlying issue; they should only be considered after the read‑only diagnostics confirm the current state.
