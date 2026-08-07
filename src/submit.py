"""
Submission script for Kaggriculture competition.
Handles packaging agent for Kaggle submission.
"""

import os
import sys
import json
import shutil
from pathlib import Path
import subprocess
from typing import Dict, Any, Optional
from datetime import datetime

try:
    import kaggle
    KAGGLE_AVAILABLE = True
except ImportError:
    KAGGLE_AVAILABLE = False
    print("Warning: Kaggle API not available. Install with: pip install kaggle")


class SubmissionManager:
    """Manage Kaggle submissions for Kaggriculture competition."""

    def __init__(self, competition_slug: str = "kaggriculture"):
        """Initialize submission manager."""
        self.competition_slug = competition_slug
        self.submission_history = []
        self.submission_dir = "submissions"
        Path(self.submission_dir).mkdir(parents=True, exist_ok=True)

    def check_kaggle_setup(self) -> bool:
        """Check if Kaggle API is properly configured."""
        if not KAGGLE_AVAILABLE:
            print("Kaggle API not installed. Please install with: pip install kaggle")
            return False

        try:
            # Check if kaggle.json exists
            kaggle_dir = Path.home() / ".kaggle"
            kaggle_json = kaggle_dir / "kaggle.json"

            if not kaggle_json.exists():
                print("Kaggle API token not found. Please create one at:")
                print("https://www.kaggle.com/settings/account")
                print(f"Then place it at: {kaggle_json}")
                return False

            # Test API connection
            subprocess.run(["kaggle", "--version"], capture_output=True, check=True)
            print("✓ Kaggle API configured correctly")
            return True

        except Exception as e:
            print(f"Error checking Kaggle setup: {e}")
            return False

    def create_submission_package(self, agent_file: str = "src/agent.py",
                                  notebook_template: str = None) -> str:
        """Create submission package for Kaggle."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        package_name = f"submission_{timestamp}"
        package_path = os.path.join(self.submission_dir, package_name)

        # Create package directory
        os.makedirs(package_path, exist_ok=True)

        # Copy agent files
        agent_files = [
            "src/agent.py",
            "src/utils.py",
            "config/hyperparameters.yaml"
        ]

        for file in agent_files:
            if os.path.exists(file):
                dest = os.path.join(package_path, os.path.basename(file))
                shutil.copy2(file, dest)
                print(f"✓ Copied {file} to package")

        # Create minimal requirements.txt
        requirements = [
            "kaggle-environments>=1.15.0",
            "numpy>=1.24.0",
            "pandas>=2.0.0"
        ]

        req_path = os.path.join(package_path, "requirements.txt")
        with open(req_path, 'w') as f:
            f.write("\n".join(requirements))
        print(f"✓ Created requirements.txt")

        # Create metadata
        metadata = {
            "competition": self.competition_slug,
            "timestamp": timestamp,
            "agent_version": "1.0.0",
            "files_included": [os.path.basename(f) for f in agent_files if os.path.exists(f)]
        }

        metadata_path = os.path.join(package_path, "metadata.json")
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)
        print(f"✓ Created metadata.json")

        # Create submission notebook if template provided
        if notebook_template and os.path.exists(notebook_template):
            notebook_dest = os.path.join(package_path, "submission.ipynb")
            shutil.copy2(notebook_template, notebook_dest)
            print(f"✓ Copied notebook template")

        print(f"\n✓ Submission package created: {package_path}")
        return package_path

    def create_submission_notebook(self, output_path: str = "notebooks/submission.ipynb"):
        """Create Kaggle submission notebook."""
        notebook_content = {
            "cells": [
                {
                    "cell_type": "markdown",
                    "metadata": {},
                    "source": [
                        "# Kaggriculture Submission Notebook\n",
                        "This notebook contains the submission for the Kaggriculture competition.\n",
                        "The agent is implemented in the following cells.\n",
                        "\n",
                        "**Competition:** https://www.kaggle.com/competitions/kaggriculture\n",
                        "**Created:** " + datetime.now().strftime("%Y-%m-%d %H:%M:%S") + "\n",
                        "**Agent:** Metatron Kaggriculture AI Agent"
                    ]
                },
                {
                    "cell_type": "code",
                    "execution_count": None,
                    "metadata": {},
                    "outputs": [],
                    "source": [
                        "# Install required packages\n",
                        "!pip install -q kaggle-environments numpy"
                    ]
                },
                {
                    "cell_type": "code",
                    "execution_count": None,
                    "metadata": {},
                    "outputs": [],
                    "source": [
                        "# Import dependencies\n",
                        "import sys\n",
                        "import os\n",
                        "import json\n",
                        "import numpy as np\n",
                        "from kaggle_environments import make, evaluate\n",
                        "\n",
                        "# Add agent code to path\n",
                        "sys.path.append('/kaggle/working/')\n",
                        "\n",
                        "print(\"✓ Dependencies loaded\")"
                    ]
                },
                {
                    "cell_type": "code",
                    "execution_count": None,
                    "metadata": {},
                    "outputs": [],
                    "source": [
                        "# Load agent code\n",
                        "# The agent code will be copied here during submission\n",
                        "with open('agent.py', 'r') as f:\n",
                        "    agent_code = f.read()\n",
                        "\n",
                        "exec(agent_code)\n",
                        "print(\"✓ Agent loaded successfully\")"
                    ]
                },
                {
                    "cell_type": "code",
                    "execution_count": None,
                    "metadata": {},
                    "outputs": [],
                    "source": [
                        "# Test agent locally (optional)\n",
                        "try:\n",
                        "    env = make(\"kaggriculture\", {\"episodeSteps\": 50})\n",
                        "    obs = env.reset(num_agents=2)[0].observation\n",
                        "    config = env.configuration\n",
                        "    \n",
                        "    # Test one action\n",
                        "    action = kaggriculture_agent(obs, config)\n",
                        "    print(f\"✓ Agent test successful. First action: {action}\")\n",
                        "except Exception as e:\n",
                        "    print(f\"✗ Agent test failed: {e}\")"
                    ]
                },
                {
                    "cell_type": "code",
                    "execution_count": None,
                    "metadata": {},
                    "outputs": [],
                    "source": [
                        "# Create submission function\n",
                        "# This function is required by Kaggle for agent competitions\n",
                        "def agent(observation, configuration):\n",
                        "    \"\"\"\n",
                        "    Kaggle competition agent function.\n",
                        "    This is the entry point called by the Kaggle environment.\n",
                        "    \"\"\"\n",
                        "    return kaggriculture_agent(observation, configuration)\n",
                        "\n",
                        "print(\"✓ Submission function created\")"
                    ]
                },
                {
                    "cell_type": "markdown",
                    "metadata": {},
                    "source": [
                        "## Submission Ready\n",
                        "\n",
                        "This agent is now ready for submission to the Kaggriculture competition.\n",
                        "\n",
                        "### Next Steps:\n",
                        "1. Click **Save Version** (top right)\n",
                        "2. Select **Save & Run All**\n",
                        "3. Wait for execution to complete\n",
                        "4. Click **Submit to Competition**\n",
                        "\n",
                        "### Agent Features:\n",
                        "- Multi-strategy decision making\n",
                        "- Phase-based game adaptation\n",
                        "- Market price awareness\n",
                        "- Resource optimization"
                    ]
                }
            ],
            "metadata": {
                "kernelspec": {
                    "display_name": "Python 3",
                    "language": "python",
                    "name": "python3"
                },
                "language_info": {
                    "codemirror_mode": {
                        "name": "ipython",
                        "version": 3
                    },
                    "file_extension": ".py",
                    "mimetype": "text/x-python",
                    "name": "python",
                    "nbconvert_exporter": "python",
                    "pygments_lexer": "ipython3",
                    "version": "3.10.13"
                }
            },
            "nbformat": 4,
            "nbformat_minor": 4
        }

        # Write notebook
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, 'w') as f:
            json.dump(notebook_content, f, indent=2)

        print(f"✓ Submission notebook created: {output_path}")
        return output_path

    def submit_via_api(self, package_path: str, message: str = None) -> bool:
        """Submit to Kaggle using API."""
        if not self.check_kaggle_setup():
            return False

        if not message:
            message = f"Kaggriculture submission - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"

        try:
            # Create zip file
            import zipfile
            zip_path = f"{package_path}.zip"
            with zipfile.ZipFile(zip_path, 'w') as zipf:
                for root, dirs, files in os.walk(package_path):
                    for file in files:
                        file_path = os.path.join(root, file)
                        arcname = os.path.relpath(file_path, package_path)
                        zipf.write(file_path, arcname)

            print(f"✓ Created zip archive: {zip_path}")

            # Submit via Kaggle API
            command = [
                "kaggle", "competitions", "submit",
                self.competition_slug,
                "-f", zip_path,
                "-m", message
            ]

            print(f"Submitting with command: {' '.join(command)}")
            result = subprocess.run(command, capture_output=True, text=True)

            if result.returncode == 0:
                print("✓ Submission successful!")
                print("Output:", result.stdout)
                return True
            else:
                print("✗ Submission failed:")
                print("Error:", result.stderr)
                return False

        except Exception as e:
            print(f"✗ Error during submission: {e}")
            return False

    def submit_via_manual(self, package_path: str):
        """Print manual submission instructions."""
        print("\n" + "=" *20)
        print("MANUAL SUBMISSION INSTRUCTIONS")
        print("=" *20)
        print("\nSince Kaggle API submission failed or was skipped,")
        print("you can submit manually:")
        print("\n1. Go to: https://www.kaggle.com/competitions/kaggriculture/submit")
        print("2. Click 'Upload Submission File'")
        print("3. Select the zip file from:", f"{package_path}.zip")
        print("4. Add a description and submit")
        print("\nPackage contents:")
        for root, dirs, files in os.walk(package_path):
            for file in files:
                print(f"  - {os.path.join(root, file)}")


def main():
    """Main submission function."""
    import argparse

    parser = argparse.ArgumentParser(description="Submit Kaggriculture agent to Kaggle")
    parser.add_argument("--mode", type=str, default="package",
                        choices=["package", "api", "manual", "notebook"],
                        help="Submission mode")
    parser.add_argument("--agent", type=str, default="src/agent.py",
                        help="Path to agent file")
    parser.add_argument("--message", type=str,
                        help="Submission message")
    parser.add_argument("--output", type=str, default="submissions",
                        help="Output directory")

    args = parser.parse_args()

    print("Starting Kaggriculture submission process...")

    # Initialize submission manager
    manager = SubmissionManager()

    if args.mode in ["package", "api", "manual"]:
        # Create submission package
        package_path = manager.create_submission_package(args.agent)

        if args.mode == "api":
            # Submit via API
            success = manager.submit_via_api(package_path, args.message)
            if not success:
                manager.submit_via_manual(package_path)
        elif args.mode == "manual":
            # Manual submission instructions
            manager.submit_via_manual(package_path)

    elif args.mode == "notebook":
        # Create submission notebook
        notebook_path = manager.create_submission_notebook()
        print(f"Notebook created: {notebook_path}")
        print("\nTo submit:")
        print("1. Upload this notebook to Kaggle")
        print("2. Run it in Kaggle Notebooks")
        print("3. Submit from the notebook interface")

    print("\n✓ Submission process complete!")


if __name__ == "__main__":
    main()