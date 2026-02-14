# Agent Research - System Architecture

## Overview

This document describes the technical architecture of the A2S (Agent-to-Skills) framework and its implementation in the StuLife campus environment.

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Root Agent (LLM)                        │
│  - Task understanding and decomposition                    │
│  - Manager selection and routing                           │
│  - High-level decision making                              │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                   Specialized Managers                      │
├─────────────┬──────────────┬──────────────┬────────────────┤
│ Navigation  │  Course      │   Email      │  Calendar      │
│  Manager    │  Selection   │   Manager    │  Manager       │
│             │   Manager    │              │                │
└─────────────┴──────────────┴──────────────┴────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                   Specialized Workers (22)                  │
├───────────┬───────────┬───────────┬───────────┬────────────┤
│ Navigation│ Course    │ Email     │ Calendar  │ Reservation │
│  Workers  │  Workers  │  Workers  │  Workers  │   Workers   │
│  (5)      │  (4)      │  (3)      │  (3)      │    (3)      │
└───────────┴───────────┴───────────┴───────────┴────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                      Environment API                        │
│  - Campus locations                                         │
│  - Course catalog                                           │
│  - Email system                                             │
│  - Calendar system                                          │
│  - Reservation system                                       │
└─────────────────────────────────────────────────────────────┘
```

## Core Components

### 1. Root Agent

**Purpose**: Top-level decision making and task routing

**Responsibilities**:
- Understand high-level task requirements
- Decompose complex tasks into subtasks
- Select appropriate managers for execution
- Coordinate multi-step workflows
- Handle failure recovery

**Key Features**:
- LLM-based reasoning (not keyword matching)
- Context-aware routing
- Dynamic task decomposition
- Memory-guided decisions

**File**: `design/A2S/Stulife/agents/root_agent.py`

### 2. Specialized Managers

#### NavigationManager
**Purpose**: Handle all campus movement tasks

**Workers**:
- `WalkingWorker`: Basic walking between locations
- `NavigationWorker`: Route planning and execution
- `PathPlanningWorker`: Optimal path calculation
- `LocationFinderWorker`: Find specific locations
- `BuildingFinderWorker`: Find buildings

**File**: `design/A2S/Stulife/agents/managers/navigation_manager.py`

#### CourseSelectionManager
**Purpose**: Manage course registration and scheduling

**Workers**:
- `CourseQueryWorker`: Search and query courses
- `RegistrationWorker`: Handle registration process
- `ScheduleWorker`: Manage course schedules
- `DropAddWorker`: Handle drop/add operations

**File**: `design/A2S/Stulife/agents/managers/course_selection_manager.py`

#### EmailManager
**Purpose**: Handle email communication

**Workers**:
- `SendEmailWorker`: Compose and send emails
- `ReadEmailWorker`: Read and parse emails
- `SearchEmailWorker`: Search email history

**File**: `design/A2S/Stulife/agents/managers/email_manager.py`

### 3. ReMe Memory System

```
┌──────────────────────────────────────────────────────────────┐
│                    ReMe Memory System                        │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐ │
│  │  Task Memory   │  │  Tool Memory   │  │Personal Memory │ │
│  ├────────────────┤  ├────────────────┤  ├────────────────┤ │
│  │ - Task history │  │ - Capabilities │  │ - Preferences  │ │
│  │ - Strategies   │  │ - Usage stats  │  │ - Goals        │ │
│  │ - Outcomes     │  │ - Effectiveness│  │ - Reflections  │ │
│  │ - Patterns     │  │ - Parameters   │  │ - Insights     │ │
│  └────────────────┘  └────────────────┘  └────────────────┘ │
│                                                              │
├──────────────────────────────────────────────────────────────┤
│                    Memory Operations                         │
│  - store(task_type, experience)                              │
│  - retrieve(task_type, context)                              │
│  - reflect(outcome, generate_insights)                       │
│  - update(insights, reinforce_patterns)                      │
└──────────────────────────────────────────────────────────────┘
```

**Implementation**: `design/A2S/Stulife/agents/memory/reme_memory.py`

**Storage Format**: JSON with hierarchical structure

**Key Methods**:
- `store_experience()`: Save task execution details
- `retrieve_relevant()`: Find similar past experiences
- `reflect()`: Generate insights from outcomes
- `get_strategies()`: Retrieve successful approaches

### 4. Self-Evolution Framework

```
┌──────────────────────────────────────────────────────────────┐
│                  Self-Evolution System                       │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────────────┐         ┌──────────────────┐         │
│  │  Task Execution  │───────▶│  Reflection Agent│         │
│  └──────────────────┘         └──────────────────┘         │
│         │                            │                       │
│         │                            ▼                       │
│         │                  ┌──────────────────┐            │
│         │                  │  Generate        │            │
│         │                  │  Insights        │            │
│         │                  └──────────────────┘            │
│         │                            │                       │
│         ▼                            ▼                       │
│  ┌──────────────────────────────────────────────┐         │
│  │            Meta-Learning Engine              │         │
│  │  - Extract transferrable knowledge           │         │
│  │  - Update strategy templates                 │         │
│  │  - Improve tool selection                    │         │
│  │  - Refine reasoning patterns                 │         │
│  └──────────────────────────────────────────────┘         │
│         │                                                    │
│         ▼                                                    │
│  ┌──────────────────────────────────────────────┐         │
│  │          Updated Memory & Behaviors           │         │
│  └──────────────────────────────────────────────┘         │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

