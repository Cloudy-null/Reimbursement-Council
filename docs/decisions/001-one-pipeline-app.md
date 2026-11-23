# 001: One pipeline app instead of services or a single agent

Date: 2026-11-23
Status: Accepted

## Context
We have a few nights to build and must measure every idea. The judges see the demo, not the infrastructure.

## Options
A. One Python service with stages in order (read, rules, council, decide, explain), one database, three screens.
B. Event-driven pipeline with a queue, separate workers and a small warehouse.
C. One AI agent with tools that decides by itself.

## Choice
A.

## Trade-off
A is less impressive on an architecture slide than B. We accept that because A is far more likely to fully work and be tested by day 5. Each stage has a clean boundary, so splitting into B later is straightforward. C was dropped because it makes decisions hard to repeat and hard to measure, which goes against weighted votes, calibration and ablation testing.
