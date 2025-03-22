# Problematic Commit Finder

A tool that helps developers identify which Git commits likely caused test failures by comparing a "good" build (where tests pass) and a "bad" build (where tests fail).

## Purpose

This prototype was developed to solve a common problem in software development: finding which commit broke the build. When tests suddenly start failing, developers often spend hours manually checking each commit to identify the culprit. This tool automates that process by analyzing commits between a working and non-working state to highlight the most likely problematic ones.

The goal is to develop an automated system that identifies problematic Git commits causing test failures in both performance and non-performance test scenarios. Instead of checking all commits manually, this tool narrows down the search to the most suspicious ones.

## Project Phases

### Phase 1: Rule-Based Approach (Current)
The current implementation uses a comprehensive rule-based system to identify problematic commits.

### Phase 2: Machine Learning Approach (Planned)
The next phase will implement machine learning models to improve accuracy by learning from historical data.

## How It Works

The system consists of two main components:

1. **GitHub Data Collector** (`github_data_collector.py`): 
   - Collects all the necessary data from GitHub
   - Fetches commit details, code diffs, and test failure information
   - Creates a comprehensive JSON dataset

2. **Problematic Commit Analyzer** (`problematic_commit_analyzer.py`): 
   - Analyzes the collected data using rule-based techniques
   - Scores each commit based on how likely it is to have caused the test failures
   - Generates reports to help developers focus their debugging efforts

## Rule-Based Analysis

The analyzer applies a point-based scoring system with 11 comprehensive rules. Each rule contributes to a raw score, which is then normalized to a 0-100 scale:

### Core Rules

1. **String Matching** (+30 points)
   - Checks if commit messages mention failed tests directly
   - Example: If a test named "TestMemoryAllocation" is failing and a commit message mentions "fixing memory allocation test"

2. **Error Keyword Matching** (+20 points) 
   - Extracts keywords from error messages and checks if they appear in commit messages
   - Requires at least 2 matching keywords to reduce coincidences

3. **Test-Related Code Changes** (+10 points)
   - Identifies changes to test code or test-related components
   - Looks for patterns like 'test', 'assert', 'benchmark', 'performance', etc.

4. **Risky Code Pattern Detection** (+15 points)
   - Identifies changes to code areas that commonly cause issues:
     - Concurrency (threads, locks, synchronization)
     - Memory management
     - Timing mechanisms
     - Performance-related code
     - Configuration changes

5. **Large Changes** (+10 points)
   - Flags commits with more than 100 lines changed
   - Large changes are more likely to introduce bugs

6. **Multiple Files** (+10 points)
   - Flags commits that modify more than 5 different files
   - Widespread changes increase the risk of unintended side effects

### Additional Risk Assessment Rules

7. **Critical Area Impact** (+15 points)
   - Detects changes to sensitive areas like authentication, payment processing, databases
   - These areas have higher impact when failures occur

8. **Lack of Tests** (+20 points)
   - Identifies production code changes without corresponding test updates
   - Changes without test coverage are higher risk

9. **Poor Documentation** (+10 points)
   - Flags very short or vague commit messages
   - Poor documentation may indicate rushed changes or incomplete review

10. **Code Complexity Increase** (+15 points)
    - Measures introduction of new control structures (if, for, while, etc.)
    - Complex code changes are more error-prone

11. **Suspicious Commit Patterns** (+10-25 points)
    - Identifies commits made at unusual hours
    - Detects keywords suggesting bypassing normal processes ("hotfix", "emergency", "hack")

### Scoring and Categorization

- Raw scores are calculated by adding points from all triggered rules
- The raw score is then normalized to a 0-100 scale for easier interpretation
- Commits scoring 30 or more points are categorized as "Likely Problematic"
- All other commits are categorized as "Safe"
- Results are sorted by likelihood score (highest first)

## Binary Search Capability

For performance-related issues, the system includes a placeholder for binary search implementation that will:

1. Start with the range of commits between good and bad builds
2. Test the middle commit
3. Narrow search to first or second half based on test results
4. Repeat until finding the exact problematic commit

*Note: Full binary search implementation requires integration with your build system.*

