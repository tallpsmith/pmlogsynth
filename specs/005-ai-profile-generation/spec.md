# Feature Specification: AI-Driven Profile Generation

**Feature Branch**: `005-ai-profile-generation`
**Created**: 2026-03-03
**Status**: Draft
**Input**: User description: "Allow users to generate pmlogsynth profiles from natural language descriptions using an AI agent, with support for Claude, ChatGPT, Gemini, and local models."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Natural Language Archive Creation via Claude (Priority: P1)

A performance engineer wants to create a realistic PCP archive for testing or demonstration purposes. Rather than hand-crafting YAML, they describe the desired workload characteristics in plain English to a Claude-based AI agent. The agent generates a valid pmlogsynth profile and invokes pmlogsynth to produce the archive.

**Why this priority**: This is the core value proposition of the feature. If this works, users can stop fiddling with YAML and start describing what they actually want in human terms. P1 because it's the fastest path to a working demonstration and the most likely entry point for new users.

**Independent Test**: A user can describe a workload in natural language, receive a generated profile file, and confirm that pmlogsynth successfully produces an archive from it — without any manual YAML editing.

**Acceptance Scenarios**:

1. **Given** a user is running a Claude-enabled session, **When** they describe a workload (e.g. "a week-long SaaS archive with diurnal load patterns and a CPU spike at 2:30pm"), **Then** a valid pmlogsynth YAML profile is generated that captures the described characteristics.
2. **Given** a generated profile, **When** it is passed to pmlogsynth, **Then** pmlogsynth produces a valid PCP archive without errors.
3. **Given** a description including correlated metrics (e.g. "disk IOPS spikes with CPU"), **When** the profile is generated, **Then** the profile encodes the correlated anomaly across the relevant metric domains.
4. **Given** an ambiguous or incomplete description, **When** the AI agent generates a profile, **Then** the agent either prompts the user for clarification or applies documented defaults and informs the user of assumptions made.

---

### User Story 2 - Profile Generation with Schema-Aware Context (Priority: P2)

A PCP contributor or power user wants to generate profiles without being tied to Claude. They want the AI agent of their choice — including locally-hosted open-source models — to understand the pmlogsynth profile schema and produce valid output.

**Why this priority**: The PCP community is open-source first. If the feature only works with a commercial Claude subscription, adoption by the target community will be limited. Providing a schema-aware context mechanism (e.g. a system prompt document or schema file) that any AI agent can consume makes the feature broadly usable.

**Independent Test**: A user can provide the pmlogsynth schema context to any AI agent, describe a workload, and receive a profile that passes `pmlogsynth --validate` — without using Claude specifically.

**Acceptance Scenarios**:

1. **Given** a pmlogsynth schema reference document is available, **When** it is provided to any capable AI agent as context, **Then** the agent can generate profiles that conform to the schema.
2. **Given** a locally-hosted open-source model with sufficient context, **When** a user describes a workload, **Then** the model produces a profile that passes pmlogsynth validation.
3. **Given** a generated profile from any AI agent, **When** it fails validation, **Then** the validation error message is informative enough for the AI agent to self-correct on a second attempt.

---

### User Story 3 - Iterative Refinement of Generated Profiles (Priority: P3)

A user generates an initial profile but wants to adjust it — adding more noise, changing the spike duration, or tweaking the diurnal shape — without starting from scratch.

**Why this priority**: The first-pass generation may not be perfect. Users should be able to iterate on a generated profile conversationally, refining it until it meets their needs.

**Independent Test**: A user can take an existing profile and ask the AI agent to modify specific aspects (e.g. "make the CPU spike last 20 minutes instead of 10"), and receive an updated, valid profile.

**Acceptance Scenarios**:

1. **Given** an existing pmlogsynth YAML profile, **When** a user asks the AI agent to modify a specific characteristic, **Then** the updated profile retains all unchanged sections and correctly reflects the requested modification.
2. **Given** an updated profile, **When** it is passed to pmlogsynth, **Then** the archive reflects the modification.

---

### Edge Cases

