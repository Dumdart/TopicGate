from release.verify_release_versions import get_versions, verify


def run_ci():
    versions = get_versions()

    verify(versions)
    print(f"Verified release versions: {versions}")


if __name__ == "__main__":
    run_ci()
