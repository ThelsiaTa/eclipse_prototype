import json
import csv
import re
import os
from datetime import datetime

# Main class to analyze problematic commits
class ProblematicCommitAnalyzer:
    def __init__(self, data_path=None, data=None):
        # Load data from file or direct input
        if data:
            self.data = data
        elif data_path:
            # Read JSON file
            with open(data_path, 'r', encoding='utf-8') as f:
                self.data = json.load(f)
        else:
            raise ValueError("Need either data_path or data!")
        
        # Create output folder
        self.output_dir = "commit_analysis"
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)
    
    # Analyze a single commit to see if it's problematic
    def analyze_commit(self, commit, test_failures, diff):
        # Basic info about the commit
        analysis = {
            "sha": commit.get("sha", ""),
            "author": commit.get("commit", {}).get("author", {}).get("name", ""),
            "message": commit.get("commit", {}).get("message", ""),
            "date": commit.get("commit", {}).get("author", {}).get("date", ""),
            "raw_score": 0,  # raw score before normalization
            "score": 0,      # normalized score (0-100)
            "category": "Safe",  # "Likely Problematic" or "Safe"
            "reasons": []  # why we think it's problematic
        }
        
        # RULE 1: Check commit message for test names
        commit_msg = analysis["message"].lower()
        
        # Look for test names in commit message
        for test in test_failures["tests"]:
            test_lower = test.lower()
            if test_lower in commit_msg:
                analysis["raw_score"] += 30
                analysis["reasons"].append(f"Commit mentions failed test: {test}")
        
        # Look for error message keywords in commit message
        for error in test_failures["error_messages"]:
            # Get words from error message
            keywords = re.findall(r'\b\w+\b', error.lower())
            # Filter out short words
            keywords = [word for word in keywords if len(word) > 3]
            
            # Check if commit message has these keywords
            matches = [word for word in keywords if word in commit_msg]
            if len(matches) >= 2:  # Need at least 2 matching words
                analysis["raw_score"] += 20
                analysis["reasons"].append(f"Commit message has error keywords: {', '.join(matches)}")
        
        # RULE 2: Check for test-related code changes
        test_patterns = [
            r'test', r'spec', r'benchmark', r'perf', r'performance', 
            r'assert', r'expect', r'should', r'mock', r'stub'
        ]
        
        for pattern in test_patterns:
            if re.search(pattern, diff, re.IGNORECASE):
                analysis["raw_score"] += 10
                analysis["reasons"].append(f"Changed code contains '{pattern}' patterns")
                break  # Only count once
        
        # RULE 3: Check for risky code patterns
        risky_patterns = [
            # Concurrency stuff
            (r'Thread', r'synchronize', r'concurrent', r'lock', r'atomic', r'volatile'),
            # Memory stuff
            (r'memory', r'allocation', r'free', r'delete', r'new '),
            # Timing stuff
            (r'timeout', r'sleep', r'wait', r'delay'),
            # Performance stuff
            (r'performance', r'optimize', r'speed', r'slow'),
            # Config stuff
            (r'config', r'settings', r'parameter', r'constant'),
        ]
        
        for pattern_group in risky_patterns:
            matches = []
            for p in pattern_group:
                if re.search(p, diff, re.IGNORECASE):
                    matches.append(p)
            
            if matches:
                analysis["raw_score"] += 15
                analysis["reasons"].append(f"Code has risky patterns: {', '.join(matches)}")
                break  # Only count each group once
        
        # RULE 4: Big changes are risky
        # Count lines added/removed
        lines_changed = 0
        for line in diff.split('\n'):
            if line.startswith('+') or line.startswith('-'):
                lines_changed += 1
        
        if lines_changed > 100:
            analysis["raw_score"] += 10
            analysis["reasons"].append(f"Large change with {lines_changed} lines modified")
        
        # RULE 5: Changes to many files are risky
        # Count number of files changed
        files_changed = len(re.findall(r'diff --git', diff))
        if files_changed > 5:
            analysis["raw_score"] += 10
            analysis["reasons"].append(f"Changes {files_changed} different files")
            
        # RULE 6: Critical Area Impact
        critical_patterns = [
            r'auth', r'security', r'password', r'crypt', r'login',  # Authentication
            r'payment', r'transaction', r'credit', r'debit', r'money',  # Payment
            r'core', r'kernel', r'runtime', r'cpu',  # Core system
            r'database', r'db', r'sql', r'query', r'storage'  # Data storage
        ]
        
        for pattern in critical_patterns:
            if re.search(pattern, diff, re.IGNORECASE):
                analysis["raw_score"] += 15
                analysis["reasons"].append(f"Changes affect critical area: {pattern}")
                break  # Only count once
                
        # RULE 7: Lack of Tests
        # Simple check: prod code changed but test code isn't
        has_prod_changes = False
        has_test_changes = False
        
        for line in diff.split('\n'):
            if line.startswith('diff --git'):
                file_path = line.split()[-1]
                if 'test' in file_path.lower():
                    has_test_changes = True
                else:
                    has_prod_changes = True
        
        if has_prod_changes and not has_test_changes:
            analysis["raw_score"] += 20
            analysis["reasons"].append("Changes production code without updating tests")
        
        # RULE 8: Poor Documentation
        # Check for very short commit messages
        if len(commit_msg.strip()) < 20:
            analysis["raw_score"] += 10
            analysis["reasons"].append("Very short commit message (poor documentation)")
        
        # Count meaningful words (at least 4 letters)
        meaningful_words = len(re.findall(r'\b[a-zA-Z]{4,}\b', commit_msg))
        if meaningful_words < 5:
            analysis["raw_score"] += 10
            analysis["reasons"].append("Commit message lacks descriptive content")
        
        # RULE 9: Code Complexity Increase
        # Count new control structures (if, for, while, etc.)
        control_patterns = [
            r'if\s*\(', r'for\s*\(', r'while\s*\(', r'switch\s*\(', 
            r'catch\s*\(', r'try\s*\{', r'else\s*[\{\:]'
        ]
        
        complexity_score = 0
        for pattern in control_patterns:
            # Look for the pattern in added lines (starting with +)
            matches = re.findall(r'\+.*' + pattern, diff, re.IGNORECASE)
            complexity_score += len(matches)
        
        if complexity_score > 5:
            analysis["raw_score"] += 15
            analysis["reasons"].append(f"Adds {complexity_score} new control structures (increased complexity)")
        
        # RULE 10: Odd Timing
        # Check if commit was made outside normal hours
        try:
            if analysis["date"]:
                # Parse the ISO date format
                date_str = analysis["date"].replace('Z', '+00:00')
                commit_date = datetime.fromisoformat(date_str)
                hour = commit_date.hour
                
                # Assuming normal hours are 9am-5pm
                if hour < 9 or hour > 17:
                    analysis["raw_score"] += 10
                    analysis["reasons"].append(f"Commit made at unusual hour: {hour}:00")
        except:
            # Skip this rule if we can't parse the date
            pass
        
        # RULE 11: Suspicious Keywords
        # Look for words that suggest bypassing normal processes
        bypass_words = [
            r'hotfix', r'emergency', r'bypass', r'skip[ -]ci', r'no[ -]review',
            r'urgent', r'asap', r'quick fix', r'workaround', r'hack'
        ]
        
        for word in bypass_words:
            if re.search(word, commit_msg, re.IGNORECASE):
                analysis["raw_score"] += 25
                analysis["reasons"].append(f"Contains suspicious keyword: '{word}'")
                break  # Only count once
        
        # Calculate normalized score (0-100)
        # The theoretical maximum is around 180, so we'll use that to normalize
        # Setting the max score to avoid scores above 100
        MAX_THEORETICAL_SCORE = 180
        analysis["score"] = min(100, int((analysis["raw_score"] / MAX_THEORETICAL_SCORE) * 100))
        
        # Decide if it's problematic or safe - using the normalized score
        if analysis["score"] >= 30:
            analysis["category"] = "Likely Problematic"
        else:
            analysis["category"] = "Safe"
        
        return analysis
    
    # Placeholder for binary search implementation
    def binary_search(self, test_name):
        good_sha = self.data["good_build"]["sha"]
        bad_sha = self.data["bad_build"]["sha"]
        commits = self.data["commits"]
        
        if not commits:
            return "No commits found"
        
        return f"Would test {len(commits)} commits between {good_sha} and {bad_sha}"
    
    # Analyze all commits
    def analyze_commits(self):
        good_sha = self.data["good_build"]["sha"]
        bad_sha = self.data["bad_build"]["sha"]
        commits = self.data["commits"]
        diffs = self.data["commit_diffs"]
        test_failures = self.data["bad_build"]["test_failures"]
        
        # Setup lists to store results
        all_analyzed = []
        problematic = []
        safe_commits = []
        
        print("Analyzing each commit...")
        for i, commit in enumerate(commits):
            sha = commit.get("sha", "")
            if sha in diffs:
                print(f"Analyzing commit {i+1}/{len(commits)}: {sha[:7]}...")
                diff = diffs[sha]
                result = self.analyze_commit(commit, test_failures, diff)
                all_analyzed.append(result)
                
                # Sort into problematic or safe
                if result["category"] == "Likely Problematic":
                    problematic.append(result)
                else:
                    safe_commits.append(result)
            else:
                print(f"Warning: No diff for commit {sha[:7]}, skipping")
        
        # Sort problematic commits by score (highest first)
        problematic.sort(key=lambda x: x["score"], reverse=True)
        
        # Final results
        result = {
            "good_build": {
                "sha": good_sha,
                "details": self.data["good_build"]["details"]
            },
            "bad_build": {
                "sha": bad_sha,
                "details": self.data["bad_build"]["details"],
                "test_failures": test_failures
            },
            "total_commits_analyzed": len(all_analyzed),
            "likely_problematic_commits": problematic,
            "safe_commits": safe_commits
        }
        
        return result
    
    # Save results to files
    def save_analysis(self, analysis, output_prefix=None):
        if not output_prefix:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            repo_name = "repo"  # default name
            
            # Try to get the actual repo name
            try:
                repo_name = self.data["bad_build"]["details"]["repository"]["name"]
            except:
                pass  # stick with default if we can't get it
                
            output_prefix = f"{self.output_dir}/{timestamp}_{repo_name}"
        
        # Save JSON data
        json_path = f"{output_prefix}_analysis.json"
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(analysis, f, indent=2)
        
        # Save problematic commits CSV
        problematic_path = f"{output_prefix}_problematic_commits.csv"
        with open(problematic_path, 'w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                "SHA", "Author", "Date", "Score", "Raw Score", "Category", "Reasons", "Commit Message"
            ])
            
            for commit in analysis["likely_problematic_commits"]:
                writer.writerow([
                    commit["sha"],
                    commit["author"],
                    commit["date"],
                    commit["score"],
                    commit.get("raw_score", "N/A"),
                    commit["category"],
                    "; ".join(commit["reasons"]),
                    commit["message"].replace("\n", " ")
                ])
        
        # Save test failures CSV
        failures_path = f"{output_prefix}_test_failures.csv"
        with open(failures_path, 'w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(["Test Name", "Error Message"])
            
            for test in analysis["bad_build"]["test_failures"]["tests"]:
                writer.writerow([test, ""])
            
            for msg in analysis["bad_build"]["test_failures"]["error_messages"]:
                writer.writerow(["", msg])
        
        # Save summary text file
        summary_path = f"{output_prefix}_summary.txt"
        with open(summary_path, 'w', encoding='utf-8') as f:
            f.write(f"Problematic Commit Analysis Summary\n")
            f.write(f"====================================\n\n")
            f.write(f"Good Build: {analysis['good_build']['sha']}\n")
            f.write(f"Bad Build: {analysis['bad_build']['sha']}\n\n")
            
            f.write(f"Test Failures: {analysis['bad_build']['test_failures']['count']}\n")
            if analysis['bad_build']['test_failures']['tests']:
                f.write("Failed Tests:\n")
                for test in analysis['bad_build']['test_failures']['tests']:
                    f.write(f"- {test}\n")
            
            f.write(f"\nTotal Commits Analyzed: {analysis['total_commits_analyzed']}\n")
            f.write(f"Likely Problematic Commits: {len(analysis['likely_problematic_commits'])}\n")
            f.write(f"Safe Commits: {len(analysis['safe_commits'])}\n\n")
            
            if analysis['likely_problematic_commits']:
                f.write("Top Problematic Commits:\n")
                # Show top 5 or fewer
                top_commits = analysis['likely_problematic_commits'][:5]
                for i, commit in enumerate(top_commits):
                    f.write(f"\n{i+1}. SHA: {commit['sha']}\n")
                    f.write(f"   Author: {commit['author']}\n")
                    f.write(f"   Score: {commit['score']} (Raw: {commit.get('raw_score', 'N/A')})\n")
                    f.write(f"   Message: {commit['message'].strip()}\n")
                    f.write(f"   Reasons:\n")
                    for reason in commit['reasons']:
                        f.write(f"   - {reason}\n")
        
        # Return paths to the files
        return {
            "json": json_path,
            "problematic": problematic_path,
            "failures": failures_path,
            "summary": summary_path
        }


# Function to run with command line args
def run_with_args():
    import argparse
    
    parser = argparse.ArgumentParser(description='Problematic Commit Analyzer')
    parser.add_argument('--data-path', required=True, help='Path to data JSON file')
    parser.add_argument('--output-prefix', help='Prefix for output files')
    
    args = parser.parse_args()
    
    analyzer = ProblematicCommitAnalyzer(data_path=args.data_path)
    
    try:
        print(f"Analyzing commits using data from: {args.data_path}")
        
        analysis = analyzer.analyze_commits()
        saved_files = analyzer.save_analysis(analysis, args.output_prefix)
        
        print("\nAnalysis complete!")
        print(f"Found {len(analysis['likely_problematic_commits'])} likely problematic commits")
        print(f"Summary: {saved_files['summary']}")
        print(f"Problematic commits: {saved_files['problematic']}")
        print(f"Test failures: {saved_files['failures']}")
        print(f"Full JSON: {saved_files['json']}")
        
    except Exception as e:
        print(f"Error: {e}")
        exit(1)


# Main script
if __name__ == "__main__":
    # Path to the data file from github_data_collector.py
    DATA_PATH = r"github_data\20250323_003325_openj9_data.json"
    
    # Check if we have a data path
    if DATA_PATH:
        print(f"Using data file: {DATA_PATH}")
        
        try:
            analyzer = ProblematicCommitAnalyzer(data_path=DATA_PATH)
            analysis = analyzer.analyze_commits()
            saved_files = analyzer.save_analysis(analysis)
            
            print("\nAnalysis complete!")
            print(f"Found {len(analysis['likely_problematic_commits'])} likely problematic commits")
            print(f"Summary: {saved_files['summary']}")
            print(f"Problematic commits: {saved_files['problematic']}")
            print(f"Test failures: {saved_files['failures']}")
            print(f"Full JSON: {saved_files['json']}")
        except Exception as e:
            print(f"Error: {e}")
    else:
        # If no data path, use command line
        print("No data path set, using command line")
        run_with_args()