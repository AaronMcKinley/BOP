# BOP Development Rules

## Session startup — every new conversation

At the very start of every new conversation, before anything else:

1. Read `AGENTS.md` — these rules are auto-loaded by Cline, but re-read the file from disk to confirm you have the latest version.
2. Read `README.md` — the project overview, pipeline, and data contracts.
3. Only then proceed with the user's task.

## Core goal

BOP should turn a song into an engaging, polished, short-form video.

The most important measure of success is the quality of the finished video:
- visually polished
- satisfying motion
- strong beat synchronization
- good pacing
- engaging from beginning to end
- feels intentionally designed rather than procedurally generated

The end goal is:

song → BOP → engaging finished video

Do not sacrifice the quality of the final result unnecessarily for the sake of simplicity.

However, do not add complexity just because it is technically possible.

Prefer the simplest implementation that can produce the desired finished result.


## Workspace boundary

The BOP project root is:

`~/BOP`

Only inspect, modify, or operate on files inside the BOP project directory.

Do NOT search, inspect, modify, or read files elsewhere in the filesystem unless I explicitly ask you to.

In particular, do not inspect:
- my home directory
- other projects
- server files
- SSH configuration
- personal files
- unrelated Git repositories
- system files

For normal BOP tasks, restrict file operations to the current BOP workspace.

If you believe something outside the BOP workspace is required, stop and ask me before accessing it.

## Development workflow

We work ONE STEP AT A TIME.

A step should normally be as small as one function, one tightly related group of functions, or one small piece of functionality.

Before making changes:

1. Inspect only the files relevant to the current step.
2. Explain what you found in plain language.
3. Explain what you intend to change.
4. Explain how we will test it.
5. Wait for my approval.

After I approve:

1. Implement ONLY that step.
2. Do not continue automatically.
3. Do not implement future steps "while you're here."
4. Tell me exactly what changed.
5. Tell me exactly how to test it.
6. Stop and wait for my result.

I will test each step before giving approval for the next step.

If a requested step is too large, break it into smaller steps and ask me which one to do first.

## Keep the project simple

Prefer:
- straightforward code
- small functions
- clear data structures
- existing Python/Godot functionality
- minimal dependencies
- stable interfaces

Avoid:
- unnecessary abstractions
- premature optimization
- unnecessary frameworks
- complicated architecture
- large refactors
- adding systems before they are needed

Do not make a system more complicated merely because a more sophisticated implementation exists.

The question should always be:

"Does this improve the finished video or meaningfully improve the ability to build it?"

If not, prefer the simpler solution.

## Protect the finished product

Simplicity must NOT come at the expense of the final visual result.

When there is a choice between:
- a simple implementation that produces a noticeably worse final result
- a somewhat more complex implementation that substantially improves the finished video

prefer the better visual result.

Explain the tradeoff before making the change.

The final video is the product. The code is the means to create it.

## BOP architecture

Read README.md before making architectural decisions.

The intended pipeline is:

song
↓
audio analysis
↓
timeline.json
↓
physics simulation / selection
↓
events.json
↓
Godot rendering
↓
FFmpeg
↓
finished video

Python handles:
- audio analysis
- beat detection
- energy analysis
- physics simulation
- scoring
- seed selection

Godot 4 handles:
- visual rendering
- arena
- balls
- shaders
- trails
- particles
- glow
- visual effects

FFmpeg handles:
- audio/video muxing
- loudness normalization
- final encoding
- platform export

Keep these stages independently executable.

## Data contracts

`timeline.json` and `events.json` are important interfaces between stages.

Do not change their schemas without discussing the change with me first.

Prefer preserving existing interfaces over making downstream code depend on implementation details.

## Testing

Every meaningful change should be testable.

For simulation and logic:
- add or update appropriate tests
- run the relevant tests
- verify deterministic behavior where applicable

For rendering:
- produce a small test render when practical
- visually inspect the result

Do not assume something works because the code looks correct.

## Code quality

Write code that is understandable to a person learning the project.

Use descriptive names.

Keep functions focused.

Avoid clever code when straightforward code is available.

Comments should explain WHY something is necessary, not simply repeat what the code does.

## Changes and refactoring

Do not modify unrelated files.

Do not refactor working code unless the current step requires it.

Do not rewrite large portions of the project to solve a small problem.

If you believe a larger architectural change is necessary:
1. Stop.
2. Explain the problem.
3. Explain the proposed alternatives.
4. Wait for my approval.

## Git

Do not rewrite Git history.

Do not delete working code without explaining why.

Do not commit:
- songs
- generated videos
- generated simulation output
- API keys
- passwords
- other secrets

## Communication

Explain technical concepts in plain language.

Do not assume I understand something just because it is common knowledge to an experienced programmer.

If there are multiple reasonable approaches, briefly explain the options and recommend one.

If something is uncertain, say so.

If you discover a problem with the existing plan or architecture, tell me rather than silently changing direction.

## Efficient use of AI and tools

Use reasoning, file inspection, searches, and terminal commands when they improve the quality or reliability of the result.

Do not avoid necessary investigation simply to save tokens.

However, avoid unnecessary work and context.

Before reading files or running commands, consider whether they are actually relevant to the current task.

Prefer:
- targeted file reads over scanning the whole repository
- targeted searches over broad searches
- one useful command over several redundant commands
- existing information over re-discovering it
- simple verification when the change is simple

Do not perform "just in case" investigation.

Do not inspect unrelated parts of the project.

Do not repeatedly read files that have already been read and have not changed.

Do not repeatedly verify something that is already clearly successful.

For simple tasks, keep investigation, implementation, and verification proportional to the task.

For complex tasks, investigate as much as necessary to produce a good solution.

Quality of the finished product takes priority over token savings when additional reasoning or investigation is genuinely useful.

## Golden rule

One small change.

Test it.

Understand it.

Then move on.