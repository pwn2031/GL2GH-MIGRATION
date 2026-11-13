# Runner Guide

The toolkit supports GitHub-hosted runners and EC2 self-hosted runners.

## Runner configuration

In `config.env`:

```bash
export GITHUB_HOSTED_RUNNER="ubuntu-latest"
export EC2_RUNNER_LABEL="ec2"
```

## Runner mapping

| GitLab runner tag | GitHub runner label |
|---|---|
| `poc-runner` | `ubuntu-latest` |
| `docker` | `ubuntu-latest` |
| `shell` | `ubuntu-latest` |
| `ec2` | `ec2` |
| `linux` | `ec2` |

## GitHub-hosted runners

GitHub-hosted runners are the default and require no EC2 setup.

Use:

```yaml
runs-on: ubuntu-latest
```

The toolkit converts GitLab runner tags such as `poc-runner`, `docker`, and `shell` to `ubuntu-latest`.

## EC2 self-hosted runners

Repository-level self-hosted runners are dedicated to one repository, while organization-level runners can serve multiple repositories. [319]

### Launch an EC2 instance

Recommended POC configuration:

```text
AMI: Amazon Linux 2023
Instance type: t3.small or t3.medium
Storage: 30 GB
Security group: SSH from your IP only
```

### Connect to EC2

```bash
ssh -i ~/.ssh/your-key.pem ec2-user@<EC2_PUBLIC_IP>
```

### Install dependencies

```bash
sudo dnf update -y
sudo dnf install -y git curl tar jq
```

### Create runner directory

```bash
mkdir ~/actions-runner
cd ~/actions-runner
```

### Download the runner

```bash
RUNNER_URL=$(curl -s [https://api.github.com/repos/actions/runner/releases/latest](https://api.github.com/repos/actions/runner/releases/latest) \
| jq -r '.assets[].browser_download_url' \
| grep 'linux-x64-.*\.tar\.gz$' \
| head -n 1)

curl -o runner.tar.gz "$RUNNER_URL"
tar xzf runner.tar.gz
```

### Generate a registration token

From your local machine:

```bash
gh api repos/<github-account>/<repository>/actions/runners/registration-token \
  --jq .token
```

The token is short-lived. Do not store it.

### Register the runner

On EC2:

```bash
cd ~/actions-runner

./config.sh \
  --url [https://github.com/](https://github.com/)<github-account>/<repository> \
  --token <REGISTRATION_TOKEN> \
  --labels ec2 \
  --name ec2-poc-runner
```

### Start the runner

```bash
cd ~/actions-runner
./run.sh
```

Expected:

```text
Listening for Jobs
```

## Validate the runner

Create or use:

```yaml
name: Runner Validation

on:
  workflow_dispatch:

jobs:
  github-hosted-runner:
    runs-on: ubuntu-latest
    steps:
      - run: echo "GitHub-hosted runner works"

  ec2-self-hosted-runner:
    runs-on: ec2
    steps:
      - run: echo "EC2 self-hosted runner works"
```

Run:

```bash
gh workflow run runner-validation.yml \
  --repo <github-account>/<repository> \
  --ref main
```

Check:

```bash
gh run list \
  --repo <github-account>/<repository> \
  --workflow runner-validation.yml \
  --limit 5
```

## Use EC2 only for deployment

Recommended workflow pattern:

```yaml
jobs:
  build:
    runs-on: ubuntu-latest

  test:
    needs: build
    runs-on: ubuntu-latest

  deploy:
    needs: test
    runs-on: ec2
    environment: production
```

## Security recommendations

GitHub advises caution when using self-hosted runners because they do not guarantee ephemeral clean virtual machines and may be compromised by untrusted code. [321]

- Do not use self-hosted runners for public repositories.
- Use ephemeral runners where possible.
- Restrict network access from the runner.
- Do not store long-lived credentials on the runner.
- Limit runner access to trusted repositories.
- Destroy or rotate runners after migration testing.