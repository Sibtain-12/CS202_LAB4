import os
import csv
import subprocess
from pydriller import Repository
import pandas as pd
import matplotlib.pyplot as plt

# --------------------
# Helper: run git diff safely with UTF-8
# --------------------
def run_git_diff(repo_path, parent, commit_hash, file_path, algo):
    cmd = [
        "git", "-C", repo_path, "diff", parent, commit_hash, "--", file_path,
        "--ignore-blank-lines", "--ignore-space-change", f"--diff-algorithm={algo}"
    ]
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace"
    )
    return result.stdout

# Normalize diff for better comparison
def normalize_diff(diff_text):
    lines = [
        line.strip()
        for line in diff_text.splitlines()
        if not line.startswith("index") and not line.startswith("---") and not line.startswith("+++")
    ]
    return "\n".join(lines)

# --------------------
# Repo setup
# --------------------
BASE_DIR = "repos"
os.makedirs(BASE_DIR, exist_ok=True)

repos = {
    "MaxKB": ("https://github.com/1Panel-dev/MaxKB.git", 100),
    "police-brutality": ("https://github.com/2020pb/police-brutality.git", 100),
    "manim": ("https://github.com/3b1b/manim.git", 300)   # more commits for manim
}

# Clone or pull repos
for name, (url, _) in repos.items():
    repo_path = os.path.join(BASE_DIR, name)
    if not os.path.exists(repo_path):
        print(f"Cloning {name}...")
        subprocess.run(["git", "clone", url, repo_path])
    else:
        print(f"Repository {name} already exists, pulling latest changes...")
        subprocess.run(["git", "-C", repo_path, "pull"])

# --------------------
# Part (c) + (d): Generate dataset with discrepancies
# --------------------
csv_file = "diff_dataset_final.csv"
with open(csv_file, "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerow([
        "repo", "old_file_path", "new_file_path", "commit_SHA",
        "parent_commit_SHA", "commit_message",
        "diff_myers", "diff_hist", "Discrepancy"
    ])

    for name, (url, max_commits) in repos.items():
        repo_path = os.path.join(BASE_DIR, name)
        print(f"\nAnalyzing repository: {name}")

        commit_count = 0
        for commit in Repository(repo_path).traverse_commits():
            if commit_count >= max_commits:
                break
            commit_count += 1

            for mod in commit.modified_files:
                if mod.old_path is None or mod.new_path is None:
                    continue
                if not commit.parents:  # Skip root commits
                    continue
                parent = commit.parents[0]

                # Run diffs safely
                diff_myers = run_git_diff(repo_path, parent, commit.hash, mod.new_path, "myers")
                diff_hist = run_git_diff(repo_path, parent, commit.hash, mod.new_path, "histogram")

                # Normalize
                norm_myers = normalize_diff(diff_myers)
                norm_hist = normalize_diff(diff_hist)

                # Discrepancy detection:
                # either content differs OR line counts differ
                discrepancy = "Yes" if (norm_myers != norm_hist or 
                                        len(norm_myers.splitlines()) != len(norm_hist.splitlines())) else "No"

                writer.writerow([
                    name, mod.old_path, mod.new_path, commit.hash,
                    parent, commit.msg.strip(), diff_myers, diff_hist, discrepancy
                ])

print(f"\n Final dataset generated as {csv_file}")

# --------------------
# Part (e): Stats + Plots
# --------------------
print("\n Generating mismatch statistics...")

df = pd.read_csv(csv_file)
mismatches = df[df["Discrepancy"] == "Yes"]

categories = {
    "Source Code": mismatches[mismatches["new_file_path"].str.endswith(
        (".py", ".cpp", ".java", ".js", ".ts", ".c"), na=False
    )],
    "Test Code": mismatches[mismatches["new_file_path"].str.contains("test", case=False, na=False)],
    "README": mismatches[mismatches["new_file_path"].str.contains("README", case=False, na=False)],
    "LICENSE": mismatches[mismatches["new_file_path"].str.contains("LICENSE", case=False, na=False)]
}

counts = {cat: len(data) for cat, data in categories.items()}

print("\nMismatch counts:")
for cat, count in counts.items():
    print(f"{cat}: {count}")

if any(counts.values()):
    plt.bar(counts.keys(), counts.values())
    plt.xlabel("File Type")
    plt.ylabel("Number of Mismatches")
    plt.title("Mismatch Statistics by File Type")
    plt.tight_layout()
    plt.savefig("mismatch_statistics.png")
    plt.show()
    print("\n Plot saved as mismatch_statistics.png")
else:
    print("\n No mismatches found — plot skipped.")