- What happens when the AI generates a profile with metric names that do not exist in the pmlogsynth domain model?
- What happens when the described time range or sampling interval would produce an archive that exceeds practical size limits?
- What happens when the AI generates structurally valid YAML that fails pmlogsynth schema validation (e.g. missing required fields)?
- What happens when the natural language description contains contradictory constraints (e.g. "5-minute archive with hourly samples")?
- What happens when a local model produces partial or malformed YAML output?

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Users MUST be able to describe desired archive characteristics in plain natural language and receive a valid pmlogsynth YAML profile in response.
- **FR-002**: The system MUST provide AI agents with sufficient context about the pmlogsynth profile schema to enable correct profile generation without prior training on pmlogsynth.
- **FR-003**: The system MUST support Claude-based AI agents as the primary integration path.
- **FR-004**: The system MUST provide a `--show-schema` flag that prints a self-contained schema context document to stdout, enabling users to pipe or paste it into any AI agent as a system prompt. The output MUST be sufficient for a capable AI agent to generate valid profiles without any additional reference material.
- **FR-005**: Generated profiles MUST be validated against the pmlogsynth schema before being passed to the archive generation step.
- **FR-006**: When validation fails, the user or AI agent MUST receive actionable error messages sufficient to enable correction.
- **FR-007**: The system MUST support correlated anomaly descriptions — where one metric domain's behaviour is described as dependent on another (e.g. disk IOPS correlated with CPU spikes).
- **FR-008**: The system MUST accept descriptions specifying: time span, sampling interval, diurnal load patterns, named anomaly events (spikes, drops, saturation), and inter-metric correlations.
- **FR-009**: Users MUST be able to iteratively refine an existing profile via additional natural language instructions without regenerating from scratch.
- **FR-010**: The schema context document describing the pmlogsynth profile format MUST be versioned and kept in sync with the profile schema.

### Key Entities

- **Natural Language Prompt**: The user-supplied plain-text description of the desired archive characteristics, including workload shape, time range, anomaly events, and metric correlations.
- **Schema Context Document**: A machine-readable (and human-readable) description of the pmlogsynth profile YAML schema, including field definitions, constraints, valid metric names, and annotated examples. Consumed by AI agents to enable accurate profile generation.
- **Generated Profile**: A pmlogsynth-compatible YAML file produced by an AI agent in response to a natural language prompt. Subject to validation before archive generation.
- **Validation Report**: Structured feedback produced when a generated profile fails schema validation, designed to be actionable by both humans and AI agents.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user with no prior pmlogsynth YAML experience can generate a valid archive from a plain English description in under 5 minutes.
- **SC-002**: At least 80% of first-attempt AI-generated profiles pass pmlogsynth validation without manual correction.
- **SC-003**: Generated profiles correctly capture all specified characteristics (time range, diurnal pattern, anomaly events, correlations) as verified by inspection of the resulting archive with standard PCP tools.
- **SC-004**: A user running a locally-hosted open-source AI model can generate a valid profile using only the provided schema context document, without access to Claude or any commercial AI service.
- **SC-005**: Iterative refinement — modifying an existing profile via natural language — produces a correct updated archive within one additional prompt exchange.

## Assumptions

- The pmlogsynth profile YAML format is sufficiently stable to document as a schema reference without requiring frequent updates.
- AI agents with sufficient context window (approximately 8k tokens) can generate valid profiles from schema documentation alone.
- The initial Claude-based integration uses Claude Code skills as the primary delivery mechanism; generalization to other agents follows the same schema-context approach.
- "Local models" means models running via compatible local inference servers (e.g. Ollama, llama.cpp); API compatibility is assumed, not embedded model support.
- Profile validation via `pmlogsynth --validate` provides sufficient error detail to enable AI-agent self-correction.

## Out of Scope

- Training or fine-tuning AI models on pmlogsynth profiles.
- A graphical or web-based interface for natural language profile generation.
- Automatic selection of AI agent based on availability or cost.
- Support for generating profiles that reference metrics outside the current pmlogsynth domain model.
