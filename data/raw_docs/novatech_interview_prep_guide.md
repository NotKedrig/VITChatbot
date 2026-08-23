# NovaTech Solutions — Technical Interview Preparation Guide

## Purpose

This document is intended to help candidates who have cleared the NovaTech online
assessment prepare for the two technical interview rounds. It covers the commonly
tested topics, advice on how interviewers evaluate answers, and practical preparation
strategies.

## What NovaTech Interviewers Value

NovaTech's engineering culture prizes clarity of thinking over rote knowledge. In
interviews, candidates who explain their reasoning step-by-step, identify edge cases
voluntarily, and discuss time/space complexity unprompted consistently score better than
candidates who arrive at a correct solution without articulating their thought process.

Interviewers are explicitly trained to probe depth: if you mention a concept, expect
a follow-up question one level deeper. Claiming familiarity with a topic you cannot
explain in detail is penalised.

## Data Structures and Algorithms

### Frequently Tested Topics

- **Arrays and strings**: two-pointer technique, sliding window, in-place operations.
- **Linked lists**: reversal, cycle detection (Floyd's algorithm), merging sorted lists.
- **Trees and binary search trees**: level-order traversal, lowest common ancestor,
  validating a BST, constructing a tree from traversal sequences.
- **Graphs**: BFS and DFS (both iterative and recursive), cycle detection in directed
  and undirected graphs, topological sort (Kahn's algorithm and DFS-based).
- **Dynamic programming**: top-down memoization vs. bottom-up tabulation; classic
  problems include longest common subsequence, 0/1 knapsack, and coin change.
- **Heaps and priority queues**: kth-largest element, merge k sorted arrays.
- **Hashing**: frequency counting, two-sum variants, subarray with given sum.

### Tips for the Coding Problems

1. Restate the problem and confirm your understanding before writing any code.
2. Discuss brute-force first, then optimize — NovaTech interviewers prefer seeing
   the progression from naïve to efficient over jumping to an optimal solution without
   explanation.
3. Test your code on the given example and at least one edge case (empty input, single
   element, all identical values) before declaring it complete.
4. Java, Python, and C++ are accepted. The interviewer may ask you to implement a
   specific method that does not exist in the standard library to gauge language depth.

## Object-Oriented Design

Round 1 typically includes a 10–15 minute object-oriented design question. Common
scenarios at NovaTech:

- Library management system (books, members, reservations, fines).
- Parking lot system (vehicle types, floor allocation, pricing).
- Online food ordering system (restaurants, menus, orders, delivery tracking).
- Ride-sharing platform (riders, drivers, trip lifecycle, pricing surge).

Candidates are assessed on:
- Identifying entities and their relationships correctly.
- Appropriate use of inheritance vs. composition.
- Application of at least one design pattern (Strategy, Observer, Factory, or Singleton
  are the most commonly discussed).
- Thinking about extensibility: "What if we needed to add feature X?"

## System Design (Round 2)

For fresher candidates, NovaTech scopes system-design questions to subsystem or
component design rather than full distributed-system architecture.

Common Round 2 system design topics:
- Design a URL shortener (focus: hash function, collision handling, database schema).
- Design a simple rate limiter (focus: algorithm choice — token bucket vs. sliding window,
  storage layer for counters).
- Design a notification system (focus: queue-based decoupling, fan-out patterns,
  delivery guarantees).

### What to Cover in a System Design Answer

1. **Clarify requirements**: functional requirements first, then non-functional
   (scale, latency, consistency needs).
2. **High-level design**: identify the main components and how data flows between them.
3. **Data model**: describe the key tables or document schemas.
4. **API design**: sketch the primary endpoints (method, path, request/response shape).
5. **Trade-offs**: name at least one alternative design choice and explain why you
   prefer your approach.

## Database Concepts

Expect one SQL writing question in Round 2 — typically a multi-table join with
aggregation. Topics covered in MCQ or verbal discussion:

- Normal forms (1NF through 3NF; BCNF for stronger candidates).
- Index types: B-tree vs. hash; when a composite index helps and when it doesn't.
- Transaction isolation levels (Read Uncommitted, Read Committed, Repeatable Read,
  Serializable) and the anomalies each prevents.
- Basic query optimization: avoiding SELECT *, using EXPLAIN, identifying slow queries.

## Project Discussion

Prepare a 3-minute narrative for your strongest project:
1. What problem does it solve and for whom?
2. What was your specific contribution (not the team's)?
3. What technical decisions did you make and why?
4. What would you do differently if starting over?

Interviewers are trained to follow up on any claim with "how exactly?" — be specific
about libraries, algorithms, or architectural choices.
