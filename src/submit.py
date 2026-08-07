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
            print("ERROR: Kaggle API not installed. Please install with: pip install kaggle")
            return False

        try:
            # Check for access_token (new format) or kaggle.json (legacy)
            kaggle_dir = Path.home() / ".kaggle"
            access_token = kaggle_dir / "access_token"
            kaggle_json = kaggle_dir / "kaggle.json"

            if access_token.exists():
                # Read token and set environment variable
                with open(access_token, 'r') as f:
                    token = f.read().strip()
                os.environ['KAGGLE_API_TOKEN'] = token
                print("OK: Access token found and configured")
                return True

            if kaggle_json.exists():
                print("OK: kaggle.json found")
                return True

            print("ERROR: Kaggle API token not found. Please create a token at:")
            print("https://www.kaggle.com/settings/account")
            print(f"Then place it at: {access_token}")
            return False

        except Exception as e:
            print(f"ERROR: Checking Kaggle setup: {e}")
            return False

    def create_submission_package(self, agent_file: str = "src/agent.py",
                                  notebook_template: str = None) -> str:
        """Create submission package for Kaggle (tar.gz with main.py at root)."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        package_name = f"submission_{timestamp}"
        package_path = os.path.join(self.submission_dir, package_name)

        # Create package directory
        os.makedirs(package_path, exist_ok=True)

        # Kaggle agent competitions require main.py at the ROOT of the archive
        # 1. Copy the agent source as main.py (the entry point)
        if os.path.exists(agent_file):
            shutil.copy2(agent_file, os.path.join(package_path, "main.py"))
            print(f"OK: Created main.py from {agent_file}")

        # 2. Copy helper modules (files that main.py imports)
        helper_files = ["src/utils.py", "config/hyperparameters.yaml"]
        for file in helper_files:
            if os.path.exists(file):
                dest = os.path.join(package_path, os.path.basename(file))
                shutil.copy2(file, dest)
                print(f"OK: Copied {file} to package")

        # 3. Create requirements.txt
        requirements = [
            "kaggle-environments>=1.15.0",
            "numpy>=1.24.0",
            "pandas>=2.0.0"
        ]
        req_path = os.path.join(package_path, "requirements.txt")
        with open(req_path, 'w') as f:
            f.write("\n".join(requirements))
        print(f"OK: Created requirements.txt")

        # 4. Create metadata (non-essential but useful)
        metadata = {
            "competition": self.competition_slug,
            "timestamp": timestamp,
            "agent_version": "1.0.0",
            "entry_point": "main.py"
        }
        metadata_path = os.path.join(package_path, "metadata.json")
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)

        # 5. Create submission.tar.gz with files at root
        import tarfile
        tar_path = f"{package_path}.tar.gz"
        with tarfile.open(tar_path, "w:gz") as tar:
            for fname in os.listdir(package_path):
                fpath = os.path.join(package_path, fname)
                if os.path.isfile(fpath):
                    tar.add(fpath, arcname=fname)  # arcname = basename (root)
        print(f"OK: Created tar archive: {tar_path}")

        print(f"\nOK: Submission package created: {package_path}")
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

        print(f"OK: Submission notebook created: {output_path}")
        return output_path

    def submit_via_api(self, package_path: str, message: str = None) -> bool:
        """Submit to Kaggle using API."""
        if not self.check_kaggle_setup():
            return False

        if not message:
            message = f"Kaggriculture submission - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"

        try:
            # Use the tar.gz created by create_submission_package
            tar_path = f"{package_path}.tar.gz"
            if not os.path.exists(tar_path):
                print(f"ERROR: Submission archive not found: {tar_path}")
                return False

            print(f"OK: Using submission archive: {tar_path}")

            # Submit via Kaggle Python API
            from kaggle.api.kaggle_api_extended import KaggleApi
            api = KaggleApi()
            api.authenticate()

            print(f"Submitting: {self.competition_slug} with file {tar_path}")
            api.competition_submit(tar_path, message, self.competition_slug)
            print("OK: Submission sent successfully!")
            return True

        except Exception as e:
            print(f"ERROR: Failed during submission: {e}")
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
        print("3. Select the file from:", f"{package_path}.tar.gz")
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

    print("\nOK: Submission process complete!")


if __name__ == "__main__":
    main()