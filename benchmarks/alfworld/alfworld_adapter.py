"""
ALFWorld Adapter for Auto-Expansion Agent Cluster

Borrowed from Agent_to_Skills project for optimal performance.
This adapter provides fast reset times (0.7-0.9s) and proper ALFWorld integration.
"""

import os
import sys
import yaml
import logging
from typing import Optional, Dict, Any, List

# Add ALFWorld to path if needed
alfworld_path = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'alfworld')
if os.path.exists(alfworld_path):
    sys.path.insert(0, alfworld_path)

import alfworld.agents.environment as alf_env

logger = logging.getLogger(__name__)


class AlfworldAdapter:
    """
    ALFWorld Environment Adapter

    Provides fast, efficient access to ALFWorld environment with:
    - Fast reset times (0.7-0.9s)
    - Proper configuration management
    - LLM agent integration
    """

    def __init__(
        self,
        config_path: Optional[str] = None,
        train_eval: str = 'train'
    ):
        """
        Initialize ALFWorld adapter

        Args:
            config_path: Path to ALFWorld config YAML file (optional, uses default)
            train_eval: 'train', 'eval_in_distribution', or 'eval_out_of_distribution'
        """
        self.train_eval = train_eval

        # Load configuration
        self.config = self._load_config(config_path)

        # Initialize environment
        logger.info("Initializing ALFWorld environment...")
        self.env_manager = self._create_environment()
        self.env = self.env_manager.init_env(batch_size=1)

        # Internal state
        self.obs = None
        self.infos = None
        self.is_done = False
        self.last_info = {}
        self.last_reward = 0.0

        logger.info("✅ ALFWorld adapter initialized")

    def _load_config(self, config_path: Optional[str]) -> Dict[str, Any]:
        """Load ALFWorld configuration from YAML file or use default"""
        if config_path is None:
            # Use default config from Agent_to_Skills/alfworld
            possible_paths = [
                # Path within auto_expansion_agent
                os.path.join(
                    os.path.dirname(__file__),
                    'alfworld_config.yaml'
                ),
                # Agent_to_Skills path
                '/Users/dp/Agent_research/design/alfworld/configs/base_config.yaml',
                # System path
                '/usr/local/share/alfworld/configs/base_config.yaml',
                # User home
                os.path.expanduser('~/.alfworld/configs/base_config.yaml'),
            ]

            config_path = None
            for path in possible_paths:
                if os.path.exists(path):
                    config_path = path
                    break

        if config_path and os.path.exists(config_path):
            logger.info(f"Loading config from: {config_path}")
            with open(config_path) as f:
                config = yaml.safe_load(f)
            return config
        else:
            logger.warning("Config file not found, using minimal default")
            return self._get_default_config()

    def _create_environment(self):
        """Create ALFWorld environment instance"""
        env_type = self.config.get('env', {}).get('type', 'AlfredTWEnv')

        try:
            env = alf_env.get_environment(env_type)(
                self.config,
                train_eval=self.train_eval
            )
            return env
        except Exception as e:
            logger.error(f"Failed to create {env_type}: {e}")
            logger.info("Falling back to AlfredTWEnv")
            return alf_env.AlfredTWEnv(
                self.config,
                train_eval=self.train_eval
            )

    def reset(self) -> str:
        """
        Reset environment and return task description

        Returns:
            Task description string
        """
        self.obs, self.infos = self.env.reset()
        self.is_done = False
        self.last_info = self.infos
        self.last_reward = 0.0

        # Extract task description
        if isinstance(self.obs, list) and len(self.obs) > 0:
            task_description = self.obs[0].split("\n")[-1]
        else:
            task_description = str(self.obs)

        # Add admissible commands hint
        admissible_commands = self._extract_admissible_commands(self.infos)
        command_hint = self._format_command_hint(admissible_commands)
        if command_hint:
            task_description += f"\n{command_hint}"

        return task_description

    def step(self, action_command: str) -> Dict[str, Any]:
        """
        Execute action in environment

        Args:
            action_command: Text command (e.g., 'go to kitchen', 'take apple 1')

        Returns:
            Dictionary with:
                - observation: str
                - done: bool
                - won: bool
                - reward: float
                - admissible_commands: List[str]
        """
        if self.is_done:
            return {
                'observation': "Task already finished.",
                'done': True,
                'won': self.last_info.get('won', [False])[0],
                'reward': self.last_reward,
                'admissible_commands': []
            }

        # Execute action
        obs, scores, dones, infos = self.env.step([action_command])

        raw_obs = obs[0]
        self.is_done = dones[0]
        self.last_info = infos
        self.obs = raw_obs

        # Check success
        is_success = infos.get('won', [False])[0]
        reward = scores[0] if scores and len(scores) > 0 else 0.0
        self.last_reward = reward

        # Get admissible commands
        admissible_commands = self._extract_admissible_commands(infos)

        # Format observation
        obs_text = f"Observation: {raw_obs}"
        if self.is_done:
            if is_success:
                obs_text += "\n[System]: SUCCESS! Task completed."
            else:
                obs_text += "\n[System]: FAILED. Task ended."

        command_hint = self._format_command_hint(admissible_commands)
        if command_hint:
            obs_text += f"\n{command_hint}"

        return {
            'observation': obs_text,
            'done': self.is_done,
            'won': is_success,
            'reward': reward,
            'admissible_commands': admissible_commands
        }

    def _extract_admissible_commands(self, infos) -> List[str]:
        """Extract admissible commands from environment info"""
        if not infos:
            return []

        commands = []
        if isinstance(infos, dict):
            commands = infos.get('admissible_commands', [])
        elif isinstance(infos, list) and infos and isinstance(infos[0], dict):
            commands = infos[0].get('admissible_commands', [])

        if isinstance(commands, list) and commands and isinstance(commands[0], list):
            commands = commands[0]

        if not isinstance(commands, list):
            return []

        return [cmd.strip() for cmd in commands if isinstance(cmd, str) and cmd.strip()]

    def _format_command_hint(self, commands: List[str], max_commands: int = 15) -> str:
        """Format command hint string"""
        if not commands:
            return ""

        display_cmds = commands[:max_commands]
        suffix = ""
        if len(commands) > max_commands:
            suffix = f" ... (+{len(commands) - max_commands} more)"

        return "[Hints]: Admissible commands -> " + "; ".join(display_cmds) + suffix

    def _get_default_config(self) -> Dict[str, Any]:
        """Default ALFWorld configuration (from Agent_to_Skills)"""
        return {
            'dataset': {
                'data_path': '~/.cache/alfworld/json_2.1.1/train',
                'eval_id_data_path': '~/.cache/alfworld/json_2.1.1/valid_seen',
                'eval_ood_data_path': '~/.cache/alfworld/json_2.1.1/valid_unseen',
                'num_train_games': -1,
                'num_eval_games': -1
            },
            'logic': {
                'domain': 'logic/alfred.pddl',
                'grammar': 'logic/alfred.twl2'
            },
            'env': {
                'type': 'AlfredTWEnv',
                'domain_randomization': False,
                'task_types': [1, 2, 3, 4, 5, 6],
                'expert_timeout_steps': 150,
                'expert_type': 'handcoded',
                'goal_desc_human_anns_prob': 0.0
            },
            'controller': {
                'type': 'oracle',
                'debug': False,
                'load_receps': True  # KEY: Fast reset
            },
            'general': {
                'random_seed': 42,
                'use_cuda': False,  # Disable for CPU-only machines
                'task': 'alfred',
                'training_method': 'dagger',
                'observation_pool_capacity': 3,
                'hide_init_receptacles': False
            },
            'dagger': {
                'action_space': 'generation',
                'max_target_length': 20,
                'beam_width': 10,
                'generate_top_k': 5,
                'unstick_by_beam_search': False,
                'training': {
                    'max_nb_steps_per_episode': 50
                }
            }
        }
