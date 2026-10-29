# Company Vendor Futures Enhancement Plan

1. Add tests for source classification, calendar isolation, coverage gates, protected outputs, and numeric-evaluation isolation.
2. Build an independent enhancement bundle from the Wind calendar, contract metadata, EOD schema, and existing candidate registry.
3. Emit pending archive requests for event-02 and event-06 when historical EOD coverage is unavailable.
4. Run focused and regression tests, then verify protected output fingerprints and `formal_ready=false`.
