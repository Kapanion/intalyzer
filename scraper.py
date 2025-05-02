import requests
import os
import time

GITHUB_TOKEN = os.environ["GITHUB_TOKEN"]
"""
GitHub personal access token (create one from https://github.com/settings/tokens)

It must be specified in the environment variable GITHUB_TOKEN.
"""

HEADERS = {"Authorization": f"token {GITHUB_TOKEN}", "Accept": "application/vnd.github.v3+json"}

SEARCH_URL = "https://api.github.com/search/code"


def _download_file(repo, path, branch, output_dir="ino_files_dataset"):
    url = f"https://raw.githubusercontent.com/{repo}/{branch}/{path}"
    os.makedirs(output_dir, exist_ok=True)
    filename = os.path.join(output_dir, f"{repo.replace('/', '_')}_{os.path.basename(path)}")
    r = requests.get(url)
    if r.status_code == 200:
        with open(filename, "w", encoding="utf-8") as f:
            f.write(r.text)
        return True
    else:
        return False


def download_raw_file(item, output_dir="ino_files_dataset"):
    """
    Download a raw file from a GitHub repository.
    """
    repo = item["repository"]["full_name"]
    path = item["path"]
    branch = "master"
    status = _download_file(repo, path, branch, output_dir)
    if not status:
        branch = "main"
        status = _download_file(repo, path, "master", output_dir)

    if status:
        print(f"Downloaded: {repo}/{path}")
    else:
        print(f"Failed to download {repo}/{path}")


def fetch_results(query, pages=10, download=True):
    """
    Fetch results from a GitHub search.
    """
    results = []
    for page in range(1, pages + 1):
        params = {
            "q": query,
            "per_page": 100,
            "page": page,
        }
        response = requests.get(SEARCH_URL, headers=HEADERS, params=params)
        if response.status_code != 200:
            print(f"Error: {response.status_code}, {response.text}")
            break
        data = response.json()
        items = data.get("items", [])

        if download:
            for item in items:
                download_raw_file(item)

        results.extend(items)
        print(f"Fetched page {page} with {len(items)} items.")
        time.sleep(2)  # Avoid rate limits
    return results


if __name__ == "__main__":
    query = "attachInterrupt setup() loop() extension:ino"
    results = fetch_results(query, pages=11)  # Get up to 1100 results
