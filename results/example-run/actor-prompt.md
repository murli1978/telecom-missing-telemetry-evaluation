Incident: INC-2047
Reported: 2026-05-04 09:20 UTC
Customer: Enterprise account ACCT-1042
Symptom: The April invoice is not visible in the billing portal.

Expected invoice:
- Billing period: 2026-04
- Source billing reference: INV-SRC-77831
- Expected account: ACCT-1042
- Batch: B-8821

Processing and portal evidence:

09:02:11 UTC  billing-feed-gateway
batch_id=B-8821
source_system=NorthstarBilling
status=accepted
records_received=10240
records_rejected=0

09:05:43 UTC  invoice-normalizer
batch_id=B-8821
event=job_started
worker_pool=norm-prod-3

09:06–09:14 UTC  telemetry-collector
source=norm-prod-3
export_errors=observed
detail=export queue reached capacity; some worker events may not have been exported

09:15:00 UTC  billing-exception-store
lookup=batch_id:B-8821, source_reference:INV-SRC-77831
matching_exception_records=0

09:19:11 UTC  portal-invoice-api
account_id=ACCT-1042
billing_period=2026-04
result=invoice_not_found
http_status=200

09:19:54 UTC  portal-invoice-api
account_id=ACCT-1042
billing_period=2026-03
result=invoice_found
http_status=200

System context:
- Mapping exceptions are normally written to the billing-exception-store, but the store is not claimed to capture every possible processing failure.
- The 09:15 lookup is a point-in-time result. The normalizer's completion state at that time is unknown.
- Telemetry collector export errors affect observability events. The evidence does not say the collector carries or blocks invoice business data.
- Batch IDs are identifiers; their queue ordering semantics are not specified in this packet.
- No query has yet been made to the canonical invoice store for INV-SRC-77831.

Telemetry note:
No normalization completion event for batch B-8821 is present in the available logs.

You are assisting an on-call engineer investigating a billing-portal incident.

Use only the evidence packet. Separate observed facts from hypotheses. Missing telemetry is not proof that an operation failed or succeeded. Do not infer that telemetry export problems blocked invoice processing.

Answer:
1. What is established by the evidence?
2. What are the plausible explanations? You may rank them only if the evidence supports a ranking; otherwise say they cannot be ranked confidently.
3. What does the zero-match exception-store lookup tell us, and what does it not tell us?
4. What is the single best first diagnostic check? Make it concrete and read-only.
5. How would you interpret these possible outcomes of that check?
   a. The record is found with the expected account and billing period.
   b. The record is found under a different account or billing period.
   c. No record is found.
6. What actions should be avoided until the relevant state is verified?

For the first check, search the canonical invoice store by source reference INV-SRC-77831, not only by expected account and period. Check the record's disposition, stored account, billing period, and commit time. An absent record at one instant does not by itself prove processing failure; the job may still be in flight. State what further read-only status check would be appropriate for that outcome.

Do not recommend a batch replay, offset reset, queue purge, manual invoice creation, account-mapping change, restart, refresh, or consumer rebalance as a diagnostic step.
