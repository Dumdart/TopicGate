
import os

from release.verify_release_versions import get_versions, verify

def run_cd():
    expected = os.environ["RELEASE_TAG"].removeprefix("v")
    versions = get_versions(expected)


    verify(versions)
    print(f"Verified release version {expected}")

if __name__ == "__main__":
    run_cd()
