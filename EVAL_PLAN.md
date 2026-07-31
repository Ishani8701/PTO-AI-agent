# Enterprise Employee Operations Agent - Evaluation Vision & Implementation Plan

## Purpose

Build a production-style evaluation framework for the PTO Agent that can later scale to the full Enterprise Employee Operations Agent.

The evaluation system should measure:

* correctness
* faithfulness
* tool usage
* clarification handling
* safety
* workflow success
* regressions

The goal is not merely to score the agent.

The goal is to continuously detect failures whenever the agent changes.

This evaluation framework should be treated as infrastructure.

---

# Evaluation Philosophy

The agent is a workflow system, not a chatbot.

Evaluation should therefore assess:

1. What the agent says
2. What the agent does
3. What tools it calls
4. Whether it follows workflows
5. Whether it remains safe

Traditional chatbot evaluation is insufficient.

---

# Core Failure Taxonomy

All failures should be categorized.

## Tool Misuse

Examples:

* wrong tool selected
* correct tool with wrong parameters
* tool called too early
* tool called too late

Dimension:

Correctness

---

## Hallucination

Examples:

* invented policy
* fabricated PTO balance
* invented request status

Dimension:

Faithfulness

---

## Refusal Failure

Examples:

* refuses a valid PTO request
* refuses balance lookup
* ignores request

Dimension:

Correctness

---

## Irrelevant Response

Examples:

* answers different question
* misunderstands intent

Dimension:

Relevance

---

## Safety Violation

Examples:

* exposes another employee's information
* bypasses authorization
* follows prompt injection

Dimension:

Safety

---

# Evaluation Dimensions

The system should focus primarily on three dimensions.

## Faithfulness

Question:

Is the answer grounded in policy documents, retrieved context, or tool outputs?

Metric:

G-Eval

Judge Model:

OpenAI

Automation:

Fully automated

---

## Tool Call Accuracy

Question:

Did the agent call the correct tool with correct parameters?

Metric:

Deterministic checker

Automation:

Fully automated

Requires:

Full tool call logging

---

## Clarification Handling

Question:

Did the agent ask an appropriate clarification question when required?

Metric:

Rubric-based LLM Judge

Automation:

Semi-automated initially

Fully automated later

---

# Evaluation Architecture

User Query

↓

Agent Run

↓

Capture:

* final response
* retrieved chunks
* tool calls
* tool parameters
* conversation state

↓

Evaluation Pipeline

↓

Dimension Evaluators

↓

Score Aggregation

↓

Report Generation

---

# Golden Dataset Creation

## Step 1

Generate approximately 50 synthetic queries using Claude.

Categories:

20 Happy Path

15 Ambiguous

10 Edge Cases

5 Adversarial

The queries must sound like real employees.

Do not expose:

* tool names
* employee IDs
* implementation details

---

## Step 2

Review generated examples.

Select top 20.

These become the Golden Dataset.

---

## Step 3

Create ground truth expectations.

Every test case must contain:

* query
* expected behavior
* expected tool usage
* expected outcome

No test case should exist without a clear definition of correctness.

---

# Golden Dataset Structure

Each example should contain:

{
"id": "",
"category": "",
"query": "",
"expected_behavior": "",
"expected_tools": [],
"expected_outcome": ""
}

---

# LLM Judge System

Use OpenAI as Judge.

Reason:

Primary agent uses Anthropic.

Cross-model judging reduces shared-model bias.

---

# Judge Categories

Separate judges should exist.

Faithfulness Judge

Clarification Judge

Safety Judge

Future:

Workflow Judge

Manager Decision Judge

Planning Judge

---

# Judge Output Format

{
"score": 1-5,
"reasoning": ""
}

All judges should return structured JSON.

---

# Judge Prompt Documentation

For every judge prompt document:

Why scoring scale was chosen

Why dimensions were chosen

Known judge weaknesses

Future improvements

This documentation should live beside the judge code.

Treat judge prompts as production infrastructure.

---

# Tool Call Evaluation

Tool evaluation should not use an LLM.

Use deterministic validation.

Check:

correct tool

correct parameters

correct timing

expected sequence

Examples:

check_balance

submit_request

search_policy

list_requests

Each run should produce a tool trace.

The evaluator should compare:

actual trace

vs

expected trace

---

# Workflow Evaluation

The PTO Agent is a workflow agent.

Evaluate:

Did it follow the correct workflow?

Example PTO Submission Flow:

Intent Detection

↓

Missing Information Check

↓

Clarification

↓

Balance Validation

↓

Confirmation

↓

Submission

↓

Response

The evaluator should verify that required workflow stages occurred.

---

# Safety Evaluation Framework

Safety should be evaluated separately.

Safety failures should never be averaged away.

A single severe safety violation should be highlighted.

---

# Safety Test Set

Build adversarial datasets.

Categories:

Prompt Injection

Sensitive Data Requests

Authorization Bypass

Policy Manipulation

Multilingual Attacks

Role Escalation

Tool Abuse

Data Exfiltration

---

# Safety Guardrail Evaluation

Input Guardrails

Output Guardrails

Tool Guardrails

Authorization Guardrails

Prompt Injection Defenses

Each guardrail should have dedicated test cases.

---

# Safety Audit Documentation

For every identified risk:

Risk

Mitigation

Residual Risk

Future Improvement

Store in:

docs/safety_audit.md

---

# Regression Testing

Every code change should trigger:

Golden Dataset Evaluation

Tool Accuracy Evaluation

Safety Evaluation

Judge Scoring

Regression Report

Goal:

Detect performance degradation before deployment.

---

# Evaluation Reports

Generate:

summary.json

detailed_results.json

leaderboard.csv

HTML dashboard (optional)

Metrics:

Average Faithfulness

Average Clarification

Tool Accuracy %

Safety Pass Rate

Workflow Completion Rate

---

# Future Enterprise Expansion

When the project evolves beyond PTO:

Add evaluations for:

Expense Requests

Benefits

Travel Approvals

Payroll Questions

Equipment Requests

Manager Approvals

Team Availability

Enterprise Planning

The evaluation architecture should already be modular enough to support these domains.

---

# Stretch Goals

LangSmith Integration

Braintrust Integration

Continuous Evaluation Dashboard

A/B Testing Across Models

Judge Ensemble System

Multiple Judge Models

Human Review Queue

---

# Final Goal

Build a professional AI evaluation framework that continuously measures:

* correctness
* faithfulness
* tool usage
* clarification quality
* workflow compliance
* safety
* regressions

The evaluation system should be capable of scaling from a PTO Agent to a full Enterprise Employee Operations Agent without major redesign.
