import re
import os
from typing import List, Optional
from rich.console import Console
from rich.panel import Panel

from .types import ProjectState, EngineConfig, IterationStatus, Message
from .client import AIClient
from .prompts import ARCHITECT_SYSTEM_PROMPT, CODER_SYSTEM_PROMPT

console = Console()

class AutocompleteEngine:
    def __init__(self, goal: str, config: EngineConfig = EngineConfig(), mode: str = "coder"):
        self.state = ProjectState(project_name="AutoProject", goal=goal)
        self.config = config
        self.client = AIClient(config)
        
        # Select Prompt based on mode
        base_prompt = ARCHITECT_SYSTEM_PROMPT if mode == "architect" else CODER_SYSTEM_PROMPT
        self.state.add_message("system", config.system_prompt_override or base_prompt)
        self.state.add_message("user", f"Project Goal: {goal}")

    def parse_artifacts(self, text: str):
        # Regex to find code blocks with filenames
        # Pattern: ```lang:path\ncontent\n```
        pattern = r"```\w+:(.+?)\n(.*?)```"
        matches = re.finditer(pattern, text, re.DOTALL)
        
        for match in matches:
            filepath = match.group(1).strip()
            content = match.group(2)
            self.state.artifacts[filepath] = content
            console.print(f"[green]Extracted file:[/green] {filepath}")

    def run_iteration(self):
        if self.state.status == IterationStatus.COMPLETED:
            return

        self.state.current_iteration += 1
        console.print(f"[bold blue]Starting Iteration {self.state.current_iteration}[/bold blue]")

        # Prepare context with recursive self-improvement
        context_message = self.build_project_context()

        # Update the User message for this turn to include context
        # Instead of appending to history permanently (bloating it), we can create a temporary message list
        # or just append it as a system note.
        iteration_prompt = [
            {"role": "system", "content": context_message},
            {"role": "user", "content": "Review the artifacts. If improvements are needed to the plan, make them. Otherwise, proceed with the next step."}
        ]
        
        # Combine base history + current context
        full_history = self.state.history + [Message(role="user", content=context_message)]
        
        response_text = self.client.generate_response(full_history)
        
        # Display response summary
        console.print(Panel(response_text[:200] + "...", title="AI Response", border_style="cyan"))
        
        # Update State
        self.state.add_message("assistant", response_text)
        self.parse_artifacts(response_text)

        # Enhanced completion detection
        completion_detected = self.check_completion(response_text)
        if completion_detected:
            self.state.status = IterationStatus.COMPLETED
            console.print("[bold green]Project Marked as COMPLETE[/bold green]")
        elif self.state.current_iteration >= self.state.max_iterations:
            self.state.status = IterationStatus.FAILED
            console.print("[bold red]Max iterations reached[/bold red]")

    def run(self):
        while self.state.status == IterationStatus.IN_PROGRESS:
            self.run_iteration()
            
            # Smart continuation prompt if not complete
            if self.state.status == IterationStatus.IN_PROGRESS:
                continuation_prompt = self.generate_continuation_prompt()
                self.state.add_message("user", continuation_prompt)
        
        self.save_artifacts()

    def check_completion(self, response_text: str) -> bool:
        """Enhanced completion detection with multiple strategies"""
        # Strategy 1: Explicit marker
        if "[COMPLETE]" in response_text:
            return True

        # Strategy 2: Semantic completion indicators
        completion_phrases = [
            "project is now complete",
            "implementation is finished",
            "all requirements have been met",
            "nothing more to add",
            "consider this complete"
        ]

        lower_text = response_text.lower()
        for phrase in completion_phrases:
            if phrase in lower_text:
                return True

        # Strategy 3: Check if we have core project files
        required_files = {"main.py", "README.md", "__init__.py"}
        if len(self.state.artifacts) > 0 and required_files.issubset(self.state.artifacts.keys()):
            # Check if response indicates no more work needed
            if "next:" not in lower_text and "todo:" not in lower_text:
                return True

        return False

    def build_project_context(self) -> str:
        """Build comprehensive project context with recursive self-improvement capabilities"""
        context_message = "Current Project State:\n"

        # Read existing project documents from disk if they exist
        self.load_existing_documents()

        # Analyze project structure and provide insights
        project_analysis = self.analyze_project_state()
        context_message += f"\n{project_analysis}\n"

        # Add all artifacts to context
        for path, content in self.state.artifacts.items():
            if path.endswith(".md") or len(content) < 2000:
                context_message += f"\n--- File: {path} ---\n{content}\n"
            else:
                context_message += f"\n--- File: {path} (truncated to 1000 chars) ---\n{content[:1000]}...\n"

        # Add self-improvement guidance
        context_message += "\n" + self.get_self_improvement_guidance()

        return context_message

    def load_existing_documents(self):
        """Load existing project documents from disk to enable recursive improvement"""
        output_dir = "output"
        if os.path.exists(output_dir):
            for root, _, files in os.walk(output_dir):
                for file in files:
                    filepath = os.path.join(root, file)
                    relative_path = os.path.relpath(filepath, output_dir)

                    # Only load documentation files that might need improvement
                    if file.endswith(('.md', '.txt')) and relative_path not in self.state.artifacts:
                        try:
                            with open(filepath, 'r') as f:
                                content = f.read()
                                self.state.artifacts[relative_path] = content
                                console.print(f"[yellow]Loaded existing document for improvement: {relative_path}[/yellow]")
                        except Exception as e:
                            console.print(f"[red]Error loading {filepath}: {e}[/red]")

    def analyze_project_state(self) -> str:
        """Analyze current project state and provide insights for self-improvement"""
        analysis = "Project Analysis:\n"

        # Count different file types
        file_types = {}
        for path in self.state.artifacts:
            ext = os.path.splitext(path)[1]
            file_types[ext] = file_types.get(ext, 0) + 1

        analysis += f"- Files created: {len(self.state.artifacts)}\n"
        analysis += f"- File types: {', '.join(f'{ext}({count})' for ext, count in file_types.items())}\n"

        # Check for documentation completeness
        has_readme = "README.md" in self.state.artifacts
        has_roadmap = "ROADMAP.md" in self.state.artifacts
        has_architecture = "ARCHITECTURE.md" in self.state.artifacts

        if has_readme and has_roadmap and has_architecture:
            analysis += "- Documentation: Complete (README, ROADMAP, ARCHITECTURE)\n"
        else:
            missing_docs = []
            if not has_readme: missing_docs.append("README")
            if not has_roadmap: missing_docs.append("ROADMAP")
            if not has_architecture: missing_docs.append("ARCHITECTURE")
            analysis += f"- Documentation: Incomplete (Missing: {', '.join(missing_docs)})\n"

        # Check for main entry points
        has_main = any("main" in path.lower() for path in self.state.artifacts)
        analysis += f"- Main entry point: {'Yes' if has_main else 'No'}\n"

        return analysis

    def get_self_improvement_guidance(self) -> str:
        """Provide guidance for recursive self-improvement"""
        guidance = "Self-Improvement Guidance:\n"

        # Check if we need to update documentation
        needs_doc_update = False
        if "ROADMAP.md" in self.state.artifacts:
            roadmap_content = self.state.artifacts["ROADMAP.md"]
            if "TODO" in roadmap_content or "Incomplete" in roadmap_content:
                needs_doc_update = True

        if needs_doc_update:
            guidance += "- Review and update ROADMAP.md based on current progress\n"
            guidance += "- Ensure all completed tasks are marked as done\n"
            guidance += "- Add any new tasks discovered during implementation\n"

        # Suggest architecture improvements
        if "ARCHITECTURE.md" in self.state.artifacts:
            guidance += "- Review ARCHITECTURE.md for consistency with implementation\n"
            guidance += "- Update diagrams if the actual implementation differs from the plan\n"

        # General improvement suggestions
        guidance += "- Improve code documentation and comments\n"
        guidance += "- Add error handling where missing\n"
        guidance += "- Consider performance optimizations\n"
        guidance += "- Add tests for critical functionality\n"

        return guidance

    def generate_continuation_prompt(self) -> str:
        """Generate smart continuation prompts based on current state"""
        if len(self.state.artifacts) == 0:
            return "Begin implementing the project. Start with the core functionality."

        # Analyze what we have and what might be missing
        has_main_file = any("main.py" in path or path.endswith("__main__.py") for path in self.state.artifacts)
        has_readme = "README.md" in self.state.artifacts
        has_tests = any("test" in path.lower() for path in self.state.artifacts)

        missing_components = []
        if not has_main_file:
            missing_components.append("main entry point")
        if not has_readme:
            missing_components.append("documentation")
        if not has_tests:
            missing_components.append("tests")

        if missing_components:
            return f"Continue by adding missing components: {', '.join(missing_components)}."

        # If we have basics, suggest improvements
        return "Continue by adding error handling, improving documentation, or implementing additional features."

    def save_artifacts(self):
        console.print("[bold]Saving Artifacts to disk...[/bold]")
        for filepath, content in self.state.artifacts.items():
            # Ensure absolute path or relative to CWD safe check
            # For this MVP, we assume relative to CWD/output
            full_path = os.path.join("output", filepath)
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            with open(full_path, "w") as f:
                f.write(content)
            console.print(f"Saved: {full_path}")
