"""
Benchmark Analyzer for Automatic Prompt Generation

This module analyzes benchmarks to generate domain-specific prompts
with cache optimization BEFORE running any tasks.

Key Capabilities:
1. Deep analysis of benchmark structure and requirements
2. Extraction of domains, tools, and task patterns
3. Generation of comprehensive static prefixes (~1200 tokens each)
4. Automatic prompt optimization based on benchmark metadata

Usage:
    analyzer = BenchmarkAnalyzer()
    analysis = analyzer.analyze_benchmark("alfworld")
    prompts = analyzer.generate_static_prefixes(analysis)
"""

import logging
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class DomainAnalysis:
    """Analysis of a single domain in the benchmark"""
    name: str
    task_types: List[str]
    tools: List[str]
    common_patterns: List[str]
    failure_modes: List[str]
    complexity: str  # "simple" | "medium" | "complex"
    estimated_prompt_length: int
    examples: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class BenchmarkAnalysis:
    """Complete analysis of a benchmark"""
    benchmark_name: str
    domains: Dict[str, DomainAnalysis]
    task_types: List[str]
    tools_catalog: Dict[str, List[str]]  # domain -> tools
    coordination_requirements: List[str]
    performance_expectations: Dict[str, float]
    metadata: Dict[str, Any] = field(default_factory=dict)

    def get_primary_domains(self) -> List[str]:
        """Get list of primary domains sorted by complexity"""
        sorted_domains = sorted(
            self.domains.items(),
            key=lambda x: (
                {"simple": 1, "medium": 2, "complex": 3}.get(x[1].complexity, 0),
                len(x[1].tools)
            ),
            reverse=True
        )
        return [d[0] for d in sorted_domains]


