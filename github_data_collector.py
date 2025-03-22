import requests
import json
import time
import os
from datetime import datetime

# Main class to collect GitHub data
class GitHubDataCollector:
    def __init__(self, token, owner, repo):
        # store the basics
        self.token = token
        self.owner = owner
        self.repo = repo
        # setup headers for GitHub API
        self.headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json"
        }
        self.base_url = f"https://api.github.com/repos/{owner}/{repo}"
        
        # make a folder for our data
        self.data_dir = "github_data"
        if not os.path.exists(self.data_dir):
            os.makedirs(self.data_dir)
    
    # helper function to make API calls
    def _make_request(self, url, params=None):
        # try to get data from GitHub
        try:
            response = requests.get(url, headers=self.headers, params=params)
            
            # handle rate limits
            if response.status_code == 403 and 'X-RateLimit-Remaining' in response.headers:
                if int(response.headers['X-RateLimit-Remaining']) == 0:
                    reset_time = int(response.headers['X-RateLimit-Reset'])
                    wait_time = reset_time - int(time.time()) + 1
                    print(f"Hit rate limit! Waiting {wait_time} seconds...")
                    time.sleep(wait_time)
                    # try again
                    return self._make_request(url, params)
            
            # if it worked, return the JSON
            if response.ok:
                return response.json()
            else:
                print(f"Error: {response.status_code} - {response.text}")
                # maybe try again once more
                time.sleep(2)
                retry_response = requests.get(url, headers=self.headers, params=params)
                if retry_response.ok:
                    return retry_response.json()
                return None
            
        except Exception as e:
            print(f"Request failed: {e}")
            return None
    
    # get info about a specific commit
    def get_commit_details(self, sha):
        url = f"{self.base_url}/commits/{sha}"
        return self._make_request(url)
    
    # get the diff (code changes) for a commit
    def get_commit_diff(self, sha):
        url = f"{self.base_url}/commits/{sha}"
        headers = self.headers.copy()
        headers["Accept"] = "application/vnd.github.v3.diff"
        
        try:
            response = requests.get(url, headers=headers)
            if response.status_code == 200:
                return response.text
            else:
                print(f"Couldn't get diff for {sha}")
                return ""
        except:
            print(f"Error getting diff for {sha}")
            return ""
    
    # get all commits between good and bad
    def get_all_commits_between(self, good_sha, bad_sha):
        url = f"{self.base_url}/compare/{good_sha}...{bad_sha}"
        data = self._make_request(url)
        
        if not data or "commits" not in data:
            print(f"Couldn't get commits between {good_sha} and {bad_sha}")
            return []
        
        return data["commits"]
    
    # get all check runs for a commit
    def get_check_runs(self, sha):
        url = f"{self.base_url}/commits/{sha}/check-runs"
        data = self._make_request(url)
        if data:
            return data.get("check_runs", [])
        return []
    
    # get all workflow runs for a commit
    def get_workflow_runs(self, sha):
        url = f"{self.base_url}/actions/runs"
        params = {"head_sha": sha}
        data = self._make_request(url, params=params)
        if data:
            return data.get("workflow_runs", [])
        return []
    
    # extract test failures from a commit
    def extract_test_failures(self, sha):
        # setup our data structure
        failures = {
            "count": 0,
            "tests": [],
            "error_messages": []
        }
        
        # First check workflow runs
        print("Checking workflow runs...")
        workflow_runs = self.get_workflow_runs(sha)
        for run in workflow_runs:
            run_id = run.get("id")
            if run_id:
                # get jobs for this run
                jobs_url = f"{self.base_url}/actions/runs/{run_id}/jobs"
                jobs_data = self._make_request(jobs_url)
                
                if jobs_data and "jobs" in jobs_data:
                    for job in jobs_data["jobs"]:
                        if job.get("conclusion") == "failure":
                            job_name = job.get("name", "Unknown job")
                            # look at each step
                            for step in job.get("steps", []):
                                if step.get("conclusion") == "failure":
                                    step_name = step.get("name", "Unknown step")
                                    failures["count"] += 1
                                    
                                    # save the test name
                                    if step_name not in failures["tests"]:
                                        failures["tests"].append(step_name)
                                    
                                    # make an error message
                                    error = f"Failure in {job_name} / {step_name}"
                                    if error not in failures["error_messages"]:
                                        failures["error_messages"].append(error)
        
        # Then check check runs (yes, that's not a typo)
        print("Checking check runs...")
        check_runs = self.get_check_runs(sha)
        for check in check_runs:
            if check.get("conclusion") not in ["success", "skipped", None]:
                check_name = check.get("name", "Unknown check")
                output = check.get("output", {})
                title = output.get("title", "")
                summary = output.get("summary", "")
                
                failures["count"] += 1
                
                # save the test name
                if check_name not in failures["tests"]:
                    failures["tests"].append(check_name)
                
                # save error message if we have one
                if title or summary:
                    error = f"{title}: {summary}"
                    if error not in failures["error_messages"]:
                        failures["error_messages"].append(error)
        
        return failures
    
    # main function to collect all the data
    def collect_data(self, good_sha, bad_sha):
        # Step 1: Get commit details
        print(f"Getting good build info ({good_sha})...")
        good_commit = self.get_commit_details(good_sha)
        
        print(f"Getting bad build info ({bad_sha})...")
        bad_commit = self.get_commit_details(bad_sha)
        
        if not good_commit or not bad_commit:
            raise ValueError("Couldn't get commit details!")
        
        # Step 2: Get all commits between good and bad
        print(f"Getting commits between good and bad...")
        commits = self.get_all_commits_between(good_sha, bad_sha)
        print(f"Found {len(commits)} commits to look at")
        
        # Step 3: Get test failures
        print(f"Getting test failures from bad build...")
        test_failures = self.extract_test_failures(bad_sha)
        print(f"Found {test_failures['count']} test failures")
        
        # Step 4: Get diffs for each commit
        print(f"Getting diffs for each commit...")
        commit_diffs = {}
        for i, commit in enumerate(commits):
            sha = commit.get("sha", "")
            if sha:
                print(f"Getting diff for commit {i+1}/{len(commits)}: {sha[:7]}...")
                diff = self.get_commit_diff(sha)
                commit_diffs[sha] = diff
        
        # Step 5: Put it all together
        collected_data = {
            "good_build": {
                "sha": good_sha,
                "details": good_commit
            },
            "bad_build": {
                "sha": bad_sha,
                "details": bad_commit,
                "test_failures": test_failures
            },
            "commits": commits,
            "commit_diffs": commit_diffs
        }
        
        return collected_data
    
    # save data to a file
    def save_data(self, data, output_prefix=None):
        if not output_prefix:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_prefix = f"{self.data_dir}/{timestamp}_{self.repo}"
        
        # save the JSON
        data_path = f"{output_prefix}_data.json"
        with open(data_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
        
        print(f"Data saved to: {data_path}")
        return data_path


# Function to run with command line args
def run_with_args():
    import argparse
    
    parser = argparse.ArgumentParser(description='GitHub Data Collector')
    parser.add_argument('--token', required=True, help='GitHub Token')
    parser.add_argument('--owner', required=True, help='Repo Owner')
    parser.add_argument('--repo', required=True, help='Repo Name')
    parser.add_argument('--good-sha', required=True, help='Good Build SHA')
    parser.add_argument('--bad-sha', required=True, help='Bad Build SHA')
    parser.add_argument('--output-prefix', help='Output filename prefix')
    
    args = parser.parse_args()
    
    collector = GitHubDataCollector(args.token, args.owner, args.repo)
    
    try:
        print(f"Collecting data for {args.owner}/{args.repo}")
        data = collector.collect_data(args.good_sha, args.bad_sha)
        data_path = collector.save_data(data, args.output_prefix)
        print("\nAll done!")
        print(f"Data saved to: {data_path}")
        
    except Exception as e:
        print(f"Error: {e}")
        exit(1)


# Main script
if __name__ == "__main__":
    # Fill in your values here
    YOUR_GITHUB_TOKEN = "YOUR_GITHUB_TOKEN"
    REPO_OWNER = "eclipse-openj9"
    REPO_NAME = "openj9"
    GOOD_COMMIT_SHA = "ffdf96d"
    BAD_COMMIT_SHA = "9d6f392"
    
    # Check if we have all the values
    if YOUR_GITHUB_TOKEN and REPO_OWNER and REPO_NAME and GOOD_COMMIT_SHA and BAD_COMMIT_SHA:
        print(f"Using hardcoded values for {REPO_OWNER}/{REPO_NAME}")
        
        collector = GitHubDataCollector(YOUR_GITHUB_TOKEN, REPO_OWNER, REPO_NAME)
        try:
            data = collector.collect_data(GOOD_COMMIT_SHA, BAD_COMMIT_SHA)
            data_path = collector.save_data(data)
            
            print("\nAll done!")
            print(f"Data saved to: {data_path}")
        except Exception as e:
            print(f"Error: {e}")
    else:
        # If missing values, use command line
        print("Missing hardcoded values, using command line")
        run_with_args()