**Components**:
- `ReflectionAgent`: Analyzes outcomes and generates insights
- `HelpSystem`: Discovers new tools and capabilities
- `MetaLearningEngine`: Extracts and applies transferrable knowledge

**File**: `design/A2S/Stulife/agents/self_evolution/`

## Task Execution Flow

### 1. Task Reception

```
User Input
    │
    ▼
Root Agent receives task
    │
    ▼
Understand task requirements (LLM)
```

### 2. Manager Selection

```
Task type identification
    │
    ▼
Select appropriate manager
    │
    ├─ Navigation tasks → NavigationManager
    ├─ Course tasks → CourseSelectionManager
    ├─ Email tasks → EmailManager
    ├─ Calendar tasks → CalendarManager
    └─ Reservation tasks → ReservationManager
```

### 3. Worker Selection

```
Manager receives task
    │
    ▼
Select appropriate worker
    │
    ▼
Worker executes task with tools
```

### 4. Memory Integration

```
During execution:
    │
    ├─ Check memory for similar past tasks
    ├─ Retrieve successful strategies
    ├─ Apply learned improvements
    └─ Adapt based on context
```

### 5. Reflection and Learning

```
After execution:
    │
    ├─ Store experience in memory
    ├─ Reflect on outcome
    ├─ Generate insights
    └─ Update behavior patterns
```

## Configuration System

**Config File**: `config.yaml`

```yaml
agent:
  type: SelfEvolvingLanguageModelAgent
  model: gemini-flash
  temperature: 0.7
  max_tokens: 2048

memory:
  type: ReMe
  storage_path: ./memory/
  max_entries: 10000

evolution:
  reflection_enabled: true
  learning_rate: 0.1
  memory_update_threshold: 0.8

environment:
  type: StuLifeCampus
  time_scale: real_time
  persistent_state: true
```

## Key Design Decisions

### 1. Hierarchical Architecture
**Decision**: Use managers instead of flat worker list
**Rationale**:
- Logical grouping of related capabilities
- Simplifies task routing
- Enables specialized optimization per domain
- Easier to extend with new capabilities

### 2. LLM-Based Routing
**Decision**: Use LLM reasoning instead of keyword matching
**Rationale**:
- Handles ambiguous task descriptions
- Understands context and intent
- Adapts to novel situations
- More robust to variations

### 3. Three-Layer Memory
**Decision**: Separate Task, Tool, and Personal memory
**Rationale**:
- Clear separation of concerns
- Different retention policies per layer
- Efficient retrieval for specific use cases
- Enables targeted reflection

### 4. Self-Evolution
**Decision**: Agents learn from experience
**Rationale**:
- Continuous improvement without manual tuning
- Adapts to environment changes
- Develops personalized strategies
- Reduces manual prompt engineering

## Performance Optimizations

### 1. Memory Caching
- Frequently used strategies cached in memory
- LRU eviction policy
- Pre-loading of high-probability tasks

### 2. Parallel Execution
- Independent workers can execute in parallel
- Async task processing
- Concurrent tool usage

### 3. Early Exit
- Stop execution when confidence threshold reached
- Avoid unnecessary tool calls
- Timeout-based cancellation

## Security and Privacy

- API keys stored in environment variables
- No sensitive data in logs
- Memory data encrypted at rest
- Sandboxed tool execution

## Future Extensions

1. **Multi-Agent Collaboration**: Enable agents to work together
2. **Transfer Learning**: Share knowledge across environments
3. **Hierarchical Planning**: Multi-step reasoning before execution
4. **Explainability**: Decision audit trails

---

**Last Updated**: 2025-01-30
**Version**: 1.0.0
