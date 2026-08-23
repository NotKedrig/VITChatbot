# Aether Robotics — Technical Preparation Guide for Campus Candidates

## Overview

This guide covers the technical skills assessed during Aether's campus recruitment
process. Because Aether's roles span embedded systems, perception algorithms, and
cloud software, preparation varies significantly by target role.

## Embedded Software Engineer (ESE) — Preparation Guide

### Core C/C++ Topics

Embedded firmware at Aether is written almost entirely in C and modern C++ (C++17).
Candidates should be fluent in:

- **Memory management**: stack vs. heap allocation, dynamic memory in embedded contexts
  (why `malloc` is often avoided on constrained platforms), memory-mapped I/O.
- **Pointers and references**: pointer arithmetic, const-correctness, dangling pointers,
  and how to avoid them.
- **Volatile and volatile-qualified variables**: why `volatile` is needed for
  memory-mapped registers and interrupt service routine (ISR) flag variables.
- **Bit manipulation**: setting, clearing, toggling, and testing individual bits;
  extracting bitfields from registers.
- **Inline assembly**: basic ARM assembly for critical sections; candidates are not
  expected to write complex assembly but should understand calling conventions.

### Real-Time Operating Systems (RTOS)

Aether uses FreeRTOS on most of its robot controller boards. Interview topics include:

- **Tasks and scheduling**: preemptive priority scheduling, task creation, deletion, and
  suspension; why task priorities must be chosen carefully to avoid priority inversion.
- **Inter-task communication**: queues, semaphores (binary and counting), and mutexes;
  when to use each.
- **Interrupt service routines**: restrictions on what can be done inside an ISR,
  deferring work to a task using a semaphore, safe API calls from ISR context
  (e.g., `xSemaphoreGiveFromISR` in FreeRTOS).
- **Watchdog timers**: purpose, configuration, and the risk of accidentally disabling
  a watchdog in production firmware.

### ROS 2 (Nice to Have)

Candidates with ROS 2 experience should be prepared to discuss the publish/subscribe
model, the difference between topics and services, and how to write a simple publisher
and subscriber node in Python or C++.

## Perception and Planning Engineer (PPE) — Preparation Guide

### Mathematics Foundations

PPE candidates are assessed more heavily on mathematics than on general software
engineering. Ensure you are comfortable with:

- **Linear algebra**: matrix multiplication, eigenvalues and eigenvectors, singular
  value decomposition (SVD), and when each is relevant.
- **Probability and statistics**: Bayes' theorem, Gaussian distributions, conditional
  independence, expectation and variance.
- **Estimation theory**: the Kalman filter derivation (know the predict-update cycle,
  the role of the covariance matrix, and when the assumptions break down).
- **Optimisation basics**: gradient descent, convexity, and why convex problems are
  tractable.

### Computer Vision and SLAM

- Feature extraction: SIFT vs. ORB, why ORB is preferred for real-time robotics.
- Point cloud processing: understanding of a basic ICP (Iterative Closest Point)
  algorithm.
- SLAM fundamentals: distinguish between filter-based SLAM (Extended Kalman Filter SLAM)
  and graph-based SLAM; Aether uses a graph-based approach internally.
- Coordinate transforms: homogeneous coordinates, rotation matrices, quaternions,
  and when to use each representation.

### Coding for PPE

PPE candidates may be asked a Python problem involving numpy. Common exercise types:
- Implement matrix operations from scratch (without numpy) to test mathematical
  fluency, then discuss how numpy vectorisation makes it faster.
- Write a simple particle filter for 1D localisation.
- Implement a basic convolution operation for image processing.

## Cloud and Fleet Software Engineer (CFSE) — Preparation Guide

### Backend Engineering

CFSE candidates should be comfortable with:
- REST API design: idempotency, HTTP methods, status codes, pagination strategies.
- Concurrency: goroutines and channels in Go; or Python asyncio; thread safety.
- Database design: normalization, indexing strategy, query optimisation.
- Message queues: producer/consumer patterns, at-least-once vs. exactly-once delivery,
  offset management in Kafka.

### Distributed Systems

For CFSE, Aether assesses a foundational understanding of distributed-systems concepts:
- CAP theorem: what it means in practice, examples of CP and AP systems.
- Consistency models: strong consistency, eventual consistency, and read-your-writes.
- Leader election: why it is needed, high-level concept of Raft or Paxos (not derivation).

### Kubernetes Basics

Aether's fleet cloud runs on Kubernetes. CFSE candidates should understand:
- Pod, Deployment, Service, and ConfigMap primitives.
- How horizontal pod autoscaling (HPA) works and what metrics drive it.
- Rolling updates and rollback strategy.

## Common Interview Mistakes Across All Roles

1. **Claiming expertise you cannot demonstrate**: interviewers probe any claim one level
   deeper. Say "I have some familiarity with X" rather than "I know X well" if
   you're not prepared for depth questions.

2. **Silence under pressure**: Aether interviewers expect candidates to think aloud.
   A candidate who says nothing for two minutes while staring at a problem is scored
   lower than one who verbalises a wrong approach and self-corrects.

3. **Ignoring constraints**: in embedded and robotics contexts, resource constraints
   (memory, CPU cycles, power) are as important as correctness. Ignoring them in
   answers signals unfamiliarity with the domain.

4. **Not asking clarifying questions**: every real engineering problem has ambiguities.
   Asking one or two targeted clarifying questions before designing a solution is
   expected and rewarded.