## Planned Machine Learning Approach (Phase 2)

The upcoming ML-based approach will offer more sophisticated analysis:

### Text Representation with BERT/CodeBERT
- Use BERT for semantic understanding of commit messages and error messages
- Use CodeBERT (specialized for code) to analyze code diffs
- Capture meaning beyond simple keyword matching

### Model Selection
- **Primary Model: XGBoost** - Excellent at combining multiple weak signals, handles feature interactions well
- **Alternative: Random Forest** - More interpretable, resistant to overfitting
- **Future Exploration: Neural Networks** - For capturing complex non-linear relationships

### Advanced Feature Engineering
1. **Commit Metadata:**
   - Time of day and day of week
   - Author experience (commit history)
   - File modification frequency
   
2. **Code Complexity Metrics:**
   - Cyclomatic complexity changes
   - Function/method size changes
   - Nesting level changes

3. **Structural Features:**
   - Project component modifications
   - Test coverage of modified files
   - Dependencies between files

### Future Consideration: Graph Representation
- Represent commits, files, and tests as a graph structure
- Model dependencies and change propagation
- Use Graph Neural Networks for structural awareness

## Setup and Usage

### Prerequisites
- Python 3.6+
- GitHub Personal Access Token

### Installation
1. Clone this repository
2. Install required packages: `pip install requests`

### Running the Tool
1. Edit `github_data_collector.py` to insert your GitHub token and repository details:

   ```python
   YOUR_GITHUB_TOKEN = "github_pat_xxx"
   REPO_OWNER = "eclipse-openj9"
   REPO_NAME = "openj9"
   GOOD_COMMIT_SHA = "ffdf96d"  # SHA of the good build
   BAD_COMMIT_SHA = "c08b414"   # SHA of the bad build
   ```

2. Run the data collector:
   ```
   python github_data_collector.py
   ```
   This will create a JSON file in the `github_data` directory.

3. Update `problematic_commit_analyzer.py` with the path to your data file:
   ```python
   DATA_PATH = "github_data/20250322_160155_openj9_data.json"
   ```

4. Run the analyzer:
   ```
   python problematic_commit_analyzer.py
   ```

## Output Files

The analyzer generates four main output files:

1. **Summary text file**: Human-readable overview of the analysis results
2. **Problematic commits CSV**: Detailed information about likely problematic commits
3. **Test failures CSV**: Information about the failed tests
4. **Complete JSON analysis**: Raw data for further processing

The summary file shows:
- Details about good and bad builds
- List of test failures
- Count of problematic and safe commits
- Top problematic commits with their scores and reasons

## Example Output

```
Problematic Commit Analysis Summary
====================================

Good Build: ffdf96d
Bad Build: c08b414

Test Failures: 2
Failed Tests:
- MemoryLeak
- TestThreadSafety

Total Commits Analyzed: 17
Likely Problematic Commits: 3
Safe Commits: 14

Top Problematic Commits:

1. SHA: a1b2c3d
   Author: John Doe
   Score: 75 (Raw: 135)
   Message: Fix memory allocation in threaded context
   Reasons:
   - Commit message contains error keywords: memory, allocation, thread
   - Code has risky patterns: Thread, memory, allocation
   - Large change with 156 lines modified
   - Changes affect critical area: memory

2. SHA: e4f5g6h
   Author: Jane Smith
   Score: 45 (Raw: 80)
   Message: Update thread safety tests
   Reasons:
   - Commit mentions failed test: TestThreadSafety
   - Modified code contains test patterns
   - Code has risky patterns: Thread, synchronize
```

## Future Development

This project is being developed in phases:

1. **Current Phase (Rule-Based)**: 
   - ✅ Data collection from GitHub
   - ✅ Comprehensive rule-based analysis
   - ✅ Detailed reporting system

2. **Next Phase (Machine Learning)**:
   - 🔄 BERT/CodeBERT encodings for text
   - 🔄 XGBoost model implementation
   - 🔄 Enhanced feature engineering

3. **Future Enhancements**:
   - 📝 Graph Neural Networks for structural awareness
   - 📝 Full binary search implementation
   - 📝 Integration with CI/CD pipelines
