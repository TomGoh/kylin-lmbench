# Campaign aborted

- Campaign: `d3000-apps-20260713-111300`
- Aborted: 2026-07-14 during leg 5, Pair 2/protected Geekbench
- Reason: RabbitMQ Q3 applied the intended aggregate rate to each of 8 producers, so all Q3 points were saturated; Q5 used unsupported PerfTest message-count options and did not run despite false `VALID` markers.
- Disposition: preserve all raw data for audit only; do not include this campaign in formal pKVM results.
- Replacement: patch and verify Q3/Q5, then start a new campaign from calibration leg 1.