class BenchmarkAnalyzer:
    """
    Analyze benchmarks to generate high-quality prompts

    This analyzer:
    1. Reads benchmark description and metadata
    2. Explores benchmark structure (if environment available)
    3. Extracts domains, tools, and patterns
    4. Generates comprehensive static prefixes
    """

    def __init__(self, use_llm: bool = True, llm_client=None):
        """
        Initialize benchmark analyzer

        Args:
            use_llm: Whether to use LLM for analysis (default: True)
            llm_client: LLM client for advanced analysis
        """
        self.use_llm = use_llm
        self.llm_client = llm_client
        logger.info(f"BenchmarkAnalyzer initialized (LLM: {use_llm})")

    def analyze_benchmark(
        self,
        benchmark_name: str,
        description_file: Optional[Path] = None
    ) -> BenchmarkAnalysis:
        """
        Perform deep analysis of a benchmark

        Args:
            benchmark_name: Name of benchmark (e.g., "alfworld", "stulife")
            description_file: Optional path to detailed benchmark description

        Returns:
            BenchmarkAnalysis with comprehensive domain information
        """
        logger.info(f"Analyzing benchmark: {benchmark_name}")

        # Step 1: Load benchmark metadata
        metadata = self._load_benchmark_metadata(benchmark_name)

        # Step 2: Extract domains
        domains = self._extract_domains(benchmark_name, metadata)

        # Step 3: Analyze each domain
        domain_analyses = {}
        for domain_name, domain_info in domains.items():
            analysis = self._analyze_domain(
                benchmark_name, domain_name, domain_info, metadata
            )
            domain_analyses[domain_name] = analysis

        # Step 4: Build complete analysis
        analysis = BenchmarkAnalysis(
            benchmark_name=benchmark_name,
            domains=domain_analyses,
            task_types=metadata.get("task_types", []),
            tools_catalog=self._build_tools_catalog(domain_analyses),
            coordination_requirements=metadata.get("coordination", []),
            performance_expectations=metadata.get("performance", {}),
            metadata=metadata
        )

        logger.info(
            f"Analysis complete: {len(domain_analyses)} domains, "
            f"{sum(len(d.tools) for d in domain_analyses.values())} tools"
        )

        return analysis

    def generate_static_prefixes(
        self,
        analysis: BenchmarkAnalysis,
        use_llm_generation: bool = True
    ) -> Dict[str, str]:
        """
        Generate cache-optimized static prefixes from benchmark analysis

        Args:
            analysis: Benchmark analysis results
            use_llm_generation: Use LLM to generate prompts (else use templates)

        Returns:
            Dict mapping domain names to static prefix prompts
        """
        logger.info(f"Generating static prefixes for {analysis.benchmark_name}")

        static_prefixes = {}

        for domain_name, domain_analysis in analysis.domains.items():
            logger.info(f"Generating prefix for domain: {domain_name}")

            if use_llm_generation and self.llm_client:
                prompt = self._generate_llm_static_prefix(analysis, domain_analysis)
            else:
                prompt = self._generate_template_static_prefix(analysis, domain_analysis)

            # Validate prompt length
            estimated_tokens = len(prompt) // 4
            if estimated_tokens < 800:
                logger.warning(
                    f"Generated prompt for {domain_name} is short "
                    f"({estimated_tokens} tokens), recommend 1000-1200 for optimal caching"
                )

            static_prefixes[domain_name] = prompt

        logger.info(f"Generated {len(static_prefixes)} static prefixes")
        return static_prefixes

    # ========== Private Methods ==========

    def _load_benchmark_metadata(self, benchmark_name: str) -> Dict[str, Any]:
        """Load benchmark metadata from description files"""
        # Try to load from benchmarks directory
        metadata_file = Path(__file__).parent.parent.parent / "benchmarks" / benchmark_name / "intro.md"

        metadata = {"name": benchmark_name}

        if metadata_file.exists():
            # Parse markdown file
            content = metadata_file.read_text()
            metadata = self._parse_benchmark_description(content, benchmark_name)
        else:
            # Use hardcoded knowledge for known benchmarks
            metadata = self._get_known_benchmark_metadata(benchmark_name)

        return metadata

    def _parse_benchmark_description(
        self,
        content: str,
        benchmark_name: str
    ) -> Dict[str, Any]:
        """Parse benchmark description markdown file"""
        # Simple parser - extracts sections from markdown
        sections = {}
        current_section = None
        current_content = []

        for line in content.split('\n'):
            if line.startswith('## '):
                if current_section:
                    sections[current_section] = '\n'.join(current_content).strip()
                current_section = line[3:].strip().lower()
                current_content = []
            else:
                current_content.append(line)

        if current_section:
            sections[current_section] = '\n'.join(current_content).strip()

        # Convert to metadata dict
        metadata = {
            "name": benchmark_name,
            "task_types": self._extract_list(sections.get("task types", "")),
            "coordination": self._extract_list(sections.get("coordination requirements", "")),
        }

        return metadata

    def _get_known_benchmark_metadata(self, benchmark_name: str) -> Dict[str, Any]:
        """Get metadata for known benchmarks"""
        known_benchmarks = {
            "alfworld": {
                "name": "ALFWorld",
                "domain": "embodied_ai",
                "task_types": [
                    "pick_and_place_simple",
                    "pick_clean_then_place",
                    "pick_heat_then_place",
                    "pick_cool_then_place",
                    "look_at_obj",
                    "pick_two_obj"
                ],
                "coordination": [
                    "Multi-step object manipulation",
                    "Sequential reasoning required",
                    "State tracking across actions"
                ],
                "performance": {
                    "expected_success_rate": 0.5,
                    "max_steps_per_task": 50
                }
            },
            "stulife": {
                "name": "StuLife",
                "domain": "campus_assistant",
                "task_types": [
                    "navigation",
                    "email_management",
                    "course_management",
                    "calendar_scheduling",
                    "reservation_booking"
                ],
                "coordination": [
                    "Multi-domain coordination",
                    "Information sharing across tasks",
                    "Sequential dependencies"
                ],
                "performance": {
                    "expected_success_rate": 0.7,
                    "max_steps_per_task": 20
                }
            }
        }

        return known_benchmarks.get(benchmark_name, {"name": benchmark_name})

    def _extract_domains(
        self,
        benchmark_name: str,
        metadata: Dict[str, Any]
    ) -> Dict[str, Dict[str, Any]]:
        """Extract domains from benchmark metadata"""
        if benchmark_name == "alfworld":
            return {
                "manipulation": {
                    "description": "Object manipulation and interaction",
                    "tools": ["take", "put", "open", "close", "clean", "heat", "cool"],
                    "complexity": "medium"
                },
                "navigation": {
                    "description": "Navigation and exploration",
                    "tools": ["go to", "look", "explore"],
                    "complexity": "simple"
                },
                "perception": {
                    "description": "Object perception and recognition",
                    "tools": ["look", "examine", "search"],
                    "complexity": "simple"
                },
                "reasoning": {
                    "description": "Task planning and reasoning",
                    "tools": ["think", "plan", "decide"],
                    "complexity": "complex"
                },
                "interaction": {
                    "description": "Environment interaction",
                    "tools": ["toggle", "use", "operate"],
                    "complexity": "medium"
                }
            }
        elif benchmark_name == "stulife":
            return {
                "navigation": {
                    "description": "Campus navigation",
                    "tools": ["map.find_building_id", "map.find_optimal_path",
                            "geography.walk_to", "geography.get_current_location"],
                    "complexity": "medium"
                },
                "email": {
                    "description": "Email management",
                    "tools": ["email.send", "email.search", "email.read", "email.reply", "email.forward"],
                    "complexity": "simple"
                },
                "course": {
                    "description": "Course management",
                    "tools": ["course.search", "course.register", "course.drop",
                            "course.check_prerequisites", "course.get_details"],
                    "complexity": "medium"
                }
            }
        else:
            # Default: extract from metadata
            return {
                "general": {
                    "description": "General purpose",
                    "tools": metadata.get("tools", ["help"]),
                    "complexity": "simple"
                }
            }

    def _analyze_domain(
        self,
        benchmark_name: str,
        domain_name: str,
        domain_info: Dict[str, Any],
        metadata: Dict[str, Any]
    ) -> DomainAnalysis:
        """Analyze a single domain in detail"""
        # Extract common patterns from task types
        task_types = metadata.get("task_types", [])
        relevant_tasks = [t for t in task_types if domain_name in t.lower()]

        # Identify failure modes (hardcoded for now, can be LLM-generated)
        failure_modes = self._identify_failure_modes(benchmark_name, domain_name)

        return DomainAnalysis(
            name=domain_name,
            task_types=relevant_tasks or [f"{domain_name}_task"],
            tools=domain_info.get("tools", []),
            common_patterns=self._extract_common_patterns(benchmark_name, domain_name),
            failure_modes=failure_modes,
            complexity=domain_info.get("complexity", "medium"),
            estimated_prompt_length=self._estimate_prompt_length(domain_info)
        )

    def _extract_common_patterns(
        self,
        benchmark_name: str,
        domain_name: str
    ) -> List[str]:
        """Extract common interaction patterns for a domain"""
        if benchmark_name == "alfworld" and domain_name == "manipulation":
            return [
                "1. Find object in environment",
                "2. Navigate to object location",
                "3. Pick up object",
                "4. Perform operation (clean/heat/cool)",
                "5. Navigate to target location",
                "6. Place object"
            ]
        elif benchmark_name == "alfworld" and domain_name == "navigation":
            return [
                "1. Look around current room",
                "2. Identify next room to explore",
                "3. Move to next room",
                "4. Continue until target found"
            ]
        else:
            return [
                "1. Understand task requirements",
                "2. Identify required tools",
                "3. Execute in sequence",
                "4. Verify results"
            ]

    def _identify_failure_modes(
        self,
        benchmark_name: str,
        domain_name: str
    ) -> List[str]:
        """Identify common failure modes for a domain"""
        if benchmark_name == "alfworld" and domain_name == "manipulation":
            return [
                "Picking up wrong object",
                "Placing in wrong location",
                "Forgetting to perform operation (clean/heat/cool)",
                "Dropping object accidentally",
                "Not finding target object"
            ]
        elif benchmark_name == "alfworld" and domain_name == "navigation":
            return [
                "Going in circles",
                "Missing rooms in exploration",
                "Not checking all locations",
                "Getting stuck in one room"
            ]
        else:
            return [
                "Misunderstanding task",
                "Using wrong tool",
                "Skipping verification steps"
            ]

    def _estimate_prompt_length(self, domain_info: Dict[str, Any]) -> int:
        """Estimate required prompt length based on domain complexity"""
        complexity = domain_info.get("complexity", "medium")
        tool_count = len(domain_info.get("tools", []))

        base_lengths = {"simple": 600, "medium": 1000, "complex": 1400}
        base_length = base_lengths.get(complexity, 1000)

        # Add 50 tokens per tool
        return base_length + (tool_count * 50)

    def _build_tools_catalog(
        self,
        domain_analyses: Dict[str, DomainAnalysis]
    ) -> Dict[str, List[str]]:
        """Build catalog of all tools by domain"""
        return {
            domain_name: analysis.tools
            for domain_name, analysis in domain_analyses.items()
        }

    def _extract_list(self, text: str) -> List[str]:
        """Extract list items from text"""
        items = []
        for line in text.split('\n'):
            line = line.strip()
            if line.startswith('-') or line.startswith('*'):
                items.append(line[1:].strip())
        return items

    def _generate_llm_static_prefix(
        self,
        analysis: BenchmarkAnalysis,
        domain_analysis: DomainAnalysis
    ) -> str:
        """Generate static prefix using LLM"""
        if not self.llm_client:
            return self._generate_template_static_prefix(analysis, domain_analysis)

        llm_prompt = f"""Generate a comprehensive, cache-optimized static prefix for {domain_analysis.name} agents in the {analysis.benchmark_name} benchmark.

DOMAIN: {domain_analysis.name}
DESCRIPTION: {domain_analysis.name}
TASK TYPES: {', '.join(domain_analysis.task_types)}
TOOLS: {', '.join(domain_analysis.tools)}
COMPLEXITY: {domain_analysis.complexity}

COMMON PATTERNS:
{chr(10).join(domain_analysis.common_patterns)}

COMMON FAILURE MODES:
{chr(10).join(f'- {mode}' for mode in domain_analysis.failure_modes)}

REQUIREMENTS:
1. Generate a static prefix of {domain_analysis.estimated_prompt_length} tokens
2. Structure for prompt caching (all static content, no dynamic placeholders)
3. MUST include these sections:
   - <role_definition>: Clear role and responsibilities
   - <core_protocol>: 5-10 immutable rules with specific domain knowledge
   - <workflow_structure>: 4-5 phase workflow with concrete steps
   - <tool_specifications>: Each tool with purpose, parameters, and usage examples
   - <error_prevention>: 5-7 common errors with correct/incorrect examples
   - <best_practices>: 3-5 domain-specific best practices

4. Make it HIGHLY SPECIFIC to {domain_analysis.name} in {analysis.benchmark_name}
5. Include concrete examples and patterns
6. Focus on preventing the identified failure modes
7. Write in clear, instructional style
8. Use XML-style tags for sections (<section_name>...</section_name>)

Generate the complete static prefix now:"""

        try:
            response = self.llm_client.complete(
                prompt=llm_prompt,
                temperature=0.3,
                max_tokens=2500
            )

            return self._validate_and_format_prompt(response.content)

        except Exception as e:
            logger.error(f"LLM generation failed for {domain_analysis.name}: {e}")
            return self._generate_template_static_prefix(analysis, domain_analysis)

    def _generate_template_static_prefix(
        self,
        analysis: BenchmarkAnalysis,
        domain_analysis: DomainAnalysis
    ) -> str:
        """Generate static prefix using templates"""
        return f"""<role_definition>
You are a {domain_analysis.name} specialist in the {analysis.benchmark_name} benchmark environment.
Your expertise is in {domain_analysis.name} with access to {len(domain_analysis.tools)} specialized tools.
You work efficiently to accomplish {domain_analysis.name} tasks while avoiding common pitfalls.
</role_definition>

<core_protocol>
## {domain_analysis.name.capitalize()} Protocol (v1.0)

### Immutable Rules
{chr(10).join(f'{i+1}. **{rule}**' for i, rule in enumerate(self._get_core_rules(domain_analysis.name)))}

### Domain-Specific Principles
- Always follow the common patterns for {domain_analysis.name}
- Be aware of typical failure modes and actively avoid them
- Verify each step before proceeding to the next
- Think through the full plan before acting
</core_protocol>

<workflow_structure>
## Standard {domain_analysis.name.capitalize()} Workflow

{chr(10).join(f'### Phase {i+1}: {phase["title"]}{chr(10)}{chr(10).join(f"- {step}" for step in phase["steps"])}{chr(10)}' for i, phase in enumerate(self._get_workflow_phases(domain_analysis.name)))}
</workflow_structure>

<tool_specifications>
## Available Tools

{self._format_tools(domain_analysis.tools)}
</tool_specifications>

<error_prevention>
## Common {domain_analysis.name.capitalize()} Errors

{chr(10).join(f'### Error {i+1}: {error["title"]}{chr(10)}❌ WRONG: {error["wrong"]}{chr(10)}✅ CORRECT: {error["right"]}{chr(10)}' for i, error in enumerate(self._get_error_examples(domain_analysis.name)))}
</error_prevention>

<best_practices>
## {domain_analysis.name.capitalize()} Best Practices

{chr(10).join(f'{i+1}. {practice}' for i, practice in enumerate(self._get_best_practices(domain_analysis.name)))}
</best_practices>
"""

    def _validate_and_format_prompt(self, prompt: str) -> str:
        """Validate and format generated prompt"""
        # Remove markdown code blocks
        if prompt.startswith("```"):
            lines = prompt.split('\n')
            if lines[0].startswith("```"):
                prompt = '\n'.join(lines[1:-1])

        return prompt.strip()

    def _get_core_rules(self, domain_name: str) -> List[str]:
        """Get core rules for a domain"""
        rules_map = {
            "manipulation": [
                "Always observe object locations before picking up",
                "Verify you have the correct object before acting",
                "Never skip required operations (clean/heat/cool)",
                "Check object receptacle before placing",
                "Confirm task completion before reporting success"
            ],
            "navigation": [
                "Always look around before moving to next room",
                "Track which rooms have been explored",
                "Systematically search each location",
                "Don't revisit previously explored areas without reason",
                "Report all observations in detail"
            ],
            "perception": [
                "Look carefully at all objects in view",
                "Note object states (open/closed, clean/dirty, etc.)",
                "Search thoroughly before moving on",
                "Report findings with specific details",
                "Don't make assumptions about hidden objects"
            ]
        }
        return rules_map.get(domain_name, [
            "Follow instructions precisely",
            "Verify results before proceeding",
            "Report failures clearly",
            "Use tools correctly",
            "Think before acting"
        ])

    def _get_workflow_phases(self, domain_name: str) -> List[Dict[str, Any]]:
        """Get workflow phases for a domain"""
        phases_map = {
            "manipulation": [
                {
                    "title": "Observe and Plan",
                    "steps": ["Look around current location", "Identify target object", "Identify target location", "Plan sequence of actions"]
                },
                {
                    "title": "Navigate to Object",
                    "steps": ["Move to object's location", "Verify object is present", "Check object state"]
                },
                {
                    "title": "Manipulate Object",
                    "steps": ["Pick up object", "Perform required operation if needed", "Verify operation success"]
                },
                {
                    "title": "Complete Task",
                    "steps": ["Navigate to target location", "Place object correctly", "Verify task completion", "Report success"]
                }
            ],
            "navigation": [
                {
                    "title": "Initial Assessment",
                    "steps": ["Look around current room", "Note all visible objects and locations", "Identify potential next locations"]
                },
                {
                    "title": "Exploration",
                    "steps": ["Choose unexplored location", "Move to next room", "Look around thoroughly"]
                },
                {
                    "title": "Discovery",
                    "steps": ["Search for target objects", "Check containers and surfaces", "Note object locations"]
                },
                {
                    "title": "Completion",
                    "steps": ["Verify all targets found", "Report final locations", "Confirm task completion"]
                }
            ]
        }
        return phases_map.get(domain_name, [
            {
                "title": "Understand",
                "steps": ["Read task carefully", "Identify requirements", "Plan approach"]
            },
            {
                "title": "Execute",
                "steps": ["Use appropriate tools", "Follow sequence", "Verify each step"]
            },
            {
                "title": "Complete",
                "steps": ["Confirm completion", "Report results"]
            }
        ])

    def _get_error_examples(self, domain_name: str) -> List[Dict[str, str]]:
        """Get error examples for a domain"""
        errors_map = {
            "manipulation": [
                {
                    "title": "Picking Up Wrong Object",
                    "wrong": 'take("apple") when there are multiple apples, picking the wrong one',
                    "right": 'look around, examine all apples, identify correct one, then take("apple_2")'
                },
                {
                    "title": "Forgetting Operation",
                    "wrong": 'take("apple") then put("fridge") - forgot to clean',
                    "right": 'take("apple"), clean("apple"), put("fridge")'
                },
                {
                    "title": "Wrong Receptacle",
                    "wrong": 'put("apple", "table") when task says fridge',
                    "right": 'put("apple", "fridge") - match exact task requirement'
                }
            ],
            "navigation": [
                {
                    "title": "Going in Circles",
                    "wrong": "go to rooms in random order, revisiting same rooms",
                    "right": "track visited rooms, systematically explore new areas"
                },
                {
                    "title": "Incomplete Search",
                    "wrong": "glance at room, assume nothing there, move on",
                    "right": "look around thoroughly, check all surfaces and containers"
                }
            ]
        }
        return errors_map.get(domain_name, [
            {
                "title": "Acting Without Observation",
                "wrong": "Take action without looking first",
                "right": "Always observe before acting"
            }
        ])

    def _get_best_practices(self, domain_name: str) -> List[str]:
        """Get best practices for a domain"""
        practices_map = {
            "manipulation": [
                "Always verbally narrate your actions for clarity",
                "Double-check object identities before manipulating",
                "Plan the full sequence before starting",
                "Verify each action's result before proceeding",
                "Be methodical - rushing causes mistakes"
            ],
            "navigation": [
                "Keep mental map of explored areas",
                "Look in every direction before moving",
                "Note room connections for future reference",
                "Search surfaces and containers thoroughly",
                "Report observations systematically"
            ]
        }
        return practices_map.get(domain_name, [
            "Think before acting",
            "Verify each step",
            "Report clearly",
            "Learn from mistakes"
        ])

    def _format_tools(self, tools: List[str]) -> str:
        """Format tools for prompt"""
        formatted = []
        for tool in tools:
            formatted.append(f"### {tool}")
            formatted.append(f"**Purpose**: Perform {tool} operation")
            formatted.append(f"**Usage**: `{tool}(object, location, ...)`")
            formatted.append("")
        return "\n".join(formatted)
