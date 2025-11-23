"""
Workflow Manager for loading, validating, and managing ComfyUI workflows
"""

import json
import copy
from pathlib import Path
from typing import Dict, Any, Optional, List
import logging

logger = logging.getLogger(__name__)


class WorkflowManager:
    """Manages ComfyUI workflows with validation and templating support"""

    def __init__(self):
        """Initialize Workflow Manager"""
        self.workflows: Dict[str, Dict[str, Any]] = {}
        self.templates: Dict[str, Dict[str, Any]] = {}

    @staticmethod
    def load_workflow(workflow_path: Path) -> Dict[str, Any]:
        """
        Load a workflow from JSON file

        Args:
            workflow_path: Path to workflow JSON file

        Returns:
            Workflow dictionary
        """
        if not workflow_path.exists():
            raise FileNotFoundError(f"Workflow not found: {workflow_path}")

        try:
            with open(workflow_path, 'r', encoding='utf-8') as f:
                workflow = json.load(f)

            logger.info(f"Loaded workflow from {workflow_path}")
            return workflow

        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in workflow file: {e}")
            raise ValueError(f"Invalid workflow JSON: {e}")

    @staticmethod
    def save_workflow(workflow: Dict[str, Any], output_path: Path):
        """
        Save a workflow to JSON file

        Args:
            workflow: Workflow dictionary
            output_path: Path to save workflow
        """
        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)

            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(workflow, f, indent=2)

            logger.info(f"Saved workflow to {output_path}")

        except Exception as e:
            logger.error(f"Failed to save workflow: {e}")
            raise

    @staticmethod
    def validate_workflow(workflow: Dict[str, Any]) -> tuple[bool, List[str]]:
        """
        Validate a ComfyUI workflow structure

        Args:
            workflow: Workflow dictionary to validate

        Returns:
            Tuple of (is_valid, list of error messages)
        """
        errors = []

        if not isinstance(workflow, dict):
            errors.append("Workflow must be a dictionary")
            return False, errors

        if not workflow:
            errors.append("Workflow is empty")
            return False, errors

        # Check if nodes exist
        if not any(isinstance(v, dict) and 'class_type' in v for v in workflow.values()):
            errors.append("Workflow contains no valid nodes")

        # Validate each node
        for node_id, node_data in workflow.items():
            if not isinstance(node_data, dict):
                errors.append(f"Node {node_id}: Invalid node data type")
                continue

            if 'class_type' not in node_data:
                errors.append(f"Node {node_id}: Missing 'class_type' field")

            if 'inputs' not in node_data:
                errors.append(f"Node {node_id}: Missing 'inputs' field")
            elif not isinstance(node_data['inputs'], dict):
                errors.append(f"Node {node_id}: 'inputs' must be a dictionary")

        is_valid = len(errors) == 0
        if is_valid:
            logger.info("Workflow validation passed")
        else:
            logger.warning(f"Workflow validation failed: {len(errors)} errors")

        return is_valid, errors

    def register_workflow(self, name: str, workflow: Dict[str, Any]):
        """
        Register a workflow for later use

        Args:
            name: Workflow identifier
            workflow: Workflow dictionary
        """
        self.workflows[name] = copy.deepcopy(workflow)
        logger.info(f"Registered workflow: {name}")

    def get_workflow(self, name: str) -> Dict[str, Any]:
        """
        Get a registered workflow

        Args:
            name: Workflow identifier

        Returns:
            Workflow dictionary (deep copy)
        """
        if name not in self.workflows:
            raise KeyError(f"Workflow not found: {name}")

        return copy.deepcopy(self.workflows[name])

    def list_workflows(self) -> List[str]:
        """List all registered workflows"""
        return list(self.workflows.keys())

    @staticmethod
    def update_node_input(workflow: Dict[str, Any], node_id: str,
                         input_name: str, value: Any) -> Dict[str, Any]:
        """
        Update a specific node input in a workflow

        Args:
            workflow: Workflow dictionary
            node_id: Node identifier
            input_name: Input parameter name
            value: New value

        Returns:
            Updated workflow
        """
        if node_id not in workflow:
            raise KeyError(f"Node not found: {node_id}")

        if 'inputs' not in workflow[node_id]:
            workflow[node_id]['inputs'] = {}

        workflow[node_id]['inputs'][input_name] = value
        logger.debug(f"Updated {node_id}.{input_name} = {value}")

        return workflow

    @staticmethod
    def find_nodes_by_type(workflow: Dict[str, Any],
                          class_type: str) -> List[str]:
        """
        Find all nodes of a specific type

        Args:
            workflow: Workflow dictionary
            class_type: Node class type to search for

        Returns:
            List of node IDs
        """
        nodes = []
        for node_id, node_data in workflow.items():
            if isinstance(node_data, dict) and node_data.get('class_type') == class_type:
                nodes.append(node_id)

        return nodes

    def create_template(self, name: str, workflow: Dict[str, Any],
                       parameters: Dict[str, Dict[str, str]]):
        """
        Create a workflow template with parameters

        Args:
            name: Template identifier
            workflow: Base workflow
            parameters: Dictionary mapping parameter names to
                       {node_id, input_name} mappings
        """
        self.templates[name] = {
            'workflow': copy.deepcopy(workflow),
            'parameters': parameters
        }
        logger.info(f"Created template: {name}")

    def instantiate_template(self, name: str,
                           values: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a workflow from a template with specific values

        Args:
            name: Template identifier
            values: Dictionary of parameter values

        Returns:
            Instantiated workflow
        """
        if name not in self.templates:
            raise KeyError(f"Template not found: {name}")

        template = self.templates[name]
        workflow = copy.deepcopy(template['workflow'])

        for param_name, param_config in template['parameters'].items():
            if param_name in values:
                node_id = param_config['node_id']
                input_name = param_config['input_name']
                workflow = self.update_node_input(
                    workflow, node_id, input_name, values[param_name]
                )

        logger.info(f"Instantiated template: {name}")
        return workflow

    @staticmethod
    def get_workflow_info(workflow: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get information about a workflow

        Args:
            workflow: Workflow dictionary

        Returns:
            Dictionary with workflow information
        """
        node_types = {}
        total_nodes = 0

        for node_id, node_data in workflow.items():
            if isinstance(node_data, dict) and 'class_type' in node_data:
                total_nodes += 1
                class_type = node_data['class_type']
                node_types[class_type] = node_types.get(class_type, 0) + 1

        return {
            'total_nodes': total_nodes,
            'node_types': node_types,
            'node_ids': list(workflow.keys())
        }

    @staticmethod
    def merge_workflows(workflow1: Dict[str, Any],
                       workflow2: Dict[str, Any],
                       node_id_prefix: str = "merged_") -> Dict[str, Any]:
        """
        Merge two workflows together

        Args:
            workflow1: First workflow
            workflow2: Second workflow
            node_id_prefix: Prefix for nodes from workflow2 to avoid conflicts

        Returns:
            Merged workflow
        """
        merged = copy.deepcopy(workflow1)

        for node_id, node_data in workflow2.items():
            new_id = f"{node_id_prefix}{node_id}"

            # Update node references in inputs
            updated_node = copy.deepcopy(node_data)
            if 'inputs' in updated_node:
                for input_name, input_value in updated_node['inputs'].items():
                    if isinstance(input_value, list) and len(input_value) == 2:
                        # This is a node reference [node_id, output_index]
                        ref_node_id = input_value[0]
                        if ref_node_id in workflow2:
                            updated_node['inputs'][input_name] = [
                                f"{node_id_prefix}{ref_node_id}",
                                input_value[1]
                            ]

            merged[new_id] = updated_node

        logger.info(f"Merged workflows: {len(workflow1)} + {len(workflow2)} nodes")
        return merged